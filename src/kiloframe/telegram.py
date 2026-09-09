from __future__ import annotations

import asyncio
import html
import json
import logging
import secrets
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from .activity import format_arguments, format_summary
from .agent import Agent, enforce_directive_address
from .profiles import PROFILES
from .security import Risk
from .telegram_render import telegram_html, telegram_html_chunks

log = logging.getLogger("kiloframe.telegram")


class TelegramBridge:
    """Optional long-polling bridge; every message uses the daemon's same Agent/runtime."""

    CONFIG_POLL_SECONDS = 30
    # How often the progress message is rewritten. Frequent enough that the sender can
    # see it is alive, slow enough to stay clear of Telegram's edit rate limits.
    PROGRESS_SECONDS = 1.2

    def __init__(self, config_path: Path, agent: Agent):
        self.config_path = config_path
        self.agent = agent
        self.offset = 0
        self.running = False
        self._wake = asyncio.Event()
        self._chat_locks: dict[int, asyncio.Lock] = {}
        self._replies: set[asyncio.Task[None]] = set()
        self._chat_replies: dict[int, set[asyncio.Task[None]]] = {}
        self._sessions: dict[int, str] = {}
        self._fresh: set[int] = set()
        self._chat_providers: dict[int, str] = {}
        self._chat_profiles: dict[int, str] = {}
        self._approval_waiters: dict[tuple[int, str], asyncio.Future[bool]] = {}

    def config(self) -> dict[str, Any] | None:
        try:
            config = json.loads(self.config_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, json.JSONDecodeError) as exc:
            log.warning("telegram config unreadable (%s); staying disabled", exc)
            return None
        token = str(config.get("token", "")).strip()
        try:
            allowed = {int(item) for item in config.get("allowed_chat_ids", [])}
        except (TypeError, ValueError):
            log.warning("telegram allowed_chat_ids must be integers; staying disabled")
            return None
        if not token or token == "PASTE_BOT_TOKEN_HERE":
            log.warning("telegram config has no bot token; staying disabled")
            return None
        # A valid token enables self-service onboarding.  The first /start from a
        # chat atomically adds that chat to the persistent allow-list; ordinary
        # messages from unknown chats still do nothing.
        return {"token": token, "allowed": allowed, "awaiting_start": not bool(allowed)}

    def enroll(self, chat_id: int) -> None:
        """Persist an explicit /start opt-in without losing concurrent config edits."""
        config = json.loads(self.config_path.read_text(encoding="utf-8"))
        current = {int(item) for item in config.get("allowed_chat_ids", [])}
        current.add(int(chat_id))
        config["allowed_chat_ids"] = sorted(current)
        temp = self.config_path.with_suffix(self.config_path.suffix + ".tmp")
        temp.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
        temp.chmod(0o600)
        temp.replace(self.config_path)

    # Shown under the message box by Telegram once registered with setMyCommands.
    COMMANDS = (
        ("start", "what Kilo is and how to use it"),
        ("status", "model, route and resource status"),
        ("cancel", "stop this chat's active and queued work"),
        ("new", "start a fresh conversation"),
        ("local", "use the configured Ollama route"),
        ("local_models", "list models downloaded on the Ollama server"),
        ("local_ps", "show models currently loaded in Ollama"),
        ("local_load", "load the selected or named Ollama model"),
        ("local_unload", "unload the selected or named Ollama model"),
        ("cloud", "use the default or named cloud model"),
        ("switch", "switch between local and cloud"),
        ("models", "list models on the active local or cloud route"),
        ("model", "show or select a model on the active route"),
        ("tools", "available tools and how to request work"),
        ("agent", "show or select a specialist agent"),
        ("id", "show this chat's id"),
        ("help", "list commands"),
    )

    MENU = {
        "inline_keyboard": [
            [
                {"text": "📊 Status", "callback_data": "status"},
                {"text": "⏹ Cancel", "callback_data": "cancel"},
                {"text": "✨ New chat", "callback_data": "new"},
            ],
            [
                {"text": "🏠 Local", "callback_data": "local"},
                {"text": "☁️ Cloud", "callback_data": "cloud"},
            ],
            [
                {"text": "📦 Ollama models", "callback_data": "local_models"},
                {"text": "🧩 Agents", "callback_data": "agent"},
            ],
            [
                {"text": "▶ Load local", "callback_data": "local_load"},
                {"text": "⏏ Unload local", "callback_data": "local_unload"},
            ],
            [
                {"text": "🛠 Tools", "callback_data": "tools"},
                {"text": "❓ Help", "callback_data": "help"},
            ],
        ]
    }

    # Rotating glyphs for the live progress card, so a long-running reply visibly animates
    # rather than sitting on a static line that reads as a hang.
    SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    # A small icon per phase makes the progress card scannable at a glance.
    PHASE_ICONS = {"thinking": "💭", "warming": "🔥", "running": "⚙️", "reading": "📖"}
    BAR_FILLED = "█"
    BAR_EMPTY = "░"

    @staticmethod
    def _bar(fraction: float, width: int = 10) -> str:
        """A compact unicode meter, e.g. used for free-memory in the status card."""
        fraction = max(0.0, min(1.0, fraction))
        filled = round(fraction * width)
        return TelegramBridge.BAR_FILLED * filled + TelegramBridge.BAR_EMPTY * (
            width - filled
        )

    @staticmethod
    def _call(
        token: str,
        method: str,
        data: dict[str, Any] | None = None,
        request_timeout: int | None = None,
    ) -> dict[str, Any]:
        payload = dict(data or {})
        # Nested structures (keyboards, allowed_updates) must be JSON, not form values.
        for key, value in payload.items():
            if isinstance(value, (dict, list)):
                payload[key] = json.dumps(value)
        encoded = urllib.parse.urlencode(payload).encode()
        request = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/{method}", data=encoded
        )
        long_poll = int(payload.get("timeout", 0) or 0) if method == "getUpdates" else 0
        timeout = request_timeout or max(10, long_poll + 10)
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result = json.load(response)
        if not result.get("ok", False):
            raise RuntimeError(
                str(result.get("description") or "Telegram Bot API request failed")
            )
        return result

    async def send(
        self,
        token: str,
        chat_id: int,
        text: str,
        keyboard: dict[str, Any] | None = None,
    ) -> None:
        chunks = telegram_html_chunks(text)
        for index, chunk in enumerate(chunks):
            data: dict[str, Any] = {
                "chat_id": chat_id,
                "text": chunk or "(empty response)",
                "parse_mode": "HTML",
            }
            # Attach the menu only to the final chunk so it appears once, at the end.
            if keyboard and index == len(chunks) - 1:
                if keyboard is self.MENU:
                    keyboard = json.loads(json.dumps(self.MENU))
                    cloud = chat_id in self._chat_providers
                    keyboard["inline_keyboard"][1][0]["text"] = "🏠 Local" + (" ✓" if not cloud else "")
                    keyboard["inline_keyboard"][1][1]["text"] = "☁️ Cloud" + (" ✓" if cloud else "")
                    keyboard["inline_keyboard"][2][0]["text"] = "🧠 Cloud models" if cloud else "📦 Ollama models"
                    keyboard["inline_keyboard"][3][0]["text"] = "☁️ Select cloud" if cloud else "▶ Load local"
                    keyboard["inline_keyboard"][3][1]["text"] = "⏏ Unload local"
                data["reply_markup"] = keyboard
            await asyncio.to_thread(self._call, token, "sendMessage", data)

    async def _request_approval(
        self,
        token: str,
        chat_id: int,
        capability: str,
        detail: str,
        risk: Risk,
    ) -> bool:
        """Ask the same allow-listed Telegram chat to approve one exact machine action."""
        approval_id = secrets.token_urlsafe(9)
        key = (chat_id, approval_id)
        future = asyncio.get_running_loop().create_future()
        self._approval_waiters[key] = future
        keyboard = {
            "inline_keyboard": [[
                {
                    "text": "✅ Approve once",
                    "callback_data": f"approval:yes:{approval_id}",
                },
                {
                    "text": "❌ Deny",
                    "callback_data": f"approval:no:{approval_id}",
                },
            ]]
        }
        await self.send(
            token,
            chat_id,
            "⚠️ <b>Machine approval required</b>\n"
            f"<b>Risk:</b> <code>{html.escape(risk.value)}</code>\n"
            f"<b>Action:</b> <code>{html.escape(capability)}</code>\n"
            f"<pre>{html.escape(detail)}</pre>\n"
            "Approve this action once?",
            keyboard,
        )
        try:
            return await asyncio.wait_for(future, timeout=280)
        except asyncio.TimeoutError:
            return False
        finally:
            self._approval_waiters.pop(key, None)

    def _resolve_approval(self, chat_id: int, data: str) -> bool:
        """Resolve an approval button only for the chat that received the prompt."""
        if not data.startswith("approval:"):
            return False
        try:
            _prefix, decision, approval_id = data.split(":", 2)
        except ValueError:
            return True
        future = self._approval_waiters.get((chat_id, approval_id))
        if future is not None and not future.done():
            future.set_result(decision == "yes")
        return True

    async def _send_progress(self, token: str, chat_id: int, text: str) -> int | None:
        # Progress is bounded best-effort: show the thinking indicator when Telegram
        # responds, but never hold the agent behind a network/DNS outage.
        if ":" not in token:  # malformed/test token; avoid pointless network work
            return None
        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self._call,
                    token,
                    "sendMessage",
                    {"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
                ),
                timeout=3,
            )
            return int(response["result"]["message_id"])
        except Exception:
            return None

    async def _edit_progress(
        self, token: str, chat_id: int, message_id: int | None, text: str
    ) -> None:
        """Rewrite the live status line. Telegram rejects an edit that would not change
        the text, and that rejection is not worth surfacing."""
        if message_id is None:
            return
        try:
            await asyncio.wait_for(
                asyncio.to_thread(
                    self._call,
                    token,
                    "editMessageText",
                    {
                        "chat_id": chat_id,
                        "message_id": message_id,
                        "text": text,
                        "parse_mode": "HTML",
                    },
                ),
                timeout=1,
            )
        except Exception:
            pass

    async def _delete(self, token: str, chat_id: int, message_id: int | None) -> None:
        if message_id is None:
            return
        try:
            await asyncio.wait_for(
                asyncio.to_thread(
                    self._call,
                    token,
                    "deleteMessage",
                    {"chat_id": chat_id, "message_id": message_id},
                ),
                timeout=1,
            )
        except Exception:
            pass

    async def _keep_typing(self, token: str, chat_id: int) -> None:
        """Telegram clears the typing indicator after ~5s, and a reply here can take
        minutes, so refresh it until the answer is ready."""
        try:
            while True:
                try:
                    await asyncio.to_thread(
                        self._call,
                        token,
                        "sendChatAction",
                        {"chat_id": chat_id, "action": "typing"},
                    )
                except Exception:
                    pass
                await asyncio.sleep(4)
        except asyncio.CancelledError:
            pass

    def _start_reply(self, token: str, chat_id: int, text: str) -> None:
        """Run one reply per chat off the poll loop.

        Replies are serialised per chat so two questions cannot interleave in the same
        conversation, while a slow answer in one chat never stops the bridge from
        servicing commands, buttons, or another chat.
        """

        async def serialised() -> None:
            lock = self._chat_locks.setdefault(chat_id, asyncio.Lock())
            # There is one inference slot, so a message sent while another is generating
            # waits. Acknowledge immediately when that happens, otherwise the wait reads
            # as the bot ignoring the message.
            if lock.locked():
                try:
                    await self.send(
                        token,
                        chat_id,
                        "⏳ <i>queued — finishing the previous request first</i>",
                    )
                except Exception:
                    pass
            async with lock:
                await self._reply(token, chat_id, text)

        task = asyncio.create_task(serialised())
        self._replies.add(task)
        self._chat_replies.setdefault(chat_id, set()).add(task)
        task.add_done_callback(lambda done: self._reply_finished(chat_id, done))

    def _reply_finished(self, chat_id: int, task: asyncio.Task[None]) -> None:
        self._replies.discard(task)
        chat_tasks = self._chat_replies.get(chat_id)
        if chat_tasks is not None:
            chat_tasks.discard(task)
            if not chat_tasks:
                self._chat_replies.pop(chat_id, None)
        if not task.cancelled() and (error := task.exception()) is not None:
            log.error("telegram reply task failed: %s", error)

    async def _tick_progress(
        self,
        token: str,
        chat_id: int,
        message_id: int | None,
        work_message_id: int | None,
        state: dict[str, Any],
    ) -> None:
        """Rewrite the progress message on a timer.

        Driving it from agent events alone leaves it frozen on whatever happened last:
        a step can run for minutes without emitting anything, so the sender sees
        'step 1' indefinitely and assumes the bot is stuck. Telegram also rejects an
        edit that would not change the text, so the elapsed counter doubles as the
        thing that makes each edit distinct.
        """
        frame = 0
        while True:
            await asyncio.sleep(self.PROGRESS_SECONDS)
            frame += 1
            spin = self.SPINNER[frame % len(self.SPINNER)]
            icon = self.PHASE_ICONS.get(state.get("phase_kind", "thinking"), "💭")
            elapsed = int(time.monotonic() - state["started"])
            minutes, seconds = divmod(elapsed, 60)
            clock = f"{minutes}m {seconds:02d}s" if minutes else f"{seconds}s"
            tools = list(dict.fromkeys(state["tools"]))
            body = "\n".join(
                [
                    f"{spin} <b>Kilo is working</b>",
                    "",
                    f"{icon} {html.escape(state['phase'])}",
                    f"⏱ <i>{clock}</i>",
                    *([f"🔧 <i>{html.escape(' → '.join(tools))}</i>"] if tools else []),
                ]
            )
            await self._edit_progress(token, chat_id, message_id, body)
            if frame % 2 == 0:
                await self._edit_progress(
                    token, chat_id, work_message_id, self._live_work_body(state)
                )

    @staticmethod
    def _live_work_body(state: dict[str, Any], finished: bool = False) -> str:
        """A separate persistent card for safe machine actions and streamed output."""
        title = "✅ <b>Work log</b>" if finished else "📟 <b>Live machine output</b>"
        entries = list(state.get("work", []))[-16:]
        body = title
        if entries:
            body += "\n<pre>" + html.escape("\n".join(entries)[-2200:]) + "</pre>"
        else:
            body += "\n<i>waiting for the first machine action…</i>"
        preview = "".join(state.get("output", []))[-1100:].strip()
        if preview and not finished:
            body += "\n\n<b>Live reply</b>\n<pre>" + html.escape(preview) + "</pre>"
        return body

    async def _reply(self, token: str, chat_id: int, text: str) -> None:
        typing = asyncio.create_task(self._keep_typing(token, chat_id))
        # A reply can take minutes here; a status message that is edited as work
        # progresses is the only way the sender can tell it is alive.
        progress = await self._send_progress(
            token, chat_id, "⠋ <b>Kilo is working</b>\n\n💭 thinking"
        )
        work_message = await self._send_progress(
            token,
            chat_id,
            "📟 <b>Live machine output</b>\n<i>waiting for the first machine action…</i>",
        )
        state: dict[str, Any] = {
            "phase": "thinking",
            "phase_kind": "thinking",
            "started": time.monotonic(),
            "tools": [],
            "output": [],
            "work": [],
        }
        ticker = asyncio.create_task(
            self._tick_progress(token, chat_id, progress, work_message, state)
        )
        output: list[str] = []
        agent_label: str | None = None
        brain_label: str | None = None
        provider = self._chat_providers.get(chat_id)
        profile = self._chat_profiles.get(chat_id)
        session_id = self._sessions.get(chat_id, f"telegram-{chat_id}")
        fresh = chat_id in self._fresh
        tool_started: dict[str, float] = {}
        try:
            async def request_approval(
                capability: str, detail: str, risk: Risk
            ) -> bool:
                state["phase"], state["phase_kind"] = (
                    "waiting for Sir's approval",
                    "thinking",
                )
                state["work"].append(f"⚠ approval  {risk.value}  {capability}")
                allowed = await self._request_approval(
                    token, chat_id, capability, detail, risk
                )
                state["work"].append(
                    f"{'✓ approved' if allowed else '✗ denied'}  {capability}"
                )
                return allowed

            async for event in self.agent.run(
                str(text),
                session_id,
                remote=True,
                provider=provider,
                agent_profile=profile,
                fresh=fresh,
                permission_callback=request_approval,
            ):
                self._fresh.discard(chat_id)
                kind = event.get("type")
                if kind == "token":
                    token_text = event.get("text", "")
                    output.append(token_text)
                    state["output"].append(token_text)
                elif kind == "response_reset":
                    output.clear()
                    state["output"].clear()
                    state["work"].append("↻ intercepted model tool markup; dispatching safely")
                elif kind == "agent":
                    agent_label = str(event.get("profile") or "")
                    state["work"].append(f"◇ agent  {agent_label}")
                elif kind == "capabilities":
                    names = [str(name) for name in event.get("tools") or []]
                    state["work"].append(
                        f"◇ tools active ({len(names)})  " + " · ".join(names)
                    )
                elif kind == "model":
                    brain_label = str(event.get("label") or "")
                    state["phase"] = f"using {brain_label}"
                    state["work"].append(f"◇ model  {brain_label}")
                elif kind == "warming":
                    state["phase"], state["phase_kind"] = (
                        "warming the model cache (one-off)",
                        "warming",
                    )
                    state["work"].append("◌ cache  warming model prefix")
                elif kind == "thinking":
                    # No step number: it read as stuck. The timer conveys progress.
                    state["phase"], state["phase_kind"] = "thinking", "thinking"
                elif kind == "tool_start":
                    name = str(event.get("name"))
                    state["tools"].append(name)
                    state["phase"], state["phase_kind"] = f"running {name}", "running"
                    tool_started[name] = time.monotonic()
                    detail = format_arguments(event.get("arguments") or {}, 420)
                    state["work"].append(f"▶ {name}{'  ' + detail if detail else ''}")
                elif kind == "tool_end":
                    name = str(event.get("name"))
                    elapsed = time.monotonic() - tool_started.pop(name, time.monotonic())
                    state["phase"], state["phase_kind"] = (
                        f"read {name} · interpreting",
                        "reading",
                    )
                    mark = "✓" if event.get("ok") else "✗"
                    summary = format_summary(event.get("summary", ""), 520)
                    state["work"].append(
                        f"{mark} {name}  {elapsed:0.1f}s{'  ' + summary if summary else ''}"
                    )
                elif kind == "error":
                    error = format_summary(event.get("error"), 520)
                    output.append(f"\n[error: {error}]")
                    state["work"].append(f"✗ error  {error}")
        except asyncio.CancelledError:
            state["work"].append("■ cancelled by Sir")
            ticker.cancel()
            await self._delete(token, chat_id, progress)
            await self._edit_progress(
                token, chat_id, work_message, self._live_work_body(state, finished=True)
            )
            raise
        except Exception as exc:
            # Silence looks identical to a hung bot, so always tell the user.
            log.exception("telegram request failed for chat %s", chat_id)
            ticker.cancel()
            await self._delete(token, chat_id, progress)
            await self._edit_progress(
                token, chat_id, work_message, self._live_work_body(state, finished=True)
            )
            await self.send(
                token,
                chat_id,
                telegram_html(
                    enforce_directive_address(
                        f"Kilo hit an error: {str(exc)}"
                    )
                ),
                self.MENU,
            )
            return
        finally:
            typing.cancel()
            ticker.cancel()
            await asyncio.gather(typing, ticker, return_exceptions=True)
        await self._delete(token, chat_id, progress)
        await self._edit_progress(
            token, chat_id, work_message, self._live_work_body(state, finished=True)
        )
        # Guard the final combined stream because a provider may ignore the directive.
        # Render only the body so a required address does not swallow Markdown headings.
        normalized = enforce_directive_address("".join(output))
        prefix, suffix = "Sir, ", ", Sir."
        if normalized.startswith(prefix) and normalized.endswith(suffix):
            answer = prefix + telegram_html(normalized[len(prefix):-len(suffix)]) + suffix
        else:
            answer = telegram_html(normalized)
        took = int(time.monotonic() - state["started"])
        minutes, seconds = divmod(took, 60)
        clock = f"{minutes}m {seconds:02d}s" if minutes else f"{seconds}s"
        # A thin divider then a compact meta line: which agent answered, how long it took,
        # and which tools it actually used. Reads like a signed answer, not a raw dump.
        footer_bits = []
        if agent_label and agent_label not in ("", "general", "conversation"):
            footer_bits.append(f"◆ {html.escape(agent_label)}")
        if brain_label:
            footer_bits.append(f"🖥 {html.escape(brain_label)}")
        footer_bits.append(f"⏱ {clock}")
        if state["tools"]:
            footer_bits.append(
                f"🔧 {html.escape(', '.join(dict.fromkeys(state['tools'])))}"
            )
        body = (
            f"{answer}\n\n<i>{' · '.join(footer_bits)}</i>"
            if answer
            else "🤔 <i>(no response — try rephrasing)</i>"
        )
        await self.send(token, chat_id, body, self.MENU)

    async def _command(self, token: str, chat_id: int, command: str) -> bool:
        """Handle a slash command or menu button. Returns True when handled."""
        raw = command.strip().lstrip("/")
        if not raw:
            return False
        head, _, argument = raw.partition(" ")
        name = head.split("@", 1)[0].lower()
        argument = argument.strip()

        if name == "start":
            lines = [
                "🤖 <b>KiloFrame</b> · Developed by Citadel Research",
                "Talk naturally to Kilo. Ask it to inspect files, run tasks, or research the web.",
                "Use Local or Cloud to choose where inference runs; Models follows that route.",
                "Check /status for the selected model and live availability.",
                "🛠 <i>Machine tools enabled; changes ask for approval.</i>  ·  /help",
            ]
            await self.send(token, chat_id, "\n".join(lines), self.MENU)
            return True
        if name in {"help", "commands"}:
            lines = [
                "<b>Commands</b>",
                *[
                    f"• <code>/{name}</code> — {description}"
                    for name, description in self.COMMANDS
                ],
                "",
                "🛠 <b>Machine tools are enabled</b>: safe inspection runs directly; commands,",
                "writes, services, packages, and destructive actions show Approve/Deny buttons.",
                "/local uses your configured Ollama server, which may be on another machine. /cloud explicitly selects a cloud provider.",
            ]
            await self.send(token, chat_id, "\n".join(lines), self.MENU)
            return True
        if name in {"cancel", "stop"}:
            tasks = [
                task
                for task in self._chat_replies.get(chat_id, set())
                if not task.done()
            ]
            for task in tasks:
                task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
                message = f"⏹ <b>Cancelled</b> {len(tasks)} active/queued task{'s' if len(tasks) != 1 else ''}."
            else:
                message = "✅ <i>No active or queued task in this chat.</i>"
            await self.send(token, chat_id, message, self.MENU)
            return True
        if name == "new":
            self._sessions[chat_id] = self.agent.memory.new_session(
                "telegram", "fresh Telegram chat"
            )
            self._fresh.add(chat_id)
            await self.send(
                token,
                chat_id,
                "✨ <b>Fresh conversation started.</b>\n<i>Earlier context is set aside.</i>",
                self.MENU,
            )
            return True
        if name == "local":
            self._chat_providers.pop(chat_id, None)
            await self.send(
                token,
                chat_id,
                "🏠 <b>Ollama route selected.</b>\n<i>Inference uses your configured Ollama server.</i>\nUse /local_models, /model MODEL_ID, /local_load, /local_ps, or /local_unload.",
                self.MENU,
            )
            return True
        if name in {"local_models", "local_ps", "local_load", "local_unload"}:
            try:
                if chat_id in self._chat_providers:
                    raise RuntimeError("Switch to /local before using Ollama controls.")
                if name == "local_models":
                    models = await asyncio.to_thread(self.agent.runtime.client().list_models)
                    selected = self.agent.runtime.active_model()
                    lines = ["📦 <b>Ollama models</b>"]
                    for model in models[:40]:
                        value = str(model.get("name") or model.get("model") or "")
                        mark = " ✓ selected" if value == selected else ""
                        lines.append("• <code>" + html.escape(value) + "</code>" + mark)
                    lines.append("Use <code>/model MODEL_ID</code> to select a downloaded model.")
                    lines.append("Use <code>/local_load</code> or <code>/local_unload</code> to control residency.")
                    await self.send(token, chat_id, "\n".join(lines), self.MENU)
                else:
                    if name == "local_ps":
                        running = await asyncio.to_thread(self.agent.runtime.client().running_models)
                        lines = ["▶ <b>Loaded Ollama models</b>"]
                        lines += ["• <code>" + html.escape(str(item.get("name") or item.get("model"))) + "</code>" for item in running] or ["No models are loaded."]
                    elif name == "local_load":
                        model = argument or self.agent.runtime.active_model()
                        if not model:
                            raise RuntimeError("No local model is selected.")
                        await asyncio.to_thread(self.agent.runtime.client().load, model)
                        lines = ["▶ <b>Local model loaded</b>", "<code>" + html.escape(model) + "</code>"]
                    else:
                        model = argument or self.agent.runtime.active_model()
                        if not model:
                            raise RuntimeError("No local model is selected.")
                        await asyncio.to_thread(self.agent.runtime.client().unload, model)
                        lines = ["⏏ <b>Local model unloaded</b>", "<code>" + html.escape(model) + "</code>"]
                    await self.send(token, chat_id, "\n".join(lines), self.MENU)
            except Exception as exc:
                await self.send(token, chat_id, "⚠️ " + html.escape(str(exc)), self.MENU)
            return True
        if name in {"cloud", "switch"}:
            if name == "switch" and not argument:
                argument = "local" if chat_id in self._chat_providers else ""
            if argument.lower() == "local":
                self._chat_providers.pop(chat_id, None)
                await self.send(
                    token, chat_id, "🏠 <b>Switched to local.</b>", self.MENU
                )
                return True
            try:
                provider = self.agent.providers.resolve(argument or None)
            except Exception as exc:
                await self.send(
                    token, chat_id, f"⚠️ <code>{html.escape(str(exc))}</code>", self.MENU
                )
                return True
            self._chat_providers[chat_id] = provider.name
            await self.send(
                token,
                chat_id,
                f"☁️ <b>Cloud selected</b>\n<code>{html.escape(provider.label)}</code>\n"
                "<i>Future prompts use it until /local or /switch.</i>",
                self.MENU,
            )
            return True
        if name == "tools":
            names = [item["function"]["name"] for item in self.agent.tools.schemas(remote=True)]
            await self.send(token, chat_id,
                "🛠 <b>KiloFrame tools</b>\n" + html.escape(", ".join(names)) +
                "\n\nTry: ‘Research Ollama tool calling and cite sources’, ‘Inspect disk space’, or ‘Read /tmp/example.txt’. "
                "Machine actions run on the KiloFrame host. Changes use Approve/Deny buttons.", self.MENU)
            return True
        if name in {"models", "model"}:
            try:
                provider_name = self._chat_providers.get(chat_id)
                if provider_name:
                    if name == "models":
                        models = await asyncio.to_thread(self.agent.providers.list_models, provider_name, False)
                    elif argument:
                        selected = self.agent.providers.set_model(provider_name, argument)
                    else:
                        selected = self.agent.providers.resolve(provider_name).model
                    route = "Cloud · " + provider_name
                else:
                    server = self.agent.runtime.active_server()
                    if server is None:
                        raise RuntimeError("No Ollama server configured. Use kiloframe localset on the host.")
                    route = "Ollama · " + server.name
                    if name == "models" or argument:
                        inventory = await asyncio.to_thread(self.agent.runtime.client().list_models)
                        models = [str(model.get("name") or model.get("model")) for model in inventory]
                    if name == "model":
                        selected = server.model
                        if argument:
                            if argument not in models:
                                raise RuntimeError("Model is not downloaded on this Ollama server; choose one from /models.")
                            self.agent.runtime.config.set_model(server.name, argument)
                            selected = argument
                if name == "models":
                    lines = ["🧠 <b>" + html.escape(route) + " models</b>"]
                    lines.extend("• <code>" + html.escape(model) + "</code>" for model in models[:30])
                    if not models:
                        lines.append("No downloaded models found. Pull one using kiloframe local pull on the host.")
                    lines.append("Select with <code>/model MODEL_ID</code>.")
                else:
                    lines = ["🧠 <b>" + html.escape(route) + "</b>", "<code>" + html.escape(selected or "No model selected") + "</code>"]
                    if argument and not provider_name:
                        lines.append("This updates the shared Ollama model for KiloFrame's local route.")
                await self.send(token, chat_id, "\n".join(lines), self.MENU)
            except Exception as exc:
                await self.send(token, chat_id, "⚠️ " + html.escape(str(exc)), self.MENU)
            return True
        if name == "agent":
            if not argument:
                current = self._chat_profiles.get(chat_id, "auto")
                lines = [f"🧩 <b>Agent: {html.escape(current)}</b>"]
                lines.extend(
                    f"• <code>{profile.name}</code> — {html.escape(profile.hint)}"
                    for profile in PROFILES.values()
                )
                lines.append(
                    "\nSelect with <code>/agent NAME</code>; use <code>/agent auto</code> to route automatically."
                )
                await self.send(token, chat_id, "\n".join(lines), self.MENU)
                return True
            selected = argument.lower()
            if selected == "auto":
                self._chat_profiles.pop(chat_id, None)
            elif selected in PROFILES:
                self._chat_profiles[chat_id] = selected
            else:
                await self.send(
                    token,
                    chat_id,
                    f"⚠️ Unknown agent: <code>{html.escape(selected)}</code>",
                    self.MENU,
                )
                return True
            await self.send(
                token,
                chat_id,
                f"🧩 <b>Agent selected:</b> <code>{html.escape(selected)}</code>",
                self.MENU,
            )
            return True
        if name == "id":
            await self.send(
                token,
                chat_id,
                f"🆔 This chat's id is <code>{chat_id}</code>\n"
                f"<i>Add it to allowed_chat_ids to authorise it.</i>",
                self.MENU,
            )
            return True
        if name == "status":
            try:
                provider_name = self._chat_providers.get(chat_id)
                lines = ["📊 <b>KiloFrame · live status</b>"]
                if provider_name:
                    provider = self.agent.providers.resolve(provider_name)
                    lines += ["☁️ <b>Cloud route</b>", "<code>" + html.escape(provider.label) + "</code>",
                              "Provider configured; availability is verified when a request runs."]
                    limit = self.agent.providers.context_limit(provider_name)
                    lines.append("Context: " + (str(limit) + " tokens" if limit else "provider-managed"))
                else:
                    server = self.agent.runtime.active_server()
                    healthy = await asyncio.wait_for(self.agent.runtime.healthy(), timeout=5)
                    running = await asyncio.to_thread(self.agent.runtime.client().running_models) if healthy else []
                    model = server.model if server else ""
                    loaded = any(m.get("name") == model or m.get("model") == model for m in running)
                    lines += ["🏠 <b>Local / private · Ollama</b>",
                              "Server: <code>" + html.escape(server.url if server else "not configured") + "</code>",
                              "Endpoint: " + ("reachable" if healthy else "unreachable"),
                              "Model: <code>" + html.escape(model or "not selected") + "</code>",
                              "State: " + ("loaded" if loaded else "loads on request" if model and healthy else "unavailable")]
                active = sum(not task.done() for task in self._chat_replies.get(chat_id, set()))
                lines += ["Active / queued requests in this chat: " + str(active),
                          "Agent: " + html.escape(self._chat_profiles.get(chat_id, "auto")),
                          "Session: " + html.escape(self._sessions.get(chat_id, "new"))]
                await self.send(token, chat_id, "\n".join(lines), self.MENU)
            except Exception as exc:
                await self.send(token, chat_id, "⚠️ Status unavailable: " + html.escape(str(exc)), self.MENU)
            return True
        return False

    async def _publish_bot_ui(self, token: str) -> None:
        requests = (
            (
                "setMyCommands",
                {
                    "commands": [
                        {"command": name, "description": description}
                        for name, description in self.COMMANDS
                    ]
                },
            ),
            ("setChatMenuButton", {"menu_button": {"type": "commands"}}),
            (
                "setMyShortDescription",
                {
                    "short_description": "Kilo's agent framework with local Ollama, cloud providers, tools, and specialists."
                },
            ),
            (
                "setMyDescription",
                {
                    "description": "KiloFrame, developed by Citadel Research: Kilo powered by the selected AI provider, with persistent memory and approval-gated machine tools."
                },
            ),
        )
        for method, data in requests:
            try:
                await asyncio.to_thread(self._call, token, method, data)
            except Exception:
                log.warning("could not publish Telegram %s", method, exc_info=True)

    async def run(self) -> None:
        self.running = True
        self._wake.clear()
        published_token: str | None = None
        try:
            while self.running:
                # Reload on every poll so token and allow-list edits take effect live.
                config = self.config()
                if config is None:
                    try:
                        await asyncio.wait_for(
                            self._wake.wait(), timeout=self.CONFIG_POLL_SECONDS
                        )
                    except asyncio.TimeoutError:
                        pass
                    continue
                token, allowed = config["token"], config["allowed"]
                if token != published_token:
                    self.offset = 0
                    await self._publish_bot_ui(token)
                    published_token = token
                    log.info("telegram bridge %s for %d active chat(s)",
                             "awaiting /start" if config.get("awaiting_start") else "enabled", len(allowed))
                try:
                    response = await asyncio.to_thread(
                        self._call,
                        token,
                        "getUpdates",
                        {
                            "offset": self.offset,
                            "timeout": 10,
                            "allowed_updates": ["message", "callback_query"],
                        },
                    )
                    for update in response.get("result", []):
                        self.offset = max(self.offset, int(update["update_id"]) + 1)

                        query = update.get("callback_query")
                        if query:
                            chat_id = int(
                                ((query.get("message") or {}).get("chat") or {}).get(
                                    "id", 0
                                )
                            )
                            if chat_id not in allowed:
                                log.warning(
                                    "ignored telegram button from unauthorised chat %s",
                                    chat_id,
                                )
                                continue
                            callback_data = str(query.get("data", ""))
                            # Acknowledge promptly or the client shows a spinner on the button.
                            try:
                                await asyncio.to_thread(
                                    self._call,
                                    token,
                                    "answerCallbackQuery",
                                    {"callback_query_id": query.get("id")},
                                )
                            except Exception:
                                pass
                            if not self._resolve_approval(chat_id, callback_data):
                                await self._command(token, chat_id, callback_data)
                            continue

                        message = update.get("message") or {}
                        chat_id = int((message.get("chat") or {}).get("id", 0))
                        text = message.get("text")
                        if not text:
                            continue
                        if chat_id not in allowed:
                            command = (text.strip().split() or [""])[0].lower().split("@", 1)[0]
                            if command == "/start":
                                try:
                                    await asyncio.to_thread(self.enroll, chat_id)
                                except Exception:
                                    log.exception("could not enrol Telegram chat %s", chat_id)
                                    await self.send(token, chat_id, "⚠️ KiloFrame could not save this chat's enrollment. Please try /start again.")
                                    continue
                                allowed.add(chat_id)
                                log.info("enrolled Telegram chat %s through /start", chat_id)
                                await self._command(token, chat_id, text)
                            else:
                                log.warning("ignored Telegram message before /start from chat %s", chat_id)
                            continue
                        if text.startswith("/") and await self._command(
                            token, chat_id, text
                        ):
                            continue
                        # Keep polling while the one inference slot works in the background.
                        self._start_reply(token, chat_id, text)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    log.exception("telegram poll failed; retrying")
                    try:
                        await asyncio.wait_for(self._wake.wait(), timeout=5)
                    except asyncio.TimeoutError:
                        pass
        finally:
            replies = list(self._replies)
            for task in replies:
                task.cancel()
            if replies:
                await asyncio.gather(*replies, return_exceptions=True)

    def stop(self) -> None:
        self.running = False
        self._wake.set()
        for task in list(self._replies):
            task.cancel()

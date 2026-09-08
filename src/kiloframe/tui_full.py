"""Full-screen Kilo terminal application.

A persistent layout that fills the window: a banner on top, a live stats bar, a scrollable
conversation that streams character by character, a runtime panel toggled with F2, and an
input box fixed at the bottom. The stats bar shows what Kilo is doing plus live numeric
counters — elapsed runtime, tools used, and tokens produced.

Everything visible animates so the interface always reads as alive: a light sweeps across
the wordmark, the status dot breathes, the activity glyph and word rotate with trailing
dots while Kilo works, and an idle wave drifts when it is not. There is no step counter —
a raw number that usually only reached "1" read as frozen.

Built on prompt_toolkit's widgets (TextArea) so input focus and scrolling are handled
robustly. When prompt_toolkit or a real terminal is unavailable, cli.py falls back to the
streaming line-based UI, so nothing here is a hard requirement.

Inference happens in the daemon over the Unix socket; this process only renders and
forwards keystrokes, so the interface stays responsive while a reply streams.
"""

from __future__ import annotations

import asyncio
import datetime as _dt
import json
import re
import shutil
import textwrap
import time
from pathlib import Path
from typing import Any

from prompt_toolkit.application import Application
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document
from prompt_toolkit.filters import Condition
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import (
    ConditionalContainer,
    Float,
    FloatContainer,
    HSplit,
    Layout,
    VSplit,
    Window,
)
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.menus import CompletionsMenu
from prompt_toolkit.lexers import Lexer
from prompt_toolkit.mouse_events import MouseEventType, MouseButton
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import TextArea

try:
    from prompt_toolkit.styles.pygments import pygments_token_to_classname
    from pygments import lex as pygments_lex
    from pygments.lexers import get_lexer_by_name
    from pygments.lexers.special import TextLexer
except ModuleNotFoundError:  # pragma: no cover - installer supplies Pygments
    pygments_lex = None
    get_lexer_by_name = None
    TextLexer = None
    pygments_token_to_classname = None

from .rpc import RPCClient
from .theme import KILOFRAME_ART, KILOFRAME_CREDIT

KILO_ART = KILOFRAME_ART

# Kilo's README mascot, redrawn in terminal-safe pixels. It is a little green
# machine rather than a generic eye: the shell breathes, pupils scan, and the
# eyelids blink from the shared animation tick.
MASCOT_OPEN = (
    "    ▄▄▄▄▄    ", "   ▟█████▙   ", " ▄██●▓●██▄ ",
    "▐██▓ ▾ ▓██▌", " ▜██▓═▓██▛ ", "  ▀██▓██▀  ",
)
MASCOT_BLINK = (
    "    ▄▄▄▄▄    ", "   ▟█████▙   ", " ▄██━▓━██▄ ",
    "▐██▓ ▾ ▓██▌", " ▜██▓═▓██▛ ", "  ▀██▓██▀  ",
)

SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"       # default "thinking" spinner
MOON = "◐◓◑◒"                    # a tool is running: a turning quarter
ELLIPSIS = ("·  ", "·· ", "···", " ··", "  ·")  # "interpreting" drift
PULSE = "▁▂▃▄▅▆▇█▇▆▅▄▃▂"
ACTIVITY = ("thinking", "reasoning", "planning", "working", "composing", "considering")

# Which glyph set animates for a given activity phase. Falls back to the braille spinner.
def _phase_frames(phase: str) -> str:
    if phase.startswith(("running", "warming")):
        return MOON
    return SPINNER


STYLE = Style.from_dict({
    # KiloFrame palette: black / white / grey, with hacker green as the single accent.
    "banner": "#00cc55 bold",
    "banner.hi": "#aaffcc bold",
    "evil": "#ff5f5f bold",   # the mascot's eyes
    "tagline": "#9a9a9a",
    "on": "#00ff66 bold",
    "off": "#ffd75f bold",
    "sep": "#2a2a2a",
    "stat": "#00ff66",
    "stat.k": "#7a7a7a",
    "you": "#e6e6e6 bold",
    "kilo": "#00ff66",
    "dim": "#7a7a7a",
    "warn": "#ffd75f",
    "err": "#ff5f5f",
    "panel.title": "#ffffff bold",
    "panel.key": "#7a7a7a",
    "panel.hi": "#00ff66 bold",
    "output": "bg:#000000",
    "box": "#00cc55",
    "box.you": "#e6e6e6 bold",
    "box.kilo": "#00ff66 bold",
    "diff.add": "#00ff66",
    "diff.del": "#ff5f5f",
    "code": "#c0c0c0",
    "pygments": "#d7d7d7",
    "pygments.comment": "#6c6c6c italic",
    "pygments.keyword": "#5fd787 bold",
    "pygments.name.builtin": "#5fd7af",
    "pygments.name.class": "#00ff66 bold",
    "pygments.name.decorator": "#c8c8c8",
    "pygments.name.function": "#aaffcc",
    "pygments.literal.number": "#8a8a8a",
    "pygments.literal.string": "#c8c8c8",
    "pygments.operator": "#9a9a9a",
    "pygments.punctuation": "#d7d7d7",
    "toolline": "#7a7a7a",
    "prompt": "#00ff66 bold",
    # Completion menus do not inherit the input style. Theme all visible surfaces
    # so slash suggestions use KiloFrame's dark/green palette.
    "completion-menu": "bg:#101510 #d7d7d7",
    "completion-menu.completion": "bg:#101510 #d7d7d7",
    "completion-menu.completion.current": "bg:#00aa4f #000000 bold",
    "completion-menu.meta": "bg:#101510 #7a7a7a",
    "completion-menu.meta.completion.current": "bg:#00aa4f #000000",
    "scrollbar.background": "bg:#101510",
    "scrollbar.button": "bg:#00aa4f",
})


_COMMANDS = [
    ("/commands", "show every TUI command"),
    ("/help", "show command help"),
    ("/mcp", "inspect MCP server connections and discovered tools"),
    ("/thinking ", "off | on | low | medium | high — model-supported thinking control"),
    ("/effort ", "high | medium | low — reply depth vs speed"),
    ("/agent ", "force a specialist: orchestrator research coding security math engineering systems private"),
    ("/local", "Ollama local/remote model route: status, models, pick, load, pull, unload"),
    ("/localset", "configure Ollama servers (add/remove/switch local or remote)"),
    ("/switch", "flip between Ollama and cloud (Ollama default)"),
    ("/private ", "on | off | rotate — mask web through Tor"),
    ("/cloud ", "set up or use a cloud model (provider picker)"),
    ("/model ", "change the cloud model"),
    ("/chats", "list past sessions to resume"),
    ("/delete ", "delete chats you choose (n, n,m, or all)"),
    ("/botkey", "set or change the Telegram bot token"),
    ("/cancel", "stop the running request and clear the queue"),
    ("/new", "start a fresh session"),
    ("/clear", "clear the screen"),
    ("/quit", "exit KiloFrame"),
]


class _ChatLexer(Lexer):
    """Colours the conversation: turn borders, +/- diff lines, destructive warnings,
    tool lines, and code inside ``` fences."""

    def lex_document(self, document):
        if getattr(self, "_cached_text", None) == document.text:
            return self._cached_get_line
        lines = document.lines

        def box_body(line: str) -> tuple[str, str, str]:
            prefix = "\u2502 " if line.startswith("\u2502 ") else ""
            suffix = "\u2502" if prefix and line.endswith("\u2502") else ""
            end = -1 if suffix else None
            return prefix, line[len(prefix):end], suffix

        contexts = []
        in_code, language = False, "text"
        for previous in lines:
            contexts.append((in_code, language))
            fence = re.match(r"^\s*```([^\s`]*)", box_body(previous)[1])
            if fence:
                in_code = not in_code
                language = (fence.group(1) or "text") if in_code else "text"

        from functools import lru_cache

        def syntax_fragments(line: str, language: str):
            prefix, content, suffix = box_body(line)
            fragments = [("class:box", prefix)] if prefix else []
            if (
                pygments_lex is None
                or get_lexer_by_name is None
                or pygments_token_to_classname is None
            ):
                fragments.append(("class:code", content))
            else:
                try:
                    lexer = get_lexer_by_name(language, stripnl=False, ensurenl=False)
                except Exception:
                    lexer = TextLexer(stripnl=False, ensurenl=False)
                for token, value in pygments_lex(content, lexer):
                    if value:
                        fragments.append(
                            ("class:" + pygments_token_to_classname(token), value)
                        )
            if suffix:
                fragments.append(("class:box", suffix))
            return fragments

        @lru_cache(maxsize=512)
        def get_line(lineno):
            line = lines[lineno]
            stripped = line.strip()
            if stripped and set(stripped) <= set("\u2500") or line.startswith("\u2500\u2500\u2500"):
                cls = "class:box.you" if " Sir " in line or line.startswith("\u2500\u2500\u2500Sir") else (
                    "class:box.kilo" if ("Kilo" in line or "\u2601" in line) else "class:box")
                return [(cls, line)]
            _prefix, body, _suffix = box_body(line)
            b = body.lstrip()
            in_code, language = contexts[lineno]
            if "\u26a0" in line or "destructive" in body.lower():
                return [("class:diff.del", line)]
            if b.startswith("+") and not b.startswith("+++"):
                return [("class:diff.add", line)]
            if b.startswith("-") and not b.startswith("---"):
                return [("class:diff.del", line)]
            if b.startswith(("\u25c8", "\u2713", "!")):
                return [("class:toolline", line)]
            if in_code:
                return syntax_fragments(line, language)
            if b.startswith("```"):
                return [("class:code", line)]
            return [("", line)]

        self._cached_text, self._cached_get_line = document.text, get_line
        return get_line


class _SlashCompleter(Completer):
    """Pops up a menu of / commands as soon as the line starts with a slash."""

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        if not text.startswith("/"):
            return
        for cmd, desc in _COMMANDS:
            if cmd.startswith(text) or cmd.strip() == text.strip():
                yield Completion(cmd, start_position=-len(text), display=cmd.strip(), display_meta=desc)


class KiloApp:
    def __init__(self, client: RPCClient):
        self.client = client
        self.session_id: str | None = None
        self.model_name = "Ollama"
        self.server_name = ""
        self.status: dict[str, Any] = {}

        self.busy = False          # a request is in flight
        self.streaming = False     # tokens are currently arriving
        self.phase = ""
        self.started = 0.0
        self.spin = 0
        # Live numeric counters for the stats bar.
        self.tokens = 0
        self.tools_used = 0
        self.show_panel = True     # left sidebar visibility (F2 toggles)
        self.effort = "medium"
        self.thinking = "off"      # /thinking level; forwarded to Ollama reasoning models
        self.agent_name = ""          # profile active this turn (auto-selected or forced)
        self.forced_profile = ""      # set by /agent; overrides auto-selection
        self._sessions: list[dict[str, Any]] = []
        self._active: asyncio.Task | None = None
        # Cloud escalation state. Ollama is always the default; /switch flips the
        # active route to the last-configured cloud provider and back.
        self.cloud_active = False
        self.cloud_provider = ""
        self.private_mode = False   # route web tools through Tor
        self.current_task = ""      # text of the request being worked on
        self._work_items: list[tuple[str, bool]] = []  # Kilo's live to-do items this turn
        self._model_options: list[str] = []
        self._perm_future: asyncio.Future | None = None   # resolved by 1/2/3 approval input
        self._line_buf = ""   # accumulates a streamed line until it can be boxed
        self.usage: dict[str, Any] = {}   # token usage from the last reply
        self._answered = False            # whether the current reply has started printing
        self._pending: dict[str, Any] | None = None   # awaited inline input (selector / key)
        self._choice_options: list[tuple[str, str]] = []
        self._choice_index = 0
        self._follow_output = True
        self._catalog: dict[str, Any] = {}
        self._cloud_options: list[tuple[str, dict[str, Any]]] = []
        self._ollama_models: list[dict[str, Any]] = []
        self._ollama_running: list[dict[str, Any]] = []
        # Strong refs to spawned background tasks. Without this, asyncio can garbage-
        # collect a task that is awaiting (e.g. an RPC round-trip) and silently cancel
        # it mid-run — which is why the /cloud setup appeared to do nothing.
        self._bg_tasks: set[asyncio.Task] = set()
        self._queue: asyncio.Queue | None = None   # pending (text, provider) requests
        self._worker: asyncio.Task | None = None

        self.output = TextArea(
            text="", read_only=True, scrollbar=False, wrap_lines=True,
            focusable=False, style="class:output", lexer=_ChatLexer(),
        )
        self.input = TextArea(
            height=1, multiline=False, wrap_lines=False, prompt=self._input_prompt,
            style="class:prompt", accept_handler=self._accept,
            completer=_SlashCompleter(), complete_while_typing=True,
            password=Condition(lambda: bool(self._pending and self._pending.get("kind") in
                {"cloud_key", "cloud_custom_key", "telegram_key"})),
        )
        self._build_layout()

    def _cw(self) -> int:
        try:
            cols = shutil.get_terminal_size((80, 24)).columns
        except Exception:
            cols = 80
        if self.show_panel and cols >= 88:
            cols -= 31
        return max(20, cols - 2)

    def _rule(self, label: str = "") -> str:
        w = self._cw()
        if label:
            head = "\u256d\u2500 " + label + " "
            return head + "\u2500" * max(0, w - len(head) - 1) + "\u256e"
        return "\u2570" + "\u2500" * max(0, w - 2) + "\u256f"

    def _bline(self, text: str = "") -> None:
        """Emit one fully-closed box line: | text ... | padded to the box width."""
        inner = max(1, self._cw() - 3)
        self._append("\u2502 " + text[:inner].ljust(inner) + "\u2502\n")

    def _stream_boxed(self, text: str) -> None:
        """Buffer streamed tokens and emit complete closed-box lines as they fill."""
        inner = max(1, self._cw() - 3)
        self._line_buf += text
        while True:
            nl = self._line_buf.find("\n")
            if nl >= 0:
                line, self._line_buf = self._line_buf[:nl], self._line_buf[nl + 1:]
                self._bline(self._clean_md(line))
            elif len(self._line_buf) >= inner:
                self._bline(self._line_buf[:inner])
                self._line_buf = self._line_buf[inner:]
            else:
                break

    def _clean_md(self, line: str) -> str:
        """Strip markdown noise (**, *, #, >) so replies read clean; the lexer colours
        the rest. Runs per already-buffered line, so no newlines to worry about."""
        s = re.sub(r'\*\*([^*]+)\*\*', r'\1', line)
        s = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', r'\1', s)
        s = re.sub(r'^(\s{0,3})#{1,6}\s+', r'\1', s)
        s = re.sub(r'^(\s{0,3})>\s?', r'\1', s)
        return s

    def _flush_boxed(self) -> None:
        if self._line_buf:
            self._bline(self._clean_md(self._line_buf))
            self._line_buf = ""

    def _input_prompt(self):
        if self.busy:
            glyph = PULSE[self.spin % len(PULSE)]
        else:
            glyph = "\u203a" if (self.spin // 6) % 2 else "\u276f"
        return [("class:prompt", f"  {glyph} ")]

    # ---- layout -------------------------------------------------------------

    def _shimmer(self, art: str, row: int):
        """Return a stable wordmark row.

        Repainting a multibyte block glyph one cell at a time makes some terminals show
        broken fragments while the animation ticks. The activity bar is the right place
        for motion; the product name must stay still and legible.
        """
        del row
        return [("class:banner", "  " + art + "   ")]

    @staticmethod
    def _seg_len(segs) -> int:
        return sum(len(txt) for _, txt in segs)

    def _mascot(self, row: int):
        """One row of the pixel eyeball: open most of the time, a quick blink now and
        then, with the pupil glinting red on a beat."""
        blink = (self.spin % 44) < 4
        frames = MASCOT_BLINK if blink else MASCOT_OPEN
        art = (frames[row] if row < len(frames) else "").ljust(13)
        glint = (self.spin // 4) % 6 == 0
        segs = []
        for ch in art:
            if ch == "●":
                segs.append(("class:banner.hi" if glint else "class:evil", ch))
            elif ch == "\u2593":                 # ▓ iris
                segs.append(("class:banner.hi", ch))
            elif ch in {"━", "▾"}:
                segs.append(("class:evil", ch))
            else:
                segs.append(("class:banner", ch))
        return segs

    def _banner_text(self):
        online = bool(self.status.get("healthy"))
        # A breathing dot animates even when idle, so the header never looks frozen.
        pulse = PULSE[self.spin % len(PULSE)]
        dot = f"{pulse} online" if online else "○ offline"
        info = [
            [("class:banner.hi", "KILOFRAME  "), ("class:on" if online else "class:off", dot)],
            [("class:tagline", "Kilo's framework · multiple AI providers")],
            [("class:on", f"model   {self.model_name}")],
            [("class:dim", f"server  {self.server_name}")],
            [("class:dim", "tools   files · shell · web · memory · skills")],
            [("class:tagline", "/help · F2 sidebar · Ctrl-Q quit")],
        ]
        # The block wordmark is the non-negotiable part of the header. On an 80-column
        # terminal it fits, but the additional status column does not; dropping that
        # secondary column prevents the logo from writing into (or under) the sidebar.
        inline_info = self._cw() >= len(KILO_ART[0]) + 34
        rows: list[tuple[str, str]] = []
        for i, art in enumerate(KILO_ART):
            rows += self._shimmer(art, i)
            line = info[i] if inline_info and i < len(info) else []
            rows += line
            rows.append(("", "\n"))
        # Align the credit with the left edge of the block wordmark. Centering it in
        # the entire conversation pane made it drift awkwardly as the sidebar changed.
        rows.append(("class:tagline", "  " + KILOFRAME_CREDIT))
        rows.append(("", "\n"))
        return rows

    def _stats_bar(self):
        elapsed = (time.monotonic() - self.started) if (self.busy and self.started) else 0
        if self.busy:
            phase = self.phase or ACTIVITY[(self.spin // 10) % len(ACTIVITY)]
            if self.streaming:
                # A blinking caret shows tokens are actively arriving.
                caret = "▌" if (self.spin // 3) % 2 else " "
                head = [("class:stat", " ▌ "), ("class:kilo", "responding"), ("class:stat", caret)]
            else:
                frames = _phase_frames(phase)
                glyph = frames[self.spin % len(frames)]
                dots = ELLIPSIS[(self.spin // 3) % len(ELLIPSIS)]
                head = [("class:stat", f" {glyph} "), ("class:kilo", phase), ("class:dim", f" {dots}")]
        else:
            # Do not call the application ready merely because the daemon socket is
            # alive.  A reachable Ollama server still needs a selected model.
            wave = "".join(PULSE[(self.spin + i) % len(PULSE)] for i in range(3))
            if not self.status.get("healthy"):
                state = "Ollama offline"
            elif not self.status.get("model"):
                state = "select a model (/local)"
            elif not self._ollama_running:
                state = "model selected · not loaded"
            else:
                state = "ready"
            head = [("class:stat", f" {wave} "), ("class:dim", state)]
        bar = head + [
            ("class:stat.k", "   ⏱ "), ("class:stat", f"{elapsed:0.0f}s"),
            ("class:stat.k", "   ↗ requests "), ("class:stat", str((self.status.get("memory") or {}).get("requests", 0))),
            ("class:stat.k", "   🔧 tools "), ("class:stat", f"{self.tools_used}"),
            ("class:stat.k", "   ⇥ tokens "), ("class:stat", f"{self.tokens}"),
            ("class:stat.k", "   ⌁ thinking "), ("class:stat", f"{self.thinking if self.thinking != 'off' else 'auto'}"),
            ("class:stat.k", "   ⬡ "),
            ("class:kilo", self._short_model()),
        ]
        if self.agent_name:
            bar += [("class:stat.k", "   ◆ "), ("class:kilo", self.agent_name)]
        qn = self._queue.qsize() if getattr(self, "_queue", None) else 0
        if qn:
            bar += [("class:stat.k", "   ⧉ queued "), ("class:stat", f"{qn}")]
        bg = len(getattr(self, "_bg_tasks", ()))
        if bg:
            bar += [("class:stat.k", "   ◌ background "), ("class:stat", str(bg))]
        if self.private_mode:
            bar += [("class:stat.k", "   🛡 "), ("class:kilo", "private")]
        return bar

    def _sidebar_text(self):
        mem = self.status.get("memory") or {}
        host = self.status.get("host") or {}
        rows: list[tuple[str, str]] = [
            ("class:panel.title", " KILOFRAME\n\n"),
            ("class:panel.key", " model    "), ("class:panel.hi", f"{self.model_name}\n"),
            ("class:panel.key", " route    "), ("", f"{('cloud·' + self.cloud_provider) if self.cloud_active else (self.server_name or 'ollama')}\n"),
            ("class:panel.key", " thinking "), ("", f"{self.thinking if self.thinking != 'off' else 'auto'}\n"),
            ("class:panel.key", " effort   "), ("", f"{self.effort}\n\n"),

            ("class:panel.title", " HOST · LIVE\n"),
            ("class:panel.key", " cpu "), ("class:on", f"{host.get('cpu_percent', '—')}%"),
            ("class:panel.key", "  mem "), ("class:on", f"{host.get('memory_used_mb', '—')}/{host.get('memory_total_mb', '—')} MiB"),
            ("class:dim", f" ({host.get('memory_percent', '—')}%)\n\n"),

            ("class:panel.title", " TASKS\n\n"),
        ]
        qn = self._queue.qsize() if getattr(self, "_queue", None) else 0
        if self.busy and self.current_task:
            rows.append(("class:panel.hi", " ● ")); rows.append(("", f"{self.current_task[:30]}\n"))
        else:
            rows.append(("class:dim", " idle\n"))
        if qn:
            rows.append(("class:panel.key", " queued   ")); rows.append(("", f"{qn}\n"))
        rows.append(("", "\n"))

        rows.append(("class:panel.title", " KILO'S WORK\n\n"))
        if self._work_items:
            for text, done in self._work_items[-4:]:
                mark = "✓" if done else "●"
                cls = "class:panel.hi" if done else "class:kilo"
                rows.append((cls, f" {mark} {text[:30]}\n"))
        else:
            rows.append(("class:dim", " no work yet\n"))
        rows.append(("", "\n"))

        rows.append(("class:panel.title", " CONTEXT\n\n"))
        rows.append(("class:panel.key", " agent    ")); rows.append(("", f"{self.agent_name or 'auto'}\n"))
        rows.append(("class:panel.key", " private  ")); rows.append(("class:on" if self.private_mode else "class:dim", f"{'on' if self.private_mode else 'off'}\n"))
        sid = self.session_id or ""
        rows.append(("class:panel.key", " session  ")); rows.append(("", f"{sid[:8] if sid else '—'}\n\n"))

        rows.append(("class:panel.title", " PROCESSES\n\n"))
        bg = len(getattr(self, "_bg_tasks", ()))
        rows.append(("class:panel.key", " background ")); rows.append(("", f"{bg}\n"))
        if self._ollama_running:
            for m in self._ollama_running[:2]:
                rows.append(("class:kilo", f" ▶ {str(m.get('name', ''))[:26]}\n"))
        else:
            rows.append(("class:dim", " no models loaded\n"))
        for server in self.status.get("mcp", []):
            if server.get("state") != "disabled":
                rows.append(("class:panel.key", f" MCP {server['name'][:13]} "))
                rows.append(("class:on" if server["state"] == "connected" else "class:off",
                             f"{len(server.get('tools', []))} tools\n" if server["state"] == "connected" else f"{server['state']}\n"))

        rows += [
            ("", "\n"), ("class:panel.title", " MEMORY\n"),
            ("class:panel.key", " sessions "), ("", f"{mem.get('sessions', '?')}"),
            ("class:panel.key", " · facts "), ("", f"{mem.get('facts', '?')}"),
            ("class:panel.key", " · skills "), ("", f"{mem.get('skills', '?')}\n"),
        ]
        return rows

    def _sidebar_visible(self) -> bool:
        if not self.show_panel:
            return False
        try:
            return shutil.get_terminal_size((80, 24)).columns >= 88
        except Exception:
            return True

    def _build_layout(self) -> None:
        sidebar = ConditionalContainer(
            VSplit([
                Window(FormattedTextControl(self._sidebar_text), width=30),
                Window(width=1, char="│", style="class:sep"),
            ]),
            filter=Condition(self._sidebar_visible),
        )
        root = HSplit([
            Window(FormattedTextControl(self._banner_text), height=len(KILO_ART) + 1),
            Window(height=1, char="─", style="class:sep"),
            VSplit([sidebar, self.output, Window(FormattedTextControl(self._scrollbar_text), width=1)]),
            Window(height=1, char="─", style="class:sep"),
            Window(FormattedTextControl(self._stats_bar), height=1),
            Window(height=1, char="─", style="class:sep"),
            ConditionalContainer(
                Window(FormattedTextControl(self._choice_text), height=lambda: min(8, len(self._choice_options)) + 1),
                filter=Condition(lambda: bool(self._choice_options)),
            ),
            self.input,
        ])
        root = FloatContainer(root, floats=[
            Float(xcursor=True, ycursor=True,
                  content=CompletionsMenu(max_height=8, scroll_offset=1)),
        ])
        self.layout = Layout(root, focused_element=self.input)

    def _spawn(self, coro) -> asyncio.Task:
        task = asyncio.create_task(coro)
        self._bg_tasks.add(task)
        task.add_done_callback(self._bg_tasks.discard)
        return task

    async def _worker_loop(self) -> None:
        """Process queued requests one at a time. There is a single inference slot, so
        running requests concurrently clobbers shared state and loses output — which
        looked like 'some messages never responded'. Serialising fixes that."""
        while True:
            text, provider = await self._queue.get()
            self.current_task = text
            try:
                await self._ask(text, provider)
            except Exception as exc:  # noqa: BLE001
                self._append(f"\n⚠ {exc}\n")
            finally:
                self.current_task = ""
                self._queue.task_done()
                self.app.invalidate()

    def _enqueue(self, text: str, provider: str | None = None) -> None:
        inner = max(1, self._cw() - 3)
        self._append("\n" + self._rule("Sir") + "\n")
        for para in text.split("\n"):
            if not para:
                self._bline("")
            while para:
                self._bline(para[:inner])
                para = para[inner:]
        self._append(self._rule() + "\n")
        ahead = (self._queue.qsize() if self._queue else 0) + (1 if self.busy else 0)
        if ahead > 0:
            self._append(f"⏳ queued — {ahead} task(s) ahead\n")
        if self._queue is not None:
            self._queue.put_nowait((text, provider))

    def _append(self, text: str) -> None:
        buff = self.output.buffer
        new = buff.text + text
        position = len(new) if self._follow_output else buff.cursor_position
        buff.set_document(Document(new, position), bypass_readonly=True)

    def _scroll_to(self, row: int) -> None:
        document = self.output.buffer.document
        row = max(0, min(row, document.line_count - 1))
        self._follow_output = row >= document.line_count - 1
        self.output.buffer.cursor_position = document.translate_row_col_to_index(row, 0)
        self.output.window.vertical_scroll = row
        app = getattr(self, "app", None)
        if app:
            app.invalidate()

    def _scrollbar_text(self):
        info = self.output.window.render_info
        height = max(3, info.window_height if info else 10)
        count = self.output.buffer.document.line_count
        top = self.output.window.vertical_scroll
        thumb = 1 + int((height - 3) * top / max(1, count - 1))

        def click(event):
            if event.event_type == MouseEventType.SCROLL_UP:
                self._scroll_to(top - 3)
            elif event.event_type == MouseEventType.SCROLL_DOWN:
                self._scroll_to(top + 3)
            elif event.event_type == MouseEventType.MOUSE_DOWN or (
                event.event_type == MouseEventType.MOUSE_MOVE and event.button == MouseButton.LEFT
            ):
                y = event.position.y
                if y == 0:
                    self._scroll_to(top - 1)
                elif y >= height - 1:
                    self._scroll_to(top + 1 if top + height < count else count - 1)
                else:
                    self._scroll_to(round((y - 1) * (count - 1) / max(1, height - 3)))
            else:
                return NotImplemented
            return None

        rows = []
        for y in range(height):
            glyph = "^" if y == 0 else "v" if y == height - 1 else "█" if y == thumb else "│"
            rows.extend([("class:scrollbar.button" if y == thumb else "class:scrollbar", glyph, click), ("", "\n")])
        return rows

    def _command_panel(self, title: str, lines: list[str]) -> None:
        """Keep command feedback readable instead of adding loose transcript text."""
        self._append("\n" + self._rule(title) + "\n")
        inner = max(1, self._cw() - 3)
        for line in lines:
            text = line or ""
            if not text:
                self._bline()
                continue
            for wrapped in textwrap.wrap(
                text,
                width=inner,
                break_long_words=False,
                break_on_hyphens=False,
            ):
                self._bline(wrapped)
        self._append(self._rule() + "\n")

    # ---- interaction --------------------------------------------------------

    def _choice_text(self):
        start = max(0, self._choice_index - 6)
        hint = "  ↑/↓ select · Enter apply · Esc cancel\n"
        if (self._pending or {}).get("kind") == "cloud_pick":
            hint = "  ↑/↓ select · Enter apply · type a provider name + Enter to search · Esc cancel\n"
        rows = [("class:dim", hint)]
        for i in range(start, min(start + 8, len(self._choice_options))):
            label = self._choice_options[i][1]
            selected = i == self._choice_index
            rows.append(("class:kilo" if selected else "class:dim",
                         f"  {'›' if selected else ' '} {label}\n"))
        return rows

    def _choose(self, title: str, options: list[tuple[str, str]], kind: str, **context) -> None:
        self._append(f"\n— {title} —\n")
        self._pending = {"kind": kind, **context}
        self._choice_options = options
        self._choice_index = 0
        if not options:
            self._pending = None
            self._append("— no options available —\n")
        if getattr(self, "app", None):
            self.app.invalidate()

    def _cancel_pending(self) -> None:
        self._choice_options = []
        if self._perm_future and not self._perm_future.done():
            self._perm_future.set_result("3")
        self._pending = None
        self._append("\n— cancelled —\n")

    def _accept(self, buff) -> bool:
        text = buff.text.strip()
        if self._choice_options and not text:
            text = self._choice_options[self._choice_index][0]
        if text.startswith("/") and self._pending:
            self._cancel_pending()
            self._handle_command(text)
            return False
        # Returning False clears the input for the next message.
        if not text:
            if self._pending:
                self._cancel_pending()
            return False
        # An awaited answer (cloud provider pick or API key) is consumed here rather than
        # being sent to the model. Returning False also wipes the key from the input line.
        if self._pending is not None:
            self._choice_options = []
            if self._pending.get("kind") == "permission" and self._perm_future and not self._perm_future.done():
                self._perm_future.set_result(text)
                self._pending = None
                return False
            self._spawn(self._resume_pending(text))
            return False
        if self._handle_command(text):
            return False
        self._enqueue(text)
        return False

    def _handle_command(self, text: str) -> bool:
        text = text.strip()
        command, _, argument = text.partition(" ")
        # Match complete command tokens. /modelsXYZ must never trigger /model.
        aliases = {"/kilochats": "/chats", "/kchats": "/chats", "/chat": "/chats",
                   "/cloudswitch": "/cloud", "/exit": "/quit", "/q": "/quit"}
        command = aliases.get(command, command)
        text = command + (" " + argument if argument else "")
        known = {name.strip() for name, _ in _COMMANDS}
        if command.startswith("/") and command not in known:
            self._append(f"\n— unknown command {command}; use /commands —\n")
            return True
        menus = {
            "/effort": [(f"/effort {x}", x) for x in ("low", "medium", "high")],
            "/agent": [(f"/agent {x}", x) for x in ("auto", "orchestrator", "research", "coding", "security", "math", "engineering", "systems", "general", "conversation", "private")],
            "/private": [(f"/private {x}", x) for x in ("status", "on", "off", "rotate")],
        }
        if text in menus:
            self._choose(text[1:], menus[text], "command")
            return True
        if text == "/thinking":
            self._spawn(self._thinking_menu())
            return True
        if text == "/mcp":
            self._spawn(self._mcp_menu())
            return True
        if text in {"/quit", "/exit", "/q", "quit", "exit"}:
            self.app.exit()
            return True
        if text == "/clear":
            self.output.buffer.set_document(Document("", 0), bypass_readonly=True)
            return True
        if text == "/new":
            self.session_id = None
            self.output.buffer.set_document(Document("", 0), bypass_readonly=True)
            self._append("— new session · the previous chat is saved (use /chats to reopen it) —\n")
            return True
        if text == "/help":
            self._command_panel("Help", [
                "/thinking off|on|low|medium|high   model-supported thinking control",
                "/effort high|medium|low             reply depth vs speed",
                "/agent <name>|off                   select a specialist or restore auto",
                "/local [status|models|ps|pull|select|load|unload]",
                "/localset [list|add|remove|default] configure Ollama servers",
                "/switch · /cloud · /model            change route or cloud model",
                "/chats · /delete                     manage conversations",
                "/private [on|off|rotate] · /cancel · /new · /clear · /quit",
                "F2 sidebar · Ctrl-C cancel · Ctrl-Q quit · /commands full reference",
            ])
            return True
        if text == "/chats":
            self._spawn(self._kilochats())
            return True
        if text.startswith("/chats "):
            self._spawn(self._open_chat(argument))
            return True
        if text == "/commands":
            self._command_panel("Commands", [f"{name:<18} {description}" for name, description in _COMMANDS])
            return True
        if text.startswith("/botkey"):
            token = text[len("/botkey"):].strip()
            if token:
                self._spawn(self._set_botkey(token))
            else:
                self._append("\n🔐 paste the Telegram bot token and press Enter (it will not be echoed back):\n")
                self._pending = {"kind": "telegram_key"}
            return True
        if text in ("/kilochats", "/kchats"):
            self._spawn(self._kilochats())
            return True
        if text == "/delete":
            self._spawn(self._delete_chats())
            return True
        if text.startswith("/delete "):
            self._spawn(self._delete_pick(text.split(maxsplit=1)[1].strip()))
            return True
        if text.startswith("/chat "):
            self._spawn(self._open_chat(text.split(maxsplit=1)[1].strip()))
            return True
        if text.startswith("/agent"):
            parts = text.split()
            name = parts[1].lower() if len(parts) > 1 else ""
            name = {"hacking": "security", "hack": "security", "pentest": "security",
                    "chat": "conversation", "convo": "conversation", "anon": "private",
                    "tor": "private", "orchestrate": "orchestrator", "router": "orchestrator"}.get(name, name)
            valid = {"research", "coding", "security", "math", "engineering", "systems", "general", "conversation",
                     "private", "orchestrator"}
            if name in {"", "off", "auto"}:
                self.forced_profile = ""
                self._append("\n— agent auto-selection restored —\n")
            elif name in valid:
                self.forced_profile = name
                self.agent_name = name
                self._append(f"\n— forced {name} agent (use /agent off to auto-select) —\n")
            else:
                self._append(f"\n— unknown agent; choose {', '.join(sorted(valid))} —\n")
            return True
        if text.startswith("/effort"):
            parts = text.split()
            level = parts[1].lower() if len(parts) > 1 else ""
            if level in {"high", "medium", "low"}:
                self.effort = level
                self._append(f"\n— effort set to {level} —\n")
            else:
                self._append("\n— use /effort high|medium|low —\n")
            return True
        if text.startswith("/thinking"):
            parts = text.split()
            level = parts[1].lower() if len(parts) > 1 else ""
            if level in {"off", "on", "low", "medium", "high"}:
                self._spawn(self._set_thinking(level))
            else:
                self._append("\n— use /thinking off|on|low|medium|high —\n")
            return True
        if text.startswith("/local "):
            parts = text.split(maxsplit=2)
            action = parts[1].lower()
            value = parts[2].strip() if len(parts) == 3 else ""
            if action == "status":
                self._spawn(self._local_status())
            elif action in {"models", "list"}:
                self._spawn(self._local_models())
            elif action in {"ps", "running"}:
                self._spawn(self._local_running())
            elif action == "pull" and value:
                self._spawn(self._local_pull(value))
            elif action == "select" and value:
                self._spawn(self._local_select(value))
            elif action == "select":
                self._spawn(self._local_models())
            elif action == "load" and value:
                self._spawn(self._local_load(value))
            elif action == "load":
                self._spawn(self._local_models(load_after_select=True))
            elif action == "pull":
                self._append("\n— Model name to download:\n")
                self._pending = {"kind": "local_pull"}
            elif action == "unload":
                self._spawn(self._local_unload(value or None))
            else:
                self._append("\n— /local [status|models|ps|pull <model>|select <model>|load [model]|unload [model]] —\n")
            return True
        if text == "/local":
            self._spawn(self._local_menu())
            return True
        if text.startswith("/localset "):
            parts = text.split(maxsplit=2)
            action = parts[1].lower()
            value = parts[2].strip() if len(parts) == 3 else ""
            if action == "list":
                self._spawn(self._localset_menu())
            elif action == "add" and len(value.split(maxsplit=1)) == 2:
                name, url = value.split(maxsplit=1)
                self._spawn(self._localset_add(name, url))
            elif action == "add":
                self._append("\n— Ollama server address:\n")
                self._pending = {"kind": "localset_url"}
            elif action in {"remove", "default", "switch"} and not value:
                self._spawn(self._server_picker("localset_remove" if action == "remove" else "localset_default"))
            elif action == "remove" and value:
                self._spawn(self._localset_remove(value))
            elif action in {"default", "switch"} and value:
                self._spawn(self._localset_default(value))
            else:
                self._append("\n— /localset [list|add <name> <url>|remove <name>|default <name>] —\n")
            return True
        if text == "/localset":
            self._spawn(self._localset_menu())
            return True
        if text.startswith("/cloudswitch"):
            self._spawn(self._cloud_setup(force_key=False))
            return True
        if text.startswith("/cloud"):
            rest = text[len("/cloud"):].strip()
            # Re-run the provider picker to add or change an API key at any time.
            if rest.lower() in ("add", "key", "keys", "change", "new", "setup"):
                self._spawn(self._cloud_setup(force_key=True))
                return True
            # No provider yet: run the pick-and-key setup, carrying any question along.
            if not self.cloud_provider:
                self._spawn(self._cloud_setup(pending_question=rest or None))
                return True
            if not rest:
                self._spawn(self._cloud_setup())
                return True
            self._enqueue(rest, provider=self.cloud_provider)
            return True
        if text == "/switch":
            self._spawn(self._switch_route())
            return True
        if text.startswith("/private"):
            arg = text[len("/private"):].strip().lower()
            if arg == "off":
                self.private_mode = False
                self._append("\n— private mode OFF · web requests go direct again —\n")
            elif arg == "rotate":
                self._spawn(self._rotate_circuit())
            elif arg == "status":
                self._spawn(self._private_status())
            elif arg == "on":
                self.private_mode = True
                self._append("\n🛡 private mode ON · web searches and fetches route through Tor.\n"
                             "   Your IP is hidden; if Tor is down the request is refused, never sent\n"
                             "   unmasked. Exit with /private off · new IP with /private rotate\n")
                self._spawn(self._private_status())
            else:
                self._append("\n— use /private to select status, on, off or rotate —\n")
            return True
        if text.startswith("/model"):
            arg = text[len("/model"):].strip()
            if arg:
                self._spawn(self._model_cmd(arg))
            else:
                self._spawn(self._model_picker())
            return True
        if text == "/cancel":
            cancelled = False
            if self._queue is not None:
                while not self._queue.empty():
                    try:
                        self._queue.get_nowait()
                        self._queue.task_done()
                        cancelled = True
                    except Exception:
                        break
            if self._active and not self._active.done():
                self._active.cancel()
                cancelled = True
            self._append("\n— cancelled —\n" if cancelled else "\n— nothing to cancel —\n")
            return True
        return False

    async def _list_chats(self) -> None:
        try:
            data = await self.client.request("sessions")
        except (ConnectionError, FileNotFoundError, OSError) as exc:
            self._append(f"\n⚠ could not list sessions: {exc}\n")
            return
        self._sessions = data.get("sessions", [])
        if not self._sessions:
            self._append("\n— no past sessions yet —\n")
            return
        lines = ["\npast sessions — choose one below to resume:"]
        for i, s in enumerate(self._sessions, 1):
            title = " ".join((s.get("title") or "").split()) or "(untitled)"
            stamp = s.get("updated_at")
            when = _dt.datetime.fromtimestamp(float(stamp)).strftime("%Y-%m-%d %H:%M") if stamp else "unknown time"
            lines.append(f"  {i:>2}. {when}  {title[:48]}  · {s.get('messages',0)} msgs")
        self._append("\n".join(lines) + "\n")

    async def _mcp_menu(self) -> None:
        try:
            data = await self.client.request("mcp_status")
            servers = data.get("servers", [])
            self._choose("MCP servers", [(str(i), f"{s['name']} · {s['state']} · {len(s['tools'])} tools")
                         for i, s in enumerate(servers)], "mcp_pick", servers=servers)
        except (ConnectionError, OSError) as exc:
            self._append(f"\n⚠ {exc}\n")

    async def _kilochats(self) -> None:
        """List past chats and arm a selector: the next number typed opens and continues it."""
        await self._list_chats()
        if self._sessions:
            self._choose("Open conversation", [(str(i), " ".join(str(s.get("title") or "Untitled").split())[:90])
                         for i, s in enumerate(self._sessions, 1)], "chat_pick")

    async def _open_chat(self, arg: str) -> None:
        try:
            session = self._sessions[int(arg) - 1]
        except (ValueError, IndexError):
            self._append("\n— unknown chat number; run /chats first —\n")
            return
        self.session_id = session["id"]
        try:
            data = await self.client.request("session_history", session_id=self.session_id)
        except (ConnectionError, FileNotFoundError, OSError) as exc:
            self._append(f"\n⚠ could not load session: {exc}\n")
            return
        self.output.buffer.set_document(Document("", 0), bypass_readonly=True)
        self._append(f"— resumed session · {session.get('messages',0)} messages —\n")
        for m in data.get("messages", []):
            self._append(f"\n{_you(m['content']) if m['role']=='user' else m['content']}\n")
        self._append("\n— continue below —\n")

    async def _delete_chats(self) -> None:
        """List past chats and arm a delete selector: the next number(s) typed are removed."""
        await self._list_chats()
        if self._sessions:
            self._append("  choose one conversation below to delete; Esc cancels.\n")
            self._pending = {"kind": "chat_delete"}
            self._choose("Delete conversation", [(str(i), " ".join(str(s.get("title") or "Untitled").split())[:90])
                         for i, s in enumerate(self._sessions, 1)], "chat_delete")

    async def _delete_pick(self, arg: str) -> None:
        """Delete chats chosen by number from the last listing (or 'all')."""
        if not self._sessions:
            await self._list_chats()
        await self._do_delete(arg)

    async def _do_delete(self, arg: str) -> None:
        arg = arg.strip().lower()
        sessions = list(self._sessions)
        if not sessions:
            self._append("\n— no chats to delete; run /chats first —\n")
            return
        if arg in {"all", "*", "everything"}:
            targets = list(sessions)
        else:
            picked: list[dict[str, Any]] = []
            for part in arg.replace(",", " ").split():
                if part.isdigit() and 1 <= int(part) <= len(sessions):
                    picked.append(sessions[int(part) - 1])
            if not picked:
                self._append("\n— nothing deleted (no valid chat number given) —\n")
                return
            seen: set[str] = set()
            targets = [s for s in picked if not (s["id"] in seen or seen.add(s["id"]))]
        removed = 0
        for session in targets:
            try:
                data = await self.client.request("delete_session", session_id=session["id"])
            except (ConnectionError, FileNotFoundError, OSError) as exc:
                self._append(f"\n⚠ could not delete a chat: {exc}\n")
                continue
            if data.get("deleted"):
                removed += 1
                if session["id"] == self.session_id:
                    self.session_id = None
        self._append(f"\n\U0001f5d1  deleted {removed} chat{'s' if removed != 1 else ''}.\n")
        await self._list_chats()

    async def _cloud_setup(self, pending_question: str | None = None, force_key: bool = False) -> None:
        """Show built-in providers, configured custom providers, and custom setup."""
        try:
            data = await self.client.request("providers_catalog")
        except (ConnectionError, FileNotFoundError, OSError) as exc:
            self._append(f"\n⚠ could not load providers: {exc}\n")
            return
        self._catalog = data
        self._cloud_options = list((data.get("known") or {}).items())
        self._cloud_options.append(("custom", {
            "label": "Custom endpoint", "model": "OpenAI-compatible HTTPS"
        }))
        configured = set(data.get("configured", []))
        self._append("\n☁ choose a cloud provider below. Type part of its name and press Enter to filter; use ↑/↓ and Enter to select.\n")
        self._pending = {"kind": "cloud_pick", "question": pending_question, "force_key": force_key}
        self._choose("Cloud provider", [("__search__", "Search provider catalog…"),
                     *[(name, meta["label"] + (" ✓ configured" if name in configured else ""))
                       for name, meta in self._cloud_options]], "cloud_pick", question=pending_question, force_key=force_key)

    def _run_cloud(self, name: str, question: str | None) -> None:
        """Activate a configured provider and, if a question was queued, send it now."""
        self.cloud_provider = name
        self.cloud_active = True
        self._append(f"\n— routing to cloud · {name} (use /switch for Ollama) —\n")
        self._spawn(self._refresh_model_label())
        if question:
            self._enqueue(question, provider=name)

    async def _switch_route(self) -> None:
        """Toggle routes, discovering the persisted cloud default on a fresh TUI."""
        if self.cloud_active:
            self.cloud_active = False
            self._append("\n— switched to Ollama —\n")
            await self._refresh_model_label()
            return
        if not self.cloud_provider:
            try:
                info = await self.client.request("provider_info")
            except (ConnectionError, FileNotFoundError, OSError) as exc:
                self._append(f"\n⚠ could not inspect cloud providers: {exc}\n")
                return
            default = str(info.get("default") or "").strip()
            if not default:
                self._append("\n— no configured cloud provider; run /cloud to set one up —\n")
                return
            self.cloud_provider = default
        self.cloud_active = True
        self._append(f"\n— switched to cloud · {self.cloud_provider} —\n")
        await self._refresh_model_label()

    async def _resume_pending(self, text: str) -> None:
        pending = self._pending or {}
        self._pending = None
        kind = pending.get("kind")
        self._choice_options = []
        if kind == "command":
            self._handle_command(text)
            return
        if kind == "mcp_pick":
            try:
                server = pending["servers"][int(text)]
            except (ValueError, IndexError, KeyError):
                self._append("\n— invalid MCP selection —\n")
                return
            self._command_panel(server["name"], [server["state"], server.get("error") or "",
                                *server.get("tools", []), "Configure servers in /etc/kiloframe/mcp.json; restart after changes."])
            return
        if kind == "localset_url":
            from urllib.parse import urlsplit
            url = text.strip()
            if "://" not in url:
                url = "http://" + url
            parsed = urlsplit(url)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
                self._append("\n⚠ enter an HTTP(S) Ollama server address\n")
                self._pending = {"kind": "localset_url"}
                return
            if not parsed.port:
                url = url.rstrip("/") + ":11434" if not parsed.path or parsed.path == "/" else url
            name = re.sub(r"[^a-zA-Z0-9_-]", "-", parsed.hostname)
            await self._localset_add(name, url)
            return
        if kind == "local_menu":
            arg = text.strip().lower()
            if arg == "m":
                await self._local_models()
            elif arg == "p":
                await self._local_running()
            elif arg == "pull":
                self._append("\n— type the model name to pull (e.g. llama3.2 or qwen2.5:14b):\n")
                self._pending = {"kind": "local_pull"}
            elif arg == "select":
                await self._local_models()
            elif arg == "load":
                await self._local_models(load_after_select=True)
            elif arg == "u":
                await self._local_unload()
            else:
                self._append("— cancelled —\n")
            return
        if kind == "local_pull":
            if text.strip():
                await self._local_pull(text.strip())
            else:
                self._append("\n— cancelled —\n")
            return
        if kind == "local_select":
            name = None
            if text.isdigit() and 1 <= int(text) <= len(self._ollama_models):
                name = self._ollama_models[int(text) - 1].get("name")
            elif text.strip():
                name = text.strip()
            if name:
                await self._local_select(name)
            else:
                self._append("\n— cancelled —\n")
            return
        if kind == "local_load":
            name = None
            if text.isdigit() and 1 <= int(text) <= len(self._ollama_models):
                name = self._ollama_models[int(text) - 1].get("name")
            elif text.strip():
                name = text.strip()
            if name:
                await self._local_load(str(name))
            else:
                self._append("\n— cancelled —\n")
            return
        if kind == "localset_menu":
            arg = text.strip().lower()
            if arg == "add":
                self._append("\n— Ollama server address (e.g. http://localhost:11434):\n")
                self._pending = {"kind": "localset_url"}
            elif arg == "remove":
                await self._server_picker("localset_remove")
            elif arg == "default":
                await self._server_picker("localset_default")
            else:
                self._append("— cancelled —\n")
            return
        if kind == "localset_add":
            parts = text.strip().split(maxsplit=1)
            if len(parts) == 2:
                await self._localset_add(parts[0], parts[1])
            else:
                self._append("\n— cancelled (expected <name> <url>) —\n")
            return
        if kind == "localset_remove":
            if text.strip():
                await self._localset_remove(text.strip())
            else:
                self._append("\n— cancelled —\n")
            return
        if kind == "localset_default":
            if text.strip():
                await self._localset_default(text.strip())
            else:
                self._append("\n— cancelled —\n")
            return
        if kind == "chat_pick":
            if text.strip().isdigit():
                await self._open_chat(text.strip())
            else:
                self._append("— stayed in the current chat —\n")
            return
        if kind == "chat_delete":
            stripped = text.strip().lower()
            if stripped in {"all", "*", "everything"} or any(c.isdigit() for c in stripped):
                await self._do_delete(text)
            else:
                self._append("— cancelled; no chats deleted —\n")
            return
        if kind == "model_pick":
            name = None
            if text.isdigit() and 1 <= int(text) <= len(self._model_options):
                name = self._model_options[int(text) - 1]
            elif text.strip() in self._model_options:
                name = text.strip()
            if not name:
                self._append("\n— cancelled —\n")
                return
            await self._model_cmd(name)
            return
        if kind == "cloud_pick":
            if text.strip() == "__search__":
                self._append("\n☁ search provider catalog:\n")
                self._pending = {"kind": "cloud_search", "question": pending.get("question"),
                                 "force_key": pending.get("force_key")}
                return
            name = None
            choices = self._choice_options or [(n, meta.get("label", n)) for n, meta in self._cloud_options]
            names = [n for n, _ in choices]
            if text.isdigit() and 1 <= int(text) <= len(names):
                name = names[int(text) - 1]
            elif text.strip().lower() in names:
                name = text.strip().lower()
            if not name:
                query = text.strip().lower()
                matches = [(provider, meta) for provider, meta in self._cloud_options
                           if query and (query in provider or query in str(meta.get("label", "")).lower())]
                if matches:
                    configured = set(self._catalog.get("configured", []))
                    self._append(f"\n— {len(matches)} provider match{'es' if len(matches) != 1 else ''} for {query!r} —\n")
                    self._choose("Cloud provider", [(provider, meta["label"] + (" ✓ configured" if provider in configured else ""))
                        for provider, meta in matches], "cloud_pick", question=pending.get("question"), force_key=pending.get("force_key"))
                    return
                self._append("\n— no provider matches; type part of a provider name or use /cloud again —\n")
                return
            if name in set(self._catalog.get("configured", [])) and not pending.get("force_key"):
                self._run_cloud(name, pending.get("question"))
                return
            if name == "custom":
                self._append("\n☁ custom provider name (lowercase letters, numbers, '-' or '_'):\n")
                self._pending = {"kind": "cloud_custom_name", "question": pending.get("question")}
                return
            if name == "cloudflare":
                self._append("\n☁ enter your Cloudflare account ID:\n")
                self._pending = {"kind": "cloud_account", "name": name, "question": pending.get("question")}
            else:
                self._append(f"\n☁ paste your {name} API key and press Enter:\n")
                self._pending = {"kind": "cloud_key", "name": name, "question": pending.get("question")}
            return
        if kind == "cloud_search":
            query = text.strip().lower()
            matches = [(provider, meta) for provider, meta in self._cloud_options
                       if query and (query in provider or query in str(meta.get("label", "")).lower())]
            if not matches:
                self._append("\n— no provider matches; try another name —\n")
                self._pending = {"kind": "cloud_search", "question": pending.get("question"),
                                 "force_key": pending.get("force_key")}
                return
            configured = set(self._catalog.get("configured", []))
            self._append(f"\n— {len(matches)} provider match{'es' if len(matches) != 1 else ''} for {query!r} —\n")
            self._choose("Cloud provider", [(provider, meta["label"] + (" ✓ configured" if provider in configured else ""))
                for provider, meta in matches], "cloud_pick", question=pending.get("question"), force_key=pending.get("force_key"))
            return
        if kind == "cloud_custom_name":
            name = text.strip().lower()
            if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,39}", name) or name == "custom":
                self._append("\n⚠ invalid custom provider name\n")
                return
            self._append("\n☁ OpenAI-compatible base URL (https://…/v1):\n")
            self._pending = {"kind": "cloud_custom_url", "name": name, "question": pending.get("question")}
            return
        if kind == "cloud_custom_url":
            url = text.strip().rstrip("/")
            if not url.startswith("https://"):
                self._append("\n⚠ custom cloud endpoints must use https://\n")
                return
            self._append("\n☁ model name served by this endpoint:\n")
            self._pending = {"kind": "cloud_custom_model", "name": pending["name"], "base_url": url, "question": pending.get("question")}
            return
        if kind == "cloud_custom_model":
            if not text.strip():
                self._append("\n⚠ a model name is required\n")
                return
            self._append("\n☁ API key (stored in the protected provider configuration):\n")
            self._pending = {"kind": "cloud_custom_key", "name": pending["name"], "base_url": pending["base_url"], "model": text.strip(), "question": pending.get("question")}
            return
        if kind == "cloud_custom_key":
            try:
                res = await self.client.request(
                    "configure_custom_provider", name=pending["name"],
                    base_url=pending["base_url"], model=pending["model"], api_key=text,
                )
            except (ConnectionError, FileNotFoundError, OSError) as exc:
                self._append(f"\n⚠ could not save custom endpoint: {exc}\n")
                return
            if not res.get("ok"):
                self._append(f"\n⚠ {res.get('error', 'could not configure custom endpoint')}\n")
                return
            self._append(f"\n✓ {res.get('label', pending['name'])} configured.\n")
            self._run_cloud(pending["name"], pending.get("question"))
            return
        if kind == "cloud_account":
            if not text.strip() or not text.strip().replace("-", "").isalnum():
                self._append("\n⚠ invalid Cloudflare account ID\n")
                return
            self._append("\n☁ paste your Cloudflare API token and press Enter:\n")
            self._pending = {"kind": "cloud_key", "name": "cloudflare", "account_id": text.strip(), "question": pending.get("question")}
            return
        if kind == "cloud_key":
            name = pending["name"]
            try:
                res = await self.client.request("configure_provider", name=name, api_key=text, account_id=pending.get("account_id"))
            except (ConnectionError, FileNotFoundError, OSError) as exc:
                self._append(f"\n⚠ could not save key: {exc}\n")
                return
            if not res.get("ok"):
                self._append(f"\n⚠ {res.get('error', 'could not configure provider')}\n")
                return
            self._append(f"\n✓ {res.get('label', name)} configured.\n")
            self._run_cloud(name, pending.get("question"))
            return
        if kind == "telegram_key":
            await self._set_botkey(text.strip())

    async def _set_botkey(self, token: str) -> None:
        try:
            res = await self.client.request("set_telegram_token", token=token)
        except (ConnectionError, FileNotFoundError, OSError) as exc:
            self._append(f"\n⚠ could not save Telegram bot token: {exc}\n")
            return
        if not res.get("ok"):
            self._append(f"\n⚠ {res.get('error', 'invalid Telegram bot token')}\n")
            return
        self._append("\n✓ Telegram bot token saved securely. Restart or wait for the bridge to reload it.\n")

    async def _rotate_circuit(self) -> None:
        try:
            res = await self.client.request("rotate_circuit")
        except (ConnectionError, FileNotFoundError, OSError) as exc:
            self._append(f"\n⚠ could not rotate: {exc}\n")
            return
        if res.get("ok"):
            self._append(f"\n🛡 new Tor circuit · exit IP {res.get('exit_ip') or 'unknown'}\n")
        else:
            self._append(f"\n⚠ {res.get('error', 'could not rotate circuit')}\n")

    async def _private_status(self) -> None:
        try:
            res = await self.client.request("tor_status")
        except (ConnectionError, FileNotFoundError, OSError):
            return
        if not res.get("available"):
            self._append("\n⚠ Tor is not reachable — private requests will be refused (fail-closed), "
                         "not sent unmasked. Start it: sudo systemctl start tor\n")

    async def _refresh_model_label(self) -> None:
        """Keep the displayed model/server in sync with the active route: the Ollama
        server's selected model, or the cloud provider's current model."""
        try:
            if self.cloud_active and self.cloud_provider:
                info = await self.client.request("provider_info")
                model = info.get("model")
                self.model_name = f"{info.get('default')}:{model}" if model else f"cloud·{self.cloud_provider}"
                self.server_name = ""
            else:
                st = await self.client.request("status")
                self.model_name = str(st.get("model") or "Ollama") or "Ollama"
                self.server_name = str(st.get("server") or "")
        except (ConnectionError, FileNotFoundError, OSError):
            pass
        # Unit tests and headless callers can exercise cloud switching before the
        # prompt_toolkit Application is attached; refreshing the label must stay safe.
        app = getattr(self, "app", None)
        if app is not None:
            app.invalidate()

    async def _refresh_ollama_running(self) -> None:
        try:
            if not self.cloud_active:
                running = await self.client.request("ollama_running")
                self._ollama_running = running if isinstance(running, list) else []
        except Exception:
            self._ollama_running = []

    async def _thinking_menu(self) -> None:
        options = [("/thinking off", "Off")]
        if not self.cloud_active:
            try:
                capability = await self.client.request("ollama_thinking_capability")
                if capability.get("supported"):
                    options += [(f"/thinking {x}", x.title()) for x in (capability.get("levels") or ["on"])]
                else:
                    self._append(f"\n— {capability.get('reason', 'Thinking unsupported')} —\n")
            except (ConnectionError, OSError) as exc:
                self._append(f"\n⚠ {exc}\n")
        self._choose("Thinking", options, "command")

    async def _set_thinking(self, level: str) -> None:
        """Set native reasoning only after checking the selected route's capability."""
        if level == "off":
            self.thinking = "off"
            self._append("\n— native thinking disabled —\n")
            return
        if self.cloud_active:
            self._append("\n— /thinking is unavailable on the active cloud route; this provider has not advertised a compatible control —\n")
            return
        try:
            capability = await self.client.request("ollama_thinking_capability")
        except (ConnectionError, FileNotFoundError, OSError) as exc:
            self._append(f"\n⚠ could not inspect thinking support: {exc}\n")
            return
        if not capability.get("supported"):
            self._append(f"\n— /thinking not enabled: {capability.get('reason', 'unsupported by the selected model')} —\n")
            return
        levels = set(capability.get("levels") or [])
        if level == "on":
            self.thinking = "on"
            self._append(f"\n— native thinking enabled for {capability.get('model', 'the selected model')} —\n")
        elif level in levels:
            self.thinking = level
            self._append(f"\n— native thinking set to {level} for {capability.get('model', 'the selected model')} —\n")
        else:
            self._append("\n— the selected model supports thinking but has not advertised effort levels; use /thinking on or /thinking off —\n")

    async def _model_picker(self) -> None:
        try:
            info = await self.client.request("provider_info", name=self.cloud_provider or None)
        except (ConnectionError, FileNotFoundError, OSError) as exc:
            self._append(f"\n⚠ {exc}\n")
            return
        if not info.get("default"):
            self._append("\n— no cloud provider configured; run /cloud first —\n")
            return
        self._append("\n☁ fetching available models…\n")
        try:
            res = await self.client.request("provider_models", name=info["default"], only_free=False)
        except (ConnectionError, FileNotFoundError, OSError) as exc:
            self._append(f"\n⚠ {exc}\n")
            return
        if not res.get("ok"):
            self._append(f"\n⚠ {res.get('error', 'could not list models')} — use /model <name>\n")
            return
        await self._refresh_model_label()
        models = res.get("models", [])
        if not models:
            self._append("\n— no models returned; use /model <name> —\n")
            return
        self._model_options = models
        self._append(f"\n☁ {info['default']} · current {info.get('model') or '(unset)'} — choose a model below.\n")
        self._pending = {"kind": "model_pick"}
        self._choose("Cloud model", [(str(i), model) for i, model in enumerate(models, 1)], "model_pick")

    async def _local_menu(self) -> None:
        """The /local command: Ollama route status, models, pull, select, unload."""
        await self._refresh_model_label()
        try:
            st = await self.client.request("status")
            server = st.get("server") or "no server"
            model = st.get("model") or "no model"
        except (ConnectionError, FileNotFoundError, OSError):
            server, model = "unknown", "unknown"
        self._append(
            f"\n◆ Ollama route\n"
            f"  server  {server}\n"
            f"  model   {model}\n"
            f"  choose an action below.\n"
        )
        self._pending = {"kind": "local_menu"}
        self._choose("Ollama", [("select", "Select a downloaded model"), ("m", "Downloaded models"),
                     ("p", "Running models"), ("load", "Load a model now"), ("pull", "Download a model"), ("u", "Unload selected model")], "local_menu")

    async def _local_status(self) -> None:
        try:
            status = await self.client.request("ollama_status")
        except (ConnectionError, FileNotFoundError, OSError) as exc:
            self._append(f"\n⚠ {exc}\n")
            return
        if not status.get("healthy"):
            self._append(f"\n◆ Ollama route unavailable\n  {status.get('error') or status.get('server') or 'no configured server'}\n")
            return
        self._append(
            f"\n◆ Ollama route reachable\n"
            f"  server     {status.get('server')}\n"
            f"  model      {status.get('model') or 'none selected'}\n"
            f"  downloaded {len(status.get('models') or [])}\n"
            f"  loaded     {len(status.get('running') or [])}\n"
        )

    async def _local_models(self, load_after_select: bool = False) -> None:
        try:
            models = await self.client.request("ollama_models")
        except (ConnectionError, FileNotFoundError, OSError) as exc:
            self._append(f"\n⚠ {exc}\n")
            return
        if isinstance(models, dict):
            self._append(f"\n⚠ {models.get('error', 'could not list models')}\n")
            return
        self._ollama_models = models or []
        if not models:
            self._append("\n— no models downloaded on this server —\n"
                         "   run /local → pull to download one\n")
            return
        lines = ["\n◆ models on this server — choose below to select:"]
        for i, m in enumerate(models, 1):
            size = m.get("size", 0) // (1024 * 1024)
            detail = m.get("details") or {}
            extra = f"  {detail.get('parameter_size', '')} {detail.get('quantization_level', '')}".strip()
            lines.append(f"  {i:>2}. {m.get('name')}  {size} MiB  {extra}")
        self._append("\n".join(lines) + "\n")
        self._choose("Ollama model", [(str(i), str(m.get("name")))
                     for i, m in enumerate(models, 1)], "local_load" if load_after_select else "local_select")

    async def _local_running(self) -> None:
        try:
            running = await self.client.request("ollama_running")
        except (ConnectionError, FileNotFoundError, OSError) as exc:
            self._append(f"\n⚠ {exc}\n")
            return
        if isinstance(running, dict):
            self._append(f"\n⚠ {running.get('error', 'could not list running models')}\n")
            return
        if not running:
            self._append("\n— no models currently running/loaded on the server —\n")
            return
        lines = ["\n◆ running models:"]
        for m in running:
            lines.append(f"  ▶ {m.get('name')}  {m.get('size', 0) // (1024*1024)} MiB")
        self._append("\n".join(lines) + "\n")

    async def _local_pull(self, model: str) -> None:
        self._append(f"\n⇣ pulling {model} …\n")
        try:
            async for event in self.client.stream("ollama_pull", model=model):
                if event.get("type") == "ollama_progress":
                    self._append(f"  {event.get('status')}\n")
                elif event.get("type") == "result":
                    if event.get("data", {}).get("ok"):
                        self._append(f"\n✓ pulled {model}\n")
                    else:
                        self._append(f"\n⚠ {event.get('data', {}).get('error', 'pull failed')}\n")
                elif event.get("type") == "error":
                    self._append(f"\n⚠ {event.get('error')}\n")
        except (ConnectionError, FileNotFoundError, OSError) as exc:
            self._append(f"\n⚠ {exc}\n")
        self._spawn(self._refresh_ollama_running())

    async def _local_select(self, model: str) -> None:
        # The model list is deliberately numbered for terminal users, so accept
        # that number everywhere selection is accepted (including the direct
        # `/local select 2` form), not only in the interactive picker.
        if model.strip().isdigit():
            try:
                models = await self.client.request("ollama_models")
            except (ConnectionError, FileNotFoundError, OSError) as exc:
                self._append(f"\n⚠ {exc}\n")
                return
            if isinstance(models, dict):
                self._append(f"\n⚠ {models.get('error', 'could not list models')}\n")
                return
            index = int(model.strip()) - 1
            if index < 0 or index >= len(models or []):
                self._append(f"\n⚠ model number {model.strip()} is not in /local models\n")
                return
            model = str((models or [])[index].get("name") or "").strip()
            if not model:
                self._append(f"\n⚠ model number {index + 1} has no usable name\n")
                return
        try:
            data = await self.client.request("ollama_select_model", model=model)
        except (ConnectionError, FileNotFoundError, OSError) as exc:
            self._append(f"\n⚠ {exc}\n")
            return
        if data.get("ok"):
            self._append(f"\n✓ selected {data.get('model')} on {data.get('server')}\n")
            self._spawn(self._refresh_model_label())
        else:
            self._append(f"\n⚠ {data.get('error', 'could not select model')}\n")

    async def _local_load(self, model: str | None = None) -> None:
        label = model or self.model_name or "selected model"
        self._append(f"\n↻ loading {label} on the active Ollama server… this can take up to 3 minutes for a remote or CPU-only server.\n")
        try:
            data = await self.client.request("ollama_load", model=model or "")
        except (ConnectionError, FileNotFoundError, OSError) as exc:
            self._append(f"\n⚠ {exc}\n")
            return
        if data.get("ok"):
            self._append(f"\n✓ loaded {data.get('model')}\n")
            self._spawn(self._refresh_ollama_running())
            self._spawn(self._refresh_model_label())
        else:
            self._append(f"\n⚠ {data.get('error', 'could not load model')}\n")

    async def _local_unload(self, model: str | None = None) -> None:
        try:
            data = await self.client.request("ollama_unload", model=model)
        except (ConnectionError, FileNotFoundError, OSError) as exc:
            self._append(f"\n⚠ {exc}\n")
            return
        if data.get("ok"):
            self._append(f"\n✓ unloaded {data.get('model')}\n")
            self._spawn(self._refresh_ollama_running())
        else:
            self._append(f"\n⚠ {data.get('error', 'could not unload')}\n")

    async def _localset_menu(self) -> None:
        """The /localset command: add/remove/switch Ollama servers."""
        try:
            info = await self.client.request("ollama_servers")
        except (ConnectionError, FileNotFoundError, OSError) as exc:
            self._append(f"\n⚠ {exc}\n")
            return
        lines = ["\n◆ configured Ollama servers:"]
        if not info.get("servers"):
            lines.append("  (none — add one below)")
        for s in info.get("servers", []):
            mark = "*" if s["name"] == info.get("default") else " "
            model = f"  model {s['model']}" if s.get("model") else ""
            lines.append(f"  {mark} {s['name']:<14} {s['url']}{model}")
        lines += [
            "  add)      add a server (name + url)",
            "  remove)   remove a server",
            "  default)  make a server active",
            "  (blank cancels)",
        ]
        self._append("\n".join(lines) + "\n")
        self._pending = {"kind": "localset_menu"}
        self._choose("Ollama servers", [("add", "Enter Ollama server address"),
                     ("default", "Use an existing server"), ("remove", "Remove a server")], "localset_menu")

    async def _server_picker(self, kind: str) -> None:
        try:
            info = await self.client.request("ollama_servers")
            self._choose("Select server", [(s["name"], f"{s['name']} · {s['url']}")
                         for s in info.get("servers", [])], kind)
        except (ConnectionError, OSError) as exc:
            self._append(f"\n⚠ {exc}\n")

    async def _localset_add(self, name: str, url: str) -> None:
        try:
            data = await self.client.request("ollama_add_server", name=name, url=url)
        except (ConnectionError, FileNotFoundError, OSError) as exc:
            self._append(f"\n⚠ {exc}\n")
            return
        if data.get("ok"):
            self._append(f"\n✓ server '{name}' added/updated\n")
            await self._localset_default(name)
            await self._local_models()
            if self._ollama_models:
                self._choose("Select model on this server", [(str(i), str(m.get("name")))
                             for i, m in enumerate(self._ollama_models, 1)], "local_select")
        else:
            self._append(f"\n⚠ {data.get('error', 'could not add server')}\n")

    async def _localset_remove(self, name: str) -> None:
        try:
            data = await self.client.request("ollama_remove_server", name=name)
        except (ConnectionError, FileNotFoundError, OSError) as exc:
            self._append(f"\n⚠ {exc}\n")
            return
        if data.get("ok"):
            self._append(f"\n✓ server '{name}' removed\n")
            self._spawn(self._refresh_model_label())
        else:
            self._append(f"\n⚠ {data.get('error', 'could not remove server')}\n")

    async def _localset_default(self, name: str) -> None:
        try:
            data = await self.client.request("ollama_set_default", name=name)
        except (ConnectionError, FileNotFoundError, OSError) as exc:
            self._append(f"\n⚠ {exc}\n")
            return
        if data.get("ok"):
            self._append(f"\n✓ active server is now '{name}'\n")
            self.cloud_active = False
            self.thinking = "off"
            self._spawn(self._refresh_model_label())
        else:
            self._append(f"\n⚠ {data.get('error', 'could not set default')}\n")

    async def _model_cmd(self, arg: str) -> None:
        try:
            info = await self.client.request("provider_info", name=self.cloud_provider or None)
        except (ConnectionError, FileNotFoundError, OSError) as exc:
            self._append(f"\n⚠ {exc}\n")
            return
        if not info.get("default"):
            self._append("\n— no cloud provider configured; run /cloud first —\n")
            return
        if not arg:
            self._append(f"\n☁ {info['default']} · model: {info.get('model') or '(unset)'}\n"
                         f"   change it with /model <model-name>\n")
            return
        if arg.isdigit():
            if not 1 <= int(arg) <= len(self._model_options):
                self._append("\n— select a model from /model first —\n")
                return
            arg = self._model_options[int(arg) - 1]
        try:
            res = await self.client.request("set_model", name=info["default"], model=arg)
        except (ConnectionError, FileNotFoundError, OSError) as exc:
            self._append(f"\n⚠ {exc}\n")
            return
        if res.get("ok"):
            self._append(f"\n✓ {info['default']} model set to {res.get('model')}\n")
            self._spawn(self._refresh_model_label())
        else:
            self._append(f"\n⚠ {res.get('error', 'could not set model')}\n")

    async def _ask(self, text: str, provider: str | None = None) -> None:
        # A plain message follows the active route: Ollama by default, the last cloud
        # provider after /switch.
        if provider is None and self.cloud_active and self.cloud_provider:
            provider = self.cloud_provider
        self.busy = True
        self._active = asyncio.current_task()
        self.tokens = self.tools_used = 0
        self._answered = False
        self._work_split = False
        self._had_work = False
        self._work_items = []
        self.usage = {}
        self.streaming = False
        self.agent_name = ""
        self.phase = "thinking"
        self.started = time.monotonic()
        reader = writer = None
        try:
            reader, writer = await asyncio.open_unix_connection(self.client.socket_path)
            req: dict[str, Any] = {"command": "chat", "text": text, "session_id": self.session_id, "cwd": str(Path.cwd()), "effort": self.effort}
            if self.forced_profile:
                req["agent_profile"] = self.forced_profile
            if provider is not None:
                req["provider"] = provider
            if self.private_mode:
                req["private"] = True
            if self.thinking != "off":
                req["thinking"] = self.thinking
            writer.write((json.dumps(req) + "\n").encode())
            await writer.drain()
            while raw := await reader.readline():
                event = json.loads(raw)
                kind = event.get("type")
                if kind == "session":
                    self.session_id = event["session_id"]
                elif kind == "model":
                    self.model_name = event.get("label", self.model_name)
                    if event.get("location") == "cloud":
                        self._open_box()
                        self._bline(f"\u2601 escalated to {event.get('label')}")
                        self._had_work = True
                elif kind == "agent":
                    self.agent_name = event.get("profile", "")
                    self._open_box()
                    self._bline(f"\u25c7 orchestrator \u2192 {event.get('profile','')} agent")
                    self._had_work = True
                    self._work_items.append((f"profile: {event.get('profile','')}", True))
                elif kind == "warming":
                    self.phase = "warming cache (one-off)"
                    self._open_box()
                    self._bline("\u23f3 warming the prompt cache (one-off after a change)")
                    self._had_work = True
                elif kind == "runtime_status":
                    self.phase = "recovering model"
                    self._open_box()
                    self._bline(f"\u26a0 {event.get('text', 'model runtime recovery in progress')}")
                    self._had_work = True
                elif kind == "compaction":
                    self._open_box()
                    self._bline(f"◇ conversation compacted · preserved recent context + {event.get('turns', 0)} earlier turns")
                    self._had_work = True
                    self._work_items.append(("conversation context compacted", True))
                elif kind == "thinking":
                    self.phase = "thinking"
                    self.streaming = False
                elif kind == "token":
                    self._open_box()
                    if self._had_work and not self._work_split:
                        # A clear labelled rule closes the work section (escalation,
                        # orchestrator hand-off, tool output) and opens Kilo's reply, so the
                        # two never blur together inside his box.
                        self._flush_boxed()
                        self._bline("")
                        inner = max(10, self._cw() - 4)
                        label = "\u2500\u2500 reply "
                        self._bline(label + "\u2500" * max(0, inner - len(label)))
                        self._work_split = True
                    self.streaming = True
                    self.tokens += 1
                    self._stream_boxed(event.get("text", ""))
                elif kind == "tool_start":
                    self.tools_used += 1
                    self.phase = f"running {event['name']}"
                    self.streaming = False
                    args = event.get("arguments") or {}
                    detail = ", ".join(f"{k}={str(v)[:32]}" for k, v in list(args.items())[:2])
                    self._open_box()
                    self._flush_boxed()
                    self._bline(f"\u25c8 {event['name']} {detail}")
                    self._had_work = True
                    self._work_items.append((f"{event['name']} {detail}", False))
                elif kind == "tool_end":
                    ok = "✓" if event.get("ok") else "!"
                    self._open_box()
                    self._bline(f"{ok} {event.get('name')} \u00b7 {str(event.get('summary',''))[:90]}")
                    self.phase = "interpreting"
                    if self._work_items:
                        self._work_items[-1] = (self._work_items[-1][0], True)
                elif kind == "error":
                    self._append(f"\n⚠ {event.get('error')}\n")
                elif kind == "permission":
                    allow, remember = await self._ask_permission(event)
                    writer.write((json.dumps({"type": "permission_response", "id": event.get("id"), "allow": allow, "remember": remember}) + "\n").encode())
                    await writer.drain()
                elif kind == "done":
                    if self._answered:
                        self._flush_boxed()
                        self._append(self._rule() + "\n")
                    self.usage = event.get("usage") or {}
                    break
                self.app.invalidate()
        except asyncio.CancelledError:
            self._append("\n[cancelled]\n")
        except (ConnectionError, FileNotFoundError, OSError) as exc:
            self._append(f"\n⚠ daemon unavailable: {exc}\n")
        finally:
            if writer is not None:
                writer.close()
            self.busy = self.streaming = False
            self.phase = ""
            self._append("\n")
            self.app.invalidate()

    def _open_box(self) -> None:
        """Open Kilo's response box exactly once, so every part of his turn — escalation
        notices, agent hand-offs, tool work, and the reply — renders INSIDE his border,
        never floating under the owner's input box."""
        if self._answered:
            return
        self._append("\n" + self._rule("Kilo") + "\n")
        self._answered = True
        self._work_split = False
        self._line_buf = ""

    def _short_model(self) -> str:
        """A compact model label for the status bar so long ids never crowd it."""
        name = self.model_name or (("cloud\u00b7" + self.cloud_provider) if self.cloud_active else "ollama")
        name = name.replace(":free", "")
        if "/" in name:
            name = name.rsplit("/", 1)[-1]
        elif ":" in name and not name.startswith("cloud"):
            name = name.split(":", 1)[-1]
        return (name[:20] + "\u2026") if len(name) > 21 else name

    async def _ask_permission(self, event: dict) -> tuple[bool, bool]:
        """Ask the owner to approve a risky action. Type 1 (yes), 2 (yes, all this
        session) or 3 (no). Times out to a denial so a walked-away prompt fails safe."""
        risk = str(event.get("risk", "?"))
        self._append(
            f"\n\u26a0 approval needed \u2014 {event.get('capability')} [{risk}]\n"
            f"   {event.get('detail', '')}\n"
            f"   1) yes   2) yes, all this session   3) no\n   \u203a "
        )
        self._perm_future = asyncio.get_event_loop().create_future()
        self._pending = {"kind": "permission"}
        self._choose("Approve action", [("1", "Yes, this action"), ("2", "Yes, this session"),
                     ("3", "No")], "permission")
        self._choice_index = 2
        self.app.invalidate()
        try:
            ans = (await asyncio.wait_for(self._perm_future, timeout=280)).strip().lower()
        except (asyncio.TimeoutError, asyncio.CancelledError):
            ans = "3"
        allow = ans in {"1", "2", "y", "yes"}
        remember = ans == "2"
        self._append(f"   \u2192 {'approved' if allow else 'denied'}{' (session)' if remember else ''}\n")
        return allow, remember

    def _bindings(self) -> KeyBindings:
        kb = KeyBindings()

        @kb.add("up", filter=Condition(lambda: bool(self._choice_options)), eager=True)
        def _(event):
            self._choice_index = (self._choice_index - 1) % len(self._choice_options)

        @kb.add("down", filter=Condition(lambda: bool(self._choice_options)), eager=True)
        def _(event):
            self._choice_index = (self._choice_index + 1) % len(self._choice_options)

        @kb.add("enter", filter=Condition(lambda: bool(self._pending)), eager=True)
        def _(event):
            self._accept(self.input.buffer)
            self.input.buffer.reset()

        @kb.add("escape", filter=Condition(lambda: bool(self._pending)), eager=True)
        def _(event):
            self._cancel_pending()

        @kb.add("pageup")
        def _(event):
            self._scroll_to(self.output.window.vertical_scroll - 15)

        @kb.add("pagedown")
        def _(event):
            self._scroll_to(self.output.window.vertical_scroll + 15)

        @kb.add("c-q")
        @kb.add("c-d")
        def _(event):
            event.app.exit()

        @kb.add("c-l")
        def _(event):
            self.output.buffer.set_document(Document("", 0), bypass_readonly=True)

        @kb.add("f2")
        def _(event):
            self.show_panel = not self.show_panel

        @kb.add("c-c")
        def _(event):
            if self._active and not self._active.done():
                self._active.cancel()
            else:
                event.app.exit()

        return kb

    async def _tick(self) -> None:
        """Animate the spinner and refresh status so the interface always feels alive."""
        n = 0
        while True:
            self.spin += 1
            n += 1
            if n % 25 == 0:  # ~ every 2.5s
                try:
                    self.status = await self.client.request("status")
                    # Don't overwrite the cloud model label with the local model name while a
                    # cloud provider is the active route.
                    if not self.cloud_active:
                        self.model_name = str(self.status.get("model") or "Ollama") or "Ollama"
                        self.server_name = str(self.status.get("server") or "")
                except Exception:
                    pass
            if n % 50 == 0 and not self.cloud_active:  # ~ every 5s
                await self._refresh_ollama_running()
            # Always invalidate so the header dot and idle wave keep moving; the rate is
            # modest, so this is cheap even while nothing is happening.
            self.app.invalidate()
            await asyncio.sleep(0.12)

    async def run(self) -> None:
        try:
            self.status = await self.client.request("status")
            self.model_name = str(self.status.get("model") or "Ollama") or "Ollama"
            self.server_name = str(self.status.get("server") or "")
        except Exception:
            pass
        self.app = Application(
            layout=self.layout,
            key_bindings=self._bindings(),
            style=STYLE,
            full_screen=True,
            mouse_support=True,
        )
        self._queue = asyncio.Queue()
        self._worker = asyncio.create_task(self._worker_loop())
        ticker = asyncio.create_task(self._tick())
        self._spawn(self._refresh_ollama_running())
        try:
            await self.app.run_async()
        finally:
            ticker.cancel()
            self._worker.cancel()


def _you(text: str) -> str:
    return f"› {text}"


async def run_full_tui(client: RPCClient) -> bool:
    """Run the full-screen UI. Returns False if it could not start, so the caller can fall
    back to the line-based UI."""
    try:
        await KiloApp(client).run()
        return True
    except Exception:
        return False

from __future__ import annotations

import asyncio
import json
import os
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from .activity import running_processes
from .agent import Agent
from .errors import KiloFrameError
from .memory import MemoryStore
from .resources import ResourceManager
from .runtime import OllamaRuntime
from .security import Risk


class RPCServer:
    def __init__(
        self,
        socket_path: Path,
        agent: Agent,
        runtime: OllamaRuntime,
        resources: ResourceManager,
        memory: MemoryStore,
    ):
        self.socket_path = socket_path
        self.agent = agent
        self.runtime = runtime
        self.resources = resources
        self.memory = memory
        self.server: asyncio.AbstractServer | None = None
        self._clients: set[asyncio.Task[Any]] = set()

    async def start(self) -> None:
        self.socket_path.parent.mkdir(parents=True, exist_ok=True)
        self.socket_path.unlink(missing_ok=True)
        self.server = await asyncio.start_unix_server(
            self._handle, path=self.socket_path
        )
        os.chmod(self.socket_path, 0o660)

    async def close(self) -> None:
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            self.server = None
        clients = [task for task in self._clients if task is not asyncio.current_task()]
        for task in clients:
            task.cancel()
        if clients:
            await asyncio.gather(*clients, return_exceptions=True)
        self.socket_path.unlink(missing_ok=True)

    async def _send(
        self, writer: asyncio.StreamWriter, payload: dict[str, Any]
    ) -> None:
        writer.write(json.dumps(payload, ensure_ascii=False).encode() + b"\n")
        await writer.drain()

    async def _handle(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        task = asyncio.current_task()
        if task is not None:
            self._clients.add(task)
        try:
            raw = await asyncio.wait_for(reader.readline(), timeout=30)
            request = json.loads(raw)
            command = request.get("command")
            if command == "status":
                status = self.runtime.status()
                try:
                    status["healthy"] = await asyncio.wait_for(self.runtime.healthy(), timeout=3)
                except asyncio.TimeoutError:
                    status["healthy"] = False
                status["processes"] = await asyncio.to_thread(running_processes)
                status["memory"] = self.memory.stats()
                mcp = getattr(self.agent.tools, "mcp", None)
                status["mcp"] = mcp.info() if mcp else []
                # Host capacity is runtime data, not invented model metadata.
                status["profile"] = self.resources.profile().to_dict()
                await self._send(writer, {"type": "result", "data": status})
            elif command == "mcp_status":
                mcp = getattr(self.agent.tools, "mcp", None)
                await self._send(writer, {"type": "result", "data": {"servers": mcp.info() if mcp else []}})
            elif command == "doctor":
                from dataclasses import asdict
                from .doctor import run_checks
                checks = await asyncio.to_thread(run_checks, self.agent.settings)
                await self._send(writer, {"type": "result", "data": {
                    "checks": [asdict(check) for check in checks], "uid": os.getuid(),
                }})
            elif command == "resources":
                await self._send(
                    writer,
                    {"type": "result", "data": self.resources.profile().to_dict()},
                )
            elif command == "model_info":
                try:
                    await self._send(
                        writer, {"type": "result", "data": self.runtime.metadata()}
                    )
                except (ConnectionError, OSError) as exc:
                    await self._send(
                        writer, {"type": "error", "error": f"model_info failed: {exc}"}
                    )
            elif command == "ollama_servers":
                await self._send(
                    writer,
                    {"type": "result", "data": self.runtime.config.info()},
                )
            elif command == "ollama_status":
                try:
                    status = self.runtime.status()
                    status["healthy"] = await self.runtime.healthy()
                    status["models"] = await asyncio.to_thread(
                        self.runtime.client().list_models
                    )
                    status["running"] = await asyncio.to_thread(
                        self.runtime.client().running_models
                    )
                    await self._send(writer, {"type": "result", "data": status})
                except Exception as exc:
                    await self._send(
                        writer, {"type": "result", "data": {"ok": False, "error": str(exc)}}
                    )
            elif command == "ollama_models":
                try:
                    await self._send(
                        writer,
                        {
                            "type": "result",
                            "data": await asyncio.to_thread(
                                self.runtime.client().list_models
                            ),
                        },
                    )
                except Exception as exc:
                    await self._send(
                        writer, {"type": "result", "data": {"ok": False, "error": str(exc)}}
                    )
            elif command == "ollama_running":
                try:
                    await self._send(
                        writer,
                        {
                            "type": "result",
                            "data": await asyncio.to_thread(
                                self.runtime.client().running_models
                            ),
                        },
                    )
                except Exception as exc:
                    await self._send(
                        writer, {"type": "result", "data": {"ok": False, "error": str(exc)}}
                    )
            elif command == "ollama_thinking_capability":
                await self._send(
                    writer,
                    {"type": "result", "data": await self.runtime.thinking_capability()},
                )
            elif command == "ollama_pull":
                try:
                    model = str(request.get("model", "")).strip()
                    if not model:
                        raise ValueError("a model name is required")
                    async for status in self.runtime.client().pull(model):
                        await self._send(
                            writer, {"type": "ollama_progress", "status": status}
                        )
                    await self._send(
                        writer, {"type": "result", "data": {"ok": True, "model": model}}
                    )
                except Exception as exc:
                    await self._send(
                        writer, {"type": "result", "data": {"ok": False, "error": str(exc)}}
                    )
            elif command == "ollama_select_model":
                try:
                    model = str(request.get("model", "")).strip()
                    if not model:
                        raise ValueError("a model name is required")
                    # Selection is not a promise that a model exists.  Check the
                    # active server itself so remote storage is represented honestly.
                    installed = await asyncio.to_thread(self.runtime.client().list_models)
                    names = {
                        str(item.get("name") or item.get("model") or "")
                        for item in installed
                        if isinstance(item, dict)
                    }
                    if model not in names:
                        raise ValueError(
                            f"{model!r} is not downloaded on the active Ollama server; use /local pull {model}"
                        )
                    self.runtime.config.set_model(None, model)
                    server = self.runtime.active_server()
                    await self._send(
                        writer,
                        {
                            "type": "result",
                            "data": {
                                "ok": True,
                                "model": model,
                                "server": server.name if server else None,
                            },
                        },
                    )
                except Exception as exc:
                    await self._send(
                        writer, {"type": "result", "data": {"ok": False, "error": str(exc)}}
                    )
            elif command == "ollama_unload":
                try:
                    model = str(request.get("model") or "").strip() or self.runtime.active_model()
                    if not model:
                        raise ValueError("no model selected and none given")
                    await asyncio.to_thread(self.runtime.client().unload, model)
                    await self._send(
                        writer, {"type": "result", "data": {"ok": True, "model": model}}
                    )
                except Exception as exc:
                    await self._send(
                        writer, {"type": "result", "data": {"ok": False, "error": str(exc)}}
                    )
            elif command == "ollama_load":
                try:
                    model = str(request.get("model") or "").strip() or self.runtime.active_model()
                    if not model:
                        raise ValueError("no model selected and none given")
                    await asyncio.to_thread(self.runtime.client().load, model)
                    await self._send(
                        writer, {"type": "result", "data": {"ok": True, "model": model}}
                    )
                except Exception as exc:
                    await self._send(
                        writer, {"type": "result", "data": {"ok": False, "error": str(exc)}}
                    )
            elif command == "ollama_set_options":
                try:
                    options = self.runtime.config.set_options(str(request.get("name", "")), request.get("options", {}))
                    await self._send(writer, {"type": "result", "data": {"ok": True, "options": options}})
                except (ValueError, KiloFrameError) as exc:
                    await self._send(writer, {"type": "result", "data": {"ok": False, "error": str(exc)}})
            elif command == "ollama_add_server":
                try:
                    server = self.runtime.config.add_server(
                        str(request.get("name", "")), str(request.get("url", ""))
                    )
                    await self._send(
                        writer,
                        {
                            "type": "result",
                            "data": {"ok": True, "name": server.name, "url": server.url},
                        },
                    )
                except Exception as exc:
                    await self._send(
                        writer, {"type": "result", "data": {"ok": False, "error": str(exc)}}
                    )
            elif command == "ollama_remove_server":
                try:
                    self.runtime.config.remove_server(str(request.get("name", "")))
                    await self._send(writer, {"type": "result", "data": {"ok": True}})
                except Exception as exc:
                    await self._send(
                        writer, {"type": "result", "data": {"ok": False, "error": str(exc)}}
                    )
            elif command == "ollama_set_default":
                try:
                    self.runtime.config.set_default(str(request.get("name", "")))
                    await self._send(writer, {"type": "result", "data": {"ok": True}})
                except Exception as exc:
                    await self._send(
                        writer, {"type": "result", "data": {"ok": False, "error": str(exc)}}
                    )
            elif command == "sessions":
                await self._send(
                    writer,
                    {
                        "type": "result",
                        "data": {"sessions": self.memory.list_sessions()},
                    },
                )
            elif command == "delete_session":
                sid = str(request.get("session_id", ""))
                await self._send(
                    writer,
                    {"type": "result", "data": {"deleted": self.memory.delete_session(sid)}},
                )
            elif command == "session_history":
                sid = str(request.get("session_id", ""))
                await self._send(
                    writer,
                    {
                        "type": "result",
                        "data": {"messages": self.memory.history(sid, 200)},
                    },
                )
            elif command == "rotate_circuit":
                from . import net

                if not net.tor_available():
                    await self._send(
                        writer,
                        {
                            "type": "result",
                            "data": {"ok": False, "error": "Tor is not available"},
                        },
                    )
                else:
                    ok = await asyncio.to_thread(net.rotate_circuit)
                    ip = await asyncio.to_thread(net.exit_ip) if ok else None
                    await self._send(
                        writer, {"type": "result", "data": {"ok": ok, "exit_ip": ip}}
                    )
            elif command == "tor_status":
                from . import net

                await self._send(
                    writer,
                    {"type": "result", "data": {"available": net.tor_available()}},
                )
            elif command == "provider_models":
                try:
                    models = await asyncio.to_thread(
                        self.agent.providers.list_models,
                        request.get("name"),
                        bool(request.get("only_free", True)),
                    )
                    await self._send(
                        writer,
                        {"type": "result", "data": {"ok": True, "models": models}},
                    )
                except Exception as exc:
                    await self._send(
                        writer,
                        {"type": "result", "data": {"ok": False, "error": str(exc)}},
                    )
            elif command == "provider_info":
                await self._send(
                    writer,
                    {
                        "type": "result",
                        "data": self.agent.providers.info(request.get("name")),
                    },
                )
            elif command == "set_model":
                try:
                    m = self.agent.providers.set_model(
                        str(request.get("name", "")), str(request.get("model", ""))
                    )
                    await self._send(
                        writer, {"type": "result", "data": {"ok": True, "model": m}}
                    )
                except Exception as exc:
                    await self._send(
                        writer,
                        {"type": "result", "data": {"ok": False, "error": str(exc)}},
                    )
            elif command == "providers_catalog":
                from .providers import KNOWN_PROVIDERS

                configured = self.agent.providers.providers()
                known = {
                    n: {"label": v["label"], "model": v["model"]}
                    for n, v in KNOWN_PROVIDERS.items()
                }
                for name, provider in configured.items():
                    if name not in known:
                        known[name] = {
                            "label": f"{name} (custom)",
                            "model": provider.model,
                            "custom": True,
                        }
                await self._send(
                    writer,
                    {
                        "type": "result",
                        "data": {
                            "known": known,
                            "configured": sorted(configured),
                            "default": self.agent.providers.default_name(),
                        },
                    },
                )
            elif command == "configure_provider":
                try:
                    prov = self.agent.providers.configure(
                        str(request.get("name", "")),
                        str(request.get("api_key", "")),
                        request.get("model") or None,
                        request.get("account_id") or None,
                    )
                    await self._send(
                        writer,
                        {
                            "type": "result",
                            "data": {
                                "ok": True,
                                "label": prov.label,
                                "name": prov.name,
                            },
                        },
                    )
                except Exception as exc:
                    await self._send(
                        writer,
                        {"type": "result", "data": {"ok": False, "error": str(exc)}},
                    )
            elif command == "configure_custom_provider":
                try:
                    prov = self.agent.providers.configure_custom(
                        str(request.get("name", "")),
                        str(request.get("base_url", "")),
                        str(request.get("model", "")),
                        str(request.get("api_key", "")),
                    )
                    await self._send(
                        writer,
                        {"type": "result", "data": {"ok": True, "label": prov.label, "name": prov.name}},
                    )
                except Exception as exc:
                    await self._send(
                        writer,
                        {"type": "result", "data": {"ok": False, "error": str(exc)}},
                    )
            elif command == "telegram_config":
                try:
                    path = self.agent.settings.telegram_path
                    config = json.loads(path.read_text()) if path.exists() else {}
                    action = request.get("action", "status")
                    allowed = set(int(x) for x in config.get("allowed_chat_ids", []))
                    if action == "allow":
                        allowed.add(int(request["chat_id"]))
                    elif action == "disallow":
                        allowed.discard(int(request["chat_id"]))
                    elif action == "disable":
                        config["token"] = ""
                    elif action != "status":
                        raise ValueError("unknown Telegram action")
                    if action != "status":
                        config["allowed_chat_ids"] = sorted(allowed)
                        tmp = path.with_suffix(".tmp")
                        tmp.write_text(json.dumps(config, indent=2) + "\n")
                        os.chmod(tmp, 0o600)
                        os.replace(tmp, path)
                    token = str(config.get("token") or "")
                    await self._send(writer, {"type": "result", "data": {
                        "ok": True, "configured": bool(token and token != "PASTE_BOT_TOKEN_HERE"),
                        "allowed_chat_ids": sorted(allowed)}})
                except Exception as exc:
                    await self._send(writer, {"type": "result", "data": {"ok": False, "error": str(exc)}})
            elif command == "set_telegram_token":
                token = str(request.get("token", "")).strip()
                if not token or ":" not in token or len(token) > 256:
                    await self._send(
                        writer,
                        {
                            "type": "result",
                            "data": {
                                "ok": False,
                                "error": "invalid Telegram bot token",
                            },
                        },
                    )
                else:
                    path = self.agent.settings.telegram_path
                    try:
                        current: dict[str, Any] = {}
                        if path.is_file():
                            current = json.loads(path.read_text(encoding="utf-8"))
                        current["token"] = token
                        path.parent.mkdir(parents=True, exist_ok=True)
                        tmp = path.with_suffix(path.suffix + ".tmp")
                        tmp.write_text(
                            json.dumps(current, indent=2) + "\n", encoding="utf-8"
                        )
                        os.chmod(tmp, 0o600)
                        os.replace(tmp, path)
                        await self._send(
                            writer, {"type": "result", "data": {"ok": True}}
                        )
                    except Exception as exc:
                        await self._send(
                            writer,
                            {
                                "type": "result",
                                "data": {"ok": False, "error": str(exc)},
                            },
                        )
            elif command == "chat":

                async def permission(capability: str, detail: str, risk: Risk) -> bool:
                    permission_id = uuid.uuid4().hex
                    await self._send(
                        writer,
                        {
                            "type": "permission",
                            "id": permission_id,
                            "capability": capability,
                            "detail": detail,
                            "risk": risk.value,
                        },
                    )
                    raw_answer = await asyncio.wait_for(reader.readline(), timeout=300)
                    answer = json.loads(raw_answer)
                    if (
                        answer.get("type") != "permission_response"
                        or answer.get("id") != permission_id
                    ):
                        return False
                    allow = bool(answer.get("allow"))
                    # "yes for this session": grant this capability for the daemon's lifetime
                    # (not persisted to disk), so the same kind of action stops re-prompting.
                    if allow and answer.get("remember"):
                        self.agent.tools.permissions.rules[capability] = "allow"
                    return allow

                run = self.agent.run(
                    str(request.get("text", "")),
                    request.get("session_id"),
                    Path(request.get("cwd") or self.agent.settings.home),
                    bool(request.get("remote", False)),
                    permission,
                    request.get("provider"),
                    request.get("effort"),
                    request.get("agent_profile"),
                    bool(request.get("private", False)),
                    bool(request.get("fresh", False)),
                    request.get("thinking"),
                )
                pending: asyncio.Task[dict[str, Any]] | None = None
                try:
                    # A peer can disappear while inference is silent for minutes. Merely
                    # waiting for the next model event cannot notice that EOF, so race each
                    # event against the socket state and close the generator promptly.
                    while True:
                        pending = asyncio.create_task(anext(run))
                        while not pending.done():
                            await asyncio.wait({pending}, timeout=0.25)
                            if reader.at_eof() or writer.is_closing():
                                pending.cancel()
                                await asyncio.gather(pending, return_exceptions=True)
                                pending = None
                                return
                        try:
                            event = pending.result()
                        except StopAsyncIteration:
                            pending = None
                            break
                        pending = None
                        await self._send(writer, event)
                finally:
                    if pending is not None and not pending.done():
                        pending.cancel()
                        await asyncio.gather(pending, return_exceptions=True)
                    await run.aclose()
            else:
                await self._send(
                    writer, {"type": "error", "error": f"unknown command: {command}"}
                )
        except Exception as exc:
            try:
                await self._send(writer, {"type": "error", "error": str(exc)})
            except Exception:
                pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except (ConnectionError, OSError):
                pass
            if task is not None:
                self._clients.discard(task)


class RPCClient:
    def __init__(self, socket_path: Path):
        self.socket_path = socket_path

    async def request(self, command: str, **kwargs: Any) -> dict[str, Any]:
        async for event in self.stream(command, **kwargs):
            if event.get("type") == "result":
                return event.get("data", {})
            if event.get("type") == "error":
                raise KiloFrameError(event.get("error", "unknown daemon error"))
        return {}

    async def stream(
        self, command: str, **kwargs: Any
    ) -> AsyncIterator[dict[str, Any]]:
        reader, writer = await asyncio.open_unix_connection(self.socket_path)
        writer.write(json.dumps({"command": command, **kwargs}).encode() + b"\n")
        await writer.drain()
        try:
            while raw := await reader.readline():
                yield json.loads(raw)
        finally:
            writer.close()
            await writer.wait_closed()

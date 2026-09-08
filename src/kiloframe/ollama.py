"""Ollama local/remote server integration.

KiloFrame's local and private model path is Ollama: a server — local or remote — that
owns its own model storage and runtime state. This module implements the client side of
Ollama's documented HTTP API and the small amount of configuration the framework needs
to make it comfortable to use.

The endpoints used are the ones Ollama documents:

    GET  /api/tags    -> models downloaded on the server
    GET  /api/ps      -> models currently loaded/running
    GET  /api/version -> server version
    POST /api/show    -> model details / capabilities
    POST /api/pull    -> download a model (streaming status)
    POST /api/chat    -> chat completion (streaming), native tools, ``think``
    POST /api/generate (keep_alive=0) -> unload a model

A remote server owns its model storage and runtime state: a model that is running on a
remote host may not exist on this machine, and a model that is downloaded there is not
downloaded here. KiloFrame never assumes otherwise; it always asks the server it is
connected to.
"""

from __future__ import annotations

import asyncio
import json
import logging
import urllib.error
import urllib.request
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from .errors import KiloFrameError


log = logging.getLogger("kiloframe.ollama")

DEFAULT_LOCAL_URL = "http://127.0.0.1:11434"
USER_AGENT = "KiloFrame/1.0 (+https://github.com/0v3r51ght/kiloframe)"


class OllamaError(KiloFrameError):
    """The Ollama server could not fulfil a request."""


@dataclass(frozen=True, slots=True)
class OllamaServer:
    name: str
    url: str
    enabled: bool = True
    model: str = ""  # model selected for use on this server

    @classmethod
    def from_dict(cls, name: str, raw: dict[str, Any]) -> "OllamaServer":
        url = str(raw.get("url", DEFAULT_LOCAL_URL)).strip().rstrip("/")
        if not url.startswith(("http://", "https://")):
            raise ValueError(f"server {name}: url must be http(s)")
        return cls(
            name=name,
            url=url,
            enabled=bool(raw.get("enabled", True)),
            model=str(raw.get("model", "")).strip(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {"url": self.url, "enabled": self.enabled, "model": self.model}


class OllamaConfig:
    """Owns ``ollama.json``: the configured servers and the active server/model.

    Layout::

        {
          "default": "local",                       # active server name
          "servers": {
            "local": {"url": "http://127.0.0.1:11434", "model": "llama3.2"},
            "office": {"url": "http://10.0.0.5:11434", "model": "qwen2.5:14b"}
          }
        }

    The selected model is stored per server because each server owns its own model
    storage: the model chosen on one host has no meaning on another.
    """

    def __init__(self, path: Any):
        self.path = path

    def _raw(self) -> dict[str, Any]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (OSError, json.JSONDecodeError) as exc:
            log.warning("ollama config unreadable (%s); using defaults", exc)
            return {}

    def _write(self, raw: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")
        tmp.replace(self.path)

    def servers(self) -> dict[str, OllamaServer]:
        raw = self._raw()
        found: dict[str, OllamaServer] = {}
        for name, entry in (raw.get("servers") or {}).items():
            if not isinstance(entry, dict):
                continue
            try:
                server = OllamaServer.from_dict(str(name), entry)
            except ValueError as exc:
                log.warning("ignoring ollama server: %s", exc)
                continue
            if server.enabled:
                found[str(name)] = server
        return found

    def default_name(self) -> str | None:
        available = self.servers()
        preferred = str(self._raw().get("default", "")).strip()
        if preferred and preferred in available:
            return preferred
        return next(iter(available), None)

    def active(self) -> OllamaServer | None:
        name = self.default_name()
        if name is None:
            return None
        return self.servers()[name]

    def client(self, server: OllamaServer | None = None) -> "OllamaClient":
        target = server or self.active()
        if target is None:
            raise OllamaError("no Ollama server is configured; run /localset to add one")
        return OllamaClient(target.url)

    def add_server(self, name: str, url: str) -> OllamaServer:
        """Add or update a server. The first server added becomes the default."""
        name = name.strip()
        if not name:
            raise OllamaError("a server needs a name")
        raw = self._raw()
        servers = raw.setdefault("servers", {})
        server = OllamaServer.from_dict(name, {
            "url": url, "enabled": True, "model": servers.get(name, {}).get("model", "")
        })
        servers[name] = server.to_dict()
        if not raw.get("default"):
            raw["default"] = name
        self._write(raw)
        return OllamaServer.from_dict(name, servers[name])

    def remove_server(self, name: str) -> None:
        raw = self._raw()
        servers = raw.setdefault("servers", {})
        if name not in servers:
            raise OllamaError(f"unknown server: {name}")
        del servers[name]
        if raw.get("default") == name:
            raw["default"] = next(iter(servers), "")
        self._write(raw)

    def set_default(self, name: str) -> None:
        if name not in self.servers():
            raise OllamaError(f"unknown server: {name}")
        raw = self._raw()
        raw["default"] = name
        self._write(raw)

    def set_model(self, name: str | None, model: str) -> None:
        """Record the model selected for a server (default: the active server)."""
        raw = self._raw()
        servers = raw.setdefault("servers", {})
        target = name or raw.get("default")
        if not target or target not in servers:
            raise OllamaError("no active Ollama server to select a model for")
        entry = servers[target]
        entry["model"] = model.strip()
        self._write(raw)

    def info(self) -> dict[str, Any]:
        active = self.active()
        return {
            "default": active.name if active else None,
            "model": active.model if active else "",
            "servers": [
                {"name": s.name, "url": s.url, "model": s.model}
                for s in self.servers().values()
            ],
        }


class OllamaClient:
    """Thin HTTP client for one Ollama server."""

    def __init__(self, url: str, timeout: int = 30):
        self.url = url.rstrip("/")
        self.timeout = timeout

    def _get(self, path: str) -> dict[str, Any]:
        req = urllib.request.Request(
            self.url + path, headers={"Accept": "application/json", "User-Agent": USER_AGENT}
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return json.load(r)
        except urllib.error.URLError as exc:
            raise OllamaError(f"Ollama server unreachable at {self.url}: {exc.reason}") from exc

    def _post(self, path: str, data: dict[str, Any], timeout: int | None = None) -> dict[str, Any]:
        req = urllib.request.Request(
            self.url + path,
            data=json.dumps(data).encode(),
            headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout or self.timeout) as r:
                return json.load(r)
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = json.loads(exc.read()).get("error", "")
            except Exception:
                detail = ""
            finally:
                exc.close()
            raise OllamaError(f"Ollama server refused {path} ({exc.code}): {detail or exc.reason}") from exc
        except urllib.error.URLError as exc:
            raise OllamaError(f"Ollama server unreachable at {self.url}: {exc.reason}") from exc

    def version(self) -> str:
        version = self._get("/api/version").get("version")
        if not isinstance(version, str) or not version:
            raise OllamaError("server did not return an Ollama version")
        return version

    def list_models(self) -> list[dict[str, Any]]:
        data = self._get("/api/tags")
        models = data.get("models") or []
        return [m for m in models if isinstance(m, dict)]

    def running_models(self) -> list[dict[str, Any]]:
        data = self._get("/api/ps")
        models = data.get("models") or []
        return [m for m in models if isinstance(m, dict)]

    def show(self, model: str) -> dict[str, Any]:
        return self._post("/api/show", {"model": model})

    def pull(self, model: str) -> AsyncIterator[str]:
        """Download a model, yielding progress status strings as they arrive."""
        req = urllib.request.Request(
            self.url + "/api/pull",
            data=json.dumps({"model": model, "stream": True}).encode(),
            headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
        )

        async def _stream() -> AsyncIterator[str]:
            try:
                response = await asyncio.to_thread(
                    urllib.request.urlopen, req, timeout=self.timeout
                )
            except urllib.error.HTTPError as exc:
                detail = ""
                try:
                    detail = json.loads(exc.read()).get("error", "")
                except Exception:
                    detail = ""
                raise OllamaError(f"pull {model} refused ({exc.code}): {detail or exc.reason}") from exc
            except urllib.error.URLError as exc:
                raise OllamaError(f"Ollama server unreachable at {self.url}: {exc.reason}") from exc
            try:
                while True:
                    raw = await asyncio.to_thread(response.readline)
                    if not raw:
                        raise OllamaError("model pull ended without a success response")
                    line = raw.decode("utf-8", "replace").strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    status = str(event.get("status", ""))
                    if event.get("error"):
                        raise OllamaError(str(event["error"]))
                    if status:
                        if event.get("total") and event.get("completed") is not None:
                            total = int(event["total"])
                            completed = int(event["completed"])
                            pct = min(100, completed * 100 // max(1, total))
                            yield f"{status} {pct}%"
                        else:
                            yield status
                        if status == "success":
                            return
            finally:
                response.close()

        return _stream()

    def unload(self, model: str) -> None:
        self._post("/api/generate", {"model": model, "keep_alive": 0})

    def load(self, model: str, keep_alive: str = "5m") -> None:
        """Ask Ollama to preload a downloaded model without generating an answer."""
        # Loading multi-gigabyte models can take substantially longer than a normal
        # status or inference request on a remote/CPU-only Ollama host.
        self._post("/api/generate", {
            "model": model,
            "prompt": "",
            "stream": False,
            "keep_alive": keep_alive,
        }, timeout=max(self.timeout, 180))

    async def chat_stream(
        self,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int | None = None,
        temperature: float = 0.4,
        top_p: float = 0.9,
        num_ctx: int | None = None,
        think: str | bool | None = None,
        keep_alive: str = "5m",
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream a native Ollama chat completion, translated to the framework's
        OpenAI-compatible event shape (``delta`` with ``content``/``tool_calls``, and a
        final ``usage``) so the agent loop and cloud providers stay unified.

        ``think`` is forwarded only when the caller supplied a level; Ollama applies it to
        thinking-capable models and ignores it elsewhere, which is the honest behaviour.
        """
        native_messages = []
        for original in messages:
            message = dict(original)
            message["content"] = message.get("content") or ""
            if message.get("role") == "tool":
                message["tool_name"] = message.pop("name", message.get("tool_name", ""))
                message.pop("tool_call_id", None)
            if message.get("tool_calls"):
                native_calls = []
                for call in message["tool_calls"]:
                    function = dict(call["function"])
                    if isinstance(function.get("arguments"), str):
                        function["arguments"] = json.loads(function["arguments"])
                    native_calls.append({"function": function})
                message["tool_calls"] = native_calls
            native_messages.append(message)
        payload: dict[str, Any] = {
            "model": model,
            "messages": native_messages,
            "stream": True,
            "keep_alive": keep_alive,
        }
        if tools:
            payload["tools"] = tools
        options: dict[str, Any] = {"temperature": temperature, "top_p": top_p}
        if num_ctx is not None:
            options["num_ctx"] = num_ctx
        if max_tokens is not None:
            options["num_predict"] = max_tokens
        payload["options"] = options
        # Reasoning models may default to a long hidden trace. Native thinking is
        # opt-in through /thinking, so ordinary requests return visible output promptly.
        payload["think"] = think if think else False

        def open_request():
            return urllib.request.urlopen(
                urllib.request.Request(
                    self.url + "/api/chat",
                    data=json.dumps(payload).encode(),
                    headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
                ),
                timeout=2400,
            )

        try:
            response = await asyncio.to_thread(open_request)
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = json.loads(exc.read()).get("error", "")
            except Exception:
                detail = ""
            finally:
                exc.close()
            failure = str(detail or exc.reason)
            # Ollama exposes num_gpu as an official request option. When its automatic
            # GPU placement returns a CUDA OOM, retry this request once on CPU rather
            # than claiming the configured model is unavailable.
            if exc.code == 500 and "out of memory" in failure.lower() and "cuda" in failure.lower():
                options["num_gpu"] = 0
                yield {"status": "GPU memory exhausted; retrying the selected model on CPU"}
                try:
                    response = await asyncio.to_thread(open_request)
                except urllib.error.HTTPError as retry_exc:
                    retry_detail = ""
                    try:
                        retry_detail = json.loads(retry_exc.read()).get("error", "")
                    except Exception:
                        retry_detail = ""
                    finally:
                        retry_exc.close()
                    raise OllamaError(
                        f"inference request refused ({retry_exc.code}) after CPU fallback: "
                        f"{retry_detail or retry_exc.reason}"
                    ) from retry_exc
                except urllib.error.URLError as retry_exc:
                    raise OllamaError(f"Ollama server unreachable at {self.url}: {retry_exc.reason}") from retry_exc
            else:
                raise OllamaError(f"inference request refused ({exc.code}): {failure}") from exc
        except urllib.error.URLError as exc:
            raise OllamaError(f"Ollama server unreachable at {self.url}: {exc.reason}") from exc

        tool_index = 0
        try:
            while True:
                raw = await asyncio.to_thread(response.readline)
                if not raw:
                    raise OllamaError("chat stream ended without a completion response")
                line = raw.decode("utf-8", "replace").strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("error"):
                    raise OllamaError(str(event["error"]))
                message = event.get("message") or {}
                content = message.get("content")
                if content:
                    yield {"delta": {"content": str(content)}}
                for call in message.get("tool_calls") or []:
                    function = call.get("function") or {}
                    arguments = function.get("arguments", {})
                    if not isinstance(arguments, str):
                        arguments = json.dumps(arguments, ensure_ascii=False)
                    yield {
                        "delta": {
                            "tool_calls": [
                                {
                                    "index": tool_index,
                                    "id": "call-" + uuid.uuid4().hex,
                                    "function": {
                                        "name": str(function.get("name") or ""),
                                        "arguments": arguments,
                                    },
                                }
                            ]
                        }
                    }
                    tool_index += 1
                if event.get("done"):
                    prompt_tokens = int(event.get("prompt_eval_count") or 0)
                    completion_tokens = int(event.get("eval_count") or 0)
                    done_reason = str(event.get("done_reason") or "stop")
                    finish_reason = "length" if done_reason == "length" else "stop"
                    yield {
                        "usage": {
                            "prompt_tokens": prompt_tokens,
                            "completion_tokens": completion_tokens,
                            "total_tokens": prompt_tokens + completion_tokens,
                        },
                        "finish_reason": finish_reason,
                    }
                    return
        finally:
            response.close()

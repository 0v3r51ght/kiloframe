from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from typing import Any

from .config import Settings
from .errors import ModelUnavailable, RuntimeUnavailable
from .ollama import OllamaClient, OllamaConfig, OllamaError, OllamaServer


class OllamaRuntime:
    """KiloFrame's local/private model runtime, backed by an Ollama server.

    Ollama owns the model process, its storage and its runtime state, so this class owns
    nothing to spawn or stop. It connects to the configured server (local or remote) and
    streams completions from the model selected for that server.
    """

    def __init__(self, settings: Settings, config: OllamaConfig):
        self.settings = settings
        self.config = config
        self.started_at: float | None = None
        # No llama.cpp cache to warm; kept so callers that probe ``warming`` see a stable
        # false rather than an attribute error.
        self.warming = False
        self.cache_restored = False

    def active_server(self) -> OllamaServer | None:
        return self.config.active()

    def active_model(self) -> str:
        server = self.active_server()
        return server.model if server else ""

    def client(self) -> OllamaClient:
        return self.config.client()

    async def start(self, timeout: float = 30.0) -> None:
        """Verify the active server is reachable before declaring the runtime ready."""
        if self.active_server() is None:
            raise ModelUnavailable("no Ollama server is configured; run /localset to add one")
        try:
            await asyncio.to_thread(self.client().version)
        except OllamaError as exc:
            raise RuntimeUnavailable(str(exc)) from exc
        self.started_at = time.monotonic()

    async def healthy(self) -> bool:
        if self.active_server() is None:
            return False
        try:
            await asyncio.to_thread(self.client().version)
            return True
        except (OllamaError, OSError):
            return False

    async def ensure_ready(self) -> None:
        """Raise if the server is unreachable, so the agent reports a real failure."""
        if not await self.healthy():
            server = self.active_server()
            where = server.url if server else "no server configured"
            raise RuntimeUnavailable(f"Ollama server is not reachable ({where})")

    async def stop(self) -> None:
        # Ollama is an external service; KiloFrame does not own its process.
        return

    async def chat_stream(self, payload: dict[str, Any]) -> AsyncIterator[dict[str, Any]]:
        """Stream from the selected model in the framework's OpenAI-compatible event shape.

        The agent supplies ``messages``, ``tools``, ``max_tokens``, ``temperature``,
        ``top_p`` and an optional ``think`` level; everything else is Ollama's concern.
        """
        model = self.active_model()
        if not model:
            raise ModelUnavailable("no model is selected on this Ollama server; use /local to pick one")
        think = payload.get("think")
        if think not in {"low", "medium", "high", "max"}:
            think = None
        async for event in self.client().chat_stream(
            model=model,
            messages=payload.get("messages") or [],
            tools=payload.get("tools"),
            max_tokens=payload.get("max_tokens"),
            temperature=float(payload.get("temperature", 0.4)),
            top_p=float(payload.get("top_p", 0.9)),
            think=think,
        ):
            yield event

    def metadata(self) -> dict[str, Any]:
        """Model info for ``kiloframe model-info``, without Ollama's verbose template."""
        server = self.active_server()
        return {
            "model_alias": self.active_model(),
            "server": server.url if server else None,
            "server_name": server.name if server else None,
            "sleeping": False,
        }

    def status(self) -> dict[str, Any]:
        server = self.active_server()
        return {
            "running": server is not None,
            "pid": None,
            "healthy": None,
            "uptime_seconds": int(time.monotonic() - self.started_at) if self.started_at else 0,
            "model": self.active_model(),
            "server": server.url if server else None,
            "server_name": server.name if server else None,
            "warming": self.warming,
            "profile": None,
        }

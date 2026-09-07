from __future__ import annotations

import json
import os
import pwd
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def _env_path(name: str, default: str) -> Path:
    return Path(os.environ.get(name, default)).expanduser()


def current_home() -> Path:
    return Path(pwd.getpwuid(os.getuid()).pw_dir)


@dataclass(slots=True)
class Settings:
    data_dir: Path = field(default_factory=lambda: _env_path("KILOFRAME_DATA_DIR", "/var/lib/kiloframe"))
    config_dir: Path = field(default_factory=lambda: _env_path("KILOFRAME_CONFIG_DIR", "/etc/kiloframe"))
    runtime_dir: Path = field(default_factory=lambda: _env_path("KILOFRAME_RUNTIME_DIR", "/run/kiloframe"))
    log_dir: Path = field(default_factory=lambda: _env_path("KILOFRAME_LOG_DIR", "/var/log/kiloframe"))
    max_agent_steps: int = 60
    max_output_tokens: int = 1536
    command_timeout: int = 120
    # Bytes captured from a subprocess; what actually reaches the model is bounded
    # separately by max_tool_result_tokens, because bytes are a poor proxy for context
    # cost -- dense output tokenises at about two characters per token.
    max_tool_output: int = 64 * 1024
    # Token allowance for a single tool result in the prompt. Kept well under the
    # context window so a large result cannot displace the conversation.
    max_tool_result_tokens: int = 900
    # Allowance for replayed conversation, so old turns cannot crowd out the current
    # task or the tool results it depends on.
    max_history_tokens: int = 1800
    # A conservative default avoids an Ollama GPU OOM from an oversized KV cache.
    # Operators can raise it deliberately after checking their server capacity.
    ollama_context_tokens: int = field(
        default_factory=lambda: int(os.environ.get("KILOFRAME_OLLAMA_CONTEXT_TOKENS", "2048"))
    )
    max_read_bytes: int = 2 * 1024 * 1024
    memory_message_limit: int = 10_000
    memory_fact_limit: int = 2_000
    memory_skill_limit: int = 200
    reserve_memory_mb: int = 640
    home: Path = field(default_factory=current_home)

    @property
    def database_path(self) -> Path:
        return self.data_dir / "memory.sqlite3"

    @property
    def socket_path(self) -> Path:
        return self.runtime_dir / "kiloframe.sock"

    @property
    def policy_path(self) -> Path:
        return self.config_dir / "policy.json"

    @property
    def telegram_path(self) -> Path:
        return self.config_dir / "telegram.json"

    @property
    def mcp_path(self) -> Path:
        return self.config_dir / "mcp.json"

    @property
    def providers_path(self) -> Path:
        return self.config_dir / "providers.json"

    @property
    def ollama_path(self) -> Path:
        return self.config_dir / "ollama.json"

    @property
    def allowed_roots(self) -> tuple[Path, ...]:
        return (self.home.resolve(), Path("/tmp").resolve())

    def ensure_user_dirs(self) -> None:
        for path in (self.data_dir, self.runtime_dir, self.log_dir):
            path.mkdir(parents=True, exist_ok=True)

    def load_json(self, path: Path, default: Any) -> Any:
        try:
            with path.open("r", encoding="utf-8") as handle:
                return json.load(handle)
        except FileNotFoundError:
            return default

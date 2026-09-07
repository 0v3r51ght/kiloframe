"""Serena integration for KiloFrame.

Serena provides IDE-like semantic code tools via MCP. This module configures
the Serena MCP server when available and provides fallback tool implementations.
"""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


class SerenaConfig:
    """Manages Serena MCP server configuration."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.config_path = project_root / ".serena"
        self.enabled = False
        self.server_ready = False

    def check_installation(self) -> bool:
        """Check if Serena is installed and available."""
        try:
            result = subprocess.run(
                ["python", "-m", "serena", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def setup(self) -> bool:
        """Set up Serena MCP configuration for the project."""
        if not self.check_installation():
            log.info("Serena not installed; skipping MCP configuration")
            return False

        # Create .serena directory
        self.config_path.mkdir(exist_ok=True)

        # Write server configuration
        server_config = {
            "name": "serena",
            "command": "python",
            "args": ["-m", "serena", "server"],
            "enabled": True,
        }

        mcp_config_path = self.project_root / ".serena" / "mcp.json"
        mcp_config_path.write_text(json.dumps({"servers": {"serena": server_config}}, indent=2))

        self.enabled = True
        self.server_ready = True
        log.info("Serena MCP configured successfully")
        return True

    def get_mcp_config(self) -> dict[str, Any] | None:
        """Get the MCP configuration for Serena."""
        if not self.enabled:
            return None

        return {
            "servers": {
                "serena": {
                    "command": "python",
                    "args": ["-m", "serena", "server"],
                    "enabled": True,
                }
            }
        }


class SerenaTools:
    """Serena code navigation tools for KiloFrame."""

    def __init__(self, config: SerenaConfig):
        self.config = config
        self.available = config.enabled

    async def find_symbol(
        self, name: str, relative_path: str | None = None
    ) -> list[dict[str, Any]]:
        """Find symbols by name."""
        if not self.available:
            return []

        # Use Serena's LSP-based symbol finding
        cmd = ["python", "-m", "serena", "find-symbol", "--name", name]
        if relative_path:
            cmd.extend(["--path", relative_path])

        try:
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await result.communicate()
            return json.loads(stdout.decode())
        except Exception as exc:
            log.warning("Serena find_symbol failed: %s", exc)
            return []

    async def find_references(self, name_path: str, relative_path: str) -> list[dict[str, Any]]:
        """Find all references to a symbol."""
        if not self.available:
            return []

        cmd = ["python", "-m", "serena", "find-references", name_path, "--path", relative_path]

        try:
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await result.communicate()
            return json.loads(stdout.decode())
        except Exception as exc:
            log.warning("Serena find_references failed: %s", exc)
            return []

    async def rename_symbol(self, name_path: str, new_name: str, relative_path: str) -> bool:
        """Rename a symbol across the codebase."""
        if not self.available:
            return False

        cmd = ["python", "-m", "serena", "rename-symbol", name_path, new_name, "--path", relative_path]

        try:
            result = await asyncio.create_subprocess_exec(*cmd)
            await result.communicate()
            return result.returncode == 0
        except Exception as exc:
            log.warning("Serena rename_symbol failed: %s", exc)
            return False

    def list_tools(self) -> list[dict[str, Any]]:
        """List available Serena tools."""
        if not self.available:
            return []

        return [
            {
                "type": "function",
                "function": {
                    "name": "serena_find_symbol",
                    "description": "Find symbols by name using semantic analysis",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "Symbol name to find"},
                            "relative_path": {"type": "string", "description": "Optional path to search in"},
                        },
                        "required": ["name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "serena_find_references",
                    "description": "Find all references to a symbol",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name_path": {"type": "string", "description": "Full name path of symbol"},
                            "relative_path": {"type": "string", "description": "Path to file containing symbol"},
                        },
                        "required": ["name_path", "relative_path"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "serena_rename_symbol",
                    "description": "Rename a symbol across the codebase",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name_path": {"type": "string", "description": "Full name path of symbol"},
                            "new_name": {"type": "string", "description": "New name for the symbol"},
                            "relative_path": {"type": "string", "description": "Path to file containing symbol"},
                        },
                        "required": ["name_path", "new_name", "relative_path"],
                    },
                },
            },
        ]

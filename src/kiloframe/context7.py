"""Context7 integration for KiloFrame.

Context7 provides up-to-date library documentation lookup. This module
configures the Context7 CLI and provides documentation fetching capabilities.
"""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
from typing import Any

log = logging.getLogger(__name__)


class Context7Config:
    """Manages Context7 configuration."""

    def __init__(self):
        self.api_key: str | None = None
        self.enabled = False

    def check_installation(self) -> bool:
        """Check if Context7 CLI is installed."""
        try:
            result = subprocess.run(
                ["ctx7", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def setup(self) -> bool:
        """Set up Context7 CLI."""
        if not self.check_installation():
            log.info("Context7 CLI not installed; run: npm install -g ctx7")
            return False

        self.enabled = True
        log.info("Context7 CLI available")
        return True

    def get_mcp_config(self) -> dict[str, Any] | None:
        """Get MCP configuration for Context7."""
        if not self.enabled:
            return None

        return {
            "servers": {
                "context7": {
                    "command": "npx",
                    "args": ["-y", "@upstash/context7-mcp"],
                    "enabled": True,
                    "env": {
                        "CONTEXT7_API_KEY": self.api_key or "",
                    },
                }
            }
        }


class Context7Client:
    """Client for Context7 documentation lookup."""

    def __init__(self, config: Context7Config):
        self.config = config
        self.available = config.enabled

    async def resolve_library_id(self, library_name: str, query: str) -> dict[str, Any] | None:
        """Resolve a library name to a Context7 library ID."""
        if not self.available:
            return None

        cmd = ["ctx7", "resolve", library_name, "--query", query]

        try:
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await result.communicate()

            if result.returncode != 0:
                return None

            return json.loads(stdout.decode())
        except Exception as exc:
            log.warning("Context7 resolve_library_id failed: %s", exc)
            return None

    async def query_docs(self, library_id: str, query: str) -> str | None:
        """Query documentation for a library."""
        if not self.available:
            return None

        cmd = ["ctx7", "docs", library_id, "--query", query]

        try:
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await result.communicate()

            if result.returncode != 0:
                return None

            return stdout.decode().strip()
        except Exception as exc:
            log.warning("Context7 query_docs failed: %s", exc)
            return None

    def list_tools(self) -> list[dict[str, Any]]:
        """List available Context7 tools."""
        if not self.available:
            return []

        return [
            {
                "type": "function",
                "function": {
                    "name": "context7_resolve_library_id",
                    "description": "Resolve a library name to a Context7 library ID",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "library_name": {"type": "string", "description": "Name of the library"},
                            "query": {"type": "string", "description": "What to look up"},
                        },
                        "required": ["library_name", "query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "context7_query_docs",
                    "description": "Query documentation for a library",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "library_id": {"type": "string", "description": "Context7 library ID"},
                            "query": {"type": "string", "description": "Documentation query"},
                        },
                        "required": ["library_id", "query"],
                    },
                },
            },
        ]

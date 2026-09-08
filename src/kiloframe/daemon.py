from __future__ import annotations

import asyncio
import logging
import os
import signal

from .agent import Agent
from .config import Settings
from .mcp import MCPRegistry
from .memory import MemoryStore
from .ollama import OllamaConfig
from .providers import ProviderRegistry
from .resources import ResourceManager
from .rpc import RPCServer
from .runtime import OllamaRuntime
from .security import PermissionManager
from .skills import seed_preconfigured_skills
from .telegram import TelegramBridge
from .tools import ToolRegistry


async def serve() -> None:
    settings = Settings()
    settings.ensure_user_dirs()
    pid_path = settings.runtime_dir / "kiloframe.pid"
    pid_path.write_text(f"{os.getpid()}\n", encoding="ascii")
    logging.basicConfig(
        filename=settings.log_dir / "kiloframe.log",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    log = logging.getLogger("kiloframe")
    memory = MemoryStore(settings.database_path, settings.memory_message_limit, settings.memory_fact_limit, settings.memory_skill_limit)
    memory.save_skill("verified-mathematics", "when solving equations, calculations or quantitative questions", "Define variables and units; solve symbolically; verify with an independent safe computation; check dimensions, signs, edge cases and rounding; state assumptions and precision.")
    memory.save_skill("engineering-design-review", "when designing or analysing a mechanical, electrical, civil, chemical, aerospace or other engineered system", "Extract requirements and constraints; identify standards and safety factors; state assumptions; calculate or simulate; verify critical values; document risks, tests, acceptance criteria and rollback using authoritative sources.")
    seed_preconfigured_skills(memory, settings)
    resources = ResourceManager(settings)
    permissions = PermissionManager(settings.policy_path)
    mcp = MCPRegistry(settings.mcp_path)
    tools = ToolRegistry(settings, memory, permissions, mcp)
    ollama = OllamaConfig(settings.ollama_path)
    runtime = OllamaRuntime(settings, ollama)
    providers = ProviderRegistry(settings.providers_path)
    agent = Agent(settings, runtime, memory, tools, providers)
    rpc = RPCServer(settings.socket_path, agent, runtime, resources, memory)
    telegram = TelegramBridge(settings.telegram_path, agent)
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for name in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(name, stop_event.set)

    telegram_task: asyncio.Task[None] | None = None
    mcp_task: asyncio.Task[None] | None = None

    try:
        log.info("verifying Ollama connectivity")
        try:
            await runtime.start()
        except Exception as exc:
            # KiloFrame remains usable for cloud providers even when no Ollama server is
            # configured or reachable; only the local/private route is affected.
            log.warning("Ollama not available at startup (%s); local/private route is down", exc)
        # The core TUI must be available even if an optional/integration server is slow,
        # absent, or downloading its own package. Start the RPC socket first; MCP tools
        # join the registry in the background and report their real availability later.
        await rpc.start()
        mcp_task = asyncio.create_task(mcp.start(), name="mcp-startup")
        telegram_task = asyncio.create_task(telegram.run(), name="telegram-bridge")
        log.info("ready on %s", settings.socket_path)
        await stop_event.wait()
    finally:
        telegram.stop()
        tasks = [task for task in (telegram_task, mcp_task) if task]
        for task in tasks:
            task.cancel()
        await rpc.close()
        await runtime.stop()
        await mcp.stop()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        memory.close()
        try:
            if pid_path.read_text(encoding="ascii").strip() == str(os.getpid()):
                pid_path.unlink()
        except FileNotFoundError:
            pass
        log.info("stopped cleanly")


def main() -> None:
    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

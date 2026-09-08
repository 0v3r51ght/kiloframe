from __future__ import annotations

import argparse
import asyncio
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from . import __version__
from .config import Settings
from .doctor import Check, run_checks
from .errors import KiloFrameError
from .resources import ResourceManager
from .rpc import RPCClient
from .theme import BOLD, RED
from .tui import DIM, GREEN, RESET, YELLOW, TerminalUI


def json_print(value: Any) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False))


def _duration(seconds: int | float) -> str:
    total = max(0, int(seconds))
    days, total = divmod(total, 86400)
    hours, total = divmod(total, 3600)
    minutes, secs = divmod(total, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours or days:
        parts.append(f"{hours}h")
    if minutes or hours or days:
        parts.append(f"{minutes}m")
    parts.append(f"{secs}s")
    return " ".join(parts)


def _systemd_available() -> bool:
    """Whether systemctl can actually control a running systemd instance."""
    if not os.path.isdir("/run/systemd/system"):
        return False
    return subprocess.run(
        ["systemctl", "show-environment"], stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, check=False,
    ).returncode == 0


def daemon_start_hint() -> str:
    """Give an executable recovery command, including for containers without systemd."""
    if _systemd_available():
        return "sudo systemctl start kiloframe"
    return "sudo kiloframe start"


def print_status(status: dict[str, Any] | None) -> None:
    """Pretty-print the daemon status."""
    if status is None:
        print("KILOFRAME STATUS")
        print("STATE        STOPPED")
        print("daemon       INACTIVE")
        print(f"start        {daemon_start_hint()}")
        return

    model = str(status.get("model") or "").strip()
    state = "READY" if status.get("running") and status.get("healthy") and model else "STARTING"
    if not status.get("running"):
        state = "STOPPED"
    elif not status.get("healthy"):
        state = "UNHEALTHY"
    elif not model:
        state = "MODEL REQUIRED"
    elif status.get("loaded") is False:
        state = "MODEL SELECTED"

    print("KILOFRAME STATUS")
    print(f"STATE        {state}")
    print(f"daemon       {'ACTIVE' if status.get('running') else 'INACTIVE'}  pid {status.get('pid', '?')}")
    print(f"ollama       {'REACHABLE' if status.get('healthy') else 'UNREACHABLE'}  {status.get('server') or 'not configured'}")
    print(f"model        {model or 'none selected'}")
    if status.get("loaded") is not None:
        print(f"loaded       {'YES' if status.get('loaded') else 'NO — loads on first request'}")
    print(f"uptime       {_duration(status.get('uptime_seconds', 0))}")
    mem = status.get("profile", {})
    total = (mem or {}).get("total_mb", 0)
    avail = (mem or {}).get("available_mb", 0)
    print(f"memory       {total} MiB total · {avail} MiB available")
    meminfo = status.get("memory", {})
    if meminfo:
        print(f"memory       {meminfo.get('facts', '?')} facts · {meminfo.get('skills', '?')} skills · {meminfo.get('sessions', '?')} sessions")
    start_hint = daemon_start_hint()
    restart_hint = "sudo systemctl restart kiloframe" if _systemd_available() else "sudo kiloframe restart"
    if not status.get("healthy"):
        print(f"recovery     check the configured Ollama server, then: {restart_hint}")
    elif not model:
        print("next step    select a downloaded model: kiloframe local models; kiloframe local select <model>")
    else:
        print(f"control      {restart_hint}  ·  kiloframe logs  ·  kiloframe doctor")
    print(f"start        {start_hint}")


def runtime_summary(data: dict[str, Any]) -> dict[str, Any]:
    """Return a subset of the runtime info for display in the status bar."""
    result: dict[str, Any] = {}
    if "build_info" in data:
        result["build"] = data["build_info"]
    if "default_generation_settings" in data:
        n_ctx = data["default_generation_settings"].get("n_ctx")
        if n_ctx is not None:
            result["context_size"] = n_ctx
    if "chat_template_caps" in data:
        supports_tool_calls = data["chat_template_caps"].get("supports_tool_calls")
        if supports_tool_calls is not None:
            result["tool_calling"] = supports_tool_calls
    return result


def _manual_daemon_pid(settings: Settings) -> int | None:
    """Return the PID recorded by KiloFrame, but never trust a stale PID file."""
    path = settings.runtime_dir / "kiloframe.pid"
    try:
        pid = int(path.read_text(encoding="ascii").strip())
        os.kill(pid, 0)
        command = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ")
        return pid if b"kiloframe.daemon" in command else None
    except (FileNotFoundError, PermissionError, ProcessLookupError, ValueError, OSError):
        return None


def _manual_service_action(action: str, settings: Settings) -> int:
    if os.geteuid() != 0:
        print(f"Manual daemon control needs root. Run: sudo kiloframe {action}", file=sys.stderr)
        return 2

    def stop() -> int:
        pid = _manual_daemon_pid(settings)
        if pid is None:
            print("KiloFrame daemon is already stopped.")
            return 0
        os.kill(pid, signal.SIGTERM)
        for _ in range(100):
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                print("KiloFrame daemon stopped.")
                return 0
            time.sleep(0.1)
        # A blocked MCP child or model request can prevent graceful shutdown.
        # Installation/restart must still be reliable, so force-stop only the
        # verified daemon PID after the grace period.
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        print(f"KiloFrame daemon pid {pid} force-stopped after graceful timeout.", file=sys.stderr)
        return 0

    def start() -> int:
        pid = _manual_daemon_pid(settings)
        if pid is not None:
            print(f"KiloFrame daemon is already active (pid {pid}).")
            return 0
        import pwd
        # The installer owns the protected configuration directory as the selected
        # non-root runtime account. Use the same identity on non-systemd hosts.
        runtime_user = pwd.getpwuid(settings.config_dir.stat().st_uid).pw_name
        if runtime_user == "root":
            print("Runtime account must be non-root; rerun the installer.", file=sys.stderr)
            return 1
        subprocess.Popen(
            ["sudo", "-H", "-u", runtime_user, "env", "PYTHONPATH=/opt/kiloframe/app/src",
             "/usr/bin/python3", "-m", "kiloframe.daemon"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        for _ in range(100):
            pid = _manual_daemon_pid(settings)
            if pid is not None and settings.socket_path.exists():
                print(f"KiloFrame daemon started (pid {pid}).")
                return 0
            time.sleep(0.1)
        print(f"KiloFrame daemon did not become ready. Check {settings.log_dir / 'kiloframe.log'}", file=sys.stderr)
        return 1

    if action == "stop":
        return stop()
    if action == "start":
        return start()
    stopped = stop()
    return start() if stopped == 0 else stopped


def service_action(action: str, settings: Settings | None = None) -> int:
    settings = settings or Settings()
    if not _systemd_available():
        return _manual_service_action(action, settings)
    command = ["systemctl", action, "kiloframe.service"]
    if os.geteuid() != 0:
        command.insert(0, "sudo")
    return subprocess.run(command, check=False).returncode


def show_logs(lines: int, settings: Settings) -> int:
    if _systemd_available():
        return subprocess.run(
            ["journalctl", "-u", "kiloframe.service", "-n", str(lines), "--no-pager"],
            check=False,
        ).returncode
    path = settings.log_dir / "kiloframe.log"
    try:
        content = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except FileNotFoundError:
        print(f"No KiloFrame log exists yet at {path}", file=sys.stderr)
        return 1
    print("\n".join(content[-max(0, lines):]))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kiloframe", description="KiloFrame local-first terminal AI")
    parser.add_argument("--version", action="version", version=f"KiloFrame {__version__}")
    sub = parser.add_subparsers(dest="command")
    chat = sub.add_parser("chat", help="send one prompt and stream the answer")
    chat.add_argument("text", nargs="+")
    sub.add_parser("status", help="show daemon, Ollama and resource status")
    doctor = sub.add_parser("doctor", help="run installation and health checks")
    sub.add_parser("resources", help="show the live resource profile")
    sub.add_parser("model-info", help="show the active Ollama server and selected model")
    sub.add_parser("version", help="show KiloFrame and runtime versions")
    logs = sub.add_parser("logs", help="show service logs")
    logs.add_argument("-n", "--lines", type=int, default=100)
    for action in ("restart", "stop", "start"):
        sub.add_parser(action, help=f"{action} the KiloFrame service")
    benchmark = sub.add_parser("benchmark", help="measure a short real inference")
    benchmark.add_argument("--prompt", default="Reply with exactly: KiloFrame is ready.")

    # Ollama management
    local = sub.add_parser("local", help="manage the Ollama local/remote model route")
    local_sub = local.add_subparsers(dest="local_command")
    local_sub.add_parser("status", help="show the active server, model and health")
    local_sub.add_parser("models", help="list models downloaded on the active server")
    local_sub.add_parser("ps", help="list models currently running/loaded on the server")
    pull = local_sub.add_parser("pull", help="download a model on the active server")
    pull.add_argument("model", help="model name, e.g. llama3.2 or qwen2.5:14b")
    select = local_sub.add_parser("select", help="select the model KiloFrame uses")
    select.add_argument("model", help="model name")
    unload = local_sub.add_parser("unload", help="unload a model from the server's memory")
    unload.add_argument("model", nargs="?", default=None, help="model name (default: the selected model)")

    localset = sub.add_parser("localset", help="configure Ollama servers (local or remote)")
    ls_sub = localset.add_subparsers(dest="localset_command")
    ls_sub.add_parser("list", help="list configured Ollama servers")
    ls_add = ls_sub.add_parser("add", help="add or update a server")
    ls_add.add_argument("name", help="server name, e.g. local or office")
    ls_add.add_argument("url", help="server URL, e.g. http://127.0.0.1:11434")
    ls_rm = ls_sub.add_parser("remove", help="remove a server")
    ls_rm.add_argument("name")
    ls_default = ls_sub.add_parser("default", help="set the active server")
    ls_default.add_argument("name")

    tg = sub.add_parser("telegram", help="manage the Telegram bot (token and allowed chats)")
    tg_sub = tg.add_subparsers(dest="telegram_command")
    tg_sub.add_parser("status", help="show whether Telegram is enabled and which chats are allowed")
    tg_token = tg_sub.add_parser("set-token", help="set the bot token")
    tg_token.add_argument("token", help="the @BotFather bot token")
    tg_allow = tg_sub.add_parser("allow", help="authorise a chat id")
    tg_allow.add_argument("chat_id", type=int, help="numeric chat id (send /id to the bot to find it)")
    tg_deny = tg_sub.add_parser("disallow", help="remove a chat id")
    tg_deny.add_argument("chat_id", type=int)
    tg_sub.add_parser("disable", help="turn Telegram off by clearing the token")
    return parser


def telegram_command(args: argparse.Namespace, settings: Settings) -> int:
    """Manage the Telegram bot without hand-editing JSON. The bridge polls its config
    after each long poll, so these changes take effect without a restart. The file is written 0600
    because it holds the bot token."""
    import json
    import os

    path = settings.telegram_path
    action = getattr(args, "telegram_command", None) or "status"
    try:
        config = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except (OSError, json.JSONDecodeError):
        config = {}
    config.setdefault("token", "")
    allowed = [int(x) for x in config.get("allowed_chat_ids", []) if str(x).lstrip("-").isdigit()]

    def save() -> None:
        config["allowed_chat_ids"] = sorted(set(allowed))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass

    if action == "status":
        token = str(config.get("token", "")).strip()
        enabled = bool(token) and token != "PASTE_BOT_TOKEN_HERE" and bool(allowed)
        print(f"telegram   {GREEN + 'enabled' + RESET if enabled else YELLOW + 'disabled' + RESET}")
        print(f"token      {'set (' + token[:6] + '…)' if token else DIM + 'unset' + RESET}")
        print(f"allowed    {', '.join(map(str, allowed)) if allowed else DIM + 'none' + RESET}")
        if not enabled:
            print(f"\n{DIM}enable with: kiloframe telegram set-token <token> && kiloframe telegram allow <chat_id>{RESET}")
        return 0
    if action == "set-token":
        config["token"] = args.token.strip()
        save()
        print(f"{GREEN}token set{RESET}. The bridge picks it up after the current poll (about 10s).")
        return 0
    if action == "allow":
        allowed.append(int(args.chat_id))
        save()
        print(f"{GREEN}authorised{RESET} chat {args.chat_id}.")
        return 0
    if action == "disallow":
        allowed[:] = [c for c in allowed if c != int(args.chat_id)]
        save()
        print(f"{YELLOW}removed{RESET} chat {args.chat_id}.")
        return 0
    if action == "disable":
        config["token"] = ""
        save()
        print(f"{YELLOW}telegram disabled{RESET} (token cleared).")
        return 0
    return 0


async def local_command(args: argparse.Namespace, client: RPCClient) -> int:
    action = getattr(args, "local_command", None) or "status"
    try:
        if action == "status":
            status = await client.request("ollama_status")
            json_print(status)
        elif action == "models":
            models = await client.request("ollama_models")
            if isinstance(models, dict):
                print(f"{YELLOW}{models.get('error', 'could not list models')}{RESET}", file=sys.stderr)
                return 1
            if not models:
                print(f"{DIM}no models downloaded on this server{RESET}")
                return 0
            for m in models:
                size = m.get("size", 0) // (1024 * 1024)
                detail = m.get("details") or {}
                extra = f"  {DIM}{detail.get('parameter_size', '')} {detail.get('quantization_level', '')}{RESET}".rstrip()
                print(f"{GREEN}{m.get('name')}{RESET}  {size} MiB{extra}")
        elif action == "ps":
            running = await client.request("ollama_running")
            if isinstance(running, dict):
                print(f"{YELLOW}{running.get('error', 'could not list running models')}{RESET}", file=sys.stderr)
                return 1
            if not running:
                print(f"{DIM}no models currently running{RESET}")
                return 0
            for m in running:
                print(f"{GREEN}{m.get('name')}{RESET}  {m.get('size', 0) // (1024*1024)} MiB")
        elif action == "pull":
            print(f"pulling {args.model} …")
            async for event in client.stream("ollama_pull", model=args.model):
                if event.get("type") == "ollama_progress":
                    print(f"\r\033[2K{DIM}{event.get('status')}{RESET}", end="", flush=True)
                elif event.get("type") == "result":
                    print()
                    if event.get("data", {}).get("ok"):
                        print(f"{GREEN}pulled{RESET} {args.model}")
                    else:
                        print(f"{YELLOW}{event.get('data', {}).get('error', 'pull failed')}{RESET}")
                        return 1
                elif event.get("type") == "error":
                    print()
                    print(f"{YELLOW}{event.get('error')}{RESET}")
                    return 1
        elif action == "select":
            data = await client.request("ollama_select_model", model=args.model)
            if data.get("ok"):
                print(f"{GREEN}selected{RESET} {data.get('model')} on {data.get('server')}")
            else:
                print(f"{YELLOW}{data.get('error', 'could not select model')}{RESET}")
                return 1
        elif action == "unload":
            data = await client.request("ollama_unload", model=args.model)
            if data.get("ok"):
                print(f"{GREEN}unloaded{RESET} {data.get('model')}")
            else:
                print(f"{YELLOW}{data.get('error', 'could not unload')}{RESET}")
                return 1
    except (FileNotFoundError, ConnectionError, OSError) as exc:
        print(f"{YELLOW}KiloFrame daemon is not running.{RESET} Start it: {daemon_start_hint()}", file=sys.stderr)
        return 2
    except KiloFrameError as exc:
        print(f"{YELLOW}error:{RESET} {exc}", file=sys.stderr)
        return 1
    return 0


async def localset_command(args: argparse.Namespace, client: RPCClient) -> int:
    action = getattr(args, "localset_command", None) or "list"
    try:
        if action == "list":
            info = await client.request("ollama_servers")
            default = info.get("default")
            if not info.get("servers"):
                print(f"{DIM}no Ollama servers configured yet. Add one with: kiloframe localset add local http://127.0.0.1:11434{RESET}")
                return 0
            for s in info["servers"]:
                mark = f"{GREEN}*{RESET} " if s["name"] == default else "  "
                model = f"  model {s['model']}" if s.get("model") else ""
                print(f"{mark}{s['name']:<14}{s['url']}{model}")
        elif action == "add":
            data = await client.request("ollama_add_server", name=args.name, url=args.url)
            if data.get("ok"):
                print(f"{GREEN}server '{args.name}' added/updated{RESET}")
            else:
                print(f"{YELLOW}{data.get('error', 'could not add server')}{RESET}")
                return 1
        elif action == "remove":
            data = await client.request("ollama_remove_server", name=args.name)
            if data.get("ok"):
                print(f"{GREEN}server '{args.name}' removed{RESET}")
            else:
                print(f"{YELLOW}{data.get('error', 'could not remove server')}{RESET}")
                return 1
        elif action == "default":
            data = await client.request("ollama_set_default", name=args.name)
            if data.get("ok"):
                print(f"{GREEN}active server is now '{args.name}'{RESET}")
            else:
                print(f"{YELLOW}{data.get('error', 'could not set default')}{RESET}")
                return 1
    except (FileNotFoundError, ConnectionError, OSError) as exc:
        print(f"{YELLOW}KiloFrame daemon is not running.{RESET} Start it: {daemon_start_hint()}", file=sys.stderr)
        return 2
    except KiloFrameError as exc:
        print(f"{YELLOW}error:{RESET} {exc}", file=sys.stderr)
        return 1
    return 0


async def async_main(args: argparse.Namespace, settings: Settings) -> int:
    client = RPCClient(settings.socket_path)
    if args.command is None:
        # Prefer the full-screen interface; fall back to the streaming line UI when
        # prompt_toolkit is missing or there is no real terminal (piped, dumb term).
        if sys.stdout.isatty() and not os.environ.get("KILOFRAME_SIMPLE_TUI"):
            try:
                from .tui_full import run_full_tui
                if await run_full_tui(client):
                    return 0
            except ImportError:
                pass
        await TerminalUI(client).run()
        return 0
    if args.command == "chat":
        return 0 if await TerminalUI(client).ask(" ".join(args.text)) else 1
    elif args.command == "status":
        status = await client.request("status")
        try:
            running = await client.request("ollama_running")
            if isinstance(running, list):
                selected = str(status.get("model") or "")
                status["loaded"] = any(str(item.get("name") or "") == selected for item in running)
        except (FileNotFoundError, ConnectionError, OSError, KiloFrameError):
            status["loaded"] = None
        print_status(status)
    elif args.command == "resources":
        try:
            json_print(await client.request("resources"))
        except (FileNotFoundError, ConnectionError):
            json_print(ResourceManager(settings).profile().to_dict())
    elif args.command == "model-info":
        try:
            json_print(await client.request("model_info"))
        except (FileNotFoundError, ConnectionError):
            json_print({"server": None, "model": "", "note": "daemon not running"})
    elif args.command == "version":
        print(f"KiloFrame {__version__}")
        try:
            metadata = await client.request("model_info")
            if metadata and metadata.get("model_alias"):
                print(f"selected model: {metadata['model_alias']}")
        except (FileNotFoundError, ConnectionError):
            pass
    elif args.command == "doctor":
        try:
            report = await client.request("doctor")
            checks = [Check(**item) for item in report["checks"]]
            print(f"Runtime checks executed by daemon uid {report['uid']}")
        except (FileNotFoundError, ConnectionError, OSError):
            checks = await asyncio.to_thread(run_checks, settings)
        for check in checks:
            icon = f"{GREEN}PASS" if check.ok else f"{YELLOW}{'WARN' if check.warning else 'FAIL'}"
            print(f"{icon}{RESET}  {check.name:<20} {check.detail}")
        return 0 if all(item.ok or item.warning for item in checks) else 1
    elif args.command == "benchmark":
        started = time.monotonic()
        count = 0
        async for event in client.stream("chat", text=args.prompt, cwd=str(Path.cwd())):
            if event.get("type") == "token":
                piece = event.get("text", "")
                count += len(piece.split())
                print(piece, end="", flush=True)
        elapsed = time.monotonic() - started
        print(f"\n\n{count} approximate word-tokens in {elapsed:.2f}s ({count / max(elapsed, 0.001):.2f}/s end-to-end)")
    elif args.command == "local":
        return await local_command(args, client)
    elif args.command == "localset":
        return await localset_command(args, client)
    return 0


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    settings = Settings()
    if args.command in {"start", "stop", "restart"}:
        raise SystemExit(service_action(args.command, settings))
    if args.command == "logs":
        raise SystemExit(show_logs(args.lines, settings))
    if args.command == "telegram":
        raise SystemExit(telegram_command(args, settings))
    try:
        raise SystemExit(asyncio.run(async_main(args, settings)))
    except (KeyboardInterrupt, asyncio.CancelledError):
        # Quitting the TUI (Ctrl-Q/Ctrl-C) must exit cleanly, not dump a traceback.
        raise SystemExit(0) from None
    except (FileNotFoundError, ConnectionRefusedError):
        if args.command == "status":
            print_status(None)
            raise SystemExit(2) from None
        print(f"{YELLOW}KiloFrame daemon is not running.{RESET} Start it: {daemon_start_hint()}", file=sys.stderr)
        raise SystemExit(2) from None
    except KiloFrameError as exc:
        print(f"{YELLOW}KiloFrame error:{RESET} {exc}", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()

from __future__ import annotations

import os
import shutil
import sqlite3
import stat
import sys
from dataclasses import dataclass
from pathlib import Path

from .config import Settings
from .ollama import OllamaConfig, OllamaError
from .resources import ResourceManager


@dataclass(frozen=True, slots=True)
class Check:
    name: str
    ok: bool
    detail: str
    warning: bool = False


def stat_is_socket(path: Path) -> bool:
    try:
        return stat.S_ISSOCK(path.stat().st_mode)
    except OSError:
        return False


def run_checks(settings: Settings) -> list[Check]:
    checks: list[Check] = []

    python_ok = sys.version_info >= (3, 11)
    checks.append(Check("python", python_ok, f"{sys.version.split()[0]}", warning=not python_ok))

    tui = shutil.which("prompt_toolkit") is not None or _has_module("prompt_toolkit")
    checks.append(Check("prompt_toolkit", tui, "present" if tui else "missing; simple TUI fallback", warning=not tui))

    ollama = OllamaConfig(settings.ollama_path)
    active = ollama.active()
    if active is None:
        checks.append(Check("Ollama server", False, "no server configured — run 'kiloframe localset add local http://127.0.0.1:11434'", warning=True))
    else:
        client = ollama.client(active)
        try:
            version = client.version()
            checks.append(Check("Ollama server", True, f"{active.url} (v{version})"))
        except OllamaError as exc:
            checks.append(Check("Ollama server", False, str(exc), warning=True))

        if active.model:
            try:
                info = client.show(active.model)
                detail = str((info.get("details") or {}).get("parameter_size", "present"))
                checks.append(Check("selected model", True, f"{active.model} ({detail})"))
            except OllamaError as exc:
                checks.append(Check("selected model", False, str(exc), warning=True))
        else:
            checks.append(Check("selected model", False, "no model selected on this server — run 'kiloframe local models' then 'kiloframe local select <model>'", warning=True))

    resources = ResourceManager(settings)
    profile = resources.profile()
    fast_cpu = profile.cpu_level in {"avx2", "avx512"}
    cpu_detail = f"{profile.cpu_arch}/{profile.cpu_level}, {profile.threads} threads"
    checks.append(Check("CPU", fast_cpu, cpu_detail, warning=not fast_cpu))

    disk = shutil.disk_usage(settings.data_dir if settings.data_dir.exists() else settings.data_dir.parent)
    checks.append(Check("disk space", disk.free > 2 * 1024**3, f"{disk.free // (1024**3)} GiB free", warning=disk.free <= 4 * 1024**3))

    for name, path in (("data directory", settings.data_dir), ("runtime directory", settings.runtime_dir), ("log directory", settings.log_dir)):
        checks.append(Check(name, path.exists() and os.access(path, os.W_OK), str(path)))

    try:
        db = sqlite3.connect(settings.database_path)
        result = db.execute("PRAGMA quick_check").fetchone()[0]
        db.close()
        checks.append(Check("memory database", result == "ok", result))
    except sqlite3.Error as exc:
        checks.append(Check("memory database", False, str(exc)))

    socket_ok = settings.socket_path.exists() and stat_is_socket(settings.socket_path)
    checks.append(Check("daemon socket", socket_ok, str(settings.socket_path), warning=not socket_ok))
    return checks


def _has_module(name: str) -> bool:
    try:
        __import__(name)
        return True
    except ImportError:
        return False

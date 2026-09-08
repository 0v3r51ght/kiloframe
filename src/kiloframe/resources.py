from __future__ import annotations

import os
import platform
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from .config import Settings


MIB = 1024 * 1024


def _meminfo() -> dict[str, int]:
    result: dict[str, int] = {}
    try:
        for line in Path("/proc/meminfo").read_text(encoding="ascii").splitlines():
            key, value = line.split(":", 1)
            result[key] = int(value.strip().split()[0]) * 1024
    except (OSError, ValueError):
        pass
    return result


def _cpu_times() -> tuple[int, int] | None:
    """Return aggregate Linux CPU total and idle ticks without dependencies."""
    try:
        fields = Path("/proc/stat").read_text(encoding="ascii").splitlines()[0].split()
        if not fields or fields[0] != "cpu":
            return None
        values = [int(value) for value in fields[1:]]
        return sum(values), values[3] + (values[4] if len(values) > 4 else 0)
    except (OSError, ValueError, IndexError):
        return None


def _cgroup_available() -> int | None:
    root = Path("/sys/fs/cgroup")
    try:
        limit_text = (root / "memory.max").read_text().strip()
        if limit_text == "max":
            return None
        limit = int(limit_text)
        current = int((root / "memory.current").read_text().strip())
        return max(0, limit - current)
    except (OSError, ValueError):
        return None


def _cpu_flags() -> set[str]:
    try:
        text = Path("/proc/cpuinfo").read_text(encoding="ascii", errors="ignore")
    except OSError:
        return set()
    for line in text.splitlines():
        if line.startswith("flags") or line.startswith("Features"):
            return set(line.split(":", 1)[1].split())
    return set()


def _gpu_name() -> str | None:
    if not shutil.which("lspci"):
        return None
    try:
        output = subprocess.run(
            ["lspci"], capture_output=True, text=True, timeout=3, check=False
        ).stdout
    except (OSError, subprocess.TimeoutExpired):
        return None
    matches = [
        line.split(": ", 1)[-1]
        for line in output.splitlines()
        if "VGA" in line or "3D controller" in line
    ]
    return matches[0] if matches else None


@dataclass(frozen=True, slots=True)
class ResourceProfile:
    total_mb: int
    available_mb: int
    safe_available_mb: int
    threads: int
    gpu: str | None
    cpu_arch: str
    cpu_level: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class ResourceManager:
    """Reports live hardware state. Model tuning (context, threads, GPU offload) is
    Ollama's responsibility, not the framework's, so it is not reimplemented here."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._last_cpu = _cpu_times()

    def profile(self) -> ResourceProfile:
        mem = _meminfo()
        total = mem.get("MemTotal", 0)
        available = mem.get("MemAvailable", mem.get("MemFree", 0))
        cgroup = _cgroup_available()
        if cgroup is not None:
            available = min(available, cgroup)
        reserve = max(self.settings.reserve_memory_mb * MIB, int(total * 0.18))
        safe = max(0, available - reserve)
        cores = os.cpu_count() or 1
        threads = max(1, min(cores, 8))
        flags = _cpu_flags()
        if "avx512f" in flags:
            level = "avx512"
        elif "avx2" in flags:
            level = "avx2"
        elif "avx" in flags:
            level = "avx"
        elif "sse4_1" in flags:
            level = "sse4"
        else:
            level = "baseline"
        return ResourceProfile(
            total_mb=total // MIB,
            available_mb=available // MIB,
            safe_available_mb=safe // MIB,
            threads=threads,
            gpu=_gpu_name(),
            cpu_arch=platform.machine(),
            cpu_level=level,
        )

    def live_headroom(self) -> tuple[bool, int]:
        """A quick pressure check before running a tool-heavy step."""
        available = _meminfo().get("MemAvailable", 0)
        cgroup = _cgroup_available()
        if cgroup is not None:
            available = min(available, cgroup)
        available_mb = available // MIB
        return available_mb >= 320, available_mb

    def live_usage(self) -> dict[str, int | None]:
        """A cheap daemon-host sample for UI refreshes, independent of the model."""
        mem = _meminfo()
        total = mem.get("MemTotal", 0)
        available = mem.get("MemAvailable", mem.get("MemFree", 0))
        cgroup = _cgroup_available()
        if cgroup is not None:
            available = min(available, cgroup)
        current = _cpu_times()
        cpu_percent: int | None = None
        if current and self._last_cpu:
            delta_total, delta_idle = current[0] - self._last_cpu[0], current[1] - self._last_cpu[1]
            if delta_total > 0:
                cpu_percent = max(0, min(100, round(100 * (delta_total - delta_idle) / delta_total)))
        self._last_cpu = current
        used = max(0, total - available)
        return {"cpu_percent": cpu_percent, "memory_used_mb": used // MIB,
                "memory_total_mb": total // MIB,
                "memory_percent": round(100 * used / total) if total else None}

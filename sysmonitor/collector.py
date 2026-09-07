"""Data collection layer.

This is the only module that touches ``psutil`` directly. Everything else
consumes the values it returns, which is what lets the rest of the package be
tested without depending on the machine the tests run on (mock this module).
"""

import os
import time
from datetime import datetime, timezone

import psutil

from sysmonitor.models import ProcessSnapshot, SystemSnapshot

_VALID_SORT_KEYS = {"cpu": "cpu_percent", "memory": "memory_percent"}


def _disk_root() -> str:
    """Return the drive root psutil expects for a usage check.

    ``"/"`` on POSIX, the current drive's root (e.g. ``"C:\\"``) on Windows.
    """
    return os.path.abspath(os.sep)


def get_system_snapshot() -> SystemSnapshot:
    """Collect one point-in-time reading of whole-machine resource usage.

    ``cpu_percent`` blocks for one second so the value reflects that interval
    instead of returning 0.0 on a cold call.
    """
    net = psutil.net_io_counters()
    return SystemSnapshot(
        timestamp=datetime.now(timezone.utc),
        cpu_percent=psutil.cpu_percent(interval=1),
        memory_percent=psutil.virtual_memory().percent,
        disk_percent=psutil.disk_usage(_disk_root()).percent,
        net_sent_bytes=net.bytes_sent,
        net_recv_bytes=net.bytes_recv,
    )


def get_top_processes(n: int = 5, by: str = "cpu") -> list[ProcessSnapshot]:
    """Return the ``n`` processes using the most CPU or memory.

    ``by`` is ``"cpu"`` or ``"memory"``. Processes that die or become
    permission-restricted mid-scan are skipped, not raised — a monitoring tool
    must survive a moving target.
    """
    if by not in _VALID_SORT_KEYS:
        raise ValueError(f"'by' must be one of {sorted(_VALID_SORT_KEYS)}, got {by!r}")

    # psutil computes cpu_percent as a delta between two reads, so the first read
    # per process is always 0.0. Prime every process, wait briefly, then measure.
    for proc in psutil.process_iter():
        try:
            proc.cpu_percent()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    time.sleep(0.1)

    processes: list[ProcessSnapshot] = []
    for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
        try:
            info = proc.info
            # PID 0 is the idle task (e.g. "System Idle Process" on Windows); it
            # reports idle time, not real usage, and would dominate a CPU sort.
            if info["pid"] == 0:
                continue
            processes.append(
                ProcessSnapshot(
                    pid=info["pid"],
                    name=info["name"] or "",
                    cpu_percent=info["cpu_percent"] or 0.0,
                    memory_percent=info["memory_percent"] or 0.0,
                )
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    sort_attr = _VALID_SORT_KEYS[by]
    processes.sort(key=lambda p: getattr(p, sort_attr), reverse=True)
    return processes[:n]


if __name__ == "__main__":
    # Throwaway sanity check: eyeball these against Task Manager / htop.
    print(get_system_snapshot().model_dump_json(indent=2))
    print()
    for p in get_top_processes(n=5, by="cpu"):
        print(f"{p.pid:>7}  {p.name[:30]:<30}  cpu={p.cpu_percent:5.1f}%  mem={p.memory_percent:5.1f}%")

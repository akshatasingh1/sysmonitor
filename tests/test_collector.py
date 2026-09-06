from datetime import datetime
from unittest.mock import patch

import psutil
import pytest

from sysmonitor.collector import get_system_snapshot, get_top_processes


class FakeProc:
    """Stand-in for a psutil.Process yielded by process_iter."""

    def __init__(self, pid, name, cpu, mem, error=None):
        self._error = error
        self._data = {
            "pid": pid,
            "name": name,
            "cpu_percent": cpu,
            "memory_percent": mem,
        }

    def cpu_percent(self):
        if self._error:
            raise self._error
        return self._data["cpu_percent"]

    @property
    def info(self):
        if self._error:
            raise self._error
        return self._data


# ============================================================
# get_system_snapshot()
# ============================================================

@patch("sysmonitor.collector.psutil")
def test_get_system_snapshot_assembles_mocked_values(mock_psutil):
    mock_psutil.cpu_percent.return_value = 12.5
    mock_psutil.virtual_memory.return_value.percent = 43.0
    mock_psutil.disk_usage.return_value.percent = 55.5
    mock_psutil.net_io_counters.return_value.bytes_sent = 1000
    mock_psutil.net_io_counters.return_value.bytes_recv = 2000

    snap = get_system_snapshot()

    assert snap.cpu_percent == 12.5
    assert snap.memory_percent == 43.0
    assert snap.disk_percent == 55.5
    assert snap.net_sent_bytes == 1000
    assert snap.net_recv_bytes == 2000
    assert isinstance(snap.timestamp, datetime)


# ============================================================
# get_top_processes()
# ============================================================

@patch("sysmonitor.collector.time.sleep")
@patch("sysmonitor.collector.psutil.process_iter")
def test_top_processes_sorts_by_cpu_and_respects_n(mock_iter, _sleep):
    mock_iter.return_value = [
        FakeProc(10, "a", 5.0, 1.0),
        FakeProc(11, "b", 50.0, 2.0),
        FakeProc(12, "c", 20.0, 9.0),
    ]

    result = get_top_processes(n=2, by="cpu")

    assert [p.pid for p in result] == [11, 12]


@patch("sysmonitor.collector.time.sleep")
@patch("sysmonitor.collector.psutil.process_iter")
def test_top_processes_sorts_by_memory(mock_iter, _sleep):
    mock_iter.return_value = [
        FakeProc(10, "a", 5.0, 1.0),
        FakeProc(11, "b", 50.0, 2.0),
        FakeProc(12, "c", 20.0, 9.0),
    ]

    result = get_top_processes(n=3, by="memory")

    assert [p.pid for p in result] == [12, 11, 10]


@patch("sysmonitor.collector.time.sleep")
@patch("sysmonitor.collector.psutil.process_iter")
def test_top_processes_skips_dead_and_denied_and_idle(mock_iter, _sleep):
    mock_iter.return_value = [
        FakeProc(10, "alive", 5.0, 1.0),
        FakeProc(11, "gone", 99.0, 2.0, error=psutil.NoSuchProcess(11)),
        FakeProc(12, "denied", 99.0, 2.0, error=psutil.AccessDenied(12)),
        FakeProc(0, "System Idle Process", 100.0, 0.0),
    ]

    result = get_top_processes(n=5, by="cpu")

    assert [p.pid for p in result] == [10]


def test_top_processes_rejects_bad_sort_key():
    with pytest.raises(ValueError):
        get_top_processes(by="disk")

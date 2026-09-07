import json
import textwrap
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from sysmonitor.cli import cli
from sysmonitor.models import ProcessSnapshot, SystemSnapshot

CONFIG_YAML = textwrap.dedent(
    """
    poll_interval_seconds: 5
    top_n_processes: 3
    thresholds:
      cpu_percent:    {{ warning: 70, critical: 90 }}
      memory_percent: {{ warning: 70, critical: 90 }}
      disk_percent:   {{ warning: 70, critical: 90 }}
    logging:
      log_file: {log_file}
      format: json
    """
)


class Config:
    def __init__(self, path, log_file):
        self.path = path
        self.log_file = log_file

    def log_events(self):
        lines = self.log_file.read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines if line.strip()]


@pytest.fixture
def config_file(tmp_path):
    log_file = tmp_path / "sysmonitor.log"
    cfg_path = tmp_path / "thresholds.yaml"
    cfg_path.write_text(
        CONFIG_YAML.format(log_file=log_file.as_posix()), encoding="utf-8"
    )
    return Config(str(cfg_path), log_file)


@pytest.fixture
def runner():
    return CliRunner()


def _snapshot(cpu=10.0, mem=40.0, disk=25.0):
    return SystemSnapshot(
        timestamp=datetime.now(timezone.utc),
        cpu_percent=cpu,
        memory_percent=mem,
        disk_percent=disk,
        net_sent_bytes=1,
        net_recv_bytes=2,
    )


# ============================================================
# snapshot
# ============================================================

@patch("sysmonitor.cli.get_system_snapshot")
def test_snapshot_runs_and_reports_normal(mock_snap, runner, config_file):
    mock_snap.return_value = _snapshot(cpu=10, mem=40, disk=25)

    result = runner.invoke(cli, ["snapshot", "--config", config_file.path])

    assert result.exit_code == 0
    assert "SYSTEM DIAGNOSTIC REPORT" in result.output
    assert "No major performance issues detected." in result.output


@patch("sysmonitor.cli.get_system_snapshot")
def test_snapshot_applies_config_thresholds(mock_snap, runner, tmp_path):
    yaml_text = CONFIG_YAML.format(log_file=(tmp_path / "s.log").as_posix()).replace(
        "cpu_percent:    { warning: 70, critical: 90 }",
        "cpu_percent:    { warning: 10, critical: 15 }",
    )
    path = tmp_path / "c.yaml"
    path.write_text(yaml_text, encoding="utf-8")
    mock_snap.return_value = _snapshot(cpu=20, mem=40, disk=25)

    result = runner.invoke(cli, ["snapshot", "--config", str(path)])

    assert result.exit_code == 0
    assert "CPU usage is critically high." in result.output


def test_force_utf8_output_survives_stream_without_reconfigure():
    # objects lacking .reconfigure (or rejecting it) must not raise
    from sysmonitor.cli import _force_utf8_output

    class Dumb:
        pass

    with patch("sysmonitor.cli.sys.stdout", Dumb()), patch(
        "sysmonitor.cli.sys.stderr", Dumb()
    ):
        _force_utf8_output()  # no exception


def test_snapshot_missing_config_fails_cleanly(runner, tmp_path):
    result = runner.invoke(cli, ["snapshot", "--config", str(tmp_path / "nope.yaml")])

    assert result.exit_code != 0
    assert "not found" in result.output
    assert "Traceback" not in result.output


# ============================================================
# top
# ============================================================

@patch("sysmonitor.cli.get_top_processes")
def test_top_prints_table(mock_top, runner, config_file):
    mock_top.return_value = [
        ProcessSnapshot(pid=101, name="python.exe", cpu_percent=55.0, memory_percent=3.0),
        ProcessSnapshot(pid=202, name="brave.exe", cpu_percent=12.0, memory_percent=8.0),
    ]

    result = runner.invoke(cli, ["top", "--by", "cpu", "--config", config_file.path])

    assert result.exit_code == 0
    assert "PID" in result.output and "CPU%" in result.output
    assert "python.exe" in result.output
    mock_top.assert_called_once_with(n=3, by="cpu")  # n falls back to config


@patch("sysmonitor.cli.get_top_processes")
def test_top_n_flag_overrides_config(mock_top, runner, config_file):
    mock_top.return_value = []

    result = runner.invoke(cli, ["top", "--n", "10", "--config", config_file.path])

    assert result.exit_code == 0
    mock_top.assert_called_once_with(n=10, by="cpu")


def test_top_rejects_bad_by(runner, config_file):
    result = runner.invoke(cli, ["top", "--by", "disk", "--config", config_file.path])
    assert result.exit_code != 0


# ============================================================
# watch
# ============================================================

@patch("sysmonitor.cli.time.sleep")
@patch("sysmonitor.cli.get_system_snapshot")
def test_watch_once_logs_one_cycle_and_breach(mock_snap, mock_sleep, runner, config_file):
    mock_snap.return_value = _snapshot(cpu=95, mem=40, disk=25)

    result = runner.invoke(cli, ["watch", "--once", "--config", config_file.path])

    assert result.exit_code == 0
    assert mock_snap.call_count == 1
    mock_sleep.assert_not_called()

    events = config_file.log_events()
    by_event = {e["event"]: e for e in events}
    assert by_event["snapshot"]["cpu_percent"] == 95.0
    assert by_event["snapshot"]["cpu_state"] == "CRITICAL"
    assert by_event["snapshot"]["level"] == "INFO"
    assert by_event["threshold_breach"]["metric"] == "cpu"
    assert by_event["threshold_breach"]["state"] == "CRITICAL"
    assert by_event["threshold_breach"]["level"] == "WARNING"
    # only CPU breached
    assert sum(1 for e in events if e["event"] == "threshold_breach") == 1


@patch("sysmonitor.cli.time.sleep")
@patch("sysmonitor.cli.get_system_snapshot")
def test_watch_once_all_normal_logs_no_breach(mock_snap, mock_sleep, runner, config_file):
    mock_snap.return_value = _snapshot(cpu=10, mem=20, disk=30)

    result = runner.invoke(cli, ["watch", "--once", "--config", config_file.path])

    assert result.exit_code == 0
    events = config_file.log_events()
    assert [e["event"] for e in events] == ["snapshot"]


@patch("sysmonitor.cli.get_system_snapshot")
def test_watch_stops_cleanly_on_interrupt(mock_snap, runner, config_file):
    mock_snap.side_effect = KeyboardInterrupt()

    result = runner.invoke(cli, ["watch", "--config", config_file.path])

    assert result.exit_code == 0
    assert "Stopped monitoring." in result.output
    assert "Traceback" not in result.output


# --- debounce -------------------------------------------------

@patch("sysmonitor.cli.time.sleep")
@patch("sysmonitor.cli.get_system_snapshot")
def test_watch_debounces_ongoing_breach(mock_snap, mock_sleep, runner, config_file):
    # three cycles all breached on CPU, then interrupt
    mock_snap.side_effect = [
        _snapshot(cpu=95, mem=20, disk=20),
        _snapshot(cpu=96, mem=20, disk=20),
        _snapshot(cpu=97, mem=20, disk=20),
        KeyboardInterrupt(),
    ]

    result = runner.invoke(cli, ["watch", "--config", config_file.path])

    assert result.exit_code == 0
    events = config_file.log_events()
    assert sum(1 for e in events if e["event"] == "threshold_breach") == 1
    assert sum(1 for e in events if e["event"] == "snapshot") == 3


@patch("sysmonitor.cli.time.sleep")
@patch("sysmonitor.cli.get_system_snapshot")
def test_watch_alerts_again_on_escalation_and_recovery(mock_snap, mock_sleep, runner, config_file):
    mock_snap.side_effect = [
        _snapshot(cpu=75, mem=20, disk=20),   # NORMAL -> WARNING  (breach)
        _snapshot(cpu=95, mem=20, disk=20),   # WARNING -> CRITICAL (breach)
        _snapshot(cpu=10, mem=20, disk=20),   # CRITICAL -> NORMAL  (cleared)
        KeyboardInterrupt(),
    ]

    result = runner.invoke(cli, ["watch", "--config", config_file.path])

    assert result.exit_code == 0
    events = [e for e in config_file.log_events() if e["event"] != "snapshot"]
    assert [(e["event"], e["state"]) for e in events] == [
        ("threshold_breach", "WARNING"),
        ("threshold_breach", "CRITICAL"),
        ("threshold_cleared", "NORMAL"),
    ]
    assert events[-1]["previous_state"] == "CRITICAL"

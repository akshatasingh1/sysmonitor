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
      cpu_percent:    { warning: 70, critical: 90 }
      memory_percent: { warning: 70, critical: 90 }
      disk_percent:   { warning: 70, critical: 90 }
    logging:
      log_file: logs/sysmonitor.log
      format: text
    """
)


@pytest.fixture
def config_file(tmp_path):
    path = tmp_path / "thresholds.yaml"
    path.write_text(CONFIG_YAML, encoding="utf-8")
    return str(path)


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

    result = runner.invoke(cli, ["snapshot", "--config", config_file])

    assert result.exit_code == 0
    assert "SYSTEM DIAGNOSTIC REPORT" in result.output
    assert "No major performance issues detected." in result.output


@patch("sysmonitor.cli.get_system_snapshot")
def test_snapshot_applies_config_thresholds(mock_snap, runner, tmp_path):
    # critical cut-off lowered to 15 -> cpu of 20 should read CRITICAL
    yaml_text = CONFIG_YAML.replace(
        "cpu_percent:    { warning: 70, critical: 90 }",
        "cpu_percent:    { warning: 10, critical: 15 }",
    )
    path = tmp_path / "c.yaml"
    path.write_text(yaml_text, encoding="utf-8")
    mock_snap.return_value = _snapshot(cpu=20, mem=40, disk=25)

    result = runner.invoke(cli, ["snapshot", "--config", str(path)])

    assert result.exit_code == 0
    assert "CPU usage is critically high." in result.output


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

    result = runner.invoke(cli, ["top", "--by", "cpu", "--config", config_file])

    assert result.exit_code == 0
    assert "PID" in result.output and "CPU%" in result.output
    assert "python.exe" in result.output
    mock_top.assert_called_once_with(n=3, by="cpu")  # n falls back to config


@patch("sysmonitor.cli.get_top_processes")
def test_top_n_flag_overrides_config(mock_top, runner, config_file):
    mock_top.return_value = []

    result = runner.invoke(cli, ["top", "--n", "10", "--config", config_file])

    assert result.exit_code == 0
    mock_top.assert_called_once_with(n=10, by="cpu")


def test_top_rejects_bad_by(runner, config_file):
    result = runner.invoke(cli, ["top", "--by", "disk", "--config", config_file])
    assert result.exit_code != 0


# ============================================================
# watch
# ============================================================

@patch("sysmonitor.cli.time.sleep")
@patch("sysmonitor.cli.get_system_snapshot")
def test_watch_once_runs_single_cycle(mock_snap, mock_sleep, runner, config_file):
    mock_snap.return_value = _snapshot(cpu=95, mem=40, disk=25)

    result = runner.invoke(cli, ["watch", "--once", "--config", config_file])

    assert result.exit_code == 0
    assert mock_snap.call_count == 1
    mock_sleep.assert_not_called()
    assert "CPU  95.0%" in result.output
    assert "✗ CRITICAL  CPU at 95.0%" in result.output


@patch("sysmonitor.cli.get_system_snapshot")
def test_watch_stops_cleanly_on_interrupt(mock_snap, runner, config_file):
    mock_snap.side_effect = KeyboardInterrupt()

    result = runner.invoke(cli, ["watch", "--config", config_file])

    assert result.exit_code == 0
    assert "Stopped monitoring." in result.output
    assert "Traceback" not in result.output

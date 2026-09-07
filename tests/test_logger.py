import json
import logging
import sys
from logging.handlers import RotatingFileHandler

from sysmonitor.logger import JsonFormatter, get_logger
from sysmonitor.models import LoggingConfig


def _record(level=logging.INFO, msg="hello", **extra):
    rec = logging.LogRecord("sysmonitor", level, __file__, 10, msg, (), None)
    for key, value in extra.items():
        setattr(rec, key, value)
    return rec


def _config(tmp_path, fmt="json", name="sysmonitor.log"):
    return LoggingConfig(log_file=str(tmp_path / name), format=fmt)


# ============================================================
# JsonFormatter
# ============================================================

def test_json_formatter_includes_standard_and_extra_fields():
    line = JsonFormatter().format(
        _record(msg="threshold breach", metric="cpu", value=92.3, state="CRITICAL")
    )
    obj = json.loads(line)

    assert obj["level"] == "INFO"
    assert obj["message"] == "threshold breach"
    assert obj["metric"] == "cpu"
    assert obj["value"] == 92.3
    assert obj["state"] == "CRITICAL"
    assert "time" in obj


def test_json_formatter_emits_single_line():
    line = JsonFormatter().format(_record(msg="line one\nline two"))
    assert "\n" not in line
    assert json.loads(line)["message"] == "line one\nline two"


def test_json_formatter_includes_exception_text():
    try:
        raise ValueError("boom")
    except ValueError:
        rec = logging.LogRecord(
            "sysmonitor", logging.ERROR, __file__, 1, "failed", (), sys.exc_info()
        )
    obj = json.loads(JsonFormatter().format(rec))
    assert "ValueError: boom" in obj["exc_info"]


def test_json_formatter_events_carry_different_fields():
    snapshot = json.loads(
        JsonFormatter().format(_record(msg="snapshot", event="snapshot", cpu_percent=10.0))
    )
    breach = json.loads(
        JsonFormatter().format(_record(msg="breach", event="threshold_breach", metric="disk"))
    )
    assert "cpu_percent" in snapshot and "metric" not in snapshot
    assert "metric" in breach and "cpu_percent" not in breach


# ============================================================
# text formatter
# ============================================================

def test_text_formatter_ignores_extras(tmp_path):
    logger = get_logger(_config(tmp_path, fmt="text"))
    formatter = logger.handlers[0].formatter

    out = formatter.format(_record(msg="hi there", metric="cpu", value=1.0))

    assert "[INFO] hi there" in out
    assert "metric" not in out
    assert "cpu" not in out


# ============================================================
# get_logger
# ============================================================

def test_get_logger_creates_dir_and_writes_json_line(tmp_path):
    log_file = tmp_path / "nested" / "sysmonitor.log"
    logger = get_logger(LoggingConfig(log_file=str(log_file), format="json"))

    logger.info("first record", extra={"event": "test", "n": 1})
    for handler in logger.handlers:
        handler.flush()

    assert log_file.exists()
    obj = json.loads(log_file.read_text(encoding="utf-8").strip())
    assert obj["message"] == "first record"
    assert obj["event"] == "test"
    assert obj["n"] == 1


def test_get_logger_is_idempotent(tmp_path):
    config = _config(tmp_path)
    get_logger(config)
    logger = get_logger(config)

    assert len(logger.handlers) == 1  # not stacked to 2


def test_get_logger_is_file_only(tmp_path):
    # No console handler: watch prints its own human-readable view, the file
    # stays machine-parseable.
    logger = get_logger(_config(tmp_path))

    assert len(logger.handlers) == 1
    handler = logger.handlers[0]
    assert isinstance(handler, RotatingFileHandler)
    assert handler.maxBytes == 5 * 1024 * 1024
    assert handler.backupCount == 3

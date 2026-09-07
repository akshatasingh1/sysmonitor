"""Structured logging for sysmonitor.

``get_logger(config)`` returns a logger that writes to one rotating **file** in
the format named in the config (``json`` or ``text``). It does not write to the
console - ``watch`` prints its own human-readable view there, so the file can
stay machine-parseable without a wall of JSON scrolling past the operator.

JSON mode emits one object per line: the standard ``time`` / ``level`` /
``message`` plus any fields passed through ``extra=`` on the logging call, so
each event carries exactly the fields relevant to it. Text mode is deliberately
plain (``time [LEVEL] message``) and ignores the extras - reach for JSON mode
when you need the structured data.
"""

import json
import logging
import time
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

from sysmonitor.models import LoggingConfig

LOGGER_NAME = "sysmonitor"

_MAX_BYTES = 5 * 1024 * 1024  # 5 MB per file
_BACKUP_COUNT = 3  # keep sysmonitor.log.1 .. sysmonitor.log.3

# Every LogRecord carries these attributes; anything *else* on a record was
# passed via extra= and belongs in the JSON output.
_STANDARD_RECORD_KEYS = set(
    logging.LogRecord("", 0, "", 0, "", (), None).__dict__
) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    """Render each record as a single-line JSON object, including its extras."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "time": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD_RECORD_KEYS:
                payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def _make_formatter(fmt: str) -> logging.Formatter:
    if fmt == "json":
        return JsonFormatter()
    text = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%dT%H:%M:%SZ"
    )
    text.converter = time.gmtime  # keep text timestamps in UTC, like JSON mode
    return text


def get_logger(config: LoggingConfig) -> logging.Logger:
    """Return the configured ``sysmonitor`` file logger. Safe to call repeatedly."""
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    # Drop handlers from any previous call so repeated configuration (tests, a
    # restarted watch) doesn't stack duplicates or leak open file handles.
    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)

    log_path = Path(config.log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setFormatter(_make_formatter(config.format))
    logger.addHandler(file_handler)

    return logger

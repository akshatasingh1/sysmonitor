"""Pydantic data models shared across sysmonitor.

Keeping these here (rather than scattered through the modules that build them)
gives every downstream module a single, validated shape to consume.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# ------------------------------------------------------------------
# Collected data (built by collector.py)
# ------------------------------------------------------------------


class SystemSnapshot(BaseModel):
    """A single point-in-time reading of whole-machine resource usage."""

    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    net_sent_bytes: int
    net_recv_bytes: int


class ProcessSnapshot(BaseModel):
    """A single process's resource usage at collection time."""

    pid: int
    name: str
    cpu_percent: float
    memory_percent: float


# ------------------------------------------------------------------
# Configuration (built by config.load_config)
# ------------------------------------------------------------------

# extra="forbid" turns a typo'd config key (e.g. "cpu_percnt") into a loud
# error instead of a silently-ignored setting.
_strict = ConfigDict(extra="forbid")


class ThresholdLevel(BaseModel):
    """The warning and critical cut-offs for one resource, as percentages."""

    model_config = _strict

    warning: float = Field(ge=0, le=100)
    critical: float = Field(ge=0, le=100)

    @model_validator(mode="after")
    def _warning_below_critical(self) -> "ThresholdLevel":
        if self.warning >= self.critical:
            raise ValueError(
                f"warning ({self.warning}) must be less than critical ({self.critical})"
            )
        return self


class Thresholds(BaseModel):
    """Per-resource threshold levels."""

    model_config = _strict

    cpu_percent: ThresholdLevel
    memory_percent: ThresholdLevel
    disk_percent: ThresholdLevel


class LoggingConfig(BaseModel):
    """Where and how the monitor writes its logs."""

    model_config = _strict

    log_file: str
    format: Literal["json", "text"] = "json"


class AppConfig(BaseModel):
    """The full validated configuration for a sysmonitor run."""

    model_config = _strict

    poll_interval_seconds: float = Field(gt=0)
    top_n_processes: int = Field(gt=0)
    thresholds: Thresholds
    logging: LoggingConfig

"""Pydantic data models shared across sysmonitor.

Keeping these here (rather than scattered through the modules that build them)
gives every downstream module a single, validated shape to consume.
"""

from datetime import datetime

from pydantic import BaseModel


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

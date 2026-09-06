"""Configuration loading and validation.

Implemented in Phase 2: read ``config/thresholds.yaml`` with ``yaml.safe_load``,
validate it into an ``AppConfig`` pydantic model, and surface a clear CLI-facing
error (not a raw traceback) when the file is missing or malformed.
"""

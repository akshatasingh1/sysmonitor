"""Configuration loading and validation.

Reads ``config/thresholds.yaml``, validates it into an :class:`AppConfig`, and
turns any problem - missing file, broken YAML, invalid values - into a single
:class:`ConfigError` with a readable message, so the CLI can show that instead
of a raw traceback.

Missing-file behaviour: fail loud. There is no silent fallback to hardcoded
defaults - if you point sysmonitor at a config that isn't there, that's almost
always a mistake worth stopping for.
"""

from pathlib import Path

import yaml
from pydantic import ValidationError

from sysmonitor.models import AppConfig

DEFAULT_CONFIG_PATH = "config/thresholds.yaml"


class ConfigError(Exception):
    """A configuration file could not be loaded or is invalid."""


def load_config(path: str = DEFAULT_CONFIG_PATH) -> AppConfig:
    """Load, parse and validate the config file at ``path``.

    Raises :class:`ConfigError` (never a raw ``yaml`` or ``pydantic`` error).
    """
    config_path = Path(path)

    if not config_path.is_file():
        raise ConfigError(f"Config file not found: {path}")

    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"Could not parse YAML in {path}:\n{exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigError(
            f"Config file {path} must contain a YAML mapping, got {type(raw).__name__}."
        )

    try:
        return AppConfig(**raw)
    except ValidationError as exc:
        raise ConfigError(
            f"Invalid configuration in {path}:\n{_format_validation_error(exc)}"
        ) from exc


def _format_validation_error(exc: ValidationError) -> str:
    """Render a pydantic ValidationError as indented ``location: message`` lines."""
    lines = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error["loc"]) or "(root)"
        lines.append(f"  - {location}: {error['msg']}")
    return "\n".join(lines)

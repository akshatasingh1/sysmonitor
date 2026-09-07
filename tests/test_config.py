import textwrap

import pytest

from sysmonitor.config import ConfigError, load_config

VALID_YAML = textwrap.dedent(
    """
    poll_interval_seconds: 5
    top_n_processes: 5
    thresholds:
      cpu_percent:    { warning: 70, critical: 90 }
      memory_percent: { warning: 75, critical: 95 }
      disk_percent:   { warning: 80, critical: 92 }
    logging:
      log_file: logs/sysmonitor.log
      format: text
    """
)


def _write(tmp_path, contents):
    path = tmp_path / "thresholds.yaml"
    path.write_text(contents, encoding="utf-8")
    return str(path)


# ============================================================
# Happy path
# ============================================================

def test_load_config_valid(tmp_path):
    config = load_config(_write(tmp_path, VALID_YAML))

    assert config.poll_interval_seconds == 5
    assert config.top_n_processes == 5
    assert config.thresholds.cpu_percent.warning == 70
    assert config.thresholds.memory_percent.critical == 95
    assert config.logging.format == "text"


def test_logging_format_defaults_to_json(tmp_path):
    yaml_text = VALID_YAML.replace("  format: text\n", "")
    config = load_config(_write(tmp_path, yaml_text))
    assert config.logging.format == "json"


# ============================================================
# Failure modes - all should raise ConfigError, never a raw error
# ============================================================

def test_missing_file_raises_config_error(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_config(str(tmp_path / "does_not_exist.yaml"))


def test_malformed_yaml_raises_config_error(tmp_path):
    with pytest.raises(ConfigError, match="parse YAML"):
        load_config(_write(tmp_path, "poll_interval_seconds: 5\n  bad: : indentation"))


def test_missing_required_field_raises_config_error(tmp_path):
    yaml_text = VALID_YAML.replace("top_n_processes: 5\n", "")
    with pytest.raises(ConfigError, match="top_n_processes"):
        load_config(_write(tmp_path, yaml_text))


def test_wrong_type_raises_config_error(tmp_path):
    yaml_text = VALID_YAML.replace("poll_interval_seconds: 5", "poll_interval_seconds: fast")
    with pytest.raises(ConfigError, match="poll_interval_seconds"):
        load_config(_write(tmp_path, yaml_text))


def test_warning_not_below_critical_raises_config_error(tmp_path):
    yaml_text = VALID_YAML.replace(
        "cpu_percent:    { warning: 70, critical: 90 }",
        "cpu_percent:    { warning: 95, critical: 90 }",
    )
    with pytest.raises(ConfigError, match="must be less than critical"):
        load_config(_write(tmp_path, yaml_text))


def test_threshold_out_of_range_raises_config_error(tmp_path):
    yaml_text = VALID_YAML.replace(
        "cpu_percent:    { warning: 70, critical: 90 }",
        "cpu_percent:    { warning: 70, critical: 150 }",
    )
    with pytest.raises(ConfigError, match="less than or equal to 100"):
        load_config(_write(tmp_path, yaml_text))


def test_unknown_key_raises_config_error(tmp_path):
    yaml_text = VALID_YAML.replace(
        "poll_interval_seconds: 5",
        "poll_interval_seconds: 5\npoll_intrval_typo: 9",
    )
    with pytest.raises(ConfigError, match="poll_intrval_typo"):
        load_config(_write(tmp_path, yaml_text))


def test_non_mapping_yaml_raises_config_error(tmp_path):
    with pytest.raises(ConfigError, match="must contain a YAML mapping"):
        load_config(_write(tmp_path, "- just\n- a\n- list\n"))

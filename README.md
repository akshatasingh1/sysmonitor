# sysmonitor

A terminal tool for monitoring system and per-process resource usage.

## 📋 What it does

You run it as `sysmonitor watch`. It polls system and per-process
CPU / memory / disk / network stats on an interval, checks them against
warning/critical thresholds from a YAML file, writes structured logs, and fires
a debounced alert when a metric crosses a limit. There's also `sysmonitor
snapshot` for a one-off formatted report and `sysmonitor top` for the top-N
process table. No GUI, no web server, no plugins.

It started as a one-shot diagnostic script and grew into a small monitoring CLI —
the kind of internal tool you'd leave running unattended.

### Resource status levels

Each metric is classified `NORMAL` / `WARNING` / `CRITICAL` against two
per-resource cut-offs. The defaults are 70 and 90; both come from
[`config/thresholds.yaml`](config/thresholds.yaml) and can be set per resource.

| Level        | Default range        | Icon |
| :----------- | :------------------- | :--: |
| **NORMAL**   | below `warning`      |   ✓  |
| **WARNING**  | `warning`–`critical` |   ⚠  |
| **CRITICAL** | at/above `critical`  |   ✗  |

## 🚀 Features

* 📊 **`watch`** — polls CPU / memory / disk / network on an interval and logs every cycle
* 🎯 **Two-tier thresholds** — `warning` and `critical` per resource, from validated YAML config
* 🔔 **Debounced alerts** — alerts only on a state *change*, not every cycle a breach is ongoing; logs a recovery when it clears
* 🔍 **Top processes on breach** — on a CPU/memory breach, attaches the top-N offending processes to the log
* 📝 **Structured logging** — `json` (one object per line, per-event fields) or `text`, to a rotating file and the console
* 📋 **`snapshot`** — a one-off formatted report with per-resource recommendations and an overall assessment
* 📈 **`top`** — top-N processes by CPU or memory, as a fixed-width table
* 🧪 **Tested** — `pytest` at 100% coverage, `psutil` mocked so tests don't depend on the host

## 📁 Project Structure

```text
sysmonitor/
├── sysmonitor/                  # Package
│   ├── __init__.py
│   ├── cli.py                   # click CLI: snapshot / top / watch
│   ├── collector.py            # psutil access — the only module that touches it
│   ├── alerts.py               # pure analysis / assessment / recommendation logic
│   ├── config.py               # YAML + pydantic config loading
│   ├── logger.py               # structured logging: rotating file + console
│   └── models.py               # pydantic data models
├── config/
│   ├── thresholds.yaml         # default config
│   └── thresholds.example.yaml # committed reference copy
├── tests/
│   ├── conftest.py             # shared fixtures / logger cleanup
│   ├── test_alerts.py          # analysis + debounce logic
│   ├── test_collector.py       # collector with psutil mocked
│   ├── test_config.py          # config loading + failure modes
│   ├── test_logger.py          # formatters + handler setup
│   └── test_cli.py             # all three commands via CliRunner
├── logs/                        # rotating log output (gitignored)
├── pyproject.toml               # package metadata + `sysmonitor` entry point
├── requirements.txt             # pinned direct dependencies
├── mise.toml                    # pins Python 3.11 + auto-creates .venv
├── README.md
└── .gitignore
```

## 📦 Installation

### 1. Clone the repository

```bash
git clone https://github.com/akshatasingh1/sysmonitor.git
cd sysmonitor
```

### 2. Set up the environment

The repo pins Python 3.11 and an auto-created `.venv` via [mise](https://mise.jdx.dev):

```bash
mise install          # provisions Python 3.11 + creates .venv
pip install -e ".[dev]"   # installs sysmonitor + dev deps into the venv
```

Without mise, create the venv yourself and install from `requirements.txt`:

```bash
python -m venv .venv && source .venv/bin/activate   # .venv\Scripts\activate on Windows
pip install -r requirements.txt
pip install -e .
```

## 💻 Usage

Three subcommands, each accepting `--config PATH` (defaults to
`config/thresholds.yaml`):

```bash
sysmonitor snapshot            # one reading + full diagnostic report, then exit
sysmonitor top --by cpu --n 10 # just the top-N process table
sysmonitor watch               # poll on an interval until Ctrl+C
sysmonitor watch --once        # a single poll cycle, then exit
```

### `snapshot` — example output

```text
╔═════════════════════════════════════════════════════════════════════════════════════════════════════════════════════╗
║                                          SYSTEM DIAGNOSTIC REPORT                                                   ║
╚═════════════════════════════════════════════════════════════════════════════════════════════════════════════════════╝

                                              RESOURCE STATUS
───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

CPU       25%     ✓ NORMAL
RAM       67%     ✓ NORMAL
Disk      82%     ⚠ WARNING

                                           LIKELY PERFORMANCE ISSUES
───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

• Disk space is getting low.

                                                RECOMMENDATIONS
───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

→ Disk space is getting low. Consider removing unnecessary files or uninstalling unused applications.

                                               OVERALL ASSESSMENT
───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

⚠ Your system may be experiencing performance issues primarily due to low available disk space.

=======================================================================================================================
                                                END OF REPORT
=======================================================================================================================
```

### `top` — example output

```text
    PID  NAME                             CPU%     MEM%
-------------------------------------------------------
  15424  chrome.exe                      42.0      3.4
  12524  Code.exe                         3.7      3.4
   3628  MemCompression                   0.0      2.8
```

### `watch` — example output

The **console** shows one aligned status line per cycle (yellow if anything is
WARNING, red if CRITICAL), plus a `BREACH` / `RECOVERED` block when a state
changes:

```text
Monitoring every 5s (Ctrl+C to stop). Logging to logs/sysmonitor.log.
05:16:15Z   CPU   5.3% NORMAL   MEM  68.3% NORMAL   DISK  28.7% NORMAL
05:16:20Z   CPU  85.0% WARNING  MEM  68.3% NORMAL   DISK  28.7% NORMAL
  BREACH  cpu at 85.0% is WARNING (was NORMAL)
        22924  python.exe                    cpu  90.9%  mem   0.2%
        11472  Code.exe                      cpu  49.2%  mem   2.6%
         1968  dwm.exe                       cpu  13.3%  mem   1.0%
05:16:25Z   CPU  88.0% WARNING  MEM  68.3% NORMAL   DISK  28.7% NORMAL
^C
Stopped monitoring.
```

The **log file** gets a structured record for every cycle and every state change,
in the format from `logging.format`:

`json` (one object per line, for `jq` / log aggregators):

```text
{"time": "2026-09-07T05:16:15.680999+00:00", "level": "INFO", "message": "snapshot cpu=5.3% mem=68.3% disk=28.7%", "event": "snapshot", "cpu_percent": 5.3, "memory_percent": 68.3, "disk_percent": 28.7, "cpu_state": "NORMAL", "memory_state": "NORMAL", "disk_state": "NORMAL", "net_sent_bytes": 16554323, "net_recv_bytes": 142378209}
{"time": "2026-09-07T05:16:20.681000+00:00", "level": "WARNING", "message": "cpu at 85.0% is WARNING (was NORMAL)", "event": "threshold_breach", "metric": "cpu", "value": 85.0, "state": "WARNING", "previous_state": "NORMAL", "top_processes": [{"pid": 22924, "name": "python.exe", "cpu_percent": 90.9, "memory_percent": 0.2}]}
```

`text`:

```text
2026-09-07T05:16:15Z [INFO] snapshot cpu=5.3% mem=68.3% disk=28.7%
2026-09-07T05:16:20Z [WARNING] cpu at 85.0% is WARNING (was NORMAL)
```

**Debounced alerts.** `watch` only reacts when a metric's state *changes*, not
every cycle a breach is ongoing:

```text
cycle 1   cpu 75%  NORMAL   -> WARNING    breach   (top processes attached)
cycle 2   cpu 80%  WARNING  -> WARNING    nothing  (unchanged)
cycle 3   cpu 95%  WARNING  -> CRITICAL   breach   (escalation, re-scanned)
cycle 4   cpu 10%  CRITICAL -> NORMAL     recovery (threshold_cleared, no scan)
```

Every cycle still logs its `snapshot` at INFO; only the breach/recovery events
are debounced. Breaches log `threshold_breach` at WARNING (red on the console),
recoveries log `threshold_cleared` at INFO (green).

**Top processes on breach.** On a transition *into* a CPU or memory breach — once,
at the moment it starts, not every sustained cycle — `watch` scans the running
processes and attaches the top *N* (`top_n_processes` from config), sorted by the
metric that broke:

```text
  BREACH  cpu at 95.0% is CRITICAL (was NORMAL)
        26804  python.exe                    cpu  92.6%  mem   0.2%
         1968  dwm.exe                       cpu  10.9%  mem   0.9%
        11472  Code.exe                      cpu  10.5%  mem   2.6%
```

The JSON record carries the same list as a `top_processes` field. A **disk**
breach gets no process list — `psutil` has no cheap per-process disk metric, and
a list sorted by an unrelated metric would mislead more than it helps.

## ⚙️ Configuration

Runtime settings live in [`config/thresholds.yaml`](config/thresholds.yaml). A
committed [`config/thresholds.example.yaml`](config/thresholds.example.yaml)
serves as the reference copy; create `config/thresholds.local.yaml` (gitignored)
for machine-specific overrides.

```yaml
poll_interval_seconds: 5          # how often `watch` samples the system
top_n_processes: 5                # how many processes `top` / `watch` report

thresholds:                       # per-resource warning / critical cut-offs (%)
  cpu_percent:    { warning: 70, critical: 90 }
  memory_percent: { warning: 70, critical: 90 }
  disk_percent:   { warning: 70, critical: 90 }

logging:
  log_file: logs/sysmonitor.log
  format: json                    # "json" (one object per line) or "text"
```

The file is validated on load by a pydantic `AppConfig` model. Anything wrong —
a missing field, a wrong type, a threshold outside 0–100, `warning` not below
`critical`, or an unknown key — is reported as a single readable error rather
than a traceback.

**Missing config file:** sysmonitor fails with a clear message. It does *not*
fall back to built-in defaults — pointing the tool at a config that isn't there
is treated as a mistake worth stopping for. (The `analyze_performance` logic
still carries internal 70/90 defaults, but those are a code-level fallback, not
a substitute for the config file.)

### Logging

`watch` splits the live view from the log (`sysmonitor/logger.py`):

* **Console** — `watch` prints its own aligned, human-readable status line each
  cycle. The logger does *not* write to the console, so switching the file to
  `json` never turns the terminal into a wall of JSON.
* **Rotating file** — `RotatingFileHandler`, 5 MB per file, 3 backups, so an
  unattended run doesn't grow the log without bound.
* **`json` format** emits one object per line. Standard `time` / `level` /
  `message` plus per-event structured fields passed via `extra=` — a `snapshot`
  event carries the metric values and states; a `threshold_breach` event carries
  `metric` / `value` / `state` / `previous_state` (and `top_processes` for a
  CPU/memory breach). Each event carries only the fields relevant to it.
* **`text` format** is deliberately plain (`time [LEVEL] message`, UTC) and
  ignores the structured fields — use `json` when you need them.
* Every cycle logs at `INFO`; every threshold breach logs at `WARNING`.

## 🧪 Testing

`pytest` with `pytest-cov`. Every run prints a coverage report (`--cov` is in
`addopts`); the full suite is at **100%** line + branch coverage.

```bash
pytest                      # run tests + coverage report
pytest --cov-fail-under=100  # the gate CI would use
```

External state is never touched: `psutil` is mocked in the collector tests, the
CLI is driven through click's `CliRunner`, and config/log files are written under
`tmp_path`.

### Tested Modules

* `alerts` — `analyzer()`, `analyze_performance()`, `overall_assessment()`, `generate_recommendations()`, `detect_transitions()`
* `collector` — `get_system_snapshot()`, `get_top_processes()` (with `psutil` mocked)
* `config` — `load_config()` against valid and malformed YAML
* `logger` — JSON/text formatters, rotation config, idempotent setup
* `cli` — `snapshot` / `top` / `watch` via click's `CliRunner` (collector mocked)

### Test Scenarios

The test suite covers:

* Normal / warning / critical / mixed resource usage
* Boundary values such as 69%, 70%, 89%, and 90%
* Config-driven thresholds overriding the built-in 70/90 defaults
* Different combinations of CPU, RAM, and disk problems
* Recommendations for warning and critical resources
* Collector sorting by CPU or memory, and skipping dead / permission-denied / idle processes
* Config failure modes: missing file, broken YAML, missing field, wrong type,
  out-of-range threshold, `warning` ≥ `critical`, unknown key
* CLI: each subcommand runs, `--config` errors print cleanly (no traceback),
  `--n` overrides config, `watch --once` runs one cycle, Ctrl+C exits cleanly
* Logging: JSON formatter carries `extra=` fields, text formatter drops them,
  rotation is configured, `watch` writes `snapshot` + `threshold_breach` events
* Debounce: no alert while a state is unchanged; re-alert on escalation;
  `threshold_cleared` on recovery; first cycle only alerts if it starts breached
* Top-on-breach: CPU/memory breaches attach a metric-sorted `top_processes`
  list, scanned once per transition; disk breaches and recoveries attach nothing

### Current Test Result

```text
69 passed — 100% coverage
```

## 🛠️ Design Choices

**One module owns `psutil`.** `collector.py` is the only file that imports
`psutil`; everything downstream consumes its `SystemSnapshot` / `ProcessSnapshot`
models. That isolation is what lets the rest of the package be unit-tested with
`psutil` mocked, independent of the machine running the tests.

**Pure analysis layer.** `analyzer()` classifies one usage value; the rest of
`alerts.py` builds on it — `overall_assessment()` synthesises the per-resource
statuses into one sentence, `generate_recommendations()` produces advice for
anything in a warning or critical state. None of these do I/O, so they're
trivial to test at the boundaries.

**Two-tier thresholds, config-driven.** Each resource has a `warning` and a
`critical` cut-off (default 70 / 90), loaded from YAML and validated by pydantic.
This mirrors how real monitoring tools (Prometheus, Nagios) model severity, and
it keeps a judgment layer — "is this actually a problem, and how bad?" — on top
of the raw numbers rather than emitting a flat "over threshold" message.

**Fail loud on bad config.** A missing file, an out-of-range value, or
`warning ≥ critical` stops the program with a readable message instead of a
traceback or a silent fallback. "What's the failure mode?" should have a
deliberate answer.

**JSON logs with per-event structured fields.** The reason to pick JSON logging
over text is machine-parseability — so the fields live *as fields*
(`{"metric": "cpu", "value": 92.3, ...}`), not baked into a message string that
something downstream would have to regex apart. A custom `Formatter` lifts
anything passed via `extra=` into the object; text mode stays intentionally dumb.
`RotatingFileHandler` (5 MB × 3) keeps an unattended run bounded.

**Live view ≠ the log.** The logger writes only to the file. `watch` renders its
own console output — an aligned per-cycle status line, coloured by severity —
rather than piping the log format to the terminal. That's what lets the file be
`json` for machines without the operator staring at raw objects.

**Debounce as pure logic.** `detect_transitions(previous, current)` compares two
dicts of `metric → state` and returns a `StateTransition` for each change —
nothing more. The `watch` loop owns the one piece of mutable state (last cycle's
states) and does all the formatting. Same split as `analyze_performance`: pure
decision in `alerts.py`, I/O and state in the loop that drives it. A tool that
re-fires the same alert every 5 seconds is worse than useless in a real
workflow.

**Top processes only when they answer a question.** The process scan carries a
~100 ms cost (`psutil` needs two samples for per-process CPU). Running it every
poll would spend that on ~99% of cycles where nothing is wrong, and bloat every
`snapshot` line with a list no one reads. So it runs only on the transition
*into* a CPU/memory breach — the one moment "what's using it?" actually matters —
and not again while that breach is sustained, nor on recovery.

**`psutil` and Unicode status markers.** `psutil` gives cross-platform access to
CPU / memory / disk / network from Python; `✓ ⚠ ✗` make the three states
scannable in the terminal report (structured logs use the bare words).

## 📄 Requirements

* Python 3.11+
* `psutil` — system/process metrics
* `click` — CLI framework
* `PyYAML` — config parsing
* `pydantic` — config validation
* `pytest`, `pytest-cov` — tests + coverage (dev only)

Install the required libraries with:

```bash
pip install -r requirements.txt
```

## 🤝 Contributing

This is a learning project, but suggestions and improvements are welcome.

If you find a bug or have an idea for a feature, feel free to open an issue or submit a pull request.

## 👤 Author

**Akshata Singh**

---

⭐ If you find this project useful, consider giving it a star!

"""Command-line interface for sysmonitor.

Three commands, all sharing a ``--config`` option:

* ``snapshot`` - one reading, formatted report, exit.
* ``top``      - just the top-N process table.
* ``watch``    - poll on an interval, logging each cycle, until interrupted.

``watch`` logs every cycle at INFO and, debounced, every state change at
WARNING/INFO through :func:`sysmonitor.logger.get_logger`. On a transition *into*
a CPU or memory breach it also attaches the top-N processes (sorted by the
breached metric) so the log says what was responsible, not just that something
was wrong.
"""

import sys
import time

import click

from sysmonitor.alerts import (
    CRITICAL,
    NORMAL,
    WARNING,
    analyze_performance,
    detect_transitions,
    generate_recommendations,
    overall_assessment,
)
from sysmonitor.collector import get_system_snapshot, get_top_processes
from sysmonitor.config import DEFAULT_CONFIG_PATH, ConfigError, load_config
from sysmonitor.logger import get_logger


def config_option(func):
    """Reusable ``--config`` option with a sensible default."""
    return click.option(
        "--config",
        "config_path",
        default=DEFAULT_CONFIG_PATH,
        show_default=True,
        type=click.Path(dir_okay=False),
        help="Path to the YAML configuration file.",
    )(func)


def _load(config_path):
    """Load config, converting a ConfigError into a clean CLI error."""
    try:
        return load_config(config_path)
    except ConfigError as exc:
        raise click.ClickException(str(exc)) from exc


def _force_utf8_output():
    """Make stdout/stderr UTF-8 so the status symbols survive a pipe on Windows.

    Without this, printing '✓ ⚠ ✗' or the report's box-drawing characters to a
    redirected stream raises UnicodeEncodeError under the Windows cp1252 default.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8")
            except (ValueError, OSError):
                pass


@click.group()
@click.version_option(package_name="sysmonitor")
def cli():
    """sysmonitor - system and per-process resource monitoring."""
    _force_utf8_output()


# ------------------------------------------------------------------
# snapshot
# ------------------------------------------------------------------


@cli.command()
@config_option
def snapshot(config_path):
    """Take one system snapshot and print a formatted diagnostic report."""
    config = _load(config_path)
    snap = get_system_snapshot()

    cpu_performance, ram_performance, disk_performance = analyze_performance(
        snap.cpu_percent,
        snap.memory_percent,
        snap.disk_percent,
        thresholds=config.thresholds,
    )

    assessment = overall_assessment(
        cpu_performance, ram_performance, disk_performance
    )
    cpu_recommendation, ram_recommendation, disk_recommendation = (
        generate_recommendations(
            cpu_performance, ram_performance, disk_performance
        )
    )

    display_report(
        snap.cpu_percent,
        snap.memory_percent,
        snap.disk_percent,
        cpu_performance,
        ram_performance,
        disk_performance,
        cpu_recommendation,
        ram_recommendation,
        disk_recommendation,
        assessment,
    )


# ------------------------------------------------------------------
# top
# ------------------------------------------------------------------


@cli.command()
@click.option(
    "--by",
    type=click.Choice(["cpu", "memory"]),
    default="cpu",
    show_default=True,
    help="Sort processes by CPU or memory usage.",
)
@click.option(
    "--n",
    "count",
    type=click.IntRange(min=1),
    default=None,
    help="Number of processes to show [default: top_n_processes from config].",
)
@config_option
def top(by, count, config_path):
    """Print the top-N processes by CPU or memory usage."""
    config = _load(config_path)
    processes = get_top_processes(n=count or config.top_n_processes, by=by)
    _print_process_table(processes)


def _print_process_table(processes):
    click.echo(f"{'PID':>7}  {'NAME':<28}  {'CPU%':>7}  {'MEM%':>7}")
    click.echo("-" * 55)
    for proc in processes:
        click.echo(
            f"{proc.pid:>7}  {proc.name[:28]:<28}  "
            f"{proc.cpu_percent:>7.1f}  {proc.memory_percent:>7.1f}"
        )


# ------------------------------------------------------------------
# watch
# ------------------------------------------------------------------


@cli.command()
@click.option("--once", is_flag=True, help="Run a single cycle and exit.")
@config_option
def watch(once, config_path):
    """Poll the system on an interval, logging each cycle and any breaches."""
    config = _load(config_path)
    interval = config.poll_interval_seconds
    logger = get_logger(config.logging)

    click.echo(
        f"Monitoring every {interval:g}s "
        f"(Ctrl+C to stop){' - single cycle' if once else ''}. "
        f"Logging to {config.logging.log_file}."
    )

    previous_states: dict[str, str] = {}
    try:
        while True:
            previous_states = _watch_cycle(config, logger, previous_states)
            if once:
                break
            time.sleep(interval)
    except KeyboardInterrupt:
        click.echo("\nStopped monitoring.")


def _state_word(state: str) -> str:
    """'✓ NORMAL' -> 'NORMAL' - drop the display symbol for structured output."""
    return state.rsplit(" ", 1)[-1]


def _watch_cycle(config, logger, previous_states):
    """Run one poll cycle. Returns this cycle's states for the next call."""
    snap = get_system_snapshot()
    cpu_state, memory_state, disk_state = analyze_performance(
        snap.cpu_percent,
        snap.memory_percent,
        snap.disk_percent,
        thresholds=config.thresholds,
    )
    states = {"cpu": cpu_state, "memory": memory_state, "disk": disk_state}
    values = {
        "cpu": snap.cpu_percent,
        "memory": snap.memory_percent,
        "disk": snap.disk_percent,
    }

    logger.info(
        "snapshot cpu=%.1f%% mem=%.1f%% disk=%.1f%%"
        % (snap.cpu_percent, snap.memory_percent, snap.disk_percent),
        extra={
            "event": "snapshot",
            "cpu_percent": snap.cpu_percent,
            "memory_percent": snap.memory_percent,
            "disk_percent": snap.disk_percent,
            "cpu_state": _state_word(cpu_state),
            "memory_state": _state_word(memory_state),
            "disk_state": _state_word(disk_state),
            "net_sent_bytes": snap.net_sent_bytes,
            "net_recv_bytes": snap.net_recv_bytes,
        },
    )

    # Debounce: only react to a metric whose state changed since last cycle,
    # not to an ongoing breach every single poll.
    for transition in detect_transitions(previous_states, states):
        _report_transition(logger, config, transition, values[transition.metric])

    return states


# psutil exposes per-process CPU and memory cheaply, but not per-process disk -
# so a disk breach gets no "top processes" list rather than a misleading one.
_PROCESS_SORT_BY_METRIC = {"cpu": "cpu", "memory": "memory"}


def _top_processes_for(metric: str, count: int):
    """Top-N processes sorted by the breached metric, or None if not applicable."""
    sort_by = _PROCESS_SORT_BY_METRIC.get(metric)
    if sort_by is None:
        return None
    return get_top_processes(n=count, by=sort_by)


def _report_transition(logger, config, transition, value):
    metric = transition.metric
    current = _state_word(transition.current)
    previous = _state_word(transition.previous)

    if transition.current == NORMAL:
        logger.info(
            "%s recovered to NORMAL (was %s)" % (metric, previous),
            extra={
                "event": "threshold_cleared",
                "metric": metric,
                "value": value,
                "state": current,
                "previous_state": previous,
            },
        )
        click.secho(
            f"  RECOVERED  {metric} at {value:.1f}% (was {previous})", fg="green"
        )
        return

    # Transition *into* a breach: capture what's responsible, once, now.
    extra = {
        "event": "threshold_breach",
        "metric": metric,
        "value": value,
        "state": current,
        "previous_state": previous,
    }
    top = _top_processes_for(metric, config.top_n_processes)
    if top is not None:
        extra["top_processes"] = [p.model_dump() for p in top]

    logger.warning(
        "%s at %.1f%% is %s (was %s)" % (metric, value, current, previous),
        extra=extra,
    )
    click.secho(
        f"  BREACH  {metric} at {value:.1f}% is {current} (was {previous})",
        fg="red",
    )
    for proc in top or []:
        click.echo(
            f"      {proc.pid:>7}  {proc.name[:28]:<28}  "
            f"cpu {proc.cpu_percent:5.1f}%  mem {proc.memory_percent:5.1f}%"
        )


# ------------------------------------------------------------------
# snapshot report rendering (human-facing; watch uses the logger instead)
# ------------------------------------------------------------------


def display_report(
    cpu_usage,
    ram_usage,
    disk_usage,
    cpu_performance,
    ram_performance,
    disk_performance,
    cpu_recommendation,
    ram_recommendation,
    disk_recommendation,
    assessment,
):
    print("""
╔═════════════════════════════════════════════════════════════════════════════════════════════════════════════════════╗
║                                          SYSTEM DIAGNOSTIC REPORT                                                   ║
╚═════════════════════════════════════════════════════════════════════════════════════════════════════════════════════╝
""")

    print("""
                                              RESOURCE STATUS
───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
""")

    print(
        f"CPU       {cpu_usage}%     {cpu_performance}\n"
        f"RAM       {ram_usage}%     {ram_performance}\n"
        f"Disk      {disk_usage}%     {disk_performance}"
    )

    print("""
                                           LIKELY PERFORMANCE ISSUES
───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
""")

    if cpu_performance == WARNING:
        print("• CPU usage is high.")
    elif cpu_performance == CRITICAL:
        print("• CPU usage is critically high.")

    if ram_performance == WARNING:
        print("• Memory usage is high.")
    elif ram_performance == CRITICAL:
        print("• Memory usage is critically high.")

    if disk_performance == WARNING:
        print("• Disk space is getting low.")
    elif disk_performance == CRITICAL:
        print("• Disk space is critically low.")

    if (
        cpu_performance == NORMAL
        and ram_performance == NORMAL
        and disk_performance == NORMAL
    ):
        print("• No major performance issues detected.")

    print("""
                                                RECOMMENDATIONS
───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
""")

    if cpu_recommendation:
        print(f"→ {cpu_recommendation}")

    if ram_recommendation:
        print(f"→ {ram_recommendation}")

    if disk_recommendation:
        print(f"→ {disk_recommendation}")

    if not any([cpu_recommendation, ram_recommendation, disk_recommendation]):
        print("→ No recommendations. Your system resources are within normal ranges.")

    print("""
                                               OVERALL ASSESSMENT
───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
""")

    if "No major" in assessment:
        print(f"✓ {assessment}")
    else:
        print(f"⚠ {assessment}")

    print("""
=======================================================================================================================
                                                END OF REPORT
=======================================================================================================================
""")


if __name__ == "__main__":
    cli()

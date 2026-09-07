"""Command-line interface for sysmonitor.

Three commands, all sharing a ``--config`` option:

* ``snapshot`` - one reading, formatted report, exit.
* ``top``      - just the top-N process table.
* ``watch``    - poll on an interval until interrupted.

The structured logging inside ``watch`` (Phase 4) and the alert debounce
(Phase 5) are marked with TODOs below; today ``watch`` prints to the console.
"""

import time
from datetime import datetime, timezone

import click

from sysmonitor.alerts import (
    CRITICAL,
    NORMAL,
    WARNING,
    analyze_performance,
    generate_recommendations,
    overall_assessment,
)
from sysmonitor.collector import get_system_snapshot, get_top_processes
from sysmonitor.config import DEFAULT_CONFIG_PATH, ConfigError, load_config


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


@click.group()
@click.version_option(package_name="sysmonitor")
def cli():
    """sysmonitor - system and per-process resource monitoring."""


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
    """Poll the system on an interval, printing status and threshold breaches."""
    config = _load(config_path)
    interval = config.poll_interval_seconds

    click.echo(
        f"Monitoring every {interval:g}s "
        f"(Ctrl+C to stop){' - single cycle' if once else ''}."
    )

    try:
        while True:
            _watch_cycle(config)
            if once:
                break
            time.sleep(interval)
    except KeyboardInterrupt:
        click.echo("\nStopped monitoring.")


def _watch_cycle(config):
    snap = get_system_snapshot()
    cpu_performance, ram_performance, disk_performance = analyze_performance(
        snap.cpu_percent,
        snap.memory_percent,
        snap.disk_percent,
        thresholds=config.thresholds,
    )

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    click.echo(
        f"{stamp}   "
        f"CPU {snap.cpu_percent:5.1f}% {cpu_performance}   "
        f"RAM {snap.memory_percent:5.1f}% {ram_performance}   "
        f"Disk {snap.disk_percent:5.1f}% {disk_performance}"
    )

    # TODO(Phase 4): write a structured (json/text) log record for this cycle.
    # TODO(Phase 5): debounce - only alert on an OK -> breached transition
    #                instead of every cycle a breach is ongoing.
    readings = (
        ("CPU", snap.cpu_percent, cpu_performance),
        ("RAM", snap.memory_percent, ram_performance),
        ("Disk", snap.disk_percent, disk_performance),
    )
    for label, value, status in readings:
        if status != NORMAL:
            click.secho(f"  {status}  {label} at {value:.1f}%", fg="red")


# ------------------------------------------------------------------
# report rendering (moves to the logging layer in Phase 4)
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

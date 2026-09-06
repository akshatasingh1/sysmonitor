"""Command-line interface for sysmonitor.

Right now this exposes a single ``snapshot`` command that reproduces the
original one-shot diagnostic report. The ``watch`` and ``top`` commands, plus
``--config`` handling, arrive in later phases.
"""

import click

from sysmonitor.alerts import (
    CRITICAL,
    NORMAL,
    WARNING,
    analyze_performance,
    generate_recommendations,
    overall_assessment,
)
from sysmonitor.collector import get_system_stats


@click.group()
@click.version_option(package_name="sysmonitor")
def cli():
    """sysmonitor - system and per-process resource monitoring."""


@cli.command()
def snapshot():
    """Take one system snapshot and print a formatted diagnostic report."""
    cpu_usage, ram_usage, disk_usage = get_system_stats()

    cpu_performance, ram_performance, disk_performance = analyze_performance(
        cpu_usage, ram_usage, disk_usage
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
    )


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

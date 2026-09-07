"""Resource analysis and alerting logic.

Every function here is pure: it takes values in, returns values out, does no I/O
and no logging. That is what makes this module trivially unit-testable.
"""

NORMAL = "✓ NORMAL"
WARNING = "⚠ WARNING"
CRITICAL = "✗ CRITICAL"


# Fallback cut-offs used when no config-driven thresholds are supplied. These
# match the original hardcoded values, so callers that don't pass thresholds
# (and the tests that pin this behaviour) keep working unchanged.
DEFAULT_WARNING = 70
DEFAULT_CRITICAL = 90


def analyze_performance(cpu_usage, ram_usage, disk_usage, thresholds=None):
    """Classify each raw usage percentage into a status string.

    ``thresholds`` is an optional object with ``cpu_percent`` / ``memory_percent``
    / ``disk_percent`` attributes, each exposing ``warning`` and ``critical``
    (i.e. a :class:`sysmonitor.models.Thresholds`). When omitted, the default
    70 / 90 cut-offs apply to every resource.
    """
    if thresholds is None:
        return analyzer(cpu_usage), analyzer(ram_usage), analyzer(disk_usage)

    return (
        analyzer(cpu_usage, thresholds.cpu_percent.warning, thresholds.cpu_percent.critical),
        analyzer(ram_usage, thresholds.memory_percent.warning, thresholds.memory_percent.critical),
        analyzer(disk_usage, thresholds.disk_percent.warning, thresholds.disk_percent.critical),
    )


def analyzer(usage, warning=DEFAULT_WARNING, critical=DEFAULT_CRITICAL):
    """Map a usage percentage to NORMAL (< warning), WARNING (< critical) or CRITICAL."""
    if usage < warning:
        return NORMAL
    elif usage < critical:
        return WARNING
    else:
        return CRITICAL


def overall_assessment(cpu_performance, ram_performance, disk_performance):
    """Summarise the per-resource statuses into one human-readable sentence."""
    problems = []

    # CPU problems
    if cpu_performance == WARNING:
        problems.append("high CPU usage")
    elif cpu_performance == CRITICAL:
        problems.append("critically high CPU usage")

    # RAM problems
    if ram_performance == WARNING:
        problems.append("high memory usage")
    elif ram_performance == CRITICAL:
        problems.append("critically high memory usage")

    # DISK problems
    if disk_performance == WARNING:
        problems.append("low available disk space")
    elif disk_performance == CRITICAL:
        problems.append("critically low disk space")

    # No problems
    if not problems:
        return "No major resource bottlenecks detected. Your system resources are currently within normal ranges."

    # One problem
    if len(problems) == 1:
        return f"Your system may be experiencing performance issues primarily due to {problems[0]}."
    # Multiple problems
    elif len(problems) == 2:
        return f"Your system may be experiencing performance issues due to {problems[0]} and {problems[1]}."
    else:
        return f"Your system may be experiencing performance issues due to {problems[0]}, {problems[1]} and {problems[2]}."


def generate_recommendations(cpu_performance, ram_performance, disk_performance):
    """Return a recommendation string per resource (``None`` when NORMAL)."""
    cpu_recommendation = generate_cpu_recommendations(cpu_performance)
    ram_recommendation = generate_ram_recommendations(ram_performance)
    disk_recommendation = generate_disk_recommendations(disk_performance)

    return cpu_recommendation, ram_recommendation, disk_recommendation


def generate_cpu_recommendations(cpu_performance):
    if cpu_performance == WARNING:
        return (
            "CPU usage is high. Close unnecessary applications or background processes."
        )
    elif cpu_performance == CRITICAL:
        return "CPU usage is critically high. Close resource-intensive applications and check for processes consuming excessive CPU."


def generate_ram_recommendations(ram_performance):
    if ram_performance == WARNING:
        return "Memory usage is high. Close unnecessary applications and browser tabs to free up RAM."
    elif ram_performance == CRITICAL:
        return "Memory usage is critically high. Close memory-intensive applications and unnecessary browser tabs to free up RAM."


def generate_disk_recommendations(disk_performance):
    if disk_performance == WARNING:
        return "Disk space is getting low. Consider removing unnecessary files or uninstalling unused applications."
    elif disk_performance == CRITICAL:
        return "Disk space is critically low. Free up storage by removing unnecessary files and applications."

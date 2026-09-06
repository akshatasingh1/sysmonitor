# System Diagnostic Report

A Python-based system diagnostic tool that monitors CPU, RAM, and disk usage and provides recommendations for potential performance issues.

## 📋 Description

System Diagnostic Report is a Python program that checks the current system resource usage and generates a diagnostic report. The program checks CPU usage, RAM usage, and disk usage using the `psutil` library.

I made this project because I wanted to build something practical that uses Python to interact with the computer instead of just taking input and producing an output. The program gets the current CPU, RAM, and disk usage and then checks whether each resource is in a normal, warning, or critical state.

### Resource Status Levels

| Level        | Threshold     | Icon |
| :----------- | :------------ | :--: |
| **NORMAL**   | Below 70%     |   ✓  |
| **WARNING**  | 70% – 89%     |   ⚠  |
| **CRITICAL** | 90% and above |   ✗  |

## 🚀 Features

* 📊 Monitors CPU, RAM, and disk usage
* ⚠️ Identifies the current status of each resource
* 💡 Provides recommendations for resources with high usage
* 🔍 Generates an overall assessment of system performance
* 🧪 Includes automated tests using `pytest`
* 📋 Displays a formatted diagnostic report in the terminal
* 🔧 Uses separate functions for system statistics, analysis, recommendations, and reporting

## 📁 Project Structure

```text
system-diagnostic-report/
├── sysmonitor/                  # Package
│   ├── __init__.py
│   ├── cli.py                   # click CLI (snapshot; watch/top later)
│   ├── collector.py            # psutil access — the only module that touches it
│   ├── alerts.py               # pure analysis / assessment / recommendation logic
│   ├── config.py               # YAML + pydantic config loading (Phase 2)
│   ├── logger.py               # structured logging setup (Phase 4)
│   └── models.py               # pydantic data models
├── config/
│   ├── thresholds.yaml         # default config
│   └── thresholds.example.yaml # committed reference copy
├── tests/
│   └── test_alerts.py          # unit tests for the pure logic
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
git clone https://github.com/<your-username>/system-diagnostic-report.git
cd system-diagnostic-report
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

Take a one-shot diagnostic snapshot:

```bash
sysmonitor snapshot
```

The command collects the current CPU, RAM, and disk usage and prints a formatted diagnostic report. (`watch` and `top` subcommands are on the way.)

### Example Output

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

## 🧪 Testing

The project uses `pytest` to test the main functions.

Run the tests with:

```bash
pytest
```

### Tested Functions

* `analyze_performance()`
* `overall_assessment()`
* `generate_recommendations()`

### Test Scenarios

The test suite covers:

* Normal resource usage
* Warning resource usage
* Critical resource usage
* Mixed resource statuses
* Boundary values such as 69%, 70%, 89%, and 90%
* Different combinations of CPU, RAM, and disk problems
* Recommendations for warning and critical resources

### Current Test Result

```text
18 passed
```

## 🛠️ Design Choices

I divided the program into separate functions instead of putting everything inside `main()`. This makes the code easier to understand and allows individual parts of the program to be tested independently.

The `get_system_stats()` function collects the current CPU, RAM, and disk usage. The `analyze_performance()` function then determines the status of each resource.

The `overall_assessment()` function looks at the resource statuses and identifies the main performance problems. The `generate_recommendations()` function creates recommendations for resources that are in a warning or critical state.

Finally, `display_report()` presents the results in a formatted terminal report.

I chose 70% and 90% as the thresholds for the three resource states. Usage below 70% is considered normal, usage from 70% to 89% is considered a warning, and usage of 90% or higher is considered critical.

I used `psutil` because it provides a straightforward way to access system information such as CPU, memory, and disk usage from Python.

I also used Unicode symbols such as `✓`, `⚠`, and `✗` to make the different resource states easier to identify in the terminal.

## 📄 Requirements

* Python 3.11+
* `psutil` — system/process metrics
* `click` — CLI framework
* `PyYAML` — config parsing
* `pydantic` — config validation
* `pytest` — tests (dev only)

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

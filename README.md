# Coverity Metrics

A Python-based project to generate comprehensive metrics from Coverity's PostgreSQL database.

## Overview

This tool analyzes Coverity static analysis data stored in PostgreSQL and generates various metrics to help you understand code quality, defect trends, and development team activity.

**Quick Start:**
```bash
# Install
pip install -e .

# Configure
cp config.json.example config.json
# Edit config.json with your database credentials

# Generate interactive dashboard (CLI entry point)
coverity-dashboard

# Or run as a Python module
python -m coverity_metrics dashboard

# View technical debt and security metrics
# Check the "Trends & Progress" tab for technical debt estimation
# Check the "OWASP Top 10" and "CWE Top 25" tabs (project-level) for security
# Check the "Leaderboards" tab for team performance rankings
```

**What You Get:**
- 📊 Interactive HTML dashboards with Plotly visualizations
- ⏱️ Real-time progress tracking with ETA for long-running operations
- 💰 Technical debt estimation (estimated hours/days to remediate)
- 📅 Commit activity patterns (busiest/quietest times and days)
- 🔒 OWASP Top 10 2025 security compliance mapping
- 🛡️ CWE Top 25 2025 dangerous weakness tracking
- 🏆 Team and project leaderboards for gamification
- 📈 Defect velocity and trend analysis
- 🎯 File hotspots and complexity metrics
- 👥 User activity and triage progress

## Features


**What's New:** See [CHANGELOG.md](https://github.com/lejouni/coverity_metrics/blob/main/CHANGELOG.md) for the full per-version changelog and [RELEASE_NOTES.md](https://github.com/lejouni/coverity_metrics/blob/main/RELEASE_NOTES.md) for the narrative release notes. Recent releases are also listed on the [GitHub Releases page](https://github.com/lejouni/coverity_metrics/releases).

---

The tool provides the following metric categories:

### 1. **Defect Metrics**
- **Total Defects by Project**: Count of defects grouped by project with active/fixed breakdown
- **Defects by Severity**: Distribution across High/Medium/Low impact levels
- **Defects by Category**: Top defect categories (e.g., Security, Null pointer, Resource leak)
- **Defects by Checker**: Specific checkers finding the most defects
- **Defect Density**: Defects per 1000 lines of code (KLOC) by project/stream
- **File Hotspots**: Files with the highest concentration of defects

### 2. **Triage Metrics**
- **Defects by Triage Status**: Distribution by action (Fix Required, Ignore, etc.)
- **Defects by Classification**: Bug, False Positive, Intentional, etc.
- **Defects by Owner**: Defect ownership and assignment statistics

### 3. **Code Quality Metrics**
- **Code Metrics by Stream**: Lines of code, comment ratios, file counts
- **Function Complexity**: Distribution of cyclomatic complexity
- **Most Complex Functions**: Identify high-complexity functions needing refactoring
- **Comment Ratio**: Code documentation percentage

### 4. **Trend Metrics**
- **Weekly Defect Trend**: Defect count trends over time
- **Weekly File Count Trend**: Codebase growth tracking
- **Snapshot History**: Analysis run history with defect changes
- **Defect Velocity Trends**: Introduction vs fix rates over time
- **Cumulative Trend Analysis**: Long-term defect accumulation patterns
- **Technical Debt Estimation**: Hours/days/weeks to remediate all defects
  - Based on defect impact levels (High=4h, Medium=2h, Low=1h, Unspecified=0.5h)
  - Breakdown by severity with visual indicators
  - Total person-weeks capacity needed

### 5. **User Activity Metrics**
- **Login Statistics**: User engagement with the system
- **Active Triagers**: Most active users in defect triage
- **Session Analytics**: Average session duration per user

### 6. **Security Compliance Metrics** (ENHANCED!)
- **OWASP Top 10 2025**: Complete security posture visibility
  - **All 10 categories displayed** with PASS/FAILED status badges
  - 🟢 PASS (green badge): No defects for this category
  - 🔴 FAILED (red badge): Has defects requiring attention (clickable to expand)
  - CWE-based mapping to 10 critical web application security risks
  - Click FAILED categories to see ALL defects with CID, Type, Severity, File, Function
  - Summary metrics showing "X/10 Failed" counts
  - Visual differentiation: FAILED rows (red-tinted, clickable) vs PASS rows (green-tinted, faded)
  - Project-level security dashboards
- **CWE Top 25 2025**: Complete weakness coverage
  - **All 25 CWE entries displayed** with Status column and PASS/FAILED badges
  - Track MITRE's Most Dangerous Software Weaknesses
  - 25 ranked weaknesses based on real-world vulnerability data from NVD
  - Click FAILED entries to see complete defect lists
  - Industry-standard danger scores and rankings (1-25)
  - Helps prioritize remediation by recognized danger levels
  - Summary metrics showing "X/25 Failed" counts

### 7. **Competitive Leaderboards** (NEW!)
- **Top Projects by Fix Rate**: Projects ranked by defect elimination velocity
- **Top Projects by Triage Activity**: Most active triage engagement
- **Top Fixers (Users)**: Developers who eliminated the most defects
- **Top Triagers (Users)**: Most active users in defect classification
- **Most Collaborative Users**: Users working across multiple projects

### 8. **Performance Metrics**
- **Database Statistics**: Database size and growth tracking
- **Commit Performance**: Analysis duration (min/max/average times)
- **Commit Activity Patterns**: Busiest/quietest times (3-hour blocks) and days for commits
  - Temporal analysis of when commits occur (hour-by-hour, day-by-day)
  - Identifies peak development hours and quiet periods
  - Statistics: commit counts, average duration, files changed, defects introduced
  - Helps optimize team schedules and CI/CD resource allocation
- **Snapshot Performance**: Recent commit performance with queue times
- **Defect Discovery Rate**: Daily/weekly defect discovery trends
- **System Analytics**: Largest tables, resource utilization

### 9. **Summary Metrics**
- Overall counts: projects, streams, defects, files, functions, LOC
- High severity defect counts
- Active user counts

## Installation

### From PyPI (Recommended)

```bash
pip install coverity-metrics
```

This installs the CLI commands (`coverity-dashboard`, `coverity-metrics`,
`coverity-export`) and enables running as a Python module
(`python -m coverity_metrics`).

**No admin or root rights?** Use `pip install --user coverity-metrics` or
`pipx install coverity-metrics` — no privileges required. See
[INSTALL.md](INSTALL.md#installing-without-admin-or-root-rights) for details.

### From Source

```bash
# Clone or download this repository
git clone https://github.com/lejouni/coverity_metrics.git
cd coverity_metrics

# Install the package with all dependencies
pip install -e .
```

Editable mode is useful when you want to modify the source.

### Requirements

- **Python >= 3.10** (required by `pandas` >=3.0)

The package includes these dependencies (automatically installed):
- `pg8000` - Pure-Python PostgreSQL database adapter
- `pandas` - Data analysis and manipulation
- `python-dateutil` - Date/time utilities
- `jinja2` - HTML template engine for dashboard generation
- `plotly` - Interactive charts and visualizations
- `tqdm` - Progress bars

## Configuration

The tool requires configuration through `config.json`. Create this file with your Coverity instance(s) connection details:

```bash
cp config.json.example config.json
# Edit config.json with your database credentials
```

### Configuration File Format

```json
{
  "instances": [
    {
      "name": "Production",
      "description": "Production Coverity Instance",
      "enabled": true,
      "database": {
        "host": "coverity-server.company.com",
        "port": 5432,
        "database": "cim",
        "user": "coverity_ro",
        "password": "your_password_here"
      },
      "color": "#2c3e50"
    }
  ]
}
```

**Important:** 
- Add at least one instance with `"enabled": true`
- For single-instance mode: Configure one instance
- For multi-instance mode: Configure 2+ instances (auto-detected)
- Add `config.json` to `.gitignore` to protect credentials

### Finding the database credentials in your Coverity Connect installation

The database host, port, name, user, and password live in `cim.properties`
under the Coverity Connect installation directory. On the box that runs
Coverity Connect, look for the file at:

| OS | Typical path |
| -- | ------------ |
| Linux | `<coverity-install-dir>/config/cim.properties` (e.g. `/opt/coverity/connect/config/cim.properties`) |
| Windows | `<coverity-install-dir>\config\cim.properties` (e.g. `C:\Program Files\Coverity\Coverity Connect\config\cim.properties`) |

Map the properties into `config.json` (or the corresponding `COVERITY_DB_*`
environment variables) as follows:

| `cim.properties` key | `config.json` field | Env var |
| -------------------- | ------------------- | ------- |
| `cim.database.host` | `database.host` | `COVERITY_DB_HOST` |
| `cim.database.port` | `database.port` | `COVERITY_DB_PORT` |
| `cim.database.name` | `database.database` | `COVERITY_DB_NAME` |
| `cim.database.user` | `database.user` | `COVERITY_DB_USER` |
| `cim.database.password` | `database.password` | `COVERITY_DB_PASSWORD` |

Quick peek at just the relevant lines (paths adjusted to match your install):

```bash
# Linux
grep -E '^cim\.database\.(host|port|name|user|password)=' \
     /opt/coverity/connect/config/cim.properties
```

```powershell
# Windows (PowerShell)
Select-String -Path 'C:\Program Files\Coverity\Coverity Connect\config\cim.properties' `
              -Pattern '^cim\.database\.(host|port|name|user|password)='
```

Notes:
- The password in `cim.properties` is stored in cleartext. Only the OS user
  running the Coverity Connect service should have read access to this file.
- The bundled PostgreSQL that ships with Coverity Connect listens on **port
  `5433`** by default (not `5432`) so it doesn't clash with a system-wide
  PostgreSQL. Copy whatever port is in `cim.properties`.
- The default user is `coverity`. If your security policy prefers a
  read-only role (recommended), create one in Postgres and grant
  `pg_read_all_data` — the tool never issues DML against the schema.
- Copy the file (or just those five lines) off the Coverity Connect host over
  a secure channel; don't paste the password into chat or commit it to git.

### Configuring `coverity-export` / `coverity-dashboard` from environment variables

Both `coverity-export` and `coverity-dashboard` (in database mode) can also be run against a
single instance without a `config.json`, by providing the connection details through environment
variables. This is convenient in CI pipelines and containers where you'd rather not ship a config
file. No extra flag is needed — just set the variables and omit `--config`.

**Even simpler for end users** — pre-built quickstart scripts under
[scripts/](scripts/) ([coverity-export.sh](scripts/coverity-export.sh) for Linux,
[coverity-export.ps1](scripts/coverity-export.ps1) for Windows) download the
standalone binary for the latest (or a pinned) GitHub release, set these
variables from a block you edit at the top of the script, and run
`coverity-metrics export` in one shot. They forward `--tag`, `--output`,
`--days`, `--project`, `--anonymize`, `--no-snapshots`, and `--no-leaderboards`.

For `coverity-dashboard`, the env-var check only applies to **database mode**; when `--zip-file`
is given the tool reads from the ZIP and does not need a config or env vars.

| Variable | Required | Default | Description |
| -------- | -------- | ------- | ----------- |
| `COVERITY_DB_HOST` | yes | — | Hostname of the Coverity Postgres database |
| `COVERITY_DB_NAME` | yes | — | Database name (e.g. `cim`) |
| `COVERITY_DB_USER` | yes | — | Database user |
| `COVERITY_DB_PASSWORD` | yes | — | Database password |
| `COVERITY_DB_PORT` | no | `5432` | Database port |
| `COVERITY_INSTANCE_NAME` | no | `Coverity` | Instance name used in the ZIP filename / dashboard label |

Precedence used at startup (both tools):

1. `--config <file>` explicitly passed — load that JSON (fails if the file is missing). Multi-instance is supported here.
2. All required env vars set — single-instance env-var mode with an `[INFO]` message.
3. A `config.json` in the current directory — loaded automatically (backward compatible).
4. None of the above — the tool exits with a clear error listing both options.

Example (PowerShell):

```powershell
$env:COVERITY_DB_HOST     = "coverity-prod.company.com"
$env:COVERITY_DB_NAME     = "cim"
$env:COVERITY_DB_USER     = "coverity_ro"
$env:COVERITY_DB_PASSWORD = "***"
$env:COVERITY_INSTANCE_NAME = "Production"
coverity-export    --output exports --days 365
coverity-dashboard --output output  --days 365 --no-browser
```

Example (bash):

```bash
export COVERITY_DB_HOST=coverity-prod.company.com
export COVERITY_DB_NAME=cim
export COVERITY_DB_USER=coverity_ro
export COVERITY_DB_PASSWORD=***
export COVERITY_INSTANCE_NAME=Production
coverity-export    --output exports --days 365
coverity-dashboard --output output  --days 365 --no-browser
```

`coverity-metrics` still requires `config.json`; env-var mode is currently `coverity-export` and `coverity-dashboard`–only.

## Database Schema

The tool works with the following key Coverity database tables:

- **defect**, **stream_defect**, **defect_instance** - Defect information
- **checker**, **checker_properties** - Checker and severity data (includes CWE codes)
- **triage_state**, **defect_triage** - Triage information
- **stream**, **stream_file**, **stream_function** - Code structure
- **snapshot**, **snapshot_element** - Analysis snapshots and defect lifecycle
- **project**, **project_stream** - Project organization
- **users**, **user_login** - User activity
- **weekly_issue_count**, **weekly_file_count** - Trend data
- **dynamic_enum** - Classification, action, and severity enumerations

**NEW - Security Metrics Support:**
- **checker_properties.cwe** - CWE (Common Weakness Enumeration) codes used for OWASP Top 10 and CWE Top 25 mapping
- **dynamic_enum** - Severity values (Major, Moderate, Minor, Unspecified) mapped to security risk levels

## Usage

After installation, you can use the package in two ways: **Command-Line Interface (CLI)** or **Python Library**.

### Command-Line Interface (CLI)

The package provides three CLI commands for different use cases, each also available as a `python -m coverity_metrics <subcommand>`:

| Command | Module equivalent | Purpose | Output | Data Source | Best For |
|---------|------------------|---------|--------|-------------|----------|
| **coverity-dashboard** | `python -m coverity_metrics dashboard` | Visual HTML dashboard | Interactive HTML files with charts | Database **or** ZIP file | Presentations, visual analysis, sharing |
| **coverity-metrics** | `python -m coverity_metrics report` | Console text report | Terminal output (stdout) | Database only | Quick checks, CI/CD, piping |
| **coverity-export** | `python -m coverity_metrics export` | Data export | ZIP file with JSON | Database only | Offline dashboards, data delivery, archiving |

**Key Differences:**

- **coverity-dashboard**: Creates beautiful interactive HTML dashboards with Plotly charts, saved to `output/` directory. Can read from **database OR exported ZIP files** for offline use. Auto-opens in browser for easy viewing. Supports multi-instance aggregation.

- **coverity-metrics**: Prints all metrics as formatted text tables directly to your terminal. No files created. Great for quick command-line checks or redirecting to log files (`coverity-metrics > report.txt`).

- **coverity-export**: **NEW!** Exports all metrics to ZIP files. **When multiple instances are configured in config.json, a separate ZIP file is created for each instance.** The ZIP files can be transferred (email, file share) and used to generate dashboards offline without database access.

**Offline Dashboard Workflow:**

The new ZIP export/import feature enables dashboard generation without database access:

```bash
# 1. Export data from database (on machine with database access)
coverity-export --output exports --days 365 --config config.json

# With SINGLE instance in config.json:
# Creates: exports/coverity_export_Production_YYYYMMDD_HHMMSS.zip

# With MULTIPLE instances in config.json:
# Creates: exports/coverity_export_Production_YYYYMMDD_HHMMSS.zip
#          exports/coverity_export_Development_YYYYMMDD_HHMMSS.zip
#          exports/coverity_export_Staging_YYYYMMDD_HHMMSS.zip
# (one ZIP file per instance)

# 2. Transfer ZIP file(s) (email, USB, file share, etc.)
#    Each ZIP file is self-contained with all metrics for that instance

# 3. Generate dashboards offline (on any machine, no database needed!)
coverity-dashboard --zip-file coverity_export_Production_YYYYMMDD_HHMMSS.zip

# Filter by project:
coverity-dashboard --zip-file export.zip --project MyProject

# Filter by instance (when ZIP contains multiple instances):
coverity-dashboard --zip-file export.zip --instance Production
```

**Multi-ZIP Aggregation:**

**NEW!** You can combine multiple ZIP files to create an aggregated view. This is useful when:
- Instances are exported at different times
- Instances are on different networks
- You want to combine exports from different sources

```bash
# If you have separate ZIP files (from separate exports or from multi-instance export):
coverity-dashboard --zip-file exports/*.zip

# Or explicitly list them:
coverity-dashboard --zip-file \
  coverity_export_Production_YYYYMMDD_HHMMSS.zip \
  coverity_export_Development_YYYYMMDD_HHMMSS.zip \
  coverity_export_Staging_YYYYMMDD_HHMMSS.zip

# This generates:
#   - Aggregated dashboard combining all instances (dashboard_aggregated.html)
#   - Per-instance dashboards for each ZIP (Production, Development, Staging)
#   - Per-project dashboards for all projects in all instances
```

**Use Cases for Multi-ZIP Aggregation:**
- **Different Networks**: Export from prod/dev instances on isolated networks, combine on analysis machine
- **Different Time Zones**: Collect exports from global teams and merge
- **Staggered Exports**: Don't wait for all instances - export when ready, aggregate later
- **Air-Gapped Delivery**: Transfer multiple ZIP files via USB/file share, combine offline
- **Historical Comparison**: Merge current exports with archived historical snapshots

**Benefits:**
- Share metrics with stakeholders without database credentials
- Generate dashboards on air-gapped networks
- Archive historical metrics snapshots
- Reduce database load by using cached exports
- Easy delivery of reports to management
- **NEW:** Flexible multi-instance aggregation without simultaneous database access

---

#### 1. Generate Dashboard (Main Tool)

**Data Sources**:
- **Database Mode**: Direct PostgreSQL connection (requires `config.json`)
- **ZIP File Mode**: Exported ZIP file (no database needed)

```bash
# ========== DATABASE MODE ==========
# Basic usage - auto-detects instance type from config.json
coverity-dashboard

# Filter by specific project across all instances
coverity-dashboard --project "MyProject"

# Filter by multiple projects (comma-separated)
coverity-dashboard --project "AppA,AppB,AppC"

# Generate for specific instance only
coverity-dashboard --instance Production

# Change trend analysis period (default: 365 days)
coverity-dashboard --days 180

# Custom output folder
coverity-dashboard --output reports/2026

# Enable caching for better performance
coverity-dashboard --cache --cache-ttl 86400

# Generate without opening browser
coverity-dashboard --no-browser  

# Use different configuration file
coverity-dashboard --config my-config.json

# ========== ZIP FILE MODE (OFFLINE) ==========
# Generate from exported ZIP file (no database required!)
coverity-dashboard --zip-file exports/coverity_export_Production_20260224_120000.zip

# ZIP mode with project filter (single or multiple)
coverity-dashboard --zip-file exports/coverity_export_Production_20260224_120000.zip --project MyProject
coverity-dashboard --zip-file exports/coverity_export_Production_20260224_120000.zip --project "AppA,AppB"

# ZIP mode with instance filter (single ZIP only)
coverity-dashboard --zip-file exports/coverity_export_Prod_Dev_20260224_120000.zip --instance Production

# ZIP mode with custom output
coverity-dashboard --zip-file export.zip --output offline_reports --no-browser

# ========== MULTI-ZIP AGGREGATION (NEW!) ==========
# Combine multiple ZIP files from different instances
coverity-dashboard --zip-file prod_export.zip dev_export.zip staging_export.zip

# Multi-ZIP with project filter (searches across all instances)
coverity-dashboard --zip-file file1.zip file2.zip file3.zip --project MyApp

# Multi-ZIP with wildcard
coverity-dashboard --zip-file exports/*.zip --no-browser
```

**Auto-Detection Behavior (Database Mode):**
- **config.json is required** with at least one enabled instance configured
- If `config.json` has **2+ enabled instances**: Multi-instance mode (generates aggregated + per-instance + per-project dashboards)
- If `config.json` has **1 enabled instance**: Single-instance mode (generates dashboard for that instance)
- Use `--project` to filter by one or more projects (comma-separated: `--project "AppA,AppB"`)
- Use `--instance` to generate for specific instance only (multi-instance mode)
- Use `--single-instance-mode` to force single-instance behavior even with multiple instances

**ZIP File Mode Behavior:**
- Automatically uses ZIP as data source when `--zip-file` is specified
- No `config.json` needed
- Auto-selects first instance in ZIP if not specified
- Use `--instance` to select specific instance from ZIP
- Use `--project` to filter by one or more projects, comma-separated (same as database mode)

### CLI Parameters Reference

#### coverity-dashboard Parameters

| Parameter | Short | Type | Default | Description |
|-----------|-------|------|---------|-------------|
| `--project` | `-p` | string | None | Filter metrics by project name(s). Use comma-separated values for multiple projects (e.g. `AppA,AppB,AppC`). Multiple projects generate per-project dashboards plus an aggregated instance dashboard |
| `--output` | `-o` | string | `output` | Output folder path for dashboard files |
| `--no-browser` | - | flag | False | Do not open dashboard in browser automatically |
| `--workers` | `-w` | integer | `1` | **NEW!** Number of parallel workers for per-project dashboard generation. Clamped to 1–8. In database mode each worker uses its own Postgres connection; in ZIP mode each worker uses its own `ZipDataLoader` |
| `--zip-file` | `-z` | string(s) | None | Use exported ZIP file(s) as data source instead of database. Supports multiple files for multi-instance aggregation |
| `--config` | `-c` | string | `config.json` | Path to configuration file (not needed for ZIP mode) |
| `--instance` | `-i` | string | None | Generate dashboard for specific instance only |
| `--single-instance-mode` | - | flag | False | Force single-instance mode even with multiple instances in config |
| `--cache` | - | flag | False | Enable caching to speed up subsequent generations (database mode only) |
| `--cache-dir` | - | string | `cache` | Directory for cache files |
| `--cache-ttl` | - | integer | `24` | Cache time-to-live in hours |
| `--clear-cache` | - | flag | False | Clear all cached data before generating |
| `--cache-stats` | - | flag | False | Display cache statistics and exit |
| `--no-cache` | - | flag | False | Force refresh data from database, bypass cache |
| `--days` | `-d` | integer | `365` | Number of days for trend analysis |
| `--track-progress` | - | flag | False | Enable progress tracking for large operations |
| `--resume` | - | string | None | Resume from interrupted session (provide session ID) |
| `--version` | - | flag | False | Print version and exit |

**Examples:**
```bash
# Basic dashboard with caching
coverity-dashboard --cache

# Filter by project with 180-day trends
coverity-dashboard --project "MyApp" --days 180

# Generate without browser, custom output
coverity-dashboard --no-browser --output reports/weekly

# Parallelize per-project dashboard generation (NEW in 1.0.17)
coverity-dashboard --workers 4                          # 4 workers, database mode
coverity-dashboard --workers 4 --zip-file export.zip    # 4 workers, ZIP mode

# Clear cache and regenerate
coverity-dashboard --clear-cache --no-cache

# View cache statistics
coverity-dashboard --cache-stats
```

#### coverity-metrics Parameters

| Parameter | Short | Type | Default | Description |
|-----------|-------|------|---------|-------------|
| `--zip-file` | `-z` | string(s) | None | Read metrics from exported ZIP file(s) instead of database |
| `--config` | `-c` | string | `config.json` | Path to configuration file (default: `config.json`) |
| `--version` | - | flag | False | Print version and exit |

The tool:
- Automatically uses the first enabled instance from `config.json` when no `--zip-file` is given
- Prints formatted tables directly to stdout
- Can be redirected to files: `coverity-metrics > report.txt`

#### coverity-export Parameters

**NEW!** Exports all metrics to ZIP files. **Creates a separate ZIP file for each configured instance.**

| Parameter | Short | Type | Default | Description |
|-----------|-------|------|---------|-------------|
| `--output` | `-o` | string | `exports` | Output directory for ZIP files |
| `--days` | `-d` | integer | `365` | Number of days for trend analysis |
| `--config` | `-c` | string | `config.json` | Path to configuration file |
| `--project` | `-p` | string | None | Comma-separated list of project names to export (default: all projects) |
| `--workers` | `-w` | integer | `1` | **NEW!** Number of parallel workers for per-project export. Clamped to 1–8. Each worker uses its own Postgres connection. Recommended: `--workers 4` for large deployments (645+ projects) |
| `--anonymize` | - | flag | False | **NEW in 1.0.19!** Replace real project and stream names in the ZIP with sequential `project_NNN` / `stream_NNN` ids and write a sibling `<zip>.mapping.json` file that maps the ids back to real names. See [Sharing exports without disclosing project names](#sharing-exports-without-disclosing-project-names) below |
| `--mapping-file` | - | string | None | Path to an anonymization mapping JSON. If it exists, it is loaded so ids stay stable across re-exports; the (possibly extended) mapping is written back to the same path. Only used with `--anonymize` |
| `--no-leaderboards` | - | flag | False | **NEW in 1.0.19!** Skip the five Leaderboards metrics (`top_projects_by_fix_rate`, `top_projects_by_triage_activity`, `top_users_by_fixes`, `top_triagers`, `most_collaborative_users`). Dashboards generated from the resulting ZIP automatically hide the 🏆 Leaderboards tab |
| `--no-snapshots` | - | flag | False | **NEW in 1.0.19!** Skip the `snapshot_commands` metric (recorded `cov-build`/`cov-analyze` command lines, invoker, host, platform). Project dashboards generated from the resulting ZIP automatically hide the 📸 Snapshots tab |
| `--version` | - | flag | False | Print version and exit |

The tool:
- **Creates a separate ZIP file for each enabled instance** from `config.json`
- Each ZIP file is named: `{output}/coverity_export_{InstanceName}_{YYYYMMDD_HHMMSS}.zip`
- Each ZIP contains JSON files with all metrics for that instance
- Includes metadata.json with export info, instance name, and project list
- ZIP files are self-contained and can be used for offline dashboard generation
- Multiple ZIP files can be combined using `coverity-dashboard --zip-file file1.zip file2.zip ...`

**Examples:**
```bash
# Basic export (365 days, all instances)
coverity-export
# Single instance: exports/coverity_export_Production_20260224_120000.zip
# Multiple instances: exports/coverity_export_Production_20260224_120000.zip
#                     exports/coverity_export_Development_20260224_120000.zip
#                     exports/coverity_export_Staging_20260224_120000.zip

# Custom trend period and output location
coverity-export --output archive --days 90
# Output: archive/coverity_export_{InstanceName}_20260224_120000.zip (one per instance)

# Use custom config file
coverity-export --config my-config.json --days 180

# Parallelize per-project export for large deployments (NEW in 1.0.17)
coverity-export --workers 4
# 4 workers → ~4× faster on 645-project instances vs. sequential.
# Each worker keeps its own Postgres connection; cap is 8.
```

##### Sharing exports without disclosing project names

**New in 1.0.19.** If you want to send a Coverity export to someone outside your organization
(a consultant, an auditor, a support engineer) but the real project and stream names are
sensitive, add `--anonymize`:

```bash
coverity-export --anonymize
# → exports/coverity_export_Production_20260805_130613.zip           (safe to share)
# → exports/coverity_export_Production_20260805_130613.mapping.json  (keep private)
```

Inside the ZIP, every real project name is replaced with `project_001`, `project_002`, …
and every real stream name with `stream_001`, `stream_002`, … — in the directory layout, in
`metadata.json`, and in every `project_name` / `stream_name` column of every exported JSON.
The sibling `.mapping.json` file lists the mapping so **you** can decode it later; the ZIP
alone cannot be reverse-mapped.

To keep ids stable across re-exports (so `project_001` always means the same real project),
point `--mapping-file` at a persistent path:

```bash
coverity-export --anonymize --mapping-file .\anon-map.json
# First run creates .\anon-map.json.
# Later runs load it, assign next-available ids to any new projects, and save back.
```

`*.mapping.json` is included in `.gitignore` so it won't be committed accidentally.
Instance names, host, database, and user/committer names are **not** anonymized in this
release; only project and stream names are.

---

#### 2. Console Metrics Report

**Outputs**: Text tables printed to terminal (no files created)

```bash
# Generate console metrics report
coverity-metrics

# Redirect to file
coverity-metrics > daily-report.txt

# Redirect with timestamp
coverity-metrics > "report-$(date +%Y%m%d).txt"
```

**Use Cases:**
- Quick command-line checks
- Automated CI/CD pipelines
- SSH sessions without GUI
- Piping to log files or other tools

**Note:** Supports `--zip-file`, `--config`, and `--version`. To filter by project or instance, modify `config.json` before running.

#### 3. Export to ZIP (NEW!)

**Outputs**: Single ZIP file containing all metrics for all instances in JSON format

```bash
# Basic export
coverity-export

# Custom output directory and trend period
coverity-export --output monthly_archives --days 30

# Export for long-term analysis
coverity-export --days 730 --output historical
```

**What Gets Exported:**

The ZIP file contains:
- **All Metrics (JSON)**: Defects, trends, hotspots, code metrics, performance stats, activity patterns
- **Project-Specific Data**: OWASP Top 10 and CWE Top 25 metrics per project
- **Metadata (JSON)**: Export timestamp, instance names, project lists, configuration snapshot

**ZIP File Structure:**

Each instance gets its own ZIP file with the following structure:

```
coverity_export_Production_YYYYMMDD_HHMMSS.zip
├── metadata.json                    # Export metadata (timestamp, instance info, etc.)
└── Production/                      # Instance folder
    ├── overall_summary.json         # Instance-level metrics
    ├── defects_by_project.json
    ├── defects_by_severity.json
    ├── technical_debt_summary.json
    ├── ... (other instance metrics)
    ├── MyProject/                   # Project-specific folder
    │   ├── owasp_top10_metrics.json
    │   ├── cwe_top25_metrics.json
    │   ├── owasp_A01_details.json
    │   └── cwe_79_details.json
    └── AnotherProject/              # Another project folder
        └── ... (project metrics)
```

When multiple instances are configured, you get multiple ZIP files:
```
exports/
├── coverity_export_Production_YYYYMMDD_HHMMSS.zip
├── coverity_export_Development_YYYYMMDD_HHMMSS.zip
└── coverity_export_Staging_YYYYMMDD_HHMMSS.zip
```

**Use Cases:**
- Offline dashboard generation (no database access needed)
- Sharing metrics with stakeholders without credentials
- Historical snapshots and archiving
- Air-gapped network deployments
- Reducing database load with cached exports
- Selective instance sharing (send only specific instance ZIPs)

---

### Typical Workflow

**Daily Quick Check:**
```bash
# Fast terminal check
coverity-metrics
```

**Weekly Team Review:**
```bash
# Generate visual dashboard for presentation
coverity-dashboard --cache
# Opens interactive HTML in browser
```

**Monthly Executive Report:**
```bash
# Visual dashboard
coverity-dashboard --days 90 --cache

# Export data for custom Excel charts
coverity-export
```

**Offline Dashboard Delivery (NEW!):**
```bash
# SINGLE INSTANCE:
# On machine with database access:
coverity-export --days 365 --output deliverables

# Transfer ZIP file (email, file share, USB):
# deliverables/coverity_export_Production_YYYYMMDD_HHMMSS.zip

# On stakeholder's machine (no database access):
coverity-dashboard --zip-file coverity_export_Production_YYYYMMDD_HHMMSS.zip

# Result: Full interactive dashboards without database!

# MULTI-INSTANCE AGGREGATION:
# Export from each instance separately:
# Instance A: coverity-export --output exports_prod
# Instance B: coverity-export --output exports_dev
# Instance C: coverity-export --output exports_staging

# Transfer all ZIP files, then aggregate:
coverity-dashboard --zip-file exports_prod/*.zip exports_dev/*.zip exports_staging/*.zip

# Result: Combined dashboards from all instances offline!
```

**Complete Analysis Workflow:**
```bash
# 1. Quick overview in terminal
coverity-metrics

# 2. Generate interactive dashboard
coverity-dashboard --cache --no-browser

# 3. Export for offline delivery
coverity-export --days 365

# Now you have:
# - Console output for quick reference
# - HTML dashboards (output/dashboard.html) for presentations
# - ZIP file (exports/*.zip) for offline dashboards and archiving
```

**Quarterly Comparison Workflow (NEW!):**

Run `coverity-export` at the end of each quarter with the **same `--days`
value and the same `--mapping-file`**, archive the resulting ZIPs, then
use `coverity-delta` to produce an adoption-focused delta report:

```bash
# End of Q1: export with a shared mapping file so anonymized project ids
# stay stable across every future quarterly snapshot.
coverity-export --days 90 \
    --anonymize --mapping-file archive/quarterly-mapping.json \
    --output archive/2026-Q1

# End of Q2: same --days, same --mapping-file. The mapping file is
# extended in-place for any new projects; existing projects keep their
# ids.
coverity-export --days 90 \
    --anonymize --mapping-file archive/quarterly-mapping.json \
    --output archive/2026-Q2

# Compare the two snapshots. Runs entirely offline — no database access.
coverity-delta \
    --previous archive/2026-Q1/coverity_export_Production_*.zip \
    --current  archive/2026-Q2/coverity_export_Production_*.zip \
    --output delta/2026-Q1_vs_Q2

# Produces:
#   delta/2026-Q1_vs_Q2/delta.json           (schema v1, machine-readable)
#   delta/2026-Q1_vs_Q2/dashboard_delta.html (self-contained HTML report)
```

The delta report focuses on the metrics that matter for a quarterly
customer-adoption story:

- **Projects added / dropped / retained** between the two snapshots.
- **Active-user Δ** — licensed, logged-in, active user counts + %Δ.
- **Scan-activity Δ** — snapshots taken, files analyzed, defects
  introduced, defects eliminated inside each `--days` window.
- **Stream activity** — set diff on the recent-snapshot sample: streams
  newly active (present in the current sample only) and streams that
  went dark (present in the previous sample only). Deliberately reports
  set membership rather than per-stream counts — the underlying
  `snapshot_performance` metric is a top-100 sample, so count deltas
  from it are dominated by top-N sliding, not by real activity.
- **Defects-by-project Δ** — outstanding / fixed counts + ranking movement
  (▲ climbed the outstanding-defects ranking, ▼ dropped, `new` /
  `dropped` for projects only present in one snapshot).

**Guardrails.** `coverity-delta` refuses to compare snapshots that used
different `--days` windows or different anonymization mappings — those
comparisons are almost always meaningless. Two escape hatches exist:

- `--allow-window-mismatch` — for testing / advanced use only. Every
  windowed metric is tagged with a ⚠ marker in the report and a
  `window_mismatch` entry appears in `delta.json.warnings`. Also emits a
  `normalized_per_day` view alongside the raw totals so the numbers stay
  meaningful.
- Anonymization mismatch has no override: fix the workflow by re-running
  both exports with the same `--mapping-file`.

### Python Library Usage

You can also use the package programmatically in your Python code:

```python
from coverity_metrics import CoverityMetrics, MultiInstanceMetrics, InstanceConfig

# Single instance usage
metrics = CoverityMetrics(
    connection_params={
        'host': 'localhost',
        'port': 5432,
        'database': 'coverity',
        'user': 'postgres',
        'password': 'your_password'
    },
    project_name='MyProject'  # Optional project filter
)

# Get metrics with default limits (top N results)
top_categories = metrics.get_defects_by_checker_category(limit=10)  # Top 10
file_hotspots = metrics.get_file_hotspots(limit=20)  # Top 20

# Get ALL data using fetch_all parameter
all_categories = metrics.get_defects_by_checker_category(fetch_all=True)  # All categories
all_hotspots = metrics.get_file_hotspots(fetch_all=True)  # All files with defects
all_snapshots = metrics.get_snapshot_history(fetch_all=True)  # All snapshot history

# NEW! Technical Debt Estimation
tech_debt = metrics.get_technical_debt_summary()
print(f"Total effort: {tech_debt['total_hours']} hours ({tech_debt['total_days']} days)")
print(f"High impact: {tech_debt['breakdown']['High']['hours']} hours")

# NEW! Security Compliance Metrics
owasp_metrics = metrics.get_owasp_top10_metrics()  # OWASP Top 10 2025
cwe_metrics = metrics.get_cwe_top25_metrics()      # CWE Top 25 2025

# NEW! Leaderboard Metrics
top_fixers = metrics.get_top_users_by_fixes(days=30, limit=10)
top_projects = metrics.get_top_projects_by_fix_rate(days=30, limit=10)
improved_projects = metrics.get_most_improved_projects(days=90, limit=10)

# Other methods with fetch_all support:
# - get_defects_by_checker_name(limit=20, fetch_all=False)
# - get_defects_by_owner(limit=20, fetch_all=False)
# - get_most_complex_functions(limit=20, fetch_all=False)

# Multi-instance usage
instances = [
    InstanceConfig("Production", {...connection_params...}),
    InstanceConfig("Development", {...connection_params...})
]

multi = MultiInstanceMetrics(instances)
aggregated = multi.get_aggregated_metrics()
```

See [INSTALL.md](INSTALL.md) for detailed API examples.

### Dashboard Features
- **Project Filtering**: View metrics for all projects or filter by specific project
- **Project Navigation**: Easy navigation between project-specific dashboards
- **Tabbed Interface**: Organized into multiple specialized views:
  - **Overview**: Summary metrics, defect distribution, severity analysis
  - **Code Quality**: Complexity metrics, hotspots, code coverage
  - **Performance & Analytics**: Database stats, commit performance
  - **Trends & Progress**: Velocity trends, triage progress, **technical debt estimation**
  - **Leaderboards**: 🏆 Competitive rankings (projects, users, fixers, triagers)
  - **OWASP Top 10**: 🔒 Security compliance (project-level only)
  - **CWE Top 25**: 🛡️ Dangerous weakness tracking (project-level only)
- Summary cards with key metrics and visual indicators
- Interactive Plotly charts for severity distribution, project comparison
- File hotspots with detailed tables and defects per KLOC
- Code quality metrics visualization
- Function complexity distribution
- Top defect checkers and categories
- **Technical Debt Metrics** (NEW!):
  - Total estimated hours/days/weeks to fix all defects
  - Breakdown by impact level (High/Medium/Low/Unspecified)
  - Industry-standard effort estimates per severity
  - Visual cards with color-coded severity indicators
- **Security Compliance** (NEW!):
  - OWASP Top 10 2025 categories with CWE mappings
  - CWE Top 25 2025 most dangerous weaknesses
  - Severity breakdown per category/weakness
  - Project-level security dashboards only
- **Leaderboard Rankings** (NEW!):
  - Top 10 projects by fix velocity, improvement, triage activity
  - Top 10 users by actual fixes (code eliminations)
  - Top 10 triagers by classification activity
  - Most collaborative users across projects
- **Performance metrics**:
  - Database size and statistics
  - Commit/analysis performance (min/max/average times)
  - Recent snapshot performance with queue times
  - Defect discovery rate trends
  - Largest database tables
- Responsive design for mobile/tablet viewing
- Print-friendly layout

**Dashboard Files Generated:**
- `output/dashboard.html` - Global view of all projects
- `output/dashboard_{ProjectName}.html` - Project-specific dashboards

### Multi-Instance Support

**For environments with multiple Coverity instances, the tool now auto-detects your configuration:**

Configure multiple Coverity instances in `config.json`:

```json
{
  "instances": [
    {
      "name": "Production",
      "description": "Production Coverity Instance",
      "enabled": true,
      "database": {
        "host": "coverity-prod.company.com",
        "port": 5432,
        "database": "cim",
        "user": "coverity_ro",
        "password": "your_password"
      },
      "color": "#2c3e50"
    },
    {
      "name": "Development",
      "description": "Development Coverity Instance",
      "enabled": true,
      "database": {
        "host": "coverity-dev.company.com",
        "port": 5432,
        "database": "cim",
        "user": "coverity_ro",
        "password": "your_password"
      },
      "color": "#3498db"
    }
  ],
  "aggregated_view": {
    "enabled": true,
    "name": "All Instances"
  }
}
```

**Simplified Multi-Instance Commands:**

```bash
# Generate everything - automatically creates:
#   - Aggregated dashboard across all instances
#   - Individual dashboard for each instance
#   - Project dashboards for all projects in each instance
coverity-dashboard

# Filter by specific project across all instances
coverity-dashboard --project MyApp

# Generate for specific instance only (with all its projects)
coverity-dashboard --instance Production

# Generate specific project on specific instance only
coverity-dashboard --instance Production --project MyApp

# Use custom configuration file
coverity-dashboard --config my-config.json
```

**What Gets Generated Automatically:**

When you run `coverity-dashboard` with a multi-instance config.json:
1. **Aggregated Dashboard** (`output/dashboard_aggregated.html`) - Combined view of all instances
2. **Instance Dashboards** (`output/{InstanceName}/dashboard.html`) - One per instance
3. **Project Dashboards** (`output/{InstanceName}/dashboard_{ProjectName}.html`) - All projects for each instance

**Multi-Instance Dashboard Features:**
- **Aggregated View**: Combined metrics from all Coverity instances
- **Instance Comparison Charts**: Side-by-side defect count comparison
- **Color-Coded Instances**: Visual differentiation of instances
- **Cross-Instance Project List**: All projects with instance attribution
- **Per-Instance Dashboards**: Individual dashboards for each instance
- **Instance Filtering**: Navigate between instances easily

For detailed multi-instance setup and usage, see [MULTI_INSTANCE_GUIDE.md](MULTI_INSTANCE_GUIDE.md)

For multi-ZIP aggregation (combine exports from different instances), see [MULTI_ZIP_GUIDE.md](MULTI_ZIP_GUIDE.md)

### Performance & Caching

**For large deployments with many instances/projects, enable caching to dramatically improve performance:**

```bash
# Enable caching (24-hour TTL by default)
coverity-dashboard --cache

# Custom cache TTL (48 hours)
coverity-dashboard --cache --cache-ttl 48

# View cache statistics
coverity-dashboard --cache-stats

# Clear expired cache entries
coverity-dashboard --clear-cache

# Force refresh (bypass cache)
coverity-dashboard --no-cache
```

**Performance Benefits:**
- **First run**: Same time as without caching (cache is built)
- **Subsequent runs**: 90-95% faster (uses cached data)
- **Example**: 30 minutes → 2 minutes for 10 instances × 100 projects

**Progress Tracking for Large Operations:**

```bash
# Enable progress tracking (for resumable operations)
coverity-dashboard --cache --track-progress

# Resume interrupted session
coverity-dashboard --cache --resume SESSION_ID
```

For detailed caching configuration, performance tuning, and troubleshooting, see [CACHING_GUIDE.md](CACHING_GUIDE.md)

### Export to JSON

Export all metrics to JSON files packaged in a ZIP:

```bash
coverity-export
```

This creates a timestamped ZIP file in the `exports/` directory containing all metrics in JSON format. See the [Export to ZIP section](#3-export-to-zip-new) above for details.

### Use Individual Metrics

You can also use the metrics module programmatically:

```python
from coverity_metrics import CoverityMetrics

# Initialize with connection parameters
connection_params = {
    'host': 'localhost',
    'port': 5432,
    'database': 'coverity',
    'user': 'postgres',
    'password': 'your_password'
}

metrics = CoverityMetrics(connection_params=connection_params)

# Get specific metrics (top N results)
defects_by_severity = metrics.get_defects_by_severity()
print(defects_by_severity)

# Get defect density
density = metrics.get_defect_density_by_project()
print(density)

# Get top 10 file hotspots
hotspots = metrics.get_file_hotspots(limit=10)
print(hotspots)

# Get ALL file hotspots (not just top 10)
all_hotspots = metrics.get_file_hotspots(fetch_all=True)
print(f"Found {len(all_hotspots)} files with defects")

# Get overall summary
summary = metrics.get_overall_summary()
for key, value in summary.items():
    print(f"{key}: {value}")
```

### Available Metric Methods

All methods return pandas DataFrames for easy manipulation:

**Defect Metrics:**
- `get_total_defects_by_project()`
- `get_defects_by_severity()`
- `get_defects_by_checker_category(limit=20, fetch_all=False)`
- `get_defects_by_checker_name(limit=20, fetch_all=False)`
- `get_defect_density_by_project()`
- `get_file_hotspots(limit=20, fetch_all=False)`

**Triage Metrics:**
- `get_defects_by_triage_status()`
- `get_defects_by_classification()`
- `get_defects_by_owner(limit=20, fetch_all=False)`

**Code Quality Metrics:**
- `get_code_metrics_by_stream()`
- `get_function_complexity_distribution()`
- `get_most_complex_functions(limit=20, fetch_all=False)`

**Trend Metrics:**
- `get_defect_trend_weekly(weeks=12)`
- `get_file_count_trend_weekly(weeks=12)`
- `get_snapshot_history(stream_name=None, limit=20, fetch_all=False)`
- `get_defect_velocity_trend(days=90)` - NEW! Introduction vs fix rates
- `get_cumulative_defect_trend(days=90)` - NEW! Long-term accumulation
- `get_defect_trend_summary(days=90)` - NEW! Velocity metrics and trend direction
- `get_technical_debt_summary()` - NEW! Estimated remediation effort

**Security Compliance Metrics:**
- `get_owasp_top10_metrics()` - NEW! OWASP Top 10 2025 category mapping
- `get_cwe_top25_metrics()` - NEW! CWE Top 25 2025 dangerous weaknesses

**Leaderboard Metrics:**
- `get_top_projects_by_fix_rate(days=30, limit=10)` - NEW! Projects by fix velocity
- `get_most_improved_projects(days=90, limit=10)` - NEW! Best improvement trends
- `get_top_projects_by_triage_activity(days=30, limit=10)` - NEW! Most active triage
- `get_top_users_by_fixes(days=30, limit=10)` - NEW! Users by actual code fixes
- `get_top_triagers(days=30, limit=10)` - NEW! Most active triagers
- `get_most_collaborative_users(days=30, limit=10)` - NEW! Cross-project activity

**User Activity:**
- `get_user_login_statistics(days=30)`
- `get_most_active_triagers(days=30, limit=10)`

**Performance Metrics:**
- `get_database_statistics()` - Database size and statistics
- `get_largest_tables(limit=10)` - Largest database tables by size
- `get_snapshot_performance(limit=20)` - Recent commit/analysis performance
- `get_commit_time_statistics()` - Commit time averages and statistics
- `get_defect_discovery_rate(days=30)` - Defect discovery trends over time

**Summary:**
- `get_overall_summary()`
- `get_available_projects()` - List all available projects

**Note on `fetch_all` parameter:**
- When `fetch_all=False` (default): Returns top N results based on the `limit` parameter
- When `fetch_all=True`: Returns ALL available results (ignores `limit`)
- Use `fetch_all=True` for complete data exports or comprehensive analysis
- Example: `metrics.get_file_hotspots(fetch_all=True)` returns ALL files with defects, not just top 20

## Recommended Metrics for Different Use Cases

### For Management/Executive Reports:
1. **Overall Summary** - High-level statistics
2. **Defects by Severity** - Risk assessment
3. **Defect Density by Project** - Quality comparison across projects
4. **Weekly Defect Trend** - Progress over time
5. **Defects by Triage Status** - Workload and backlog
6. **Technical Debt Summary** - NEW! Estimated remediation effort
7. **Top Projects by Fix Rate** - NEW! Team performance ranking

### For Development Teams:
1. **File Hotspots** - Identify problematic files
2. **Most Complex Functions** - Refactoring candidates
3. **Defects by Category** - Common error patterns
4. **Defects by Owner** - Individual workload
5. **Snapshot History** - Analysis run results
6. **Top Fixers** - NEW! Recognize high performers
7. **CWE Top 25** - NEW! Focus on dangerous weaknesses

### For Quality Assurance:
1. **Defects by Checker** - Tool effectiveness
2. **Defects by Classification** - False positive rate
3. **Code Metrics by Stream** - Code coverage
4. **Function Complexity** - Code maintainability
5. **Defect Density** - Quality benchmarks
6. **Technical Debt Summary** - NEW! Remediation planning

### For Security Teams:
1. **OWASP Top 10 Metrics** - NEW! Web application security risks
2. **CWE Top 25 Metrics** - NEW! Most dangerous weaknesses
3. **Defects by Severity** - Critical vulnerability counts
4. **Security Category Defects** - Security-specific findings
5. **Technical Debt (High Severity)** - NEW! Security fix effort estimation

### For Team Leads:
1. **Active Triagers** - Team engagement
2. **Defects by Owner** - Work distribution
3. **User Login Statistics** - Tool adoption
4. **Weekly Trends** - Team velocity
5. **Top Fixers and Triagers** - NEW! Team performance metrics

## Project Structure

```
coverity_metrics/              (project root)
├── config.json.example        # Configuration template
├── coverity_metrics/          # Python package
│   ├── __init__.py            # Package initialization
│   ├── __version__.py         # Version information
│   ├── db_connection.py       # Database connection handling
│   ├── metrics.py             # Core metrics calculation logic
│   ├── metrics_cache.py       # Caching and progress tracking
│   ├── multi_instance_metrics.py  # Multi-instance aggregation
│   ├── owasp_mapping.py       # OWASP Top 10 2025 CWE mappings (494 CWEs)
│   ├── cwe_top25_mapping.py   # CWE Top 25 2025 rankings and scores
│   ├── zip_data_loader.py     # ZIP-based offline data loader
│   ├── cli/
│   │   ├── dashboard.py       # Dashboard generator (main CLI)
│   │   ├── export.py          # JSON/ZIP export utility
│   │   └── report.py          # CLI metrics report
│   ├── templates/             # Jinja2 HTML templates
│   │   ├── dashboard.html     # Per-instance/project dashboard
│   │   └── dashboard_aggregated.html  # Multi-instance aggregated view
│   └── static/                # CSS/JS assets for dashboards
│       ├── css/
│       └── js/
├── requirements.txt           # Python dependencies
├── setup.py                   # Package setup
├── pyproject.toml             # Modern Python packaging
├── install.ps1                # Windows install / clean-reinstall helper
├── release.ps1                # Build, version-bump and publish script
├── README.md                  # This file
├── CHANGELOG.md               # Detailed version changelog
├── RELEASE_NOTES.md           # Release notes and version history
├── RELEASE_PROCESS.md         # How to cut a release
├── INSTALL.md                 # Detailed installation guide
├── USAGE_GUIDE.md             # Comprehensive usage examples
├── MULTI_INSTANCE_GUIDE.md    # Multi-instance setup and usage
├── MULTI_ZIP_GUIDE.md         # Multi-ZIP aggregation guide
├── CACHING_GUIDE.md           # Performance optimization guide
├── PRESENTATION_GUIDE.md      # Dashboard presentation guide
└── LICENSE                    # Project license
```

## Extending the Tool

You can easily add new metrics by extending the `CoverityMetrics` class:

```python
class CoverityMetrics:
    # ... existing methods ...
    
    def get_custom_metric(self):
        """Your custom metric description"""
        query = """
            SELECT ...
            FROM ...
        """
        results = self.db.execute_query_dict(query)
        return pd.DataFrame(results)
```

## Troubleshooting

### Database Connection Issues
- Verify PostgreSQL is running: Check Coverity services
- Check credentials in `config.json`
- Ensure PostgreSQL port (default 5432) is accessible
- Verify at least one instance is enabled in config.json

### Missing Data
- Some metrics may return empty if:
  - No snapshots have been committed
  - Streams haven't been analyzed
  - Defects haven't been triaged

### Performance
- For large databases, some queries may take time
- Consider adding database indexes on frequently queried columns
- Use the `limit` parameter to restrict result sizes

## Security Notes

- Database passwords are stored in `config.json` 
- **Always** add config.json to `.gitignore` before committing
- Use read-only database credentials when possible
- Set appropriate file system permissions on config.json
- Never commit database credentials to version control

```bash
# Recommended file permissions (Linux/Mac)
chmod 600 config.json

# Add to .gitignore
echo "config.json" >> .gitignore
```
- Use environment variables or secure vaults in production

## License

This tool is provided as-is for use with Coverity installations.

## Support

For issues or questions:
1. Check the Coverity documentation for database schema details
2. Review the SQL queries in `metrics.py` to understand data sources
3. Use `schema_explorer.py` to investigate your specific database structure

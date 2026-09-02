# Coverity Metrics

A Python toolkit that turns Coverity Connect's PostgreSQL database into
interactive HTML dashboards, terminal reports, and portable ZIP exports —
including quarter-over-quarter trend reports that run entirely offline.

## Contents

- [What you get](#what-you-get)
- [Quick start](#quick-start)
- [Installation](#installation)
- [Configuration](#configuration)
- [CLI reference](#cli-reference)
- [Workflows](#workflows)
- [Python library](#python-library)
- [Documentation index](#documentation-index)
- [Security notes](#security-notes)
- [License](#license)

## What you get

| Capability | Command | Notes |
| --- | --- | --- |
| Interactive HTML dashboards | `coverity-dashboard` | Plotly charts, sortable tables, tabbed views |
| Terminal metrics report | `coverity-metrics` | Formatted tables to stdout — great for CI |
| Portable ZIP export | `coverity-export` | One ZIP per instance, self-contained, no DB required to render |
| Multi-snapshot trend report | `coverity-delta` | Feed a folder of ZIPs, get per-quarter trend charts |
| Offline / air-gapped rendering | `coverity-dashboard --zip-file` | Turns a ZIP back into HTML with no DB access |
| Multi-instance aggregation | `coverity-dashboard --zip-file *.zip --aggregated-view` | Combine exports from separate Coverity servers |
| Anonymized delivery | `coverity-export --anonymize` | Replaces real project / stream names with `project_NNN` ids |
| Caching | `coverity-dashboard --cache` | 90 %+ speed-up on repeat runs against large deployments |

Dashboard tabs cover **Overview**, **Code Quality**, **Performance &
Analytics**, **Trends & Progress** (with technical-debt estimation),
**Leaderboards**, **OWASP Top 10 2025**, **CWE Top 25 2025**, and — in
ZIP mode — **Snapshots**.

Per-release detail lives in [CHANGELOG.md](https://github.com/lejouni/coverity_metrics/blob/main/CHANGELOG.md) and
[RELEASE_NOTES.md](https://github.com/lejouni/coverity_metrics/blob/main/RELEASE_NOTES.md).

## Quick start

```bash
pip install coverity-metrics
cp config.json.example config.json
# Edit config.json with your database credentials

coverity-dashboard                 # DB mode; opens output/dashboard.html in your browser
coverity-metrics                   # Terminal-only text report
coverity-export --output exports   # Portable ZIP for offline delivery
```

No admin / root rights? Use `pip install --user coverity-metrics` or
`pipx install coverity-metrics`, or grab a standalone binary from the
[GitHub Releases page](https://github.com/lejouni/coverity_metrics/releases)
— see [INSTALL.md](https://github.com/lejouni/coverity_metrics/blob/main/INSTALL.md) for details.

## Installation

### From PyPI

```bash
pip install coverity-metrics
```

Installs the three CLI commands (`coverity-dashboard`, `coverity-metrics`,
`coverity-export`) and `coverity-delta`, plus the `python -m
coverity_metrics <subcommand>` entry point.

### From source

```bash
git clone https://github.com/lejouni/coverity_metrics.git
cd coverity_metrics
pip install -e .
```

### Standalone binaries

Windows and Linux single-file binaries are published on every tagged
release — see [packaging/README.md](https://github.com/lejouni/coverity_metrics/blob/main/packaging/README.md). They ship
their own Python runtime so no Python install is required on the
target host.

### Requirements

- **Python ≥ 3.10** (transitive requirement from `pandas ≥ 3.0`)
- Runtime deps installed automatically: `pg8000`, `pandas`,
  `python-dateutil`, `jinja2`, `plotly`, `tqdm`

## Configuration

### `config.json`

One instance is enough for single-instance mode. Add more to enable
multi-instance aggregation.

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
  ],
  "aggregated_view": {
    "enabled": true,
    "name": "All Instances"
  }
}
```

- 2+ enabled instances → multi-instance mode (auto-detected).
- `aggregated_view.enabled: true` turns on the cross-instance dashboard.
- Add `config.json` to `.gitignore` before your first commit.

Detailed multi-instance setup is in
[MULTI_INSTANCE_GUIDE.md](https://github.com/lejouni/coverity_metrics/blob/main/MULTI_INSTANCE_GUIDE.md).

### Finding the DB credentials in Coverity Connect

The values live in `cim.properties` under the Coverity Connect install
directory:

| OS | Path |
| --- | --- |
| Linux | `<install>/config/cim.properties` (e.g. `/opt/coverity/connect/config/cim.properties`) |
| Windows | `<install>\config\cim.properties` |

Map each property into `config.json` or the matching env var:

| `cim.properties` key | `config.json` field | Env var |
| --- | --- | --- |
| `cim.database.host` | `database.host` | `COVERITY_DB_HOST` |
| `cim.database.port` | `database.port` | `COVERITY_DB_PORT` |
| `cim.database.name` | `database.database` | `COVERITY_DB_NAME` |
| `cim.database.user` | `database.user` | `COVERITY_DB_USER` |
| `cim.database.password` | `database.password` | `COVERITY_DB_PASSWORD` |

Notes:

- The password is stored in cleartext in `cim.properties`. Only the
  Coverity Connect service user should have read access to that file.
- The bundled PostgreSQL that ships with Coverity Connect listens on
  **port 5433** by default (not 5432). Copy whatever port the properties
  file has.
- Prefer creating a dedicated read-only role in Postgres and granting
  `pg_read_all_data` — the tool never issues DML.

### Environment-variable mode

`coverity-export` and `coverity-dashboard` (DB mode only) can run
without a `config.json` when all required env vars are set. Handy in
CI pipelines and containers.

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `COVERITY_DB_HOST` | yes | — | Postgres hostname |
| `COVERITY_DB_NAME` | yes | — | Database name (usually `cim`) |
| `COVERITY_DB_USER` | yes | — | Database user |
| `COVERITY_DB_PASSWORD` | yes | — | Database password |
| `COVERITY_DB_PORT` | no | `5432` | Database port |
| `COVERITY_INSTANCE_NAME` | no | `Coverity` | Instance label used in ZIP filenames + dashboards |

**Startup precedence** (both tools):

1. `--config <file>` explicitly passed → load that JSON.
2. All required env vars set → single-instance env-var mode.
3. `config.json` in the current directory → loaded automatically.
4. Otherwise → exit with guidance.

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

`coverity-metrics` still requires `config.json`; env-var mode is
`coverity-export` / `coverity-dashboard`-only.

Pre-built quickstart scripts under [`scripts/`](https://github.com/lejouni/coverity_metrics/tree/main/scripts) —
[`coverity-export.sh`](https://github.com/lejouni/coverity_metrics/blob/main/scripts/coverity-export.sh) (Linux) and
[`coverity-export.ps1`](https://github.com/lejouni/coverity_metrics/blob/main/scripts/coverity-export.ps1) (Windows) — download the
standalone binary, source these variables from a block at the top of
the script, and run one export in one shot.

## CLI reference

### `coverity-dashboard`

Reads from a database **or** from one or more `coverity-export` ZIPs.
Auto-detects multi-instance from `config.json`.

| Parameter | Short | Type | Default | Description |
| --- | --- | --- | --- | --- |
| `--project` | `-p` | string | None | Filter by project name(s). Comma-separated for multiple (`AppA,AppB`); generates per-project + aggregated dashboards |
| `--output` | `-o` | string | `output` | Output folder |
| `--no-browser` |  | flag | False | Don't auto-open the browser |
| `--workers` | `-w` | int | `1` | Parallel workers for per-project generation (1–8). Each worker holds its own DB connection / `ZipDataLoader` |
| `--zip-file` | `-z` | string(s) | None | Use one or more `coverity-export` ZIPs instead of the DB |
| `--aggregated-view` |  | flag | False | ZIP mode only: opt in to `dashboard_aggregated.html`. Also enabled if a passed `--config` has `zip_files_config.aggregated_view.enabled: true` |
| `--config` | `-c` | string | `config.json` | Config file (not required in ZIP mode) |
| `--instance` | `-i` | string | None | Generate for one instance only |
| `--single-instance-mode` |  | flag | False | Force single-instance behaviour even with multiple instances in config |
| `--cache` |  | flag | False | Enable disk cache (DB mode) |
| `--cache-dir` |  | string | `cache` | Cache directory |
| `--cache-ttl` |  | int | `24` | Cache TTL in hours |
| `--clear-cache` |  | flag | False | Clear cache before generating |
| `--cache-stats` |  | flag | False | Print cache stats and exit |
| `--no-cache` |  | flag | False | Bypass cache, force refresh |
| `--days` | `-d` | int | `365` | Trend window in days |
| `--track-progress` |  | flag | False | Progress tracking / resumable ops |
| `--resume` |  | string | None | Resume an interrupted session by id |
| `--version` |  | flag | False | Print version and exit |

Detailed caching / performance tuning is in
[CACHING_GUIDE.md](https://github.com/lejouni/coverity_metrics/blob/main/CACHING_GUIDE.md); multi-ZIP behaviour is in
[MULTI_ZIP_GUIDE.md](https://github.com/lejouni/coverity_metrics/blob/main/MULTI_ZIP_GUIDE.md).

### `coverity-metrics`

Terminal text report. Uses the first enabled instance from `config.json`
unless `--zip-file` is given.

| Parameter | Short | Type | Default | Description |
| --- | --- | --- | --- | --- |
| `--zip-file` | `-z` | string(s) | None | Read metrics from ZIP(s) instead of the DB |
| `--config` | `-c` | string | `config.json` | Config file |
| `--version` |  | flag | False | Print version and exit |

Redirect stdout to save (`coverity-metrics > report.txt`).

### `coverity-export`

Creates one ZIP per enabled instance. Each ZIP is self-contained
(all instance and per-project JSONs, metadata, and optional snapshot /
leaderboard sections) and is the input for `coverity-dashboard
--zip-file` and `coverity-delta`.

| Parameter | Short | Type | Default | Description |
| --- | --- | --- | --- | --- |
| `--output` | `-o` | string | `exports` | Output directory |
| `--days` | `-d` | int | `365` | Trend window in days |
| `--config` | `-c` | string | `config.json` | Config file |
| `--project` | `-p` | string | None | Comma-separated project filter |
| `--workers` | `-w` | int | `1` | Parallel workers for per-project export (1–8) |
| `--anonymize` |  | flag | False | Replace real project / stream names with `project_NNN` / `stream_NNN` ids; writes sibling `<zip>.mapping.json` |
| `--mapping-file` |  | string | None | Persistent mapping JSON — keeps ids stable across re-exports |
| `--no-leaderboards` |  | flag | False | Skip the five Leaderboards metrics; dashboards from the ZIP hide the 🏆 tab |
| `--no-snapshots` |  | flag | False | Skip `snapshot_commands`; project dashboards from the ZIP hide the 📸 tab |
| `--version` |  | flag | False | Print version and exit |

ZIP filenames follow
`{output}/coverity_export_{InstanceName}_{YYYYMMDD_HHMMSS}.zip`.

### `coverity-delta`

Turns two or more `coverity-export` ZIPs sitting in a folder into a
chronological trend report (`delta.json` + inline-SVG
`dashboard_delta.html`). Runs entirely offline.

```bash
coverity-delta --archive-dir archive/ --output delta/latest
```

Guardrails, timing tags on Added / Dropped lists, rank movement on
Defects-by-project, and the full CLI surface are documented in the
[Trend comparison workflow](#trend-comparison-multi-quarter-trends) below
and in [EXPORT_QUICKSTART.md](https://github.com/lejouni/coverity_metrics/blob/main/EXPORT_QUICKSTART.md).

## Workflows

### Daily / weekly / monthly

```bash
coverity-metrics                                # fast terminal check
coverity-dashboard --cache                      # visual dashboard (opens in browser)
coverity-dashboard --cache --days 90            # tighter trend window for a review
coverity-export --output exports --days 365     # snapshot for archival / delivery
```

### Offline delivery (single instance)

```bash
# On a machine with DB access
coverity-export --days 365 --output deliverables

# Ship the ZIP anywhere (email, USB, file share).
# On the receiving machine (no DB required):
coverity-dashboard --zip-file deliverables/coverity_export_Production_*.zip
```

### Multi-ZIP aggregation

Combine ZIPs from separate Coverity servers (different networks,
different regions) into a single set of dashboards:

```bash
coverity-dashboard --zip-file exports/*.zip --aggregated-view --no-browser
```

- `--aggregated-view` is off by default; it's the sole opt-in.
- Passing `--config path/to/config.json` with
  `zip_files_config.aggregated_view.enabled: true` is an equivalent
  opt-in — either source alone is enough.
- Duplicate instance names across ZIPs (all labelled `Production` even
  though they came from different servers) are disambiguated
  automatically by appending the ZIP filename's stem in parentheses —
  e.g. `Production (prod_us)`, `Production (prod_eu)`.
- `*` / `?` / `[…]` wildcards are expanded inside the tool, so the
  same command works on Linux, macOS, and Windows (PowerShell / `cmd`)
  without needing shell-side globbing.

More detail: [MULTI_ZIP_GUIDE.md](https://github.com/lejouni/coverity_metrics/blob/main/MULTI_ZIP_GUIDE.md).

### Trend comparison (multi-quarter trends)

Run `coverity-export` at the end of every period with **the same
`--days` value** and **the same `--mapping-file`**, letting the ZIPs
accumulate in a shared archive folder. Then point `coverity-delta` at
the folder:

```bash
# End of every quarter — same --days and --mapping-file across runs.
coverity-export --days 90 \
    --anonymize --mapping-file archive/shared-mapping.json \
    --output archive/

# When you have two or more ZIPs in archive/:
coverity-delta --archive-dir archive/ --output delta/latest
```

Two or more ZIPs are required; there is no upper bound. Snapshot
labels auto-derive to `YYYY-QN` from each ZIP's `export_date`; override
positionally with `--labels a,b,c,...` when the auto labels collide.

The report covers five metric families — Projects, Active users, Scan
activity, Stream activity, and Defects-by-project (with inline SVG
sparklines and rank movement) — and hard-fails on mismatched `--days`
or mismatched anonymization mappings across the archive. Full
guardrail behaviour and CLI flags in
[EXPORT_QUICKSTART.md](https://github.com/lejouni/coverity_metrics/blob/main/EXPORT_QUICKSTART.md#trend-comparison-coverity-delta).

### Anonymized delivery

```bash
coverity-export --anonymize
# → exports/coverity_export_Production_YYYYMMDD_HHMMSS.zip           (safe to share)
# → exports/coverity_export_Production_YYYYMMDD_HHMMSS.mapping.json  (keep private)

# Keep ids stable across re-exports (recommended for trend workflows):
coverity-export --anonymize --mapping-file ./anon-map.json
```

Only project and stream names are replaced. Host, database name, and
user / committer names are **not** anonymized in the current release.

## Python library

```python
from coverity_metrics import CoverityMetrics, MultiInstanceMetrics, InstanceConfig

metrics = CoverityMetrics(
    connection_params={
        "host": "localhost",
        "port": 5432,
        "database": "coverity",
        "user": "postgres",
        "password": "your_password",
    },
    project_name="MyProject",  # optional filter
)

# Top-N results (default) or all rows via fetch_all
categories = metrics.get_defects_by_checker_category(limit=10)
hotspots   = metrics.get_file_hotspots(fetch_all=True)

# Technical debt, security compliance, leaderboards
debt   = metrics.get_technical_debt_summary()
owasp  = metrics.get_owasp_top10_metrics()
cwe25  = metrics.get_cwe_top25_metrics()
fixers = metrics.get_top_users_by_fixes(days=30, limit=10)
```

Multi-instance aggregation is the same shape:

```python
instances = [
    InstanceConfig("Production",  {...connection_params...}),
    InstanceConfig("Development", {...connection_params...}),
]
multi = MultiInstanceMetrics(instances)
aggregated = multi.get_aggregated_metrics()
```

Every metric method returns a `pandas.DataFrame`. Methods that support
`fetch_all` accept `(limit=N, fetch_all=False)`; setting `fetch_all=True`
ignores `limit`. See [USAGE_GUIDE.md](https://github.com/lejouni/coverity_metrics/blob/main/USAGE_GUIDE.md) for the full method
reference and additional examples.

## Documentation index

| Topic | Guide |
| --- | --- |
| Install without admin rights, standalone binaries | [INSTALL.md](https://github.com/lejouni/coverity_metrics/blob/main/INSTALL.md) |
| Comprehensive CLI + Python usage examples | [USAGE_GUIDE.md](https://github.com/lejouni/coverity_metrics/blob/main/USAGE_GUIDE.md) |
| Multi-instance setup and behaviour | [MULTI_INSTANCE_GUIDE.md](https://github.com/lejouni/coverity_metrics/blob/main/MULTI_INSTANCE_GUIDE.md) |
| Multi-ZIP aggregation and duplicate-instance handling | [MULTI_ZIP_GUIDE.md](https://github.com/lejouni/coverity_metrics/blob/main/MULTI_ZIP_GUIDE.md) |
| Trend comparison workflow, standalone binary run recipe | [EXPORT_QUICKSTART.md](https://github.com/lejouni/coverity_metrics/blob/main/EXPORT_QUICKSTART.md) |
| Caching, TTLs, resumable operations | [CACHING_GUIDE.md](https://github.com/lejouni/coverity_metrics/blob/main/CACHING_GUIDE.md) |
| OWASP Top 10 2025 mapping details | [OWASP_TOP10_2025_IMPLEMENTATION.md](https://github.com/lejouni/coverity_metrics/blob/main/OWASP_TOP10_2025_IMPLEMENTATION.md) |
| CWE Top 25 dashboards | [CWE_TOP25_STATUS_REPORT_SETUP.md](https://github.com/lejouni/coverity_metrics/blob/main/CWE_TOP25_STATUS_REPORT_SETUP.md) |
| Presentation-ready dashboards | [PRESENTATION_GUIDE.md](https://github.com/lejouni/coverity_metrics/blob/main/PRESENTATION_GUIDE.md) |
| Cutting a release | [RELEASE_PROCESS.md](https://github.com/lejouni/coverity_metrics/blob/main/RELEASE_PROCESS.md) |
| Changelog / release notes | [CHANGELOG.md](https://github.com/lejouni/coverity_metrics/blob/main/CHANGELOG.md), [RELEASE_NOTES.md](https://github.com/lejouni/coverity_metrics/blob/main/RELEASE_NOTES.md) |

## Security notes

- Database passwords land in `config.json` in cleartext — treat it like
  any other credential file.
- Add `config.json` (and any `*.mapping.json`) to `.gitignore` before
  your first commit.
- Prefer read-only DB credentials (`pg_read_all_data`) — the tool
  issues no DML.
- Restrict file permissions on the config file:

  ```bash
  chmod 600 config.json     # Linux / macOS
  ```

- For CI, use env-var mode with your platform's secret store instead of
  shipping a config file.
- `--anonymize` masks project and stream names in shared ZIPs; the
  `<zip>.mapping.json` sidecar stays private and is the only way to
  decode the ids back.

## License

Provided as-is for use with Coverity installations. See [LICENSE](https://github.com/lejouni/coverity_metrics/blob/main/LICENSE).

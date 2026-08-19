# Coverity Metrics — Usage Guide

Practical recipes for the three CLIs and the Python API. For deeper feature
docs see [README.md](README.md), [CACHING_GUIDE.md](CACHING_GUIDE.md), and
[MULTI_INSTANCE_GUIDE.md](MULTI_INSTANCE_GUIDE.md). Placeholder project
names below (`example-project`, `AppA`, `AppB`, …) stand in for whatever you
have in your own Coverity Connect DB.

## Quick Start

### 1. Console Report

```bash
# CLI entry point
coverity-metrics

# Or as a Python module
python -m coverity_metrics report

# Point at a specific config or a ZIP export
coverity-metrics --config config.json
coverity-metrics --zip-file exports/instance.zip
```

Prints every metric table to stdout. Best for a quick sanity check or for
piping into `grep` / `tee`.

### 2. HTML Dashboard

```bash
# CLI entry point
coverity-dashboard

# Or as a Python module
python -m coverity_metrics dashboard
```

Generates an interactive HTML dashboard with:

- Summary cards for key metrics
- Interactive Plotly charts (donut, bar, line, area)
- Sortable data tables (every table has click-to-sort headers)
- File hotspots (attributed to project at instance scope, to stream at project scope)
- Codebase metrics per stream
- OWASP Top 10 and CWE Top 25 breakdowns (at project scope)
- Defect aging, triage trends, top fixers and triagers
- Snapshot activity, commit patterns, license / login stats

The dashboard is saved to `output/dashboard.html` by default.

**Filter by project:**
```bash
# Single project
coverity-dashboard --project "example-project"

# Multiple projects (comma-separated) — one dashboard per project + an aggregated instance dashboard
coverity-dashboard --project "AppA,AppB,AppC"

# Custom output directory
coverity-dashboard --output reports/my_dashboards

# Skip browser auto-open
coverity-dashboard --no-browser

# Widen the trend window (default is 365 days)
coverity-dashboard --days 730
```

Without `--project`, the tool auto-generates dashboards for every project
plus the aggregated instance dashboard.

**Multi-instance mode** (Coverity Connect fleets):
```bash
# Config lists every Coverity instance; one --config file, N dashboard sets
coverity-dashboard --config config.multi.json

# Or generate for a single named instance from a multi-config
coverity-dashboard --config config.multi.json --instance "prod-east"

# Force single-instance mode even when the config has multiple entries
coverity-dashboard --config config.json --single-instance-mode
```

See [MULTI_INSTANCE_GUIDE.md](MULTI_INSTANCE_GUIDE.md) for the config schema.

**Speed up large runs:**
```bash
# 4 parallel workers for per-project dashboards (database or ZIP mode)
coverity-dashboard --workers 4

# Same for the export CLI — recommended for instances with hundreds of projects
coverity-export --workers 4
```

Each worker uses its own Postgres connection (or its own `ZipDataLoader` in
ZIP mode). Default is `1` (sequential); the flag is clamped to a maximum of
`8`. Both CLIs print total wall time so you can measure the speedup.

**Cache the expensive queries:**
```bash
# First run populates the on-disk cache (default TTL 24h)
coverity-dashboard --cache

# Custom directory / TTL
coverity-dashboard --cache --cache-dir cache/ --cache-ttl 48

# Inspect / clear the cache
coverity-dashboard --cache-stats
coverity-dashboard --clear-cache

# Explicit opt-out (useful when the config has caching on by default)
coverity-dashboard --no-cache
```

See [CACHING_GUIDE.md](CACHING_GUIDE.md) for hit/miss semantics.

### 3. Export to ZIP

```bash
# CLI entry point
coverity-export

# Or as a Python module
python -m coverity_metrics export

# Custom output, trend window, and project scope
coverity-export --output exports/ --days 730 --project "AppA,AppB"
```

Writes one ZIP per Coverity instance under `--output`. Each ZIP contains
every metric as JSON plus a manifest — small enough to email or attach to a
support ticket, and enough for `coverity-dashboard --zip-file` /
`coverity-metrics --zip-file` to fully re-render the dashboards offline.

**Anonymize before sharing:**
```bash
# Real project / stream / user names become project_001 / stream_001 / user_001
coverity-export --anonymize

# Keep the same anon ids across re-exports by pinning the mapping file
coverity-export --anonymize --mapping-file exports/mapping.json
```

The mapping file stays on your machine so you can decode later; the ZIP
itself never contains a real name.

**Trim the payload:**
```bash
# Drop leaderboards (top fixers, top triagers, most collaborative, ...)
coverity-export --no-leaderboards

# Drop the per-snapshot performance / commands tables
coverity-export --no-snapshots
```

## Python API

```python
from coverity_metrics import CoverityMetrics
```

`CoverityMetrics` takes a connection-params dict and an optional
`project_name` (single name or comma-separated). A per-instance
`config.json` looks like:

```json
{
  "host": "coverity.example.com",
  "port": 5432,
  "database": "coverity",
  "user": "cov_ro",
  "password": "..."
}
```

### Instance vs. project scope

```python
from coverity_metrics import CoverityMetrics
import json

conn = json.load(open("config.json"))

# Instance scope — every project
inst = CoverityMetrics(conn)
summary_all = inst.get_overall_summary()

# Project scope — one project (finer split on file hotspots, etc.)
proj = CoverityMetrics(conn, project_name="example-project")
summary_proj = proj.get_overall_summary()

# Multi-project — comma-separated
multi = CoverityMetrics(conn, project_name="AppA,AppB,AppC")
```

At project scope, some metrics change their grouping to match the narrower
context — e.g. `get_file_hotspots()` returns a `stream_name` column instead
of `project_name` because streams are the useful axis inside a single
project.

### `limit` vs. `fetch_all`

Any method that accepts `limit=` also accepts `fetch_all=True` to bypass
the cap and return every row:

```python
metrics = CoverityMetrics(conn)

# Default: top 20 hotspots
top_hotspots = metrics.get_file_hotspots(limit=20)

# Every file with at least one defect
all_hotspots = metrics.get_file_hotspots(fetch_all=True)

# Works for any *by_checker_name / *by_owner / *_history / top_* method
all_checkers = metrics.get_defects_by_checker_name(fetch_all=True)
all_owners   = metrics.get_defects_by_owner(fetch_all=True)
```

### Common recipes

**Executive / management view:**
```python
summary  = metrics.get_overall_summary()
severity = metrics.get_defects_by_severity()
density  = metrics.get_defect_density_by_project()
aging    = metrics.get_defect_aging_distribution()
trend    = metrics.get_defect_trend_summary(days=90)
```

**Dev-team view:**
```python
hotspots   = metrics.get_file_hotspots(limit=20)
categories = metrics.get_defects_by_checker_category()
complex_fn = metrics.get_most_complex_functions(limit=20)
code_stats = metrics.get_code_metrics_by_stream()
```

**QA / triage view:**
```python
by_action  = metrics.get_defects_by_triage_status()
by_class   = metrics.get_defects_by_classification()
by_checker = metrics.get_defects_by_checker_name(limit=30)
progress   = metrics.get_triage_progress_summary()
```

**Team-lead view:**
```python
owners     = metrics.get_defects_by_owner(limit=20)
top_fixers = metrics.get_top_users_by_fixes(days=30, limit=10)
triagers   = metrics.get_top_triagers(days=30, limit=10)
licenses   = metrics.get_user_license_statistics(days=90)
logins     = metrics.get_user_login_statistics(days=30)
```

**Security view (OWASP / CWE — project scope only):**
```python
proj = CoverityMetrics(conn, project_name="example-project")
owasp = proj.get_owasp_top10_metrics()
cwe25 = proj.get_cwe_top25_metrics()
```

### Load from a ZIP export instead of the DB

```python
from coverity_metrics.zip_data_loader import ZipDataLoader

loader = ZipDataLoader("exports/instance.zip")
hotspots = loader.get_file_hotspots(limit=20)
summary  = loader.get_overall_summary()
```

`ZipDataLoader` exposes the same read-only method surface as
`CoverityMetrics`, so any script written against the DB path also works
against a ZIP. This is how the offline dashboard / offline report modes
work internally.

## Custom SQL

The safest way to add a custom query is to reuse the tool's outstanding-
defect anchors instead of writing `WHERE fixed_snapshot_element_id IS NULL`
by hand — the raw filter misses "fixed then reappeared" defects. See the
comment on `_ACTIVE_COND_SQL` in `coverity_metrics/metrics.py` for the
rationale. Sketch:

```python
from coverity_metrics import CoverityMetrics
metrics = CoverityMetrics(conn)

query = f"""
    SELECT
        fp.filename,
        ct.name AS checker,
        cp.impact,
        cp.cwe
    FROM stream_defect sd
    JOIN stream_defect_occurrence sdo ON sd.id = sdo.stream_defect_id
    JOIN stream_file sf    ON sdo.stream_file_id = sf.id
    JOIN file_path fp      ON sf.file_path_id = fp.id
    JOIN checker_properties cp ON sd.checker_properties_id = cp.id
    JOIN checker_type ct   ON cp.checker_type_id = ct.id
    {metrics._ACTIVE_JOIN_SQL}
    WHERE {metrics._ACTIVE_COND_SQL}
      AND (cp.security = true OR cp.cwe IS NOT NULL)
    ORDER BY
        CASE cp.impact
            WHEN 'High'   THEN 1
            WHEN 'Medium' THEN 2
            ELSE 3
        END
"""
security_defects = metrics.db.execute_query_dict(query)
```

Substituting `_ACTIVE_JOIN_SQL` / `_ACTIVE_COND_SQL` guarantees the query
matches every other Active / Fixed / Dismissed count in the tool — if the
central rule ever changes, custom queries built this way inherit the fix
automatically.

## Automating Reports

**Daily summary:**
```python
from coverity_metrics import CoverityMetrics
from datetime import datetime
import json

conn = json.load(open("config.json"))
metrics = CoverityMetrics(conn)
summary = metrics.get_overall_summary()

print(f"Daily Coverity Report — {datetime.now():%Y-%m-%d}")
print("=" * 60)
print(f"Total Active Defects: {summary['total_defects']}")
print(f"High Severity:        {summary['high_severity_defects']}")
print(f"Total LOC:            {summary['total_loc']:,}")

snapshots = metrics.get_snapshot_history(limit=1)
if not snapshots.empty:
    latest = snapshots.iloc[0]
    print(f"\nLatest analysis ({latest['date_created']}):")
    print(f"  New defects:        {latest['new_defect_count']}")
    print(f"  Eliminated defects: {latest['eliminated_defect_count']}")
```

**Weekly trend:**
```python
weekly = metrics.get_defect_trend_weekly(weeks=8)
print(weekly)

hotspots = metrics.get_file_hotspots(limit=10)
print("\nTop 10 hotspots:")
print(hotspots[['file_path', 'defect_count', 'defects_per_kloc']])
```

**CI/CD integration:** run `coverity-export --anonymize` on a schedule,
archive the ZIP, and let downstream consumers use
`coverity-dashboard --zip-file <path>` for offline review. No Postgres
credentials leave the CI runner.

## Performance Tips

- Use `--cache` for interactive exploration; the second run of the same
  dashboard is usually seconds instead of minutes.
- Use `--workers N` when scanning many projects — a mid-size instance often
  goes from 20 min to 5 min at `--workers 4`.
- Narrow the trend window with `--days` when the default 365 is heavier
  than you need.
- Prefer ZIP mode for repeated offline analysis so you're not re-querying
  Postgres.
- For custom queries, always keep a `LIMIT` while iterating and drop it
  only when you're ready for the full run.

## Troubleshooting

**No data returned**
- Verify snapshots have been committed recently.
- Check the stream(s) aren't marked deleted.
- Confirm the project filter matches an actual project name (case-sensitive).

**Slow queries**
- Turn on `--cache` and let the second run reuse warmed results.
- Add an index on `stream_defect(fixed_snapshot_element_id)` on the read
  replica if you own it.
- Narrow with `--days` or per-project `--project`.

**Multiple instances configured but only one runs**
- Add `--config config.multi.json` or drop
  `--single-instance-mode`; see
  [MULTI_INSTANCE_GUIDE.md](MULTI_INSTANCE_GUIDE.md).

**Anonymized ZIP still shows a real name somewhere**
- Only project, stream, user, and committer name columns are swept. File
  paths and commit messages are passed through as-is; treat them as
  sensitive.

## Method Reference

The `CoverityMetrics` class lives in
[coverity_metrics/metrics.py](coverity_metrics/metrics.py). A quick index of
the most-used methods (all take an optional `project_name` set on the
constructor, and read-only wrt the DB):

| Category         | Method                                                                 |
| ---------------- | ---------------------------------------------------------------------- |
| Summary          | `get_overall_summary`, `get_total_defects_by_project`                  |
| Defects          | `get_defects_by_severity`, `get_defects_by_checker_category`, `get_defects_by_checker_name`, `get_defect_density_by_project`, `get_defects_by_triage_status`, `get_defects_by_classification`, `get_defects_by_owner` |
| Hotspots / code  | `get_file_hotspots`, `get_code_metrics_by_stream`, `get_function_complexity_distribution`, `get_most_complex_functions` |
| Trends           | `get_defect_trend_weekly`, `get_defect_trend_summary`, `get_defect_trends`, `get_cumulative_defect_trend`, `get_defect_velocity_trend`, `get_fix_rate_metrics`, `get_defect_discovery_rate`, `get_scan_activity_trend`, `get_file_count_trend_weekly` |
| Aging / triage   | `get_defect_aging_distribution`, `get_triage_trends`, `get_triage_progress_summary`, `get_checker_classification_breakdown`, `get_top_projects_by_classification` |
| Snapshots        | `get_snapshot_history`, `get_snapshot_performance`, `get_snapshot_commands`, `get_commit_time_statistics`, `get_commit_activity_patterns` |
| Leaderboards     | `get_top_projects_by_fix_rate`, `get_top_projects_by_triage_activity`, `get_most_improved_projects`, `get_top_users_by_fixes`, `get_top_triagers`, `get_most_active_triagers`, `get_most_collaborative_users` |
| Users / licenses | `get_user_license_statistics`, `get_user_login_statistics`             |
| Instance meta    | `get_instance_info`, `get_database_statistics`, `get_largest_tables`, `get_analysis_versions`, `get_available_projects`, `get_technical_debt_summary` |
| Security         | `get_owasp_top10_metrics`, `get_owasp_category_details`, `get_cwe_top25_metrics`, `get_cwe_top25_details` |

For SQL details, read the docstring on each method — anchoring rules,
grouping choices, and edge-case handling are documented inline.


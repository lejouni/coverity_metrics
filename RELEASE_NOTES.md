# Release Notes

## Version History

### Version 1.0.20 - 2026-08-11

**Release Update**

#### Features
- Added `fetch_all` parameter to metrics methods for complete data retrieval
- Enhanced documentation with CLI parameter reference tables

#### Improvements
- Updated README with comprehensive parameter documentation
- Improved Python library usage examples

### Version 1.0.19 - 2026-08-06

**Sortable Instance-level Defects Table & Release Script CLI-verify Fix**

#### Added

##### ↕ Sortable Columns on the Instance-level "Defects by Project" Table
- Column headers on the instance-level **Defects by Project** table (also **Defects by Stream** on project dashboards) are now clickable
- Each header displays a `▲▼` glyph; clicking toggles ascending / descending order and re-appends the rows in place
- Uses the existing generic `sortTable(columnIndex, tableId, dataType)` helper — Project/Stream Name sorts as text (`localeCompare`), Total Defects / Active / Fixed sort numerically (digits extracted from the badge text)
- No re-export needed — the change is purely in the dashboard template

#### Fixed

##### 🛠 `release.ps1` — Post-Install CLI Verification No Longer Fails on Quoted Paths
- Symptom: the final `Verifying coverity-dashboard CLI...` step in `release.ps1` failed with `'"...\coverity-dashboard.exe"' is not recognized as an internal or external command`, even though the venv was created and the .exe existed at that path
- Root cause: `Invoke-Step` runs every command through `cmd.exe /c $Command`. When the command starts with a quoted path and has trailing arguments (`"C:\...\coverity-dashboard.exe" --help`), cmd.exe's quote-stripping rules can leave the outer quotes attached to the executable name, especially when the venv fell back to the timestamped `.pkgtest_<timestamp>` path (e.g. because the original `.pkgtest` was locked)
- Fix: the two CLI verification calls at the end of `release.ps1` now invoke the .exe directly via PowerShell's `&` operator instead of routing through `cmd.exe`. Exit codes are still checked and any non-zero result throws with a clear message
- Impact: no user-visible impact on the produced release (upload / tag / GitHub release all happen earlier in the script). This just keeps the verification step from producing a spurious failure at the end of an otherwise-successful publish

### Version 1.0.18 - 2026-08-04

**Daily Fix Efficiency % Correctness Fix**

#### Fixed

##### 📉 Daily Fix Efficiency % Was Always 0% When Fixes Landed on a Different Day Than Introductions
- `get_defect_velocity_trend` computed `fix_efficiency_pct = Fixed / New * 100` per day, with an early `WHEN new_count = 0 THEN 0` branch. Since fixes and their originating introductions almost never share the same daily snapshot, most rows collapsed to 0% — including the row where the fix actually landed
- The dashboard tooltip already promised the correct formula: `Fixes / (Fixes + Introductions) × 100%`. The SQL now matches the tooltip: `Fixed / (New + Fixed) * 100`, with a single divide-by-zero guard when both are 0
- Real-world example: project `853-descuento-en-factura-changeplan` — 5 defects introduced 2023-05-08, all 5 fixed 2023-05-17. Before this fix the Daily Fix Velocity table showed 0% on every row (contradicting the 100% shown by the aggregate Fix Rate metric); after, 2023-05-17 correctly shows 100%

### Version 1.0.17 - 2026-08-04

**Scan Activity Chart, Parallel Generation & Reliability Fixes**

#### New Features

##### 📊 Scan / Commit Activity Over Time
- New Trends & Progress section on every project and instance dashboard shows snapshot (scan/commit) counts bucketed over time
- Daily buckets for per-project dashboards, weekly buckets for instance-wide and aggregated views
- Secondary y-axis overlays unique committers per bucket so the same chart shows both cadence and team engagement
- Aggregated multi-instance dashboard adds one overlaid line per instance for cross-instance comparison
- Backed by `CoverityMetrics.get_scan_activity_trend(days, granularity)` and `MultiInstanceMetrics.get_aggregated_scan_activity(days, granularity)`
- ZIP exports now capture `scan_activity_trend.json` at both project and instance levels; pre-1.0.17 ZIPs render the section as hidden (no crash)

##### ⚡ Parallel Per-Project Generation (`--workers`)
- New `--workers N` (`-w`) flag on both `coverity-export` and `coverity-dashboard` — default 1, clamped 1–8
- In database mode each worker owns its own `CoverityMetrics` (and Postgres connection); psycopg2 connections aren't thread-safe
- In ZIP mode each worker owns its own `ZipDataLoader` (ZipFile handles aren't thread-safe)
- Typical speed-ups measured on a 645-project instance:
  - Database export: **4–6× at `--workers 4`**, up to 8× at `--workers 8`
  - ZIP-based dashboards: **~2–3× at `--workers 4`** (CPU-bound rendering shares the GIL less well)
- Per-project errors are logged and the loop continues, matching current behaviour
- Recommendation: start with `--workers 4`; bump to 8 only if the Postgres server has headroom (each worker = one sustained connection)

##### ⏱ Execution Time Reporting
- Both CLIs print `Total execution time: 8.7s` / `1m 23.4s` / `2h 5m 12s` at the end (via a `finally` block, so failures still get timed)
- Export additionally prints per-instance breakdown, e.g. `Time: 4m 12.3s for 645 projects (~0.39s/project)` — makes measuring the `--workers` speedup trivial without external timing

##### 🏷 `--version` on Every CLI
- `coverity-dashboard` now supports `--version`, matching `coverity-export` and `coverity-metrics`. Prints `coverity-dashboard version: X.Y.Z` and exits. Also documented in the parameter tables in the README

##### 📸 Snapshots Tab on Project Dashboards — Recent Analysis Command Lines
- New project-only **📸 Snapshots** tab lists the exact `cov-build` and `cov-analyze` invocations recorded for the most recent 10 snapshots on the project — mirrors the "Command Line" data shown per snapshot in the Coverity Connect UI
- Each snapshot is a collapsible entry with stream, timestamp, invoker (user), host, and platform in the header; expanding reveals the per-element blocks (`Build / Capture`, `Static Analysis`) with runtime, success/failure counts, and the full command in a scrollable preformatted block
- Useful for verifying enabled checkers, aggressiveness level, `--strip-path`, and any custom `--enable` / `--disable` flags after the fact — no need to open Coverity Connect
- Backed by `CoverityMetrics.get_snapshot_commands(limit=20)` which joins `snapshot` → `snapshot_element` and filters by project via `project_stream`/`project`
- ZIP exports include `snapshot_commands.json` under `{instance}/{project}/`; `ZipDataLoader.get_snapshot_commands()` returns an empty DataFrame gracefully on pre-1.0.17 ZIPs, so the tab simply doesn't appear until you re-export

#### Performance Improvements

- **One Postgres connection per instance, not per project**
  - Export and dashboard CLIs now build a single `CoverityMetrics` and rescope via the `.project_name` property between projects
  - Eliminates one connect+auth handshake per project (previously ~645 handshakes on a large deployment)
- **Jinja `Environment` and inline CSS cached at module scope**
  - Template files and the inline CSS payload are read + compiled once per process and reused across every dashboard render, instead of re-parsed hundreds of times

#### Bug Fixes

##### 🛡 Graceful DB Errors
- `CoverityDatabase.execute_query()` / `execute_query_dict()` now wrap queries in `try/except`, log a warning, roll the connection back, and return `[]` on failure
- Callers get an empty DataFrame instead of a traceback — a single query failure no longer aborts the whole export or dashboard run

##### ➗ Division-by-Zero in Leaderboard Queries
- `avg_fixes_per_day` in `get_top_projects_by_fix_rate` no longer crashes when a project has only a single snapshot (or all snapshots share a timestamp) — the denominator `EXTRACT(EPOCH FROM (last - first))` is now wrapped in `NULLIF(..., 0)`, returning `NULL` instead of raising
- Audited every SQL division across `metrics.py` and `multi_instance_metrics.py` — every remaining site is either a constant denominator, guarded by `CASE WHEN ... > 0`, wrapped in `NULLIF`, or gated by a Python `if x > 0` check

##### 🧩 Template `|round()` on `None` Values
- Every leaderboard cell that reads from a `NULLIF`-guarded column (`avg_fixes_per_day`, `avg_triage_per_day`, `avg_comments_per_day`, `triage_percentage`) now uses `{{ field|round(2) if field is not none else 'N/A' }}` — fixes crashes when a NULL value was piped through `|round(...)` in Jinja
- Aggregated dashboard's per-instance `triage_completion` fixed at the source: `dict.get(k, 0)` returns `None` when the key is present with value `None`, so it's now `.get(k) or 0`

##### 📦 `AttributeError` Opening Pre-1.0.17 ZIPs
- `ZipDataLoader` gained `get_scan_activity_trend()` — returns an empty DataFrame when the ZIP predates this metric, so old exports render cleanly and the new section is just hidden until you re-export

##### 🛑 Ctrl+C During Parallel Runs
- Previously Ctrl+C on a `coverity-export --workers N` or `coverity-dashboard --workers N` run appeared to hang for minutes because `ThreadPoolExecutor`'s `with` block waited for every in-flight worker to finish
- All three parallel loops (export, dashboard DB-mode, dashboard ZIP-mode) now catch `KeyboardInterrupt`, cancel every queued future, and call `executor.shutdown(wait=False, cancel_futures=True)` before re-raising
- Both CLIs catch the interrupt at the top level, print `[INTERRUPTED] Aborted by user.`, and exit with code 130. First Ctrl+C drops queued tasks; second Ctrl+C hard-kills.

##### 🏆 Individual Contributors Leaderboards Ignored `--days`
- All five leaderboard queries in `dashboard.py` were hardcoded to `days=30`, so a dashboard generated with `--days 3650` still displayed "Last 30 Days" cards. `top_projects_by_fix_rate`, `top_projects_by_triage`, `top_users_by_fixes`, `top_triagers`, and `most_collaborative_users` now all pass the CLI-supplied `days` value
- Dashboard template subtitles and tooltips replaced literal `Last 30 Days` with `{{ trend_period_text }}`, so cards now show e.g. "Last 3650 Days" matching the actual window
- Removed the stale "improvement percentage (last 90 days)" phrase from the Project Performance tooltip — the Most Improved card was removed in 1.0.13

##### 🕒 `get_top_users_by_fixes` Did Not Honor the Time Window
- The SQL query for Top Fixers ignored the `days` parameter entirely and always aggregated all history, regardless of the requested window
- Added `AND ts.date_created >= CURRENT_DATE - INTERVAL '%s days'` in the `last_triagers` CTE for both project- and instance-scoped branches, and threaded `days` into the parameter tuples

##### 👥 Individual Contributors on Project ZIP Dashboards Showed Instance-Wide Rankings
- `ZipDataLoader.get_top_users_by_fixes`, `get_top_triagers`, and `get_most_collaborative_users` were calling `_read_json_from_zip(self._get_metric_file(...))` directly, bypassing `self.project_name` and always loading the instance-level file
- Switched all three methods to `_read_metric_json(...)`, which reads `{instance}/{project}/{metric}.json` first when a project is selected — matching how `get_defects_by_severity` and other project-scoped metrics behave
- `export_project_specific_metrics` now writes `top_users_by_fixes.json`, `top_triagers.json`, and `most_collaborative_users.json` under `{instance}/{project}/`. Instance-level and project-level exports both use the CLI `days` value instead of hardcoded 30
- **Pre-1.0.17 ZIPs won't contain the per-project user leaderboard files.** On an old ZIP, project-level dashboards will now correctly show *no data* for these cards (the section auto-hides) until you re-export with 1.0.17+.

##### 🧊 Cached Dashboard Path Dropped Individual Contributors Entirely
- `_collect_and_cache_metrics` was setting `top_users_by_fixes`, `top_triagers`, and `most_collaborative_users` to empty lists with a stale "not available without defect_triage_history table" comment — so every cached dashboard rendered without the Individual Contributors section
- Replaced with real metric calls (`metrics.get_top_users_by_fixes(days=days, limit=10)` etc.) and updated `top_projects_by_fix_rate` / `top_projects_by_triage_activity` in the same block to use `days=days` instead of 30. Rebuild cache (or run once without `--use-cache`) to pick up the fix.

##### 🎯 Overview "Active Defects" Card Counted False Positives and Intentionals
- The Overview tab's Active Defects card promised (in its tooltip) to exclude False Positive and Intentional defects, but `get_overall_summary` only filtered on `stream_defect.fixed_snapshot_element_id IS NULL` — so dismissed defects were counted as active, contradicting both the tooltip and the Defects by Stream table's own `active_defects` column
- Both the project-scoped and global branches of `get_overall_summary` now `LEFT JOIN defect_triage` + `dynamic_enum` (`dtype = 'Cls'`) and add `AND (de_cls.name NOT IN ('False Positive', 'Intentional') OR de_cls.name IS NULL)` for `total_defects` and `high_severity_defects`
- Real-world impact: a project with 162 stream_defects all classified as False Positive previously showed `Active Defects: 162`; now correctly shows `0` and matches the "Active" column of the Defects by Stream table beneath it

##### ✅ Dismissed Defects (FP / Intentional) Now Treated as Fixed Everywhere
- The Overview card fix above closed one gap; the same "outstanding = `fixed_snapshot_element_id IS NULL`" pattern was still present in **fourteen** other queries, causing the severity donut, category chart, top-checkers table, defect-density leaderboard, file hotspots, aging distribution, triage progress %, triage-trends stacked bars, current-outstanding in the trend summary, top-projects-by-triage, and all OWASP + CWE Top 25 tables to include dismissed defects while the by-stream table and Overview card excluded them
- Every one of those queries now adds the same triage-classification join and exclusion, so the entire dashboard agrees on the definition of "active"
- Preserved on purpose (these are *about* classifications and would go empty otherwise): `get_checker_classification_breakdown` (Noisy Checkers) and `get_top_projects_by_classification` (Projects Ranked by Intentional). Fix-rate / velocity / cumulative / trend CTEs are also unchanged — those already count FP/Intentional on the *fixed* side of the ledger, which is exactly what the fix-rate metric is supposed to do
- Real-world example: `Vista360_Fix_KeyCloak` has 97 stream_defects with 96 classified as False Positive/Intentional. Before this release the Overview severity donut, category chart, hotspots, aging, OWASP tab and CWE Top 25 tab all showed 97 defects. After the fix they all correctly show **1** truly-active defect, matching the Defects by Stream table

##### 🔁 Refined: Five "Raw Defect" Charts Reverted to Include Dismissed
- Follow-up on the change above: the sweep was too aggressive for five charts whose whole purpose is to visualise *what Coverity is finding*, not what still needs work. Notably, **Current Triage Progress** was collapsing to `total_defects = 0` on projects where every defect had been triaged as False Positive or Intentional, hiding the entire triage picture on the Trend & Progress tab
- Reverted (now include dismissed again):
  - `get_defects_by_severity` — Defects by Severity donut
  - `get_defects_by_checker_category` — Top Defect Categories
  - `get_defects_by_checker_name` — Top Defect Checkers
  - `get_defect_density_by_project` — Defect Density (per KLOC)
  - `get_triage_progress_summary` — Current Triage Progress card and its classification breakdown
- Still enforce "active only" (these are about remediation load, not defect volume):
  - Overview `Active Defects` and `High Severity Defects` cards
  - File Hotspots, Defect Aging Distribution
  - Triage Trends stacked bars (per-stream classification of currently-outstanding defects)
  - OWASP Top 10, CWE Top 25 tabs
  - `get_defect_trend_summary` `current_state` (Current Outstanding count)
  - `get_top_projects_by_triage_activity`

##### 🧭 "Outstanding Defect" Semantic Corrected — `fixed_snapshot_element_id` Is Unreliable
- Root cause: `stream_defect.fixed_snapshot_element_id IS NULL` was used as the "currently outstanding" test in every active-defect query. But Coverity Connect does **not** clear that column when a previously-fixed defect re-appears in a later snapshot — so any defect that was once eliminated and later reintroduced looked "fixed" to us even though the UI still shows it as outstanding
- The Coverity UI itself uses the `last_detected_snapshot` table: a defect is currently outstanding iff `last_detected_snapshot.detected_snapshot_id = <latest non-deleted snapshot.id for its stream>`
- Introduced three class constants on `CoverityMetrics` that codify the correct pattern once — every query now injects them instead of open-coding `fixed_snapshot_element_id`:
  - `_ACTIVE_JOIN_SQL` — joins `last_detected_snapshot` (`lds`) and a per-stream max-snapshot subquery (`sn_latest`) via `stream_element.stream_id`
  - `_ACTIVE_COND_SQL` — `lds.detected_snapshot_id = sn_latest.latest_snap_id`
  - `_FIXED_COND_SQL` — the inverse (`IS NULL OR !=`); used alongside `fixed_snapshot_element_id IS NOT NULL` in code-fixed / fix-time / fix-rate queries so only defects that truly no longer appear are counted as fixed
- Applied to every active-defect SQL site (~20 queries): `get_total_defects_by_project`, `get_defects_by_severity`, `get_defects_by_checker_category`, `get_defects_by_checker_name`, `get_defect_density_by_project`, `get_overall_summary` (project + global branches), `get_file_hotspots`, `get_triage_trends`, `get_checker_classification_breakdown`, `get_top_projects_by_classification`, `get_fix_rate_metrics` (three CTEs), `get_defect_velocity_trend`, `get_cumulative_defect_trend`, `get_defect_trend_summary` (period_triaged + current_state), `get_defect_aging_distribution`, `get_triage_progress_summary`, `get_technical_debt_summary`, `get_top_projects_by_fix_rate`, `get_top_projects_by_triage`, `get_top_users_by_fixes` (both branches), `get_owasp_top10_metrics`, `get_owasp_category_details`, `get_cwe_top25_metrics`, `get_cwe_top25_details`
- `get_triage_progress_summary` was additionally reshaped to start `FROM stream_defect sd` (was `FROM defect_triage dt` with a `LEFT JOIN` to `sd`), so orphan triages that don't belong to a currently-outstanding defect no longer inflate the totals
- Real-world example: project `786-834_proyecto_hrim_workday` — Coverity UI shows 2 outstanding defects (CID 38907 Intentional and CID 39378 Unclassified with a stale `fixed_snapshot_element_id`). Before this fix, `get_triage_progress_summary.total_defects = 1`; after, `total_defects = 2` and the classification breakdown matches the UI exactly
- Rebuild any cached dashboard (`--use-cache` runs) after upgrading — counts for all of the above metrics will change on projects where at least one defect was ever eliminated-then-reintroduced

##### 🧮 Function Complexity Distribution Leaked Instance-wide Numbers into Every Project
- `get_function_complexity_distribution` and `get_most_complex_functions` had no project filter — every project's ZIP export and every DB-mode dashboard showed the *instance-wide* complexity histogram and top-N list, so projects with zero streams still displayed thousands of functions in the "Function Complexity Distribution" chart and the "Most Complex Functions" table
- Both queries now join `stream_file` → `stream_element` → `stream` → `project_stream` → `project` when a project filter is active and add `AND p.name = ANY(%s)`. Projects with no streams (e.g. `894-985-DetalleConsumo`) now correctly return empty
- Re-export required: pre-1.0.17 ZIPs still contain leaky per-project `function_complexity_distribution.json`. Re-run `coverity-export` with 1.0.17+ to get correct per-project numbers in ZIP dashboards

#### Developer Experience

##### 🎯 Empty-state Message on the Scan Activity Chart
- If a project or instance has no snapshots in the analysed `--days` window, the "Scan Activity Over Time" section now stays visible and shows an inline info alert:
  > ℹ️ No scan activity in the last N days. Re-export with a longer `--days` window if you expect older snapshots to be included.
- Same treatment on the aggregated multi-instance dashboard. Makes it obvious the metric ran and returned nothing, versus the section being disabled.

##### 🔖 Single-Source-of-Truth Package Version
- `pyproject.toml` now uses `dynamic = ["version"]` with `[tool.setuptools.dynamic] version = {attr = "coverity_metrics.__version__.__version__"}`
- Both the pip metadata (`pip show coverity-metrics`) and the runtime `--version` output now read from the same file: `coverity_metrics/__version__.py`
- Future releases: bump one file, not two. No more "installed 1.0.16 when 1.0.17 was expected" surprises.

---

### Version 1.0.16 - 2026-05-05

**Module Support & Documentation Release**

#### New Features

##### 🐍 `python -m coverity_metrics` Module Support
- The package can now be invoked as a Python module in addition to the existing CLI entry points
- Usage:
  ```bash
  python -m coverity_metrics dashboard  # equivalent to coverity-dashboard
  python -m coverity_metrics export     # equivalent to coverity-export
  python -m coverity_metrics report     # equivalent to coverity-metrics
  ```
- All arguments are passed through unchanged — every flag documented for the CLI entry points works identically
- Running without a subcommand prints a usage summary listing all available subcommands
- Implemented via a new `coverity_metrics/__main__.py`

#### Documentation

##### 📋 Multi-Project `--project` Parameter Now Documented
- **Issue**: Documentation described `--project` as accepting only a single project name, even though the CLI has always supported comma-separated multiple projects
- **Clarification**: Pass multiple projects as a comma-separated string — e.g. `--project "AppA,AppB,AppC"` — to generate individual per-project dashboards for each, plus an aggregated instance dashboard. Works in both database mode and ZIP file mode.
- **Updated**: README parameter table, database/ZIP mode examples, auto-detection behavior notes, and USAGE_GUIDE quick-start section
- Added `python -m coverity_metrics` usage examples to README and USAGE_GUIDE

---

### Version 1.0.15 - 2026-05-05

**Bug Fix Release**

#### Bug Fixes

##### 📊 Fixed Project-Level Metrics in ZIP Dashboards
- **Issue**: Project-level dashboards generated from ZIP exports showed instance-wide aggregate data instead of project-specific data for "Top Analysis Versions Used" and 7 other metrics
- **Example**: A project dashboard would show all analysis versions used across the entire instance rather than just the versions used for that specific project
- **Root Cause**:
  - 8 methods in `ZipDataLoader` were hardcoded to always read from instance-level files (`self._get_metric_file()`) instead of checking for project-specific files first
  - Project-level metrics were not being exported to ZIP files in the first place
- **Fix**:
  - Updated 8 `ZipDataLoader` methods to use `_read_metric_json()` which properly checks for project-specific data: `get_analysis_versions`, `get_function_complexity_distribution`, `get_snapshot_performance`, `get_commit_time_statistics`, `get_commit_activity_patterns`, `get_defect_discovery_rate`, `get_defect_velocity_trend`, `get_cumulative_defect_trend`
  - Added these metrics to `project_metrics_config` in `export.py` so they are now exported at the project level
- **Impact**: After re-exporting with `coverity-export`, project-level dashboards generated from ZIP files will correctly display project-scoped data instead of instance aggregates

##### ⏰ Fixed Negative Database Uptime Display
- **Issue**: Database uptime showed negative values like "-1d 23h 24m" along with the start time showing as future date
- **Root Cause**: `get_instance_info()` in `metrics.py` was stripping timezone information from PostgreSQL's `pg_postmaster_start_time()` (which returns a timezone-aware datetime) and comparing it with naive local time from `datetime.now()`, causing timezone offset mismatches where the database start time appeared to be in the future
- **Fix**:
  - Updated calculation to use UTC consistently: `datetime.now(timezone.utc)` for current time
  - Convert database start time to UTC using `.astimezone(timezone.utc)` to handle timezone offsets correctly
  - Added guard to detect and display "Invalid (negative)" if negative uptime occurs (edge case protection)
- **Impact**: Database uptime now calculates correctly regardless of database timezone configuration or system local timezone

---

### Version 1.0.14 - 2026-03-19

**Parameter Enhancement & Documentation**

#### Added
- **`fetch_all` Parameter**: Added `fetch_all` parameter to metrics methods — pass `fetch_all=True` to any method with a `limit` parameter to retrieve the complete result set instead of just the top N results

#### Improvements
- **CLI Parameter Documentation**: Enhanced CLI parameter documentation in README with comprehensive reference tables for all tools (`coverity-dashboard`, `coverity-metrics`, `coverity-export`)
- **Python Library Examples**: Updated Python library usage examples in README to reflect current API and features

---

### Version 1.0.13 - 2026-03-13

**Leaderboard Cleanup**

#### Changes

##### 🗑️ Removed "Most Improved" Leaderboard Card
- **Change**: The "Most Improved" leaderboard card has been removed from the Team Leaderboards section
- **Reason**: Improvement percentage was unreliable for sparse snapshot data — projects with only one snapshot had no meaningful baseline to compare against, making the metric misleading
- **Impact**: Removed `get_most_improved_projects` from all dashboard generation paths (`dashboard.py`) and from the ZIP export config (`export.py`); the "Improvement" entry has also been removed from the Leaderboard Metrics Explained legend

---

### Version 1.0.12 - 2026-03-05

**Packaging Maintenance**

#### Changes

##### 🧹 Removed Stale `~overity_metrics` dist-info Artefact
- **Issue**: pip printed `WARNING: Ignoring invalid distribution ~overity-metrics` on every invocation due to a corrupted `~overity_metrics-1.0.8.dist-info` directory left behind by a previously interrupted install
- **Fix**: Removed the stale directory from site-packages; no source code changes
- **Impact**: pip no longer emits the spurious warning

---

### Version 1.0.11 - 2026-03-05

**Bug Fix: PostgreSQL ROUND Compatibility**

#### Bug Fixes

##### 🐛 Fixed `ROUND(double precision, integer)` Error in Top Projects by Fix Rate
- **Issue**: `coverity-dashboard` crashed with `psycopg2.errors.UndefinedFunction: function round(double precision, integer) does not exist` when generating the dashboard
- **Root Cause**: In `metrics.py` `get_top_projects_by_fix_rate`, `EXTRACT(EPOCH FROM ...)` returns `double precision` in PostgreSQL. Dividing a `numeric` value by `double precision` yields `double precision`, and PostgreSQL only defines `ROUND(numeric, integer)` — not `ROUND(double precision, integer)`
- **Fix**: Added `::numeric` cast to the `EXTRACT(EPOCH FROM (last_snapshot - first_snapshot))` expression so the result is `numeric` throughout and `ROUND(x, 2)` resolves correctly
- **Impact**: Dashboard generation now completes successfully on all PostgreSQL versions

---

### Version 1.0.10 - 2026-03-04

**Documentation & Project Structure Improvements**

#### Changes

##### � Upgraded Python Dependencies to Latest Versions
All minimum version pins in `requirements.txt` have been bumped to the latest available releases:

| Package | Previous | Updated |
|---|---|---|
| `psycopg2-binary` | `>=2.9.0` | `>=2.9.11` |
| `pandas` | `>=2.0.0` | `>=3.0.1` |
| `matplotlib` | `>=3.7.0` | `>=3.10.8` |
| `seaborn` | `>=0.12.0` | `>=0.13.2` |
| `python-dateutil` | `>=2.8.0` | `>=2.9.0.post0` |
| `openpyxl` | `>=3.1.0` | `>=3.1.5` |
| `jinja2` | `>=3.1.0` | `>=3.1.6` |
| `plotly` | `>=5.18.0` | `>=6.6.0` |
| `tqdm` | `>=4.66.0` | `>=4.67.3` |

##### �📁 Refactored Project Structure Documentation
- Updated README with new file paths and project layout to accurately reflect the current source tree
- Improved organization and clarity of repository structure descriptions

##### 📊 Updated Presentation Guide
- Added Python script option for generating presentations from the command line
- Revised slide structure details for improved accuracy and usability

---

### Version 1.0.9 - 2026-03-03

**ZIP Export, Progress Tracking & Aggregated Dashboard Fixes**

#### Bug Fixes

##### 📦 Fixed Missing Classification Charts in ZIP-based Dashboards
- **Issue**: Dashboards generated from ZIP files (offline/export mode) were missing the "Checker Classification Breakdown" and "Top Projects/Streams by Triage Classification" sections
- **Root Cause**: The two metrics (`checker_classification_breakdown`, `top_projects_by_classification`) were never added to the export metric configs in `export.py` when the feature was created — `ZipDataLoader` had the reader methods, the templates had the chart sections, but the JSON files were never written into the ZIP
- **Fix**: Added both metrics to `export_instance_to_json()` and `export_project_specific_metrics()` in `export.py`
- **Impact**: Re-export with `coverity-export` to get ZIPs with the new JSON files; ZIP-based dashboards will then show the missing chart sections

##### ▶️ Implemented `--track-progress` and `--resume`
- **Issue**: `--track-progress` and `--resume` CLI flags were accepted but did nothing — `ProgressTracker` was instantiated but never used in any generation loop
- **Fix**: Fully wired progress tracking into all 7 generation paths in `dashboard.py`
  - `--track-progress`: prints a session ID at the start of generation; records each completed dashboard; call `complete_session()` at the end
  - `--resume SESSION_ID`: loads the previously completed dashboard set from `cache/progress/progress_{SESSION_ID}.json`; skips already-finished items with a `[SKIP]` message; continues from the interruption point
- **Label scheme**:
  - Aggregated view: `"Aggregated View"`
  - Instance overview: `"{instance_name}"` (multi-instance) or `"{instance_name} - All Projects"` (single-instance)
  - Per-project: `"{instance_name} - {project_name}"`
- **Impact**: Large multi-instance / multi-project runs that are interrupted (network drop, timeout, etc.) can now be resumed without regenerating already-finished dashboards

##### 📅 Fixed Hardcoded "Last 90 Days" in Aggregated Dashboard
- **Issue**: The aggregated dashboard always showed "Last 90 Days" in the User Activity section title, card labels, table headers, and tooltips, regardless of the `--days` argument passed
- **Root Cause**: `dashboard_aggregated.html` was written with `90` hardcoded in 5 places; the `trend_period_text` Jinja2 variable was available but the template was never updated to use it
- **Fix**: Replaced all 5 hardcoded occurrences with `{{ trend_period_text }}` / `{{ trend_period_text|lower }}`
  - Section title: `Last 90 Days` → dynamic
  - Card labels: `Total New (90d)` / `Total Fixed (90d)` → dynamic
  - Table headers: `New Defects (90d)` / `Fixed (90d)` → dynamic
  - Active Users and Inactive Licenses tooltips: `last 90 days` → dynamic
- **Impact**: The aggregated dashboard now correctly reflects `--days 365` (or any other value) throughout

### Version 1.0.8 - 2026-03-02

**OWASP Top 10 Count Consistency Fix**

#### Bug Fixes

##### 🛠️ Fixed OWASP Top 10 Summary / Detail Count Inconsistency
- **Issue**: OWASP Top 10 category sections showed contradictory numbers in the same panel
  - Example (A09: Security Logging and Monitoring Failures): "Total Defects: 5" in the header, "Defects (6 total)" in the table heading, and "1 CWE mapped" when the table listed 2 different CWEs
- **Root Cause 1 — Last-Writer-Wins CWE Mapping**:
  - 31 CWEs appear in more than one OWASP category in the mapping table
  - The aggregation code built a flat `cwe_to_owasp` dict: each duplicate key silently overwrote the previous entry
  - CWE-918 (SSRF) is in both A09 and A10; A10 is iterated last, so `cwe_to_owasp[918]` pointed only to A10
  - Defects with CWE-918 were excluded from A09's summary count but the detail query (which used `cp.cwe IN (all A09 CWEs)`) correctly included them — producing the mismatch
- **Root Cause 2 — Different Deduplication in Summary vs Detail**:
  - Summary counted `COUNT(DISTINCT sd.id)` — physical stream-defect rows, which can be duplicated for merged defects
  - Detail table used `SELECT DISTINCT ON (sd.merged_defect_id)` — one row per logical defect
  - For projects with merged defects the two counts diverge
- **Fix**:
  - Changed `cwe_to_owasp` to a **multi-value mapping** (`CWE → [list of all matching categories]`)
  - Aggregation loop now iterates over every matching category for each CWE, so shared CWEs contribute to all of their categories
  - Changed summary SQL to `COUNT(DISTINCT sd.merged_defect_id)` with `AND sd.merged_defect_id IS NOT NULL` to mirror the detail table's deduplication
- **Impact**: "Total Defects" in the OWASP category header, the defect table row count, and the CWE count now always match

### Version 1.0.7 - 2026-02-25

**New Features & Fixes**

#### Features
- **Script Execution Time**: Script now prints total execution time after dashboard generation, helping users measure performance for large datasets.

#### Bug Fixes & Improvements
- **Accurate Active Users**: Instance-level "Active Users" now deduplicates by activity (triage, comment, commit) and matches project-level logic for consistency.
- **Dashboard Bug Fix**: Dashboard now displays the correct "Active Users" count at all levels (instance, project, aggregated).
- **HTML Escaping**: Defect file/function fields are now HTML-escaped in dashboards to prevent invalid HTML/JS errors from untrusted content.

### Version 1.0.6 - 2026-02-24

**ZIP Export Critical Bug Fixes**

#### Bug Fixes

##### 🛠️ Fixed Project-Level Dashboard Data Filtering from ZIP Files
- **Issue**: Project-level dashboards generated from ZIP files were showing instance-level aggregate data instead of project-specific data
  - Example: Project dashboard showed 90 defects (instance total) instead of 5 defects (project actual)
- **Root Cause**: 
  - Export only created project-level files for OWASP and CWE metrics
  - ZipDataLoader always read from instance-level files regardless of `project_name` setting
  - Core metrics (overall_summary, defects_by_severity, trends, etc.) were missing at project level
- **Fix**:
  - **Updated export.py**: Now exports complete project-specific versions of all core metrics
    - overall_summary.json
    - defects_by_severity.json
    - defect_trends.json
    - triage_progress_summary.json
    - fix_rate_metrics.json
    - defect_aging_distribution.json
    - technical_debt_summary.json
    - All other dashboard metrics
  - **Updated zip_data_loader.py**: Added intelligent file path resolution
    - New `_read_metric_json()` method checks for project-specific files first
    - Falls back to instance-level files if project file doesn't exist
    - All metric getter methods now use this smart lookup
- **Impact**: Project dashboards from ZIP files now correctly show filtered data matching database mode behavior

##### 📊 Fixed Triage Progress Aggregation Discrepancy
- **Issue**: Aggregated triage progress showed different numbers between database and ZIP sources
  - Database: 36 Classified, 234 Unclassified, 13.3% Completion ✅
  - ZIP (before): 57 Classified, 213 Unclassified, 21.1% Completion ❌
- **Root Cause**: Aggregation code incorrectly summed individual triage state counts (bug_count + false_positive_count + intentional_count + action_assigned_count = 57) instead of using the `classified_count` field
  - Problem: `action_assigned_count` includes defects with actions assigned but still marked as "Unclassified"
  - The `classified_count` field correctly counts only defects with actual classifications
- **Fix**: Changed aggregation in dashboard.py to use `total_triaged` (sum of `classified_count` from each instance) instead of `sum(triage_by_state_agg.values())`
- **Impact**: ZIP and database sources now produce identical triage statistics

#### Technical Details
- ZIP file structure now includes project subdirectories with complete metric sets
  - `{instance}/{metric}.json` - instance-level data
  - `{instance}/{project}/{metric}.json` - project-specific data
- ZipDataLoader maintains backward compatibility with older ZIP exports
- No changes to database query logic - already correct

---

### Version 1.0.5 - 2026-02-20

**Enhanced Security Reporting & Complete Coverage**

#### Major Enhancements

##### 🛡️ Complete OWASP Top 10 2025 Security Coverage
- **All 10 Categories Always Visible**: Dashboard now shows all OWASP Top 10 categories regardless of defects
- **PASS/FAILED Status Badges**:
  - 🟢 **PASS** (green): No defects for this category - safe!
  - 🔴 **FAILED** (red): Has defects requiring attention
- **Interactive Defect Exploration**:
  - Click FAILED rows to expand and see ALL defects (no limits)
  - PASS rows are non-clickable and visually faded
- **Complete Security Posture**: Instantly see which OWASP categories are clean vs problematic
- **Summary Metrics**: "X/10 Failed" counts for quick assessment

##### 🏆 Complete CWE Top 25 2025 Weakness Coverage
- **All 25 CWEs Always Visible**: Shows complete MITRE CWE Top 25 list
- **Status Column**: Each CWE entry has PASS/FAILED badge
- **Ranked by Danger**: Industry-standard rankings (1-25) from MITRE
- **Same Interactive Experience**: Click FAILED entries to see all defect details
- **Summary Metrics**: "X/25 Failed" counts

##### 📝 Enhanced Defect Detail Tables
- **Comprehensive Information**:
  - **CID**: Actual Coverity ID (now correctly using merged_defect_id)
  - **Type**: Checker name describing defect type
  - **Severity**: Color-coded High/Med/Low badges
  - **File**: Full file path (with overflow handling)
  - **Function**: Function name where defect occurs
  - **CWE**: CWE identifier (OWASP report only)
- **Show ALL Defects**: Removed 10-per-CWE limits - see complete defect lists
- **Scrollable Tables**: Clean 400px height containers for large lists
- **Fixed Headers**: Sticky headers with proper visibility
- **Simplified Display**:
  - Removed aggregated "CWE Breakdown" sections
  - Removed "Top Checkers" summary from CWE Top 25
  - Focus on actionable defect details

#### Visual Improvements
- **Color-Coded Rows**:
  - FAILED: Red-tinted background, clickable, pointer cursor
  - PASS: Green-tinted faded background, non-clickable
- **Fixed Table Headers**: Proper text color (#2c3e50) on white background
- **Responsive Design**: Tables adapt to content with scrolling

#### Database & Performance
- **Corrected CID Field**: Now uses `stream_defect.merged_defect_id` (actual user-visible CID)
- **Fixed Schema Joins**:
  - Checker names via `checker_type` table
  - Function names via `stream_defect_occurrence.function_id`
  - Removed invalid `stream_file` joins
- **Performance Optimization**: Only loads details for FAILED entries (not PASS)

#### Bug Fixes
- Fixed table header visibility in security reports
- Resolved undefined CSS variable issues
- Fixed UnboundLocalError for commit_activity

#### Use Cases
- **Security Audits**: Instant view of OWASP/CWE compliance status
- **Remediation Planning**: Click FAILED categories to see all defects needing fixes
- **Compliance Reporting**: Show complete coverage for security frameworks
- **Team Communication**: Clear PASS/FAIL badges for stakeholder presentations

---

### Version 1.0.4 - 2026-02-19

**Progress Tracking & User Experience Update**

#### New Features
- **Comprehensive Progress Tracking for Multi-Instance Dashboards**
  - Added tqdm-based progress bars for all multi-instance dashboard generation workflows
  - Real-time visibility into long-running operations (10+ instances with hundreds of projects)
  - Pre-calculates total work items before execution (1 aggregated + N instances + M projects)
  - Dynamic progress descriptions showing current instance and project being processed
  - Automatic time estimation (elapsed time, remaining time, completion ETA)
  - Processing speed metrics (dashboards/second)
  
- **Three Progress Tracking Scenarios**
  - **Specific Instance + All Projects**: Shows "1 instance + N projects" with project counter
  - **All Instances + Specific Project**: Shows "Instance X/Y: {name}" for each instance
  - **Full Auto Mode (All Instances + All Projects)**: Overall progress bar tracking all dashboard types
    - Pre-flight calculation displays: "1 aggregated + N instances + M projects"
    - Single unified progress bar showing completion across all work
    - Postfix strings display current item: "{project} (X/Y)"

- **Commit Activity Patterns Analysis**
  - Added `get_commit_activity_patterns()` method to analyze when commits occur
  - Groups commits by hour of day (0-23) and day of week (0-6, Sunday-Saturday)
  - Creates 3-hour time blocks: 00-02, 03-05, 06-08, 09-11, 12-14, 15-17, 18-20, 21-23
  - Identifies busiest and quietest 3-hour windows with commit counts and statistics
  - Identifies busiest and quietest days of the week
  - Calculates average duration, files changed, and new defects per commit window
  - Multi-instance aggregation support with `get_aggregated_commit_activity()`
  - Integrated into both single-instance and aggregated dashboards
  - Display format: "14:00-16:00 (2 PM - 4 PM)" with 12-hour AM/PM conversion

#### User Experience Improvements
- Progress bars provide immediate feedback for operations that previously showed blank screen
- Users can see exactly how many dashboards will be generated before work begins
- Clear visibility into which instance and project is currently being processed
- Professional enterprise-grade experience for large multi-instance deployments
- Accurate completion percentage and time estimates help users plan their workflow

#### Technical Details
- **Files modified**: `dashboard.py` (lines 665-775), `metrics.py` (lines 1082-1210), `multi_instance_metrics.py` (lines 296-424)
- **Progress tracking implementation**:
  - Lines 665-686: Specific instance + all projects mode with total calculation
  - Lines 688-704: All instances + specific project mode with instance counter
  - Lines 706-775: Full auto mode with comprehensive work calculation and overall progress bar
- **Example output**:
  ```
  Calculating total work for progress tracking...
    Total dashboards to generate: 47
    - 1 aggregated dashboard
    - 10 instance dashboards
    - 36 project dashboards
  
  Overall Progress: 23/47 [=========>...] 48% [04:36<04:48, 12.0s/dashboard]
  Instance 5/10: Staging projects
  project_alpha (3/8)
  ```
- **Commit activity patterns**:
  - SQL queries use `EXTRACT(HOUR FROM sn.date_created)` and `EXTRACT(DOW FROM sn.date_created)`
  - Qualified column names with table alias (sn.date_created) to avoid ambiguous references
  - 3-hour block aggregation with weighted averages for statistics
  - Returns: busiest_hours, quietest_hours, busiest_day, quietest_day with commit counts

#### Bug Fixes
- Fixed SQL ambiguous column error in commit activity queries by qualifying all column references
- Progress bars now use `tqdm.write()` for clean output without interfering with progress display

### Version 1.0.3 - 2026-02-19

**Security & Technical Debt Update**

#### New Features
- **Technical Debt Estimation**
  - Added `get_technical_debt_summary()` method for effort estimation
  - Industry-standard formulas: High=4h, Medium=2h, Low=1h, Unspecified=0.5h per defect
  - Displays total hours, work days, work weeks, and breakdown by impact level
  - Integrated into "Trends & Progress" dashboard tab
  - Based on Coverity's `checker_properties.impact` field (High/Medium/Low)

- **CWE Top 25 2025 Update**
  - Updated from CWE Top 25 2024 to 2025 version (MITRE)
  - All 25 CWE rankings updated with new scores
  - Major ranking changes: CWE-306 (#20→#8), CWE-416 (#4→#18), CWE-787 (#5→#21)
  - New entries: CWE-120 (Classic Buffer Overflow #19), CWE-327 (Broken Crypto #23)
  - Removed entries: CWE-94 (Code Injection), CWE-276 (Incorrect Permissions)
  - Dashboard tab updated to show "CWE Top 25 2025"

#### Enhanced Documentation
- Updated README.md with "Latest Enhancements (2025)" section
- Added technical debt, OWASP Top 10, CWE Top 25 to features list
- Added Security Compliance Metrics section
- Added "For Security Teams" use cases
- Updated Python API examples with new methods
- Documented all 7 dashboard tabs (Overview, Code Quality, Performance, Trends & Progress, Leaderboards, OWASP Top 10, CWE Top 25)

#### Dashboard Enhancements
- Technical Debt Summary section in "Trends & Progress" tab
  - 4 primary cards: Total Hours, Work Days, Work Weeks, Avg per Defect
  - 4 breakdown cards: High/Medium/Low/Unspecified impact with color-coded severity
  - Info alert explaining estimation formula
- CWE Top 25 tab displays 2025 rankings and scores

#### Technical Details
- Files modified: `cwe_top25_mapping.py`, `metrics.py`, `dashboard.py`, `dashboard.html`
- New method: `CoverityMetrics.get_technical_debt_summary()`
- Database query: Joins `stream_defect` with `checker_properties` for impact levels
- Calculation: CASE statement for effort estimation based on impact
- Returns: Dictionary with totals (hours/days/weeks), defect count, breakdown by impact, average per defect

### Version 1.0.2 - 2026-02-18

**Feature Update**

#### Features
- Added `fetch_all` parameter support
- Enhanced documentation

### Version 1.0.0 - 2026-02-18

**Initial Release**

#### Features
- Full Python package structure with CLI commands
- Three CLI tools: `coverity-dashboard`, `coverity-metrics`, `coverity-export`
- Interactive HTML dashboard with Plotly charts
- Multi-instance aggregation support
- Performance caching system
- Progress tracking for large datasets
- CSV/JSON export functionality
- PostgreSQL database integration

#### CLI Commands
- `coverity-dashboard` - Generate interactive HTML dashboards
- `coverity-metrics` - Console text reports
- `coverity-export` - Export data to CSV files

#### Configuration
- Uses `config.json` for database configuration
- Auto-detects single vs multi-instance mode
- Support for multiple Coverity instances

#### Documentation
- Complete README with installation and usage
- Multi-instance setup guide
- Caching performance guide
- Usage examples and workflows

---

## Future Releases

Document changes here for upcoming versions.

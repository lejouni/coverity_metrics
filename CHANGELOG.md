# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.18] - 2026-08-04

### Fixed
- **Daily Fix Efficiency % always showed 0% when fixes and introductions happened on different days**
  - `get_defect_velocity_trend` computed `fix_efficiency_pct = Fixed / New * 100` with an early `WHEN new_count = 0 THEN 0` branch, so any day that had fixes but no newly-introduced defects collapsed to 0% — which is the common case, since fixes rarely land in the same daily snapshot as the defects they resolve
  - The dashboard tooltip already promised the correct formula: `Fixes / (Fixes + Introductions) × 100%`. The SQL now matches: `Fixed / (New + Fixed) * 100`, with a single divide-by-zero guard when both are 0
  - Real-world example: `853-descuento-en-factura-changeplan` — 5 new defects introduced 2023-05-08, all 5 fixed 2023-05-17. Old behaviour: fix efficiency = 0% on every row of the trend. New behaviour: 2023-05-17 correctly shows 100%, matching the aggregate `fix_rate_metrics.fix_rate_percentage = 100%`

## [1.0.17] - 2026-08-04

### Added
- **Scan Activity Over Time Chart**
  - New Trends & Progress section on every project and instance dashboard showing snapshot/commit counts bucketed over time (daily for per-project, weekly for instance-wide)
  - Secondary y-axis overlays unique committers per bucket so the chart tells both "how often" and "who"
  - Aggregated multi-instance dashboard adds a per-instance overlay chart — one colored line per instance — for cross-instance cadence comparison
  - Backed by new `CoverityMetrics.get_scan_activity_trend(days, granularity)` and `MultiInstanceMetrics.get_aggregated_scan_activity(days, granularity)`
  - ZIP exports now include `scan_activity_trend.json` at both project and instance levels; `ZipDataLoader` exposes `get_scan_activity_trend()` and returns an empty DataFrame gracefully when reading pre-1.0.17 ZIPs

- **Parallel Per-Project Export & Dashboard Generation**
  - New `--workers N` (`-w`) flag on both `coverity-export` and `coverity-dashboard` — default 1, clamped to 1–8
  - In database mode each worker gets its own `CoverityMetrics` instance (and therefore its own Postgres connection); psycopg2 connections aren't thread-safe, so no sharing
  - In ZIP mode each worker gets its own `ZipDataLoader` (ZipFile handles aren't thread-safe)
  - Auto-mode dashboard generation and per-instance export loops both parallelized with `concurrent.futures.ThreadPoolExecutor`
  - Typical wins: 4–6× at `--workers 4` for the database export path, ~2–3× for the ZIP dashboard path
  - Per-project exceptions are logged and the loop continues, matching current behaviour

- **Execution Time Reporting**
  - Both `coverity-export` and `coverity-dashboard` print `Total execution time: …` at the end (via a `finally` block, so it fires even on failure)
  - Export additionally prints per-instance timing, e.g. `Time: 4m 12.3s for 645 projects (~0.39s/project)`
  - Human-readable format: `8.7s`, `2m 5.3s`, or `1h 15m 23s`

- **`--version` Flag on `coverity-dashboard`**
  - Prints `coverity-dashboard version: X.Y.Z` and exits. Brings the dashboard CLI in line with `coverity-export` and `coverity-metrics`, which already supported `--version`. Handler short-circuits before the timing wrapper so no execution-time line is printed.

- **📸 Snapshots Tab on Project Dashboards — Recent Analysis Command Lines**
  - New project-only tab (📸 Snapshots) shows the exact `cov-build` and `cov-analyze` invocations recorded for the most recent 10 snapshots on the project — mirrors the "Command Line" data shown per snapshot in the Coverity Connect UI
  - Each snapshot is a collapsible entry displaying stream, timestamp, invoker (user), host, and platform; expanding reveals a per-element block (`Build / Capture` and `Static Analysis`) with runtime, success/failure counts, and the full command in a preformatted block
  - Backed by new `CoverityMetrics.get_snapshot_commands(limit=20)` which joins `snapshot` → `snapshot_element` and filters by project via `project_stream`/`project`
  - ZIP exports now include `snapshot_commands.json` under `{instance}/{project}/`; `ZipDataLoader.get_snapshot_commands()` reads it and returns an empty DataFrame gracefully when opening pre-1.0.17 ZIPs
  - Tab button and section are hidden automatically when there are no command rows to show (e.g. instance-level dashboards or projects with no committed snapshots)

### Changed
- **Instance-scoped `CoverityMetrics` reuse across projects**
  - Both the export CLI and the dashboard CLI now build one `CoverityMetrics` per instance and rescope via the `.project_name` property between projects
  - Eliminates ~N-1 redundant Postgres connect + auth handshakes per instance (previously one per project)
  - Redundant `get_available_projects()` call at the top of the per-instance export loop removed
- **Jinja `Environment` and inline CSS cached at module scope**
  - `Environment(loader=FileSystemLoader(...))`, template loading, and the inline CSS payload are now built once per process and reused across every project dashboard render, instead of re-created hundreds of times
- **"Scan Activity Over Time" empty-state message**
  - When there are no snapshots in the analysed window, project and instance dashboards now show an inline info alert ("No scan activity in the last N days") instead of silently hiding the section — makes it clear the metric ran and returned nothing, versus the section being disabled
- **Single-source-of-truth for the package version**
  - `pyproject.toml` now uses `dynamic = ["version"]` + `[tool.setuptools.dynamic] version = {attr = "coverity_metrics.__version__.__version__"}` — the wheel metadata is stamped from `__version__.py` at build time, so future releases only need to bump one file

### Fixed
- **Graceful DB errors**
  - `CoverityDatabase.execute_query()` and `execute_query_dict()` now wrap the query with `try/except`, log a warning via the module logger, roll the connection back, and return `[]` on any error. Callers receive an empty DataFrame instead of a traceback; the process no longer aborts if a single query fails
- **Division-by-zero in leaderboard queries**
  - `avg_fixes_per_day` in `get_top_projects_by_fix_rate` wrapped in `NULLIF(EXTRACT(EPOCH FROM ...), 0)` so projects with a single snapshot or same-timestamp snapshots return `NULL` instead of raising `division by zero`
  - Audited every other SQL division in `metrics.py` and `multi_instance_metrics.py` — all remaining sites are either dividing by a constant, guarded by `CASE WHEN ... > 0`, wrapped in `NULLIF`, or guarded by a Python `if x > 0` check
- **Jinja `|round()` on `None` values**
  - Every leaderboard cell that reads from a `NULLIF`-guarded SQL column (`avg_fixes_per_day`, `avg_triage_per_day`, `avg_comments_per_day`, `triage_percentage`) now uses `{{ field|round(2) if field is not none else 'N/A' }}` — fixes crashes when a NULLIF returns `NULL` and the template tries to round it
  - Aggregated dashboard's per-instance `triage_completion` fixed at the source (`multi_instance_metrics.py`) — `dict.get(k, 0)` returns `None` when the key exists with value `None`, so callers now use `.get(k) or 0` to convert `None`/missing to `0`
- **`AttributeError: 'ZipDataLoader' object has no attribute 'get_scan_activity_trend'`** when opening a dashboard from a pre-1.0.17 ZIP export — `ZipDataLoader` gained the method and returns an empty DataFrame if the metric isn't in the ZIP

- **Ctrl+C responsiveness during parallel runs**
  - `ThreadPoolExecutor`'s implicit `shutdown(wait=True)` at the `with` block exit was blocking Ctrl+C until every in-flight worker finished — on a 645-project run that made the CLI look frozen for minutes
  - All three parallel sites (export, dashboard DB-mode, dashboard ZIP-mode) now build the executor explicitly, catch `KeyboardInterrupt` around the `as_completed` loop, cancel every pending future, call `executor.shutdown(wait=False, cancel_futures=True)`, and re-raise
  - Both `coverity-export` and `coverity-dashboard` catch `KeyboardInterrupt` at the top level and exit cleanly with code 130 (`[INTERRUPTED] Aborted by user.`)
  - Effect: first Ctrl+C now drops all queued tasks immediately; only currently-executing DB queries or renders need to finish (typically seconds). A second Ctrl+C hard-kills the process.

- **Individual Contributors leaderboards ignored `--days`**
  - All five leaderboard queries in `dashboard.py` were hardcoded to `days=30`, so a dashboard generated with `--days 3650` still showed "Last 30 Days" cards. Now `top_projects_by_fix_rate`, `top_projects_by_triage`, `top_users_by_fixes`, `top_triagers`, and `most_collaborative_users` all pass the CLI-supplied `days` value
  - Template subtitles and tooltips replaced literal "Last 30 Days" with `{{ trend_period_text }}` so the cards match the dashboard's actual analysis window
  - Removed stale "improvement percentage (last 90 days)" fragment from the Project Performance tooltip — the Most Improved card was removed in 1.0.13
- **`get_top_users_by_fixes` did not filter by the `days` window at all**
  - The SQL for Top Fixers ignored the `days` parameter entirely — it aggregated all history regardless of the requested window
  - Added `AND ts.date_created >= CURRENT_DATE - INTERVAL '%s days'` to the `last_triagers` CTE in both the project and instance branches, and threaded `days` into the parameter tuples
- **Individual Contributors on project ZIP dashboards showed instance-wide rankings**
  - `ZipDataLoader.get_top_users_by_fixes`, `get_top_triagers`, and `get_most_collaborative_users` called `_read_json_from_zip(self._get_metric_file(...))` directly, bypassing `self.project_name`, so project-level dashboards always displayed instance-wide user rankings
  - Switched all three methods to `_read_metric_json(...)`, which checks `{instance}/{project}/{metric}.json` first and falls back to empty when the project file is absent — matching how other project-scoped metrics behave
  - `export_project_specific_metrics` now writes `top_users_by_fixes.json`, `top_triagers.json`, and `most_collaborative_users.json` under `{instance}/{project}/` so the project-scoped files exist in new ZIPs. **Pre-1.0.17 ZIPs won't contain these files**, so project user leaderboards will be hidden until the ZIP is re-exported
  - Instance-level and project-level leaderboard exports now use the CLI `days` value instead of hardcoded 30
- **Cached dashboard path dropped the Individual Contributors cards entirely**
  - `_collect_and_cache_metrics` in `dashboard.py` was setting `top_users_by_fixes`, `top_triagers`, and `most_collaborative_users` to empty lists with an outdated "not available without defect_triage_history table" comment — so every cached dashboard hid the Individual Contributors section
  - Replaced with real calls (`metrics.get_top_users_by_fixes(days=days, limit=10)`, etc.) and updated `top_projects_by_fix_rate` / `top_projects_by_triage_activity` in the same block to use `days=days` instead of hardcoded 30
- **Overview tab "Active Defects" card counted False Positive and Intentional as active**
  - `get_overall_summary` computed `total_defects` and `high_severity_defects` from `stream_defect` with only `fixed_snapshot_element_id IS NULL`, so dismissed defects (classified as `False Positive` or `Intentional`) were included even though the card's tooltip promised they were excluded and the Defects by Stream table's `active_defects` column already excluded them
  - Both the project-scoped and global branches now `LEFT JOIN defect_triage` + `dynamic_enum` (`dtype = 'Cls'`) and add `AND (de_cls.name NOT IN ('False Positive', 'Intentional') OR de_cls.name IS NULL)`, making the Overview card match the rest of the dashboard
  - Example: a project with 162 stream_defects where 162 were classified as False Positive previously showed `Active Defects: 162`; now correctly shows `0`
- **Dismissed defects (False Positive / Intentional) now treated as fixed EVERYWHERE**
  - Extended the same triage-classification exclusion to every remaining query that counted "outstanding" defects, so all Overview / Hotspots / Aging / Triage / OWASP / CWE metrics now agree on what counts as active
  - Updated queries: `get_defects_by_severity`, `get_defects_by_checker_category`, `get_defects_by_checker_name`, `get_defect_density_by_project`, `get_file_hotspots`, `get_triage_trends`, `get_defect_trend_summary` (current_state CTE), `get_defect_aging_distribution`, `get_triage_progress_summary`, `get_top_projects_by_triage_activity`, `get_owasp_top10_metrics`, `get_owasp_category_details`, `get_cwe_top25_metrics`, `get_cwe_top25_details`
  - Intentionally **not** changed: `get_checker_classification_breakdown` and `get_top_projects_by_classification` — these metrics are *about* the classification distribution itself (they surface noisy checkers / projects that dismiss a lot) and would produce empty results if dismissed were filtered out
  - Also intentionally not changed: the triaged-fix CTEs in `get_defect_trends`, `get_fix_rate_metrics`, `get_defect_velocity_trend`, `get_cumulative_defect_trend`, `get_defect_trend_summary` (period totals) — these deliberately *include* dismissed defects on the "fixed" side of the ledger, which is what the fix rate metric is supposed to show
  - Real-world example: `Vista360_Fix_KeyCloak` (97 stream_defects with 96 classified as FP/Intentional) previously showed 97 in every Overview chart; now correctly shows 1 truly-active defect everywhere
  - **Follow-up refinement**: Five of these charts were reverted to still include dismissed because they exist specifically to show *what Coverity found*, not just what remains actionable — see next entry
- **Reverted dismissed-exclusion on five "raw defect" visibility charts**
  - `get_defects_by_severity`, `get_defects_by_checker_category`, `get_defects_by_checker_name`, `get_defect_density_by_project`, and `get_triage_progress_summary` now include dismissed defects again
  - Rationale: these are Overview / Trend & Progress charts that answer "which severities / categories / checkers is Coverity firing on?" and "how much has been classified?" — hiding dismissed makes them incomplete. In particular, `get_triage_progress_summary` was showing `total_defects = 0` for projects where every defect had been triaged as FP/Intentional, making the Current Triage Progress card look like there was nothing to see
  - "Active only" is still enforced on the metrics whose purpose is remediation load: Overview `Active Defects` card, File Hotspots, Defect Aging, Triage Trends (per-stream classification bars of *outstanding* defects), OWASP Top 10, CWE Top 25, and the current-outstanding count in `get_defect_trend_summary`
- **"Outstanding defect" semantic corrected across every active-defect query — `stream_defect.fixed_snapshot_element_id` is unreliable**
  - Discovered `fixed_snapshot_element_id IS NULL` misses defects that were once removed from code but then re-appeared in a later snapshot: Coverity does not clear the field when the defect returns, so counts based purely on this column understate outstanding defects. Coverity Connect's UI uses the `last_detected_snapshot` table instead — a defect is currently outstanding iff its `last_detected_snapshot.detected_snapshot_id` equals the latest non-deleted `snapshot.id` for its stream
  - Introduced three class constants on `CoverityMetrics` that codify the correct pattern: `_ACTIVE_JOIN_SQL` (join `last_detected_snapshot` + per-stream max snapshot), `_ACTIVE_COND_SQL` (`lds.detected_snapshot_id = sn_latest.latest_snap_id`), and `_FIXED_COND_SQL` (its inverse). Every active-defect query now injects these instead of relying on `fixed_snapshot_element_id`
  - Rewrote all ~20 active-defect SQL sites in `metrics.py` to use the new pattern: `get_total_defects_by_project`, `get_defects_by_severity`, `get_defects_by_checker_category`, `get_defects_by_checker_name`, `get_defect_density_by_project`, `get_overall_summary` (project + global branches), `get_file_hotspots`, `get_triage_trends`, `get_checker_classification_breakdown`, `get_top_projects_by_classification`, `get_fix_rate_metrics` (all three CTEs), `get_defect_velocity_trend`, `get_cumulative_defect_trend`, `get_defect_trend_summary` (period_triaged + current_state), `get_defect_aging_distribution`, `get_triage_progress_summary`, `get_technical_debt_summary`, `get_top_projects_by_fix_rate`, `get_top_projects_by_triage`, `get_top_users_by_fixes` (project + global), `get_owasp_top10_metrics`, `get_owasp_category_details`, `get_cwe_top25_metrics`, `get_cwe_top25_details`
  - `get_triage_progress_summary` was additionally reshaped to start `FROM stream_defect sd` (was `FROM defect_triage dt` with a `LEFT JOIN` to `sd`), so orphan triages that never belonged to a currently-outstanding defect no longer inflate the totals
  - Real-world example: `786-834_proyecto_hrim_workday` — Coverity UI shows 2 outstanding defects (CID 38907 Intentional, CID 39378 Unclassified). Old behaviour: `get_triage_progress_summary.total_defects = 1` (CID 39378 hidden because its `fixed_snapshot_element_id` was stale). New behaviour: `total_defects = 2`, matching the UI
- **Function Complexity Distribution leaked instance-wide numbers into project dashboards**
  - `get_function_complexity_distribution` and `get_most_complex_functions` had no project filter at all — every project's ZIP export and DB dashboard showed the *instance-wide* complexity histogram / top-N list, so projects with zero streams still displayed thousands of functions
  - Both queries now join `stream_file` → `stream_element` → `stream` → `project_stream` → `project` when `_project_names` is set and filter with `AND p.name = ANY(%s)`. Projects without streams now correctly return empty
  - Pre-1.0.17 ZIPs still contain the leaky per-project `function_complexity_distribution.json` files — re-export with 1.0.17+ to get correct per-project numbers

## [1.0.16] - 2026-05-05

### Added
- **`python -m coverity_metrics` Module Support**: The package can now be run as a Python module — `python -m coverity_metrics dashboard`, `python -m coverity_metrics export`, `python -m coverity_metrics report`. Added `__main__.py` which dispatches to the appropriate CLI entry point, stripping the subcommand from `sys.argv` so all existing arguments pass through unchanged

### Documentation
- **Multi-Project `--project` Parameter**: Documented that `--project` accepts comma-separated values for filtering multiple projects simultaneously (e.g. `--project "AppA,AppB,AppC"`); updated README parameter table, CLI examples, and USAGE_GUIDE
- Updated README, USAGE_GUIDE with `python -m coverity_metrics` usage examples

## [1.0.15] - 2026-05-05

### Fixed
- **Project-Level Metrics in ZIP Dashboards**
  - Fixed "Top Analysis Versions Used" and other metrics showing instance-level data on project-level reports generated from ZIP files
  - Updated 8 `ZipDataLoader` methods to properly check for project-specific data files: `get_analysis_versions`, `get_function_complexity_distribution`, `get_snapshot_performance`, `get_commit_time_statistics`, `get_commit_activity_patterns`, `get_defect_discovery_rate`, `get_defect_velocity_trend`, `get_cumulative_defect_trend`
  - Added missing project-level metrics to export configuration so they are included in ZIP exports
  - Project dashboards now correctly display project-specific analysis versions, snapshot performance, and commit activity instead of instance-wide aggregates
- **Negative Database Uptime**
  - Fixed database uptime showing negative values (e.g., "-1d 23h 24m") due to timezone handling issues
  - Updated `get_instance_info` to use UTC consistently for both current time and PostgreSQL start time
  - Added timezone-aware conversion using `.astimezone(timezone.utc)` to handle timezone offsets correctly
  - Added guard against negative uptimes with "Invalid (negative)" display for edge cases
  - Database uptime now calculates correctly regardless of database timezone or system local timezone

## [1.0.14] - 2026-03-19

### Added
- Added `fetch_all` parameter to metrics methods for retrieving all data instead of just top N results
- Enhanced CLI parameter documentation in README

### Changed
- Updated Python library usage examples in README

### Fixed
- Bug fixes and improvements

## [1.0.13] - 2026-03-13

### Changed
- **Removed "Most Improved" Leaderboard Card**
  - The "Most Improved" leaderboard card has been removed from the Team Leaderboards section
  - Improvement percentage was unreliable for sparse snapshot data (projects with only one snapshot had no meaningful baseline to compare against)
  - Removed the corresponding `get_most_improved_projects` call from all dashboard generation paths (`dashboard.py`) and from the ZIP export config (`export.py`)
  - Removed the "Improvement" entry from the Leaderboard Metrics Explained legend in the dashboard template
  - The leaderboard section visibility condition (`{% if ... %}`) updated accordingly

### Fixed
- **`most_improved_projects` No Longer Exported to ZIP**
  - Removed from `export.py` metric config so ZIP archives are no longer populated with data that was not being displayed

## [1.0.12] - 2026-03-05

### Fixed
- **Stale `~overity_metrics` dist-info Artefact**
  - An interrupted install left a `~overity_metrics-1.0.8.dist-info` directory in site-packages, causing pip to emit `WARNING: Ignoring invalid distribution ~overity-metrics` on every invocation
  - Removed the corrupted directory; no source code changes

## [1.0.11] - 2026-03-05

### Fixed
- **PostgreSQL `ROUND` Compatibility in `get_top_projects_by_fix_rate`**
  - `EXTRACT(EPOCH FROM ...)` returns `double precision`; dividing `numeric` by it produces `double precision`, for which `ROUND(x, integer)` is undefined in PostgreSQL
  - Added `::numeric` cast to the `EXTRACT` expression in `metrics.py` so `ROUND(defects_fixed::numeric / EXTRACT(...)::numeric * 86400, 2)` resolves correctly
  - Resolves `psycopg2.errors.UndefinedFunction: function round(double precision, integer) does not exist` crash on dashboard generation

## [1.0.10] - 2026-03-04

### Changed
- **Dependency Upgrades**
  - `psycopg2-binary` `>=2.9.0` → `>=2.9.11`
  - `pandas` `>=2.0.0` → `>=3.0.1`
  - `matplotlib` `>=3.7.0` → `>=3.10.8`
  - `seaborn` `>=0.12.0` → `>=0.13.2`
  - `python-dateutil` `>=2.8.0` → `>=2.9.0.post0`
  - `openpyxl` `>=3.1.0` → `>=3.1.5`
  - `jinja2` `>=3.1.0` → `>=3.1.6`
  - `plotly` `>=5.18.0` → `>=6.6.0`
  - `tqdm` `>=4.66.0` → `>=4.67.3`

- **Project Structure Documentation**
  - Refactored project structure for improved organization and clarity
  - Updated README with new file paths and project layout reflecting the current structure

- **Presentation Guide**
  - Updated `PRESENTATION_GUIDE.md` with Python script option for generating presentations
  - Revised slide structure details for improved clarity and usability

## [1.0.9] - 2026-03-03

### Fixed
- **Missing Classification Charts in ZIP-based Dashboards**
  - `checker_classification_breakdown` and `top_projects_by_classification` were never written to ZIP export files
  - Both metrics are now exported at instance level and project level in `export.py`
  - `ZipDataLoader` getter methods already existed and read from the correct JSON paths — only the export side was missing
  - Dashboards generated with `--zip-file` now include the "Checker Classification Breakdown" and "Top Projects/Streams by Triage Classification" sections

- **`--track-progress` and `--resume` Were No-ops**
  - `ProgressTracker` class in `metrics_cache.py` was fully implemented but never wired into dashboard generation
  - `--track-progress` now creates a progress session before generation, prints the session ID, and records each completed dashboard
  - `--resume SESSION_ID` now loads the completed set from the session file and skips already-generated dashboards, printing `[SKIP]` for each
  - All 7 generation paths in `dashboard.py` are covered: single/multi-instance × specific/all projects × aggregated
  - Label scheme: `"Aggregated View"` / `"{instance}"` / `"{instance} - {project}"`

- **Hardcoded "Last 90 Days" in Aggregated Dashboard**
  - Section title, card labels (`Total New (90d)` / `Total Fixed (90d)`), Trends by Instance table headers, and tooltip texts all showed a hardcoded 90 regardless of the `--days` argument
  - All 5 occurrences in `dashboard_aggregated.html` replaced with `{{ trend_period_text }}` / `{{ trend_period_text|lower }}`
  - `generate_aggregated_dashboard()` already passed `trend_period_text=f"Last {days} Days"` — only the template was stale

## [1.0.8] - 2026-03-02

### Fixed
- **OWASP Top 10 Summary / Detail Count Inconsistency**
  - Fixed bug where "Total Defects" in the OWASP category summary did not match the defect table row count and CWE count shown below it
  - Example: A09 showed "Total Defects: 5", "Defects (6 total)", and "1 CWE mapped" when the table actually listed 6 defects across 2 different CWEs
  - Root cause 1: `cwe_to_owasp` was a flat dict — CWEs listed in multiple OWASP categories were silently dropped for all but the last category encountered (last-writer-wins). CWE-918 appears in both A09 and A10; because A10 is iterated last it stole the defects from A09's summary while A09's detail query still correctly included them.
  - Root cause 2: Summary used `COUNT(DISTINCT sd.id)` (physical stream-defect rows) while the detail table used `DISTINCT ON (sd.merged_defect_id)` (logical merged defects), so counts diverged for merged duplicates.
  - Fix: Changed `cwe_to_owasp` to a multi-value mapping (`CWE → [list of categories]`) so every shared CWE contributes to all matching categories
  - Fix: Changed summary SQL to `COUNT(DISTINCT sd.merged_defect_id)` with `AND sd.merged_defect_id IS NOT NULL` to match detail-table deduplication logic

## [1.0.7] - 2026-02-25

### Added
- **Script Execution Time**
  - Script now prints total execution time after dashboard generation

### Fixed
- **Instance-Level Active Users Deduplication**
  - Instance-level "Active Users" now deduplicates by activity (triage, comment, commit) and matches project-level logic
- **Dashboard Bug: Active Users Count**
  - Dashboard now displays correct "Active Users" count at all levels
- **HTML Escaping for Defect Fields**
  - Defect file/function fields are now HTML-escaped to prevent invalid HTML/JS errors in dashboards

## [1.0.6] - 2026-02-24

### Fixed
- **Project-Level Dashboard Data Filtering from ZIP Files**
  - Fixed issue where project-level dashboards generated from ZIP files showed instance-level aggregate data
  - Example: Project dashboard previously showed 90 defects (instance total) instead of 5 defects (project actual)
  - Root cause: Export only created project-level files for OWASP/CWE metrics, not core metrics
  - Solution:
    - Updated `export.py`: Now exports complete project-specific versions of all core metrics
      - overall_summary.json, defects_by_severity.json, defect_trends.json
      - triage_progress_summary.json, fix_rate_metrics.json, defect_aging_distribution.json
      - technical_debt_summary.json, and all other dashboard metrics
    - Updated `zip_data_loader.py`: Added intelligent file path resolution
      - New `_read_metric_json()` method checks for project-specific files first
      - Falls back to instance-level files if project file doesn't exist
      - All metric getter methods now use this smart lookup
  - ZIP structure now includes: `{instance}/{project}/{metric}.json` for all metrics
  - Project dashboards from ZIP files now correctly show filtered data matching database mode

- **Triage Progress Aggregation Discrepancy**
  - Fixed inconsistency between database and ZIP-based aggregated dashboards
  - Database showed: 36 Classified, 234 Unclassified, 13.3% Completion Ã¢Å“â€¦
  - ZIP showed (before fix): 57 Classified, 213 Unclassified, 21.1% Completion Ã¢ÂÅ’
  - Root cause: Aggregation incorrectly summed triage state counts including `action_assigned_count`
    - Problem: `action_assigned_count` includes defects with actions but still marked as "Unclassified"
    - The `classified_count` field correctly counts only actually classified defects
  - Solution: Changed aggregation in `dashboard.py` to use `total_triaged` (sum of `classified_count`) instead of `sum(triage_by_state_agg.values())`
  - ZIP and database sources now produce identical triage statistics

### Changed
- **Export Behavior - Separate ZIP Files per Instance**
  - `coverity-export` now creates a **separate ZIP file for each configured instance** instead of a single combined ZIP
  - Each ZIP file is named: `coverity_export_{InstanceName}_{timestamp}.zip`
  - Benefits:
    - Easier to share individual instance data
    - Smaller file sizes for selective distribution
    - Better organization and identification
    - Supports selective instance transfers
  - Multi-ZIP aggregation still supported: provide multiple ZIPs to `coverity-dashboard --zip-file`
  - Example: Config with 3 instances now creates 3 separate ZIPs:
    - `coverity_export_Production_20260224_113111.zip`
    - `coverity_export_Development_20260224_113111.zip`
    - `coverity_export_Emergency_20260224_113111.zip`

### Added
- **Aggregated Dashboard from ZIP Files**
  - `coverity-dashboard --zip-file` now **always generates an aggregated dashboard** (`dashboard_aggregated.html`)
  - Works with both single and multiple ZIP files
  - Aggregated dashboard shows:
    - Combined metrics across all instances in ZIP file(s)
    - Defects by instance breakdown
    - Aggregated severity distribution
    - Total defect counts and fix rates
  - Single ZIP: Generates 1 aggregated + instance/project dashboards
  - Multiple ZIPs: Generates 1 aggregated + all instance/project dashboards
  - Example: 3 ZIP files Ã¢â€ â€™ 16 dashboards total (1 aggregated + 15 instance/project)
  - **Automatic color assignment**: Each instance gets a distinct color in aggregated view (red, blue, green, orange, etc.)
    - No need for config.json when using ZIP files - colors are auto-assigned
    - 15 distinct colors available, cycles if more instances

## [1.0.5] - 2026-02-20

### Enhanced
- **OWASP Top 10 2025 Report - Complete Security Coverage**
  - Now displays all 10 OWASP categories regardless of whether defects exist
  - Added PASS/FAILED status badges for each category:
    - ÃƒÂ°Ã…Â¸Ã…Â¸Ã‚Â¢ **PASS**: No defects found for this category (green badge, non-clickable)
    - ÃƒÂ°Ã…Â¸Ã¢â‚¬ÂÃ‚Â´ **FAILED**: Has defects mapped to this category (red badge, clickable to expand)
  - Visual differentiation:
    - FAILED rows: Clickable with red-tinted background and pointer cursor
    - PASS rows: Non-clickable with green-tinted faded background
  - Summary cards show pass/fail counts (e.g., "3/10 Failed")
  - Complete security posture visibility at a glance

- **CWE Top 25 2025 Report - Complete Weakness Coverage**
  - Now displays all 25 CWE Top 25 entries with Status column
  - Added PASS/FAILED status badges matching OWASP report format
  - Same visual differentiation and clickable behavior as OWASP
  - Summary cards show failed CWE counts (e.g., "5/25 Failed")
  - Ranks 1-25 based on MITRE's danger scores

- **Enhanced Defect Details for Security Reports**
  - Removed aggregated "CWE Breakdown" sections for cleaner display
  - Removed "Top Checkers" summary from CWE Top 25 report
  - Now shows ALL defects for each failed category/CWE (no 10-per-CWE limit)
  - Detailed defect tables include:
    - **CID**: Actual Coverity ID (merged_defect_id from database)
    - **CWE**: CWE identifier (OWASP report only)
    - **Type**: Checker name (e.g., "Resource leak", "Null pointer dereference")
    - **Severity**: High/Med/Low badges
    - **File**: Full file path with overflow handling
    - **Function**: Function name where defect occurs
  - Scrollable table containers (max 400px height) for large defect lists
  - Fixed table header visibility with proper text colors (#2c3e50 on white background)

- **Database Schema Corrections**
  - Fixed CID mapping: Uses `stream_defect.merged_defect_id` (actual user-visible CID)
  - Corrected checker joins via `checker_type` table
  - Fixed function joins using `stream_defect_occurrence.function_id`
  - Removed invalid `stream_file` table joins

### Fixed
- Table header visibility in OWASP and CWE Top 25 defect tables
- Replaced undefined CSS variables (`var(--text-color)`, `var(--card-bg)`) with actual color values
- UnboundLocalError for commit_activity variable in dashboard generation

### Performance
- Optimized to only load detailed defect breakdowns for FAILED categories/CWEs
- PASS entries don't trigger database queries for details
- Significant performance improvement for large deployments

## [1.0.4] - 2026-02-19

### Added
- **Comprehensive Progress Tracking for Multi-Instance Dashboards**
  - Implemented tqdm-based progress bars for all multi-instance dashboard generation workflows
  - Pre-calculates total work items (1 aggregated + N instances + M projects) before execution
  - Real-time progress updates with completion percentage, elapsed time, and ETA
  - Dynamic descriptions showing current instance and project being processed
  - Processing speed metrics (e.g., "12.0s/dashboard")
  - Three tracking scenarios:
    1. **Specific Instance + All Projects**: Total calculation shows "1 instance + N projects"
       - Progress bar updates for instance overview + each project
       - Description format: "{instance} - {project}"
       - Postfix shows project counter: "X/Y"
    2. **All Instances + Specific Project**: Shows "Instance X/Y: {name}" 
       - One progress update per instance processed
    3. **All Instances + All Projects (Full Auto)**:
       - Displays pre-flight breakdown: "1 aggregated + N instances + M projects"
       - Single overall progress bar tracking all dashboard types
       - Dynamic descriptions for each phase: aggregated ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ instances ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ projects
       - Postfix strings: "{project} (X/Y)" showing current item within instance
  - Example output:
    ```
    Total dashboards to generate: 47
    - 1 aggregated dashboard
    - 10 instance dashboards  
    - 36 project dashboards
    
    Overall Progress: 23/47 [=========>...] 48% [04:36<04:48, 12.0s/dashboard]
    Instance 5/10: Staging projects
    project_alpha (3/8)
    ```

- **Commit Activity Patterns Analysis**
  - New `get_commit_activity_patterns()` method in `CoverityMetrics` class (lines 1082-1210)
  - Analyzes temporal patterns in commit behavior by hour and day of week
  - Groups commits into 3-hour time blocks:
    - 00:00-02:00, 03:00-05:00, 06:00-08:00, 09:00-11:00
    - 12:00-14:00, 15:00-17:00, 18:00-20:00, 21:00-23:00
  - Identifies busiest and quietest 3-hour windows with:
    - Commit counts
    - Average commit duration (seconds)
    - Average files changed per commit
    - Average new defects introduced per commit
  - Identifies busiest and quietest days of week (Sunday-Saturday)
  - SQL implementation:
    - Uses `EXTRACT(HOUR FROM sn.date_created)` for hourly grouping
    - Uses `EXTRACT(DOW FROM sn.date_created)` for day-of-week grouping (0=Sunday)
    - Qualified column names (sn.date_created, sn.duration_commit_total) to avoid ambiguity
    - Aggregates with COUNT, AVG, SUM for comprehensive statistics
  - Multi-instance aggregation support:
    - New `get_aggregated_commit_activity()` in `MultiInstanceMetrics` (lines 296-424)
    - Combines commit data across all instances using defaultdict
    - Weighted averages for duration and statistics
    - Same output structure as single-instance for template compatibility
  - Display format: "14:00-16:00 (2 PM - 4 PM)" with 12-hour AM/PM conversion
  - Integrated into dashboards:
    - Single-instance: `dashboard.html` lines 1063-1121
    - Aggregated: `dashboard_aggregated.html` lines 549-607
  - Dashboard displays 4 summary cards:
    - Busiest 3-Hour Window (info color)
    - Quietest 3-Hour Window (default color)
    - Busiest Day (success color)
    - Quietest Day (default color)

### Changed
- **Dashboard Generation User Experience**
  - All multi-instance workflows now show detailed progress instead of blank screen
  - Users receive upfront information about total work before generation starts
  - Progress bars use `tqdm.write()` for clean console output
  - Context manager pattern ensures progress bars close properly
  - `dashboard.py` lines 665-775 refactored for comprehensive progress tracking

- **Console Output Improvements**
  - Replaced `print()` statements with `tqdm.write()` throughout `dashboard.py`
  - Prevents progress bar corruption from concurrent output
  - Professional-looking output for enterprise deployments

### Fixed
- **SQL Ambiguous Column References**
  - Fixed "column reference 'date_created' is ambiguous" error in commit activity queries
  - All columns now properly qualified with table alias (e.g., `sn.date_created`)
  - Affects queries in `get_commit_activity_patterns()` method

### Technical Details
- **Modified files**:
  - `coverity_metrics/cli/dashboard.py` (lines 665-775): Progress tracking implementation
  - `coverity_metrics/metrics.py` (lines 1082-1210): Commit activity patterns method
  - `coverity_metrics/multi_instance_metrics.py` (lines 296-424): Aggregated commit activity
  - `coverity_metrics/templates/dashboard.html` (lines 1063-1121): Commit activity display
  - `coverity_metrics/templates/dashboard_aggregated.html` (lines 549-607): Aggregated display

- **API signatures**:
  - `CoverityMetrics.get_commit_activity_patterns() -> dict`
    - Returns: `{'busiest_hours': {...}, 'quietest_hours': {...}, 'busiest_day': {...}, 'quietest_day': {...}}`
  - `MultiInstanceMetrics.get_aggregated_commit_activity() -> dict`
    - Same structure as single-instance for consistent template rendering

## [1.0.3] - 2026-02-19

### Added
- **Technical Debt Estimation Feature**
  - New `get_technical_debt_summary()` method in `CoverityMetrics` class
  - Analyzes defect impact levels from Coverity's `checker_properties.impact` field
  - Calculates estimated remediation effort using industry-standard formulas:
    - High impact: 4 hours per defect
    - Medium impact: 2 hours per defect
    - Low impact: 1 hour per defect
    - Unspecified impact: 0.5 hours per defect
  - Returns comprehensive breakdown:
    - Total hours, work days (ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â·8), work weeks (ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â·40)
    - Total defect count
    - Breakdown by impact level (count, hours, percentage)
    - Average hours per defect
  - Integrated into "Trends & Progress" dashboard tab
  - Dashboard displays:
    - 4 summary cards: Total Hours, Work Days, Work Weeks, Average per Defect
    - 4 breakdown cards: High/Medium/Low/Unspecified with color-coded severity
    - Info alert explaining estimation methodology

- **CWE Top 25 2025 Support**
  - Updated CWE Top 25 rankings from 2024 to 2025 version (MITRE)
  - Updated `cwe_top25_mapping.py` with all 25 new rankings and scores
  - Major ranking changes:
    - CWE-306 (Missing Authentication): #20 ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ #8 (significant jump)
    - CWE-416 (Use After Free): #4 ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ #18 (dropped)
    - CWE-787 (Out-of-bounds Write): #5 ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ #21 (dropped)
    - CWE-862 (Missing Authorization): #3 ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ #5
    - CWE-269 (Improper Privilege Management): #8 ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ #12
  - New CWE entries in 2025:
    - CWE-120 (Classic Buffer Overflow) at #19
    - CWE-327 (Broken or Risky Crypto Algorithm) at #23
  - Removed from 2025 list:
    - CWE-94 (Improper Control of Code Generation)
    - CWE-276 (Incorrect Default Permissions)
  - Dashboard tab title updated: "CWE Top 25 2024" ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ "CWE Top 25 2025"

### Changed
- **Documentation Enhancements**
  - Updated `README.md` with comprehensive "Latest Enhancements (2025)" section
  - Added quick reference for new features (ÃƒÆ’Ã‚Â°Ãƒâ€¦Ã‚Â¸ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢Ãƒâ€šÃ‚Â° Technical Debt, ÃƒÆ’Ã‚Â°Ãƒâ€¦Ã‚Â¸ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ OWASP, ÃƒÆ’Ã‚Â°Ãƒâ€¦Ã‚Â¸ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂºÃƒâ€šÃ‚Â¡ÃƒÆ’Ã‚Â¯Ãƒâ€šÃ‚Â¸Ãƒâ€šÃ‚Â CWE, ÃƒÆ’Ã‚Â°Ãƒâ€¦Ã‚Â¸Ãƒâ€šÃ‚ÂÃƒÂ¢Ã¢â€šÂ¬Ã‚Â  Leaderboards)
  - Expanded Features section with Security Compliance Metrics and Leaderboards
  - Added "For Security Teams" use cases section
  - Updated Available Metric Methods with technical debt and security APIs
  - Updated Database Schema documentation with CWE code information
  - Updated Project Structure showing new mapping files
  - Enhanced Python API examples with technical debt, OWASP, CWE, and leaderboard methods
  - Documented all 7 dashboard tabs with detailed descriptions

- **Dashboard Improvements**
  - "Trends & Progress" tab now includes Technical Debt Summary section
  - CWE Top 25 tab displays 2025 rankings with updated scores
  - Enhanced visual presentation of technical debt metrics with color-coded severity

### Fixed
- Fixed `Decimal` to `float` type conversion in technical debt calculations to avoid TypeError
- Ensured all CWE Top 25 references point to 2025 data

### Technical Details
- **Modified Files**:
  - `coverity_metrics/cwe_top25_mapping.py`: Updated CWE_TOP_25_2025 dictionary
  - `coverity_metrics/metrics.py`: Added `get_technical_debt_summary()` method (lines 1530-1611)
  - `coverity_metrics/cli/dashboard.py`: Integrated technical debt data retrieval
  - `coverity_metrics/templates/dashboard.html`: Added Technical Debt Summary section (lines 593-657)
  - `README.md`: Comprehensive documentation updates

- **Database Schema**:
  - Utilizes existing `checker_properties.impact` field
  - Joins `stream_defect` with `checker_properties` on checker name
  - SQL CASE statement for effort calculation based on impact level

- **API Enhancement**:
  - New method: `CoverityMetrics.get_technical_debt_summary()`
  - Returns: `dict` with keys: `total_hours`, `total_days`, `total_weeks`, `total_defects`, `breakdown`, `avg_hours_per_defect`
  - Breakdown structure: `{impact_level: {'count': int, 'hours': float, 'percentage': float}}`

## [1.0.2] - 2026-02-18

### Added
- Added `fetch_all` parameter to metrics methods

### Changed
- Updated documentation

## [1.0.0] - 2026-02-18

### Added
- **Full Python Package Structure**
  - Created installable package with `pip install -e .`
  - Modern `pyproject.toml` based packaging (PEP 621)
  - Three CLI entry points: `coverity-dashboard`, `coverity-metrics`, `coverity-export`
  - Package can be used as both CLI tool and importable library
  - Proper package structure with `coverity_metrics/` module
  - Version management via `__version__.py`
  - Comprehensive `.gitignore` for Python projects
  - Installation guide in `INSTALL.md`

- **CLI Commands**
  - `coverity-dashboard`: Main dashboard generator (replaces `python generate_dashboard.py`)
  - `coverity-metrics`: Console metrics report (replaces `python main.py`)
  - `coverity-export`: CSV/JSON export utility (replaces `python export_metrics.py`)

- **Python Library API**
  - Can import with: `from coverity_metrics import CoverityMetrics, MultiInstanceMetrics`
  - Programmatic access to all metrics functionality
  - Supports both single and multi-instance configurations

### Changed
- **Configuration Simplification**
  - Removed dependency on `cim.properties` configuration file
  - All configuration now exclusively uses `config.json`
  - Removed `config.py` module (functionality merged into other modules)
  - Database connection parameters now passed as dictionaries

- **CLI Simplification**
  - Removed legacy flags: `--multi-instance`, `--aggregated`, `--all-projects`, `--all-instances`
  - Multi-instance mode now auto-detected from `config.json` (2+ instances)
  - Single-instance mode auto-detected from `config.json` (1 instance)
  - Cleaner, more intuitive command-line interface

- **Project Structure**
  - Moved all Python modules into `coverity_metrics/` package
  - Moved CLI scripts into `coverity_metrics/cli/` subdirectory
  - Moved templates into `coverity_metrics/templates/`
  - Moved static assets into `coverity_metrics/static/`
  - All imports now use package-relative paths (`coverity_metrics.*`)

- **Documentation**
  - Updated `README.md` with new installation and usage instructions
  - Updated `MULTI_INSTANCE_GUIDE.md` to reflect auto-detection behavior
  - Updated `CACHING_GUIDE.md` with current CLI commands
  - Updated `USAGE_GUIDE.md` with new command syntax
  - Added installation guide (`INSTALL.md`) with CLI and library examples

### Removed
- **Development/Testing Scripts** (Workspace Cleanup)
  - Removed 15+ database exploration scripts (`check_*.py`, `explore_*.py`, `find_*.py`, etc.)
  - Removed legacy test scripts that were for development only
  - Cleaner workspace focused on production code

- **Legacy Configuration**
  - Removed `cim.properties` file support
  - Removed `config.py` module
  - Removed dual-configuration system

- **Legacy CLI Flags**
  - Removed `--multi-instance` (auto-detected)
  - Removed `--aggregated` (auto-detected)
  - Removed `--all-projects` (default behavior)
  - Removed `--all-instances` (default behavior)

### Fixed
- Package imports now use absolute paths from package root
- Template paths corrected for package structure
- All references to old script names updated in documentation

### Technical Details
- **Package Name**: `coverity-metrics`
- **Version**: 1.0.0
- **Python Support**: >=3.8
- **Dependencies**: psycopg2-binary, pandas, matplotlib, seaborn, jinja2, plotly, tqdm, python-dateutil, openpyxl
- **Installation**: `pip install -e .` for editable/development mode
- **Entry Points**: 
  - `coverity-dashboard` ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¾ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ `coverity_metrics.cli.dashboard:main`
  - `coverity-metrics` ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¾ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ `coverity_metrics.cli.report:main`
  - `coverity-export` ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¾ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ `coverity_metrics.cli.export:main`

---

## [0.9.0] - Previous Version

### Features from Previous Development
- Interactive HTML dashboard with tabbed interface
- Multi-instance aggregation support
- Performance metrics and analysis
- Caching system for improved performance
- Progress tracking for large datasets
- CSV/JSON export functionality
- PostgreSQL database integration
- Project filtering and navigation

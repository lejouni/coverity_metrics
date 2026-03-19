# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.14] - 2026-03-19

### Added
- Added `fetch_all` parameter to metrics methods for retrieving all data instead of just top N results
- Enhanced CLI parameter documentation in README

### Changed
- Updated Python library usage examples in README

### Fixed
- Bug fixes and improvements

## [Unreleased]

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

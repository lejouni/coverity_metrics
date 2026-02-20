# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.5] - 2026-02-20

### Enhanced
- **OWASP Top 10 2025 Report - Complete Security Coverage**
  - Now displays all 10 OWASP categories regardless of whether defects exist
  - Added PASS/FAILED status badges for each category:
    - ðŸŸ¢ **PASS**: No defects found for this category (green badge, non-clickable)
    - ðŸ”´ **FAILED**: Has defects mapped to this category (red badge, clickable to expand)
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
       - Dynamic descriptions for each phase: aggregated â†’ instances â†’ projects
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
    - Total hours, work days (ÃƒÂ·8), work weeks (ÃƒÂ·40)
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
    - CWE-306 (Missing Authentication): #20 Ã¢â€ â€™ #8 (significant jump)
    - CWE-416 (Use After Free): #4 Ã¢â€ â€™ #18 (dropped)
    - CWE-787 (Out-of-bounds Write): #5 Ã¢â€ â€™ #21 (dropped)
    - CWE-862 (Missing Authorization): #3 Ã¢â€ â€™ #5
    - CWE-269 (Improper Privilege Management): #8 Ã¢â€ â€™ #12
  - New CWE entries in 2025:
    - CWE-120 (Classic Buffer Overflow) at #19
    - CWE-327 (Broken or Risky Crypto Algorithm) at #23
  - Removed from 2025 list:
    - CWE-94 (Improper Control of Code Generation)
    - CWE-276 (Incorrect Default Permissions)
  - Dashboard tab title updated: "CWE Top 25 2024" Ã¢â€ â€™ "CWE Top 25 2025"

### Changed
- **Documentation Enhancements**
  - Updated `README.md` with comprehensive "Latest Enhancements (2025)" section
  - Added quick reference for new features (Ã°Å¸â€™Â° Technical Debt, Ã°Å¸â€â€™ OWASP, Ã°Å¸â€ºÂ¡Ã¯Â¸Â CWE, Ã°Å¸Ââ€  Leaderboards)
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
  - `coverity-dashboard` ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â‚¬Å¾Ã‚Â¢ `coverity_metrics.cli.dashboard:main`
  - `coverity-metrics` ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â‚¬Å¾Ã‚Â¢ `coverity_metrics.cli.report:main`
  - `coverity-export` ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â‚¬Å¾Ã‚Â¢ `coverity_metrics.cli.export:main`

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

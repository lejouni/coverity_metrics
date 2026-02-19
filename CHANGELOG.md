# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
    - Total hours, work days (Ã·8), work weeks (Ã·40)
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
    - CWE-306 (Missing Authentication): #20 â†’ #8 (significant jump)
    - CWE-416 (Use After Free): #4 â†’ #18 (dropped)
    - CWE-787 (Out-of-bounds Write): #5 â†’ #21 (dropped)
    - CWE-862 (Missing Authorization): #3 â†’ #5
    - CWE-269 (Improper Privilege Management): #8 â†’ #12
  - New CWE entries in 2025:
    - CWE-120 (Classic Buffer Overflow) at #19
    - CWE-327 (Broken or Risky Crypto Algorithm) at #23
  - Removed from 2025 list:
    - CWE-94 (Improper Control of Code Generation)
    - CWE-276 (Incorrect Default Permissions)
  - Dashboard tab title updated: "CWE Top 25 2024" â†’ "CWE Top 25 2025"

### Changed
- **Documentation Enhancements**
  - Updated `README.md` with comprehensive "Latest Enhancements (2025)" section
  - Added quick reference for new features (ðŸ’° Technical Debt, ðŸ”’ OWASP, ðŸ›¡ï¸ CWE, ðŸ† Leaderboards)
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
  - `coverity-dashboard` ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ `coverity_metrics.cli.dashboard:main`
  - `coverity-metrics` ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ `coverity_metrics.cli.report:main`
  - `coverity-export` ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ `coverity_metrics.cli.export:main`

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

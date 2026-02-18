# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
  - `coverity-dashboard` Ã¢â€ â€™ `coverity_metrics.cli.dashboard:main`
  - `coverity-metrics` Ã¢â€ â€™ `coverity_metrics.cli.report:main`
  - `coverity-export` Ã¢â€ â€™ `coverity_metrics.cli.export:main`

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

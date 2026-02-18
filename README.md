# Coverity Metrics

A Python-based project to generate comprehensive metrics from Coverity's PostgreSQL database.

## Overview

This tool analyzes Coverity static analysis data stored in PostgreSQL and generates various metrics to help you understand code quality, defect trends, and development team activity.

## Features

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

### 5. **User Activity Metrics**
- **Login Statistics**: User engagement with the system
- **Active Triagers**: Most active users in defect triage
- **Session Analytics**: Average session duration per user

### 6. **Performance Metrics** (NEW!)
- **Database Statistics**: Database size and growth tracking
- **Commit Performance**: Analysis duration (min/max/average times)
- **Snapshot Performance**: Recent commit performance with queue times
- **Defect Discovery Rate**: Daily/weekly defect discovery trends
- **System Analytics**: Largest tables, resource utilization

### 7. **Summary Metrics**
- Overall counts: projects, streams, defects, files, functions, LOC
- High severity defect counts
- Active user counts

## Installation

### From Source (Recommended)

```bash
# Clone or download this repository
git clone https://github.com/yourusername/coverity-metrics.git
cd coverity-metrics

# Install the package with all dependencies
pip install -e .
```

This installs the package in editable mode, making the CLI commands (`coverity-dashboard`, `coverity-metrics`, `coverity-export`) available system-wide.

### From PyPI (Future)

```bash
# When published to PyPI
pip install coverity-metrics
```

### Requirements

The package includes these dependencies (automatically installed):
- `psycopg2-binary` - PostgreSQL database adapter
- `pandas` - Data analysis and manipulation
- `matplotlib` - Plotting library
- `seaborn` - Statistical data visualization
- `python-dateutil` - Date/time utilities
- `openpyxl` - Excel file support for CSV exports
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

## Database Schema

The tool works with the following key Coverity database tables:

- **defect**, **stream_defect**, **defect_instance** - Defect information
- **checker**, **checker_properties** - Checker and severity data
- **triage_state**, **defect_triage** - Triage information
- **stream**, **stream_file**, **stream_function** - Code structure
- **snapshot** - Analysis snapshots
- **project**, **project_stream** - Project organization
- **users**, **user_login** - User activity
- **weekly_issue_count**, **weekly_file_count** - Trend data

## Usage

After installation, you can use the package in two ways: **Command-Line Interface (CLI)** or **Python Library**.

### Command-Line Interface (CLI)

The package provides three CLI commands for different use cases:

| Command | Purpose | Output | Best For |
|---------|---------|--------|----------|
| **coverity-dashboard** | Visual HTML dashboard | Interactive HTML files with charts | Presentations, visual analysis, sharing |
| **coverity-metrics** | Console text report | Terminal output (stdout) | Quick checks, CI/CD, piping |
| **coverity-export** | Data export | CSV files | Excel analysis, archiving, integrations |

**Key Differences:**

- **coverity-dashboard**: Creates beautiful interactive HTML dashboards with Plotly charts, saved to `output/` directory. Auto-opens in browser for easy viewing. Supports multi-instance aggregation.

- **coverity-metrics**: Prints all metrics as formatted text tables directly to your terminal. No files created. Great for quick command-line checks or redirecting to log files (`coverity-metrics > report.txt`).

- **coverity-export**: Exports raw metric data to timestamped CSV files in `exports/` directory. Perfect for importing into Excel, Power BI, or custom analysis tools.

**Note**: All three tools require direct PostgreSQL database access. CSV exports cannot be used as input to generate dashboards—they're export-only for external analysis.

---

#### 1. Generate Dashboard (Main Tool)

```bash
# Basic usage - auto-detects instance type from config.json
coverity-dashboard

# Filter by specific project across all instances
coverity-dashboard --project "MyProject"

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
```

**Auto-Detection Behavior:**
- **config.json is required** with at least one enabled instance configured
- If `config.json` has **2+ enabled instances**: Multi-instance mode (generates aggregated + per-instance + per-project dashboards)
- If `config.json` has **1 enabled instance**: Single-instance mode (generates dashboard for that instance)
- Use `--project` to filter by specific project only
- Use `--instance` to generate for specific instance only (multi-instance mode)
- Use `--single-instance-mode` to force single-instance behavior even with multiple instances

For all options: `coverity-dashboard --help`

#### 2. Console Metrics Report

**Outputs**: Text tables printed to terminal (no files created)

```bash
# Generate console metrics report
coverity-metrics

# With options
coverity-metrics --project MyProject --no-cache

# Redirect to file
coverity-metrics > daily-report.txt
```

**Use Cases:**
- Quick command-line checks
- Automated CI/CD pipelines
- SSH sessions without GUI
- Piping to log files or other tools

#### 3. CSV Export

**Outputs**: Timestamped CSV files in `exports/` directory

```bash
# Export metrics to CSV
coverity-export

# Custom output directory
coverity-export --output exports/
```

**Files Created:**
- `defects_by_project_YYYYMMDD_HHMMSS.csv`
- `defects_by_severity_YYYYMMDD_HHMMSS.csv`
- `defect_density_YYYYMMDD_HHMMSS.csv`
- `file_hotspots_YYYYMMDD_HHMMSS.csv`
- `code_metrics_YYYYMMDD_HHMMSS.csv`
- ...and more

**Use Cases:**
- Excel pivot tables and analysis
- Power BI / Tableau dashboards
- Custom Python/R data analysis
- Archiving historical metrics
- Third-party tool integrations

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

**Complete Analysis Workflow:**
```bash
# 1. Quick overview in terminal
coverity-metrics

# 2. Generate interactive dashboard
coverity-dashboard --cache --no-browser

# 3. Export raw data for deep analysis
coverity-export

# Now you have:
# - Console output for quick reference
# - HTML dashboard (output/dashboard.html) for presentations
# - CSV files (exports/*.csv) for custom Excel analysis
```

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
    project_filter='MyProject'  # Optional
)

# Get metrics
defect_metrics = metrics.get_defect_metrics()
print(defect_metrics)

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
- **Tabbed Interface**: Organized into Overview, Code Quality, and Performance tabs
- Summary cards with key metrics
- Interactive charts for severity distribution, project comparison
- File hotspots with detailed tables
- Code quality metrics visualization
- Function complexity distribution
- Top defect checkers and categories
- **Performance metrics** (NEW!):
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

### Multi-Instance Support (NEW - Automatic!)

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

### Export to CSV

Export all metrics to CSV files:

```bash
coverity-export
```

This creates timestamped CSV files in the `exports/` directory for Excel analysis.

### Use Individual Metrics

You can also use the metrics module programmatically:

```python
from metrics import CoverityMetrics

# Initialize
metrics = CoverityMetrics()

# Get specific metrics
defects_by_severity = metrics.get_defects_by_severity()
print(defects_by_severity)

# Get defect density
density = metrics.get_defect_density_by_project()
print(density)

# Get file hotspots
hotspots = metrics.get_file_hotspots(limit=10)
print(hotspots)

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
- `get_defects_by_checker_category(limit=20)`
- `get_defects_by_checker_name(limit=20)`
- `get_defect_density_by_project()`
- `get_file_hotspots(limit=20)`

**Triage Metrics:**
- `get_defects_by_triage_status()`
- `get_defects_by_classification()`
- `get_defects_by_owner(limit=20)`

**Code Quality Metrics:**
- `get_code_metrics_by_stream()`
- `get_function_complexity_distribution()`
- `get_most_complex_functions(limit=20)`

**Trend Metrics:**
- `get_defect_trend_weekly(weeks=12)`
- `get_file_count_trend_weekly(weeks=12)`
- `get_snapshot_history(stream_name=None, limit=20)`

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

## Recommended Metrics for Different Use Cases

### For Management/Executive Reports:
1. **Overall Summary** - High-level statistics
2. **Defects by Severity** - Risk assessment
3. **Defect Density by Project** - Quality comparison across projects
4. **Weekly Defect Trend** - Progress over time
5. **Defects by Triage Status** - Workload and backlog

### For Development Teams:
1. **File Hotspots** - Identify problematic files
2. **Most Complex Functions** - Refactoring candidates
3. **Defects by Category** - Common error patterns
4. **Defects by Owner** - Individual workload
5. **Snapshot History** - Analysis run results

### For Quality Assurance:
1. **Defects by Checker** - Tool effectiveness
2. **Defects by Classification** - False positive rate
3. **Code Metrics by Stream** - Code coverage
4. **Function Complexity** - Code maintainability
5. **Defect Density** - Quality benchmarks

### For Team Leads:
1. **Active Triagers** - Team engagement
2. **Defects by Owner** - Work distribution
3. **User Login Statistics** - Tool adoption
4. **Weekly Trends** - Team velocity

## Project Structure

```
coverity_metrics/
├── config.json            # Database configuration (create from config.json.example)
├── config.json.example    # Configuration template
├── db_connection.py       # Database connection handling
├── metrics.py             # Metrics calculation logic
├── multi_instance_metrics.py  # Multi-instance support
├── generate_dashboard.py  # Dashboard generator (main entry point)
├── main.py                # CLI metrics report
├── export_metrics.py      # CSV export utility
├── requirements.txt       # Python dependencies
├── templates/             # HTML dashboard templates
├── static/                # CSS/JS assets
└── README.md             # This file
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

## Future Enhancements

Potential additions:
- Export to Excel/CSV/JSON
- Visualization charts and graphs
- Email report generation
- Scheduled report automation
- Comparison between time periods
- Custom alert thresholds
- REST API for metrics
- Web dashboard interface

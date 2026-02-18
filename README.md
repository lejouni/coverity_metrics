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

1. **Clone or download this repository**

2. **Install required packages**:
   ```bash
   pip install -r requirements.txt
   ```

   Required packages:
   - `psycopg2-binary` - PostgreSQL database adapter
   - `pandas` - Data analysis and manipulation
   - `matplotlib` - Plotting library (for future visualizations)
   - `seaborn` - Statistical data visualization
   - `python-dateutil` - Date/time utilities
   - `openpyxl` - Excel file support for CSV exports
   - `jinja2` - HTML template engine for dashboard generation
   - `plotly` - Interactive charts and visualizations

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

### Generate Full Report

Run the main script to generate a comprehensive metrics report:

```bash
python main.py
```

This will output all available metrics to the console.

### Generate HTML Dashboard

**NEW SIMPLIFIED USAGE!** The dashboard generator now auto-detects multi-instance configurations and generates comprehensive reports automatically:

```bash
# Simple usage - automatically detects configuration and generates everything
python generate_dashboard.py

# Filter by specific project across all instances (if multi-instance)
python generate_dashboard.py --project "MyProject"

# Generate for specific instance only
python generate_dashboard.py --instance Production

# Change trend analysis period (default: 365 days)
python generate_dashboard.py --days 180

# Custom output folder
python generate_dashboard.py --output reports/2026
```

**Auto-Detection Behavior:**
- **config.json is required** with at least one enabled instance configured
- If `config.json` has **2+ enabled instances**: Multi-instance mode (generates aggregated + per-instance + per-project dashboards)
- If `config.json` has **1 enabled instance**: Single-instance mode (generates dashboard for that instance)
- Use `--project` to filter by specific project only
- Use `--instance` to generate for specific instance only (multi-instance mode)
- Use `--single-instance-mode` to force single-instance behavior even with multiple instances

**Additional Options:**

```bash
# Generate without opening browser
python generate_dashboard.py --no-browser  

# Force single-instance mode even if config.json has multiple instances
python generate_dashboard.py --single-instance-mode

# Use different configuration file
python generate_dashboard.py --config my-config.json
```



The dashboard includes:
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
python generate_dashboard.py

# Filter by specific project across all instances
python generate_dashboard.py --project MyApp

# Generate for specific instance only (with all its projects)
python generate_dashboard.py --instance Production

# Generate specific project on specific instance only
python generate_dashboard.py --instance Production --project MyApp

# Use custom configuration file
python generate_dashboard.py --config my-config.json

# Test connectivity to all configured instances
python multi_instance_metrics.py
```

**What Gets Generated Automatically:**

When you run `python generate_dashboard.py` with a multi-instance config.json:
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
python generate_dashboard.py --cache

# Custom cache TTL (48 hours)
python generate_dashboard.py --cache --cache-ttl 48

# View cache statistics
python generate_dashboard.py --cache-stats

# Clear expired cache entries
python generate_dashboard.py --clear-cache

# Force refresh (bypass cache)
python generate_dashboard.py --no-cache
```

**Performance Benefits:**
- **First run**: Same time as without caching (cache is built)
- **Subsequent runs**: 90-95% faster (uses cached data)
- **Example**: 30 minutes → 2 minutes for 10 instances × 100 projects

**Progress Tracking for Large Operations:**

```bash
# Enable progress tracking (for resumable operations)
python generate_dashboard.py --cache --track-progress

# Resume interrupted session
python generate_dashboard.py --cache --resume SESSION_ID
```

For detailed caching configuration, performance tuning, and troubleshooting, see [CACHING_GUIDE.md](CACHING_GUIDE.md)

### Export to CSV

Export all metrics to CSV files:

```bash
python export_metrics.py
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

## Data Insights

Based on initial schema investigation, this Coverity instance has:
- **88 defects** detected across streams
- **376 files** under analysis
- **929 functions** tracked
- **3 streams** configured
- **2 projects** active

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

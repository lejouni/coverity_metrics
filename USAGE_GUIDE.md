# Coverity Metrics - Usage Guide

## Quick Start

### 1. Generate Full Metrics Report
```bash
coverity-metrics
```

This generates a comprehensive console report with all metrics.

### 2. Generate HTML Dashboard
```bash
coverity-dashboard
```

Creates an interactive HTML dashboard with:
- Summary cards for key metrics
- Interactive Plotly charts (pie, bar, line charts)
- Sortable data tables
- File hotspot analysis
- Code quality visualizations
- Responsive design for all devices
- Export-friendly print layout

The dashboard will be saved to `output/dashboard.html` and can optionally open in your browser.

**Filter by Project:**
```bash
# View metrics for a specific project only
coverity-dashboard --project "feature"

# Generate with custom output location
coverity-dashboard --output reports/my_dashboard.html

# Skip browser auto-open
coverity-dashboard --no-browser
```

Without `--project` filter, the tool automatically generates dashboards for all projects.

### 3. Export Metrics to CSV
```bash
coverity-export
```

Exports all metrics to CSV files in the `exports/` folder.

## Sample Metrics from Your Database

Based on the initial analysis of your Coverity database:

### Current Statistics
- **Total Defects**: 85 active defects
- **Total Projects**: 4
- **Total Streams**: 3  
- **Code Base**: 79,263 lines of code across 376 files
- **Functions**: 929 functions tracked
- **High Severity**: 13 high-impact defects

### Top Defect Categories
1. **Sigma** - 63 defects (cloud security misconfiguration)
2. **Null pointer dereferences** - 11 defects
3. **Resource leaks** - 4 defects
4. **Code maintainability issues** - 3 defects

### Defect Density Analysis
- **feature stream**: 7.51 defects per KLOC (highest)
- **Damm-Vulnerable-dotNet-Application**: 1.71 defects per KLOC
- **sampleapp-feature**: 0.44 defects per KLOC (lowest, best quality)

### File Hotspots (Files with Most Defects)
1. **main.tf** - 34 defects in 51 lines (Infrastructure as Code file)
2. **Web.config** - 9 defects
3. **SQLiteMembershipProvider.cs** - 6 defects

## Recommended Metrics for Different Audiences

### Filtering Metrics by Project (NEW!)

You can now filter all metrics by project name:

```python
from metrics import CoverityMetrics

# Global metrics (all projects)
metrics_global = CoverityMetrics()
summary_all = metrics_global.get_overall_summary()

# Project-specific metrics
metrics_project = CoverityMetrics(project_name="feature")
summary_project = metrics_project.get_overall_summary()
defects = metrics_project.get_defects_by_severity()
hotspots = metrics_project.get_file_hotspots()

# Compare projects
for project in ["feature", "sampleapp-feature", "Damm-Vulnerable-dotNet-Application"]:
    m = CoverityMetrics(project_name=project)
    summary = m.get_overall_summary()
    print(f"{project}: {summary['total_defects']} defects, {summary['high_severity_defects']} high")
```

**Benefits of Project Filtering:**
- Focus metrics on specific teams/components
- Compare quality across projects
- Generate project-specific reports
- Track individual project trends over time

### Retrieving All Results with `fetch_all`

By default, methods with a `limit` parameter return only the top N results. Pass `fetch_all=True` to get the complete result set:

```python
from metrics import CoverityMetrics

metrics = CoverityMetrics()

# Default: returns top 10 file hotspots
hotspots_top10 = metrics.get_file_hotspots(limit=10)

# fetch_all=True: returns every hotspot
all_hotspots = metrics.get_file_hotspots(fetch_all=True)

# Works with any method that accepts a limit parameter
all_checkers = metrics.get_defects_by_checker_name(fetch_all=True)
all_owners   = metrics.get_defects_by_owner(fetch_all=True)
```

### For Executive/Management Reports
```python
from metrics import CoverityMetrics

metrics = CoverityMetrics()

# High-level summary
summary = metrics.get_overall_summary()

# Risk assessment - defects by severity
severity = metrics.get_defects_by_severity()

# Quality comparison across projects
density = metrics.get_defect_density_by_project()

# Progress tracking
trends = metrics.get_defect_trend_weekly(weeks=12)
```

**Key Insights to Report:**
- Total defect backlog and high-severity issues
- Quality trends (improving/degrading)
- Comparison between projects/teams
- ROI metrics (defects per KLOC)

### For Development Teams
```python
# Files needing attention 
hotspots = metrics.get_file_hotspots(limit=20)

# Common error patterns
categories = metrics.get_defects_by_checker_category()

# Refactoring candidates
complex_functions = metrics.get_most_complex_functions(limit=20)

# Code quality metrics
code_stats = metrics.get_code_metrics_by_stream()
```

**Key Actions:**
- Prioritize fixing file hotspots
- Address common patterns (e.g., null pointer issues)
- Refactor high-complexity functions
- Improve code documentation (comment ratio)

### For Quality Assurance
```python
# Checker effectiveness
checkers = metrics.get_defects_by_checker_name(limit=30)

# False positive analysis
classification = metrics.get_defects_by_classification()

# Triage workflow status
triage_status = metrics.get_defects_by_triage_status()
```

**Key Metrics:**
- Most active checkers (finding real bugs vs. noise)
- Classification distribution (Bug vs. False Positive rates)
- Triage backlog and workflow efficiency

### For Team Leads
```python
# Work distribution
owners = metrics.get_defects_by_owner(limit=20)

# Team activity
triagers = metrics.get_most_active_triagers(days=30, limit=10)

# Login/engagement
logins = metrics.get_user_login_statistics(days=30)
```

**Team Management Insights:**
- Workload balancing across team members
- Identify who needs more training/support
- Tool adoption and engagement levels

## Understanding Your Specific Data

### Sigma Defects (Cloud Security)
Your database shows 63 **Sigma** defects - these are cloud security misconfigurations:
- Hard-coded secrets (14 instances)
- Missing TLS configurations
- Logging disabled
- CORS misconfigurations
- Authentication issues

**Recommendation**: Prioritize these for cloud deployment security.

### Infrastructure as Code Issues
The file **main.tf** has 666.67 defects per KLOC (34 defects in 51 lines).

**Recommendation**: This Terraform file needs immediate review for security best practices.

### SQL Injection Vulnerabilities
Multiple files show SQL injection patterns:
- SQLiteMembershipProvider.cs
- SQLInjection.java

**Recommendation**: Critical security fixes required before production.

## Automating Reports

### Daily Summary Email
Create a Python script:
```python
from metrics import CoverityMetrics
from datetime import datetime

metrics = CoverityMetrics()
summary = metrics.get_overall_summary()

print(f"Daily Coverity Report - {datetime.now().strftime('%Y-%m-%d')}")
print("=" * 60)
print(f"Total Active Defects: {summary['total_defects']}")
print(f"High Severity: {summary['high_severity_defects']}")
print(f"Total LOC: {summary['total_loc']:,}")

# Get recent changes
snapshots = metrics.get_snapshot_history(limit=1)
if not snapshots.empty:
    latest = snapshots.iloc[0]
    print(f"\nLatest Analysis ({latest['date_created']}):")
    print(f"  New Defects: {latest['new_defect_count']}")
    print(f"  Eliminated: {latest['eliminated_defect_count']}")
```

### Weekly Trend Report
```python
# Track improvements week-over-week
weekly_defects = metrics.get_defect_trend_weekly(weeks=8)
print(weekly_defects)

# Identify problem areas
hotspots = metrics.get_file_hotspots(limit=10)
print("\nTop 10 Problem Files:")
print(hotspots[['file_path', 'defect_count', 'defects_per_kloc']])
```

## Custom Queries

### Find All Security-Related Defects
```python
db = metrics.db
security_defects = db.execute_query_dict("""
    SELECT 
        fp.filename,
        ct.name as checker,
        cp.impact,
        cp.cwe
    FROM stream_defect sd
    JOIN stream_defect_occurrence sdo ON sd.id = sdo.stream_defect_id
    JOIN stream_file sf ON sdo.stream_file_id = sf.id
    JOIN file_path fp ON sf.file_path_id = fp.id
    JOIN checker_properties cp ON sd.checker_properties_id = cp.id
    JOIN checker_type ct ON cp.checker_type_id = ct.id
    WHERE sd.fixed_snapshot_element_id IS NULL
      AND (cp.security = true OR cp.cwe IS NOT NULL)
    ORDER BY 
        CASE cp.impact
            WHEN 'High' THEN 1
            WHEN 'Medium' THEN 2
            ELSE 3
        END
""")
```

### Calculate Technical Debt
```python
# Estimate hours to fix based on severity
db = metrics.db
tech_debt = db.execute_query_dict("""
    SELECT 
        cp.impact,
        COUNT(*) as defect_count,
        CASE cp.impact
            WHEN 'High' THEN COUNT(*) * 4    -- 4 hours per high severity
            WHEN 'Medium' THEN COUNT(*) * 2  -- 2 hours per medium
            WHEN 'Low' THEN COUNT(*) * 1     -- 1 hour per low
            ELSE COUNT(*) * 0.5
        END as estimated_hours
    FROM stream_defect sd
    JOIN checker_properties cp ON sd.checker_properties_id = cp.id
    WHERE sd.fixed_snapshot_element_id IS NULL
    GROUP BY cp.impact
""")

total_hours = sum([row['estimated_hours'] for row in tech_debt])
print(f"Estimated technical debt: {total_hours} hours ({total_hours/8:.1f} days)")
```

## Performance Tips

For large databases:
1. Use LIMIT parameters to restrict result sizes
2. Filter by date ranges for trend analysis
3. Consider creating database views for frequently-used queries
4. Export to CSV for offline analysis in Excel/Tableau

## Troubleshooting

### No Data Returned
- Check that snapshots have been committed recently
- Verify streams are not marked as deleted
- Ensure defects haven't all been fixed (check fixed_snapshot_element_id)

### Slow Queries
- Add indexes: `CREATE INDEX idx_stream_defect_fixed ON stream_defect(fixed_snapshot_element_id);`
- Use smaller date ranges
- Reduce LIMIT parameters for large result sets

## Next Steps

1. **Schedule Regular Reports**: Set up Windows Task Scheduler to run daily/weekly
2. **Create Dashboards**: Export to Excel and create pivot charts
3. **Set Baselines**: Track your starting metrics to measure improvement
4. **Define KPIs**: E.g., "Reduce defect density to <2 per KLOC by Q2"
5. **Integrate with CI/CD**: Run metrics as part of your build pipeline

## Support

For questions about specific metrics or custom queries, consult the Coverity documentation or examine the SQL queries in [metrics.py](metrics.py).

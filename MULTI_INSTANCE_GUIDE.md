# Multi-Instance Coverity Metrics - User Guide

## Overview

The Coverity Metrics project now supports **multiple Coverity instances** in a cluster environment. You can:

- Connect to multiple Coverity databases simultaneously
- Generate **aggregated dashboards** showing metrics across all instances
- Generate **per-instance dashboards** for individual Coverity servers
- Filter by both **instance** and **project** for granular views

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Multi-Instance Manager                    │
│  (aggregates data from multiple Coverity instances)         │
└───────────┬─────────────────┬─────────────────┬─────────────┘
            │                 │                 │
            ▼                 ▼                 ▼
    ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
    │ Production   │  │ Development  │  │     QA       │
    │   Instance   │  │   Instance   │  │  Instance    │
    ├──────────────┤  ├──────────────┤  ├──────────────┤
    │ PostgreSQL   │  │ PostgreSQL   │  │ PostgreSQL   │
    │ Database     │  │ Database     │  │ Database     │
    └──────────────┘  └──────────────┘  └──────────────┘
```

## Configuration

### 1. Create `config.json`

Copy and customize the example configuration:

```bash
cp config.json.example config.json
```

### 2. Configure Instances

Edit `config.json` to define your Coverity instances:

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
        "password": "your_password_here"
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
        "password": "your_password_here"
      },
      "color": "#3498db"
    }
  ],
  "default_instance": "Production",
  "aggregated_view": {
    "enabled": true,
    "name": "All Instances"
  }
}
```

### Configuration Options

| Field | Description | Required |
|-------|-------------|----------|
| `name` | Display name for the instance | Yes |
| `description` | Human-readable description | No |
| `enabled` | Enable/disable this instance | No (default: true) |
| `database.host` | PostgreSQL server hostname/IP | Yes |
| `database.port` | PostgreSQL port | Yes |
| `database.database` | Database name (usually 'cim') | Yes |
| `database.user` | Database username | Yes |
| `database.password` | Database password | Yes |
| `color` | Color code for UI visualization | No |

## Usage

### Auto-Detection (Recommended)

The dashboard generator **automatically detects** when you have multiple instances configured and generates all necessary dashboards:

```bash
# Automatically generates:
# - Aggregated dashboard (all instances combined)
# - Per-instance dashboards (one for each enabled instance)
# - Per-project dashboards (one for each project across all instances)
coverity-dashboard

# Generate dashboards for specific project across all instances
coverity-dashboard --project MyApp

# Generate dashboard for specific instance only
coverity-dashboard --instance Production

# Force single-instance mode (disables auto-detection)
coverity-dashboard --single-instance-mode
```

### How Auto-Detection Works

1. Reads `config.json` to check enabled instances
2. If **more than one** enabled instance → Multi-instance mode
3. If **one or zero** enabled instances → Single-instance mode
4. Automatically generates all relevant dashboards

### Advanced Commands

```bash
# Generate with custom time range (365 days default)
coverity-dashboard --days 180

# Don't open browser automatically
coverity-dashboard --no-browser

# Bypass cache for fresh data
coverity-dashboard --no-cache
```

### Dashboard Views

When running in multi-instance mode (automatic when 2+ instances configured), the following dashboards are generated:

#### Generated Dashboards

```bash
# Default command generates ALL of these:
coverity-dashboard

# Output files created:
output/
├── dashboard_aggregated.html          # Combined view of all instances
├── dashboard_Production.html          # Production instance
├── dashboard_Development.html         # Development instance
├── dashboard_QA.html                  # QA instance
├── dashboard_Production_MyApp.html    # MyApp project in Production
├── dashboard_Development_MyApp.html   # MyApp project in Development
└── ... (one per instance + one per project per instance)
```

#### 1. Aggregated View
Shows combined metrics from all Coverity instances:
- Total defects across all instances
- Defects by instance (comparison chart)
- All projects from all instances
- Cross-instance performance comparison

Generated as `dashboard_aggregated.html` when the aggregated view is enabled.
In database mode it is opted in via `aggregated_view.enabled: true` in
`config.json` (see the config example above). In ZIP mode it is off by default
and opts in via either the CLI flag `--aggregated-view` **or** a `--config`
whose `zip_files_config.aggregated_view.enabled` is `true` — either source
alone is enough.

#### 2. Per-Instance Views
Individual dashboard for each Coverity instance:

Generated automatically as:
- `output/dashboard_Production.html`
- `output/dashboard_Development.html`
- `output/dashboard_QA.html`

#### 3. Instance + Project Views
Drill down to specific projects in specific instances:

Generated automatically for each project in each instance:
- `output/dashboard_Production_MyApp.html`
- `output/dashboard_Development_MyApp.html`

To generate only for specific project:
```bash
coverity-dashboard --project MyApp
```

## Dashboard Features

### Instance Filter
The dashboard includes a cascading filter system:

```
┌────────────────────────────────────────┐
│  Instance: [Production ▼]             │
│                                        │
│  Project:  [MyApp ▼]                  │
└────────────────────────────────────────┘
```

### Aggregated Dashboard Sections

1. **Instance Overview**
   - Total instances
   - Combined defect count
   - Projects across all instances
   - Instance health status

2. **Defects by Instance**
   - Bar chart comparing defect counts
   - Color-coded by instance
   - Drill-down to instance details

3. **Cross-Instance Metrics**
   - Top projects across all instances
   - Global hotspots
   - Comparative performance metrics

4. **Instance Comparison Table**
   | Instance | Defects | Projects | Streams | Status |
   |----------|---------|----------|---------|--------|
   | Production | 1,234 | 45 | 67 | ✓ |
   | Development | 567 | 23 | 34 | ✓ |
   | QA | 890 | 12 | 18 | ✓ |

## Security Considerations

### 1. Protect Configuration File

The `config.json` contains database passwords:

```bash
# Linux/Mac
chmod 600 config.json

# Git ignore
echo "config.json" >> .gitignore
```

### 2. Use Read-Only Database Accounts

Create dedicated read-only users for metrics:

```sql
-- On each Coverity PostgreSQL database
CREATE USER coverity_ro WITH PASSWORD 'secure_password';
GRANT CONNECT ON DATABASE cim TO coverity_ro;
GRANT USAGE ON SCHEMA public TO coverity_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO coverity_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO coverity_ro;
```

### 3. Environment Variables (Alternative)

Use environment variables instead of storing passwords in config:

```json
{
  "database": {
    "password": "${COVERITY_PROD_PASSWORD}"
  }
}
```

```bash
export COVERITY_PROD_PASSWORD="actual_password"
coverity-dashboard
```

## Performance Considerations

### Connection Pooling
For large environments with many instances:

```python
from multi_instance_metrics import MultiInstanceMetrics

# Initialize once, reuse connections
multi_metrics = MultiInstanceMetrics('config.json')

# Use for multiple operations
summary = multi_metrics.get_aggregated_summary()
by_instance = multi_metrics.get_defects_by_instance()
```

### Parallel Data Collection
Data from multiple instances is collected in parallel for better performance:

```
Instance 1 ─┐
Instance 2 ─┼─→ Parallel Fetch → Aggregate → Dashboard
Instance 3 ─┘
```

## Examples

### Example 1: Morning Dashboard Generation (Simplified)

```bash
#!/bin/bash
# Generate all dashboards for daily review

echo "Generating Coverity Metrics Dashboards..."

# Single command generates everything:
# - Aggregated dashboard
# - Per-instance dashboards
# - Per-project dashboards
coverity-dashboard --no-browser

# Critical project across all instances
coverity-dashboard --project CriticalApp --no-browser

echo "Dashboards generated successfully!"
```

### Example 2: Programmatic Access

```python
from multi_instance_metrics import MultiInstanceMetrics

# Initialize
multi = MultiInstanceMetrics('config.json')

# Get aggregated summary
print("=== Aggregated Summary ===")
summary = multi.get_aggregated_summary()
print(f"Total defects across all instances: {summary['total_defects']}")
print(f"Total projects: {summary['total_projects']}")

# Get defects by instance
print("\n=== Defects by Instance ===")
by_instance = multi.get_defects_by_instance()
print(by_instance[['instance_name', 'total_defects', 'total_projects']])

# Access specific instance
print("\n=== Production Instance Details ===")
prod_metrics = multi.get_metrics_for_instance('Production')
prod_summary = prod_metrics.get_overall_summary()
print(f"Production defects: {prod_summary['total_defects']}")
```

### Example 3: Scheduled Reporting

```python
# weekly_report.py
from multi_instance_metrics import MultiInstanceMetrics
import pandas as pd
from datetime import datetime

multi = MultiInstanceMetrics('config.json')

# Generate weekly report
report_data = {
    'week': datetime.now().strftime('%Y-W%U'),
    'total_defects': 0,
    'instances': []
}

for instance_name in multi.get_instance_names():
    metrics = multi.get_metrics_for_instance(instance_name)
    summary = metrics.get_overall_summary()
    
    report_data['instances'].append({
        'name': instance_name,
        'defects': summary['total_defects'],
        'projects': summary['total_projects']
    })
    report_data['total_defects'] += summary['total_defects']

# Save to CSV
df = pd.DataFrame(report_data['instances'])
df.to_csv(f"weekly_report_{report_data['week']}.csv", index=False)
```

## Troubleshooting

### Connection Issues

```bash
# Test connectivity to specific instance
python multi_instance_metrics.py

# Check if instance is reachable
psql -h coverity-prod.company.com -p 5432 -U coverity_ro -d cim
```

### Missing Instances

If an instance is unavailable:
- Set `"enabled": false` in config.json to skip it
- The aggregated view will continue with available instances
- Check logs for connection errors

### Performance Issues

For slow dashboards with many instances:
- Disable unused instances
- Use `--instance` flag to generate specific dashboards
- Consider caching results for large datasets

## Migration from Single Instance

To migrate from single-instance setup:

1. **Backup current config**:
   ```bash
   cp db_config.ini db_config.ini.backup
   ```

2. **Create config.json** with your current instance as the first entry

3. **Test with single instance** (auto-detection recognizes single instance):
   ```bash
   # If only one instance in config.json, works same as before
   coverity-dashboard
   ```

4. **Add second instance** to config.json - auto-detection automatically switches to multi-instance mode:
   ```json
   {
     "instances": [
       {
         "name": "Production",
         "enabled": true,
         ...
       },
       {
         "name": "Development",
         "enabled": true,
         ...
       }
     ]
   }
   ```

5. **Generate multi-instance dashboards** with same command:
   ```bash
   # Now automatically generates aggregated + per-instance dashboards
   coverity-dashboard
   ```


## API Reference

See [multi_instance_metrics.py](multi_instance_metrics.py) for complete API documentation.

Key classes:
- `MultiInstanceMetrics`: Main manager for multi-instance operations
- `InstanceConfig`: Configuration for a single instance

Key methods:
- `get_aggregated_summary()`: Combined statistics
- `get_defects_by_instance()`: Per-instance breakdown
- `get_all_projects_across_instances()`: All projects with instance attribution

---

## Support

For questions or issues with multi-instance setup, please refer to the main README.md or create an issue in the project repository.

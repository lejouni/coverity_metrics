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
  "aggregated_view": {
    "enabled": true,
    "name": "All Instances"
  }
}
```

> `aggregated_view.enabled: true` is what opts you in to the cross-instance
> `dashboard_aggregated.html`. Leaving it out (or setting `false`) still
> generates per-instance dashboards — you just don't get the combined view.
> In ZIP mode the flag lives under `zip_files_config.aggregated_view.enabled`
> and can also be opted in from the CLI with `--aggregated-view`
> (see [MULTI_ZIP_GUIDE.md](MULTI_ZIP_GUIDE.md)).

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
├── Production/
│   ├── dashboard.html                 # Production instance overview
│   ├── dashboard_MyApp.html           # MyApp project in Production
│   └── ...                            # One dashboard_<Project>.html per project
├── Development/
│   ├── dashboard.html
│   ├── dashboard_MyApp.html
│   └── ...
└── QA/
    ├── dashboard.html
    └── ...
```

> Instance names containing spaces are sanitised to underscores in the
> folder name (`Production NAM` → `Production_NAM/`), but the visible
> labels inside the HTML preserve the original spelling.

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
- `output/Production/dashboard.html`
- `output/Development/dashboard.html`
- `output/QA/dashboard.html`

To skip per-project dashboards and generate the instance-level pages only,
pass `--instance-only` (aka `--no-projects`).

#### 3. Instance + Project Views
Drill down to specific projects in specific instances:

Generated automatically for each project in each instance:
- `output/Production/dashboard_MyApp.html`
- `output/Development/dashboard_MyApp.html`

To generate only for a specific project (across every enabled instance):
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

### 3. Environment Variables (single-instance export only)

`config.json` does **not** currently interpolate `${VAR}` placeholders — the
instance loader reads `database.password` verbatim. Store passwords in
`config.json` (with `chmod 600`) or fetch them via your existing secrets
tooling before invoking the CLI.

Env-var driven runs are supported on `coverity-export --env` for a single
instance (no `config.json` required):

```bash
export COVERITY_DB_HOST="coverity-prod.company.com"
export COVERITY_DB_NAME="cim"
export COVERITY_DB_USER="coverity_ro"
export COVERITY_DB_PASSWORD="actual_password"
export COVERITY_DB_PORT="5432"                # optional, default 5432
export COVERITY_INSTANCE_NAME="Production"    # optional, labels the ZIP

coverity-export --env --output-dir ./exports
```

Use the resulting ZIP with `coverity-dashboard --zip-file` for a fully
offline downstream run — see [EXPORT_QUICKSTART.md](EXPORT_QUICKSTART.md)
and [MULTI_ZIP_GUIDE.md](MULTI_ZIP_GUIDE.md).

## Performance Considerations

### Connection Pooling
For large environments with many instances:

```python
from coverity_metrics import MultiInstanceMetrics

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
from coverity_metrics import MultiInstanceMetrics

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
from coverity_metrics import MultiInstanceMetrics
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
# Test connectivity via the CLI (uses config.json)
coverity-dashboard --instance Production --no-browser

# Or as a module (equivalent, no PATH entry needed):
python -m coverity_metrics dashboard --instance Production --no-browser

# Check the raw PostgreSQL connectivity independently
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

## Growing a single-instance setup into a cluster

Auto-detection is the whole migration story: the same command
(`coverity-dashboard`) works for one instance or ten. There is no separate
single-instance config file to convert away from — `config.json` is the
authoritative shape.

1. **Start with one entry in `config.json`** and confirm it works:
   ```bash
   coverity-dashboard --no-browser
   ```
   With a single enabled instance the tool runs in single-instance mode and
   writes `output/dashboard.html` at the root (no per-instance folder).

2. **Add a second `instances[]` entry** — auto-detection switches to
   multi-instance mode as soon as two entries have `"enabled": true`:
   ```json
   {
     "instances": [
       { "name": "Production",  "enabled": true, "database": { ... } },
       { "name": "Development", "enabled": true, "database": { ... } }
     ],
     "aggregated_view": { "enabled": true, "name": "All Instances" }
   }
   ```

3. **Re-run the same command** — you now get per-instance folders plus, if
   `aggregated_view.enabled: true`, the cross-instance dashboard:
   ```bash
   coverity-dashboard --no-browser
   ```

Force single-instance behaviour on a multi-instance config with
`--single-instance-mode` (loads the first enabled instance only).

## API Reference

See [coverity_metrics/multi_instance_metrics.py](coverity_metrics/multi_instance_metrics.py)
for the complete API. The public surface is also re-exported from the
package root, so `from coverity_metrics import MultiInstanceMetrics,
InstanceConfig` is the recommended import.

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

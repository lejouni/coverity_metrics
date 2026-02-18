# Installing and Using coverity-metrics Package

## Installation

### From Source (Development)

```bash
# Clone the repository
git clone https://github.com/lejouni/coverity-metrics.git
cd coverity-metrics

# Install in editable mode for development
pip install -e .

# Or install with development dependencies
pip install -e ".[dev]"
```

### From Built Package

```bash
# Build the package
python -m build

# Install the built wheel
pip install dist/coverity_metrics-1.0.0-py3-none-any.whl
```

### From PyPI (when published)

```bash
pip install coverity-metrics
```

## Usage

### Command Line Interface

After installation, three CLI commands become available:

#### 1. Generate Dashboard

```bash
# Auto-detect configuration and generate dashboards
coverity-dashboard

# Filter by project
coverity-dashboard --project MyApp

# Generate for specific instance
coverity-dashboard --instance Production

# Custom configuration file
coverity-dashboard --config my-config.json

# Enable caching for better performance
coverity-dashboard --cache

# Full help
coverity-dashboard --help
```

#### 2. Generate Console Report

```bash
# Generate comprehensive console metrics report
coverity-metrics

# Full help
coverity-metrics --help
```

#### 3. Export to CSV

```bash
# Export all metrics to CSV files
coverity-export

# Full help
coverity-export --help
```

### Python API

```python
from coverity_metrics import CoverityMetrics, MultiInstanceMetrics

# Single instance
connection_params = {
    'host': 'coverity-server.com',
    'port': 5432,
    'database': 'cim',
    'user': 'coverity_ro',
    'password': 'password'
}

metrics = CoverityMetrics(connection_params=connection_params)

# Get metrics
summary = metrics.get_overall_summary()
defects = metrics.get_defects_by_severity()
hotspots = metrics.get_file_hotspots(limit=10)

# Multi-instance
multi = MultiInstanceMetrics('config.json')
aggregated = multi.get_aggregated_summary()
by_instance = multi.get_defects_by_instance()
```

## Configuration

Create `config.json` in your working directory:

```json
{
  "instances": [
    {
      "name": "Production",
      "enabled": true,
      "database": {
        "host": "coverity-prod.company.com",
        "port": 5432,
        "database": "cim",
        "user": "coverity_ro",
        "password": "your_password"
      }
    }
  ]
}
```

**Important:** Add `config.json` to `.gitignore` to protect credentials!

## Requirements

- Python >= 3.8
- PostgreSQL access to Coverity database
- Dependencies (automatically installed):
  - psycopg2-binary
  - pandas
  - jinja2
  - plotly
  - tqdm
  - and others (see pyproject.toml)

## Documentation

See the main [README.md](README.md) for detailed feature documentation.

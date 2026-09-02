# Multi-ZIP Aggregation Guide

## Overview

The **Multi-ZIP Aggregation** feature allows you to combine metrics from multiple Coverity instances exported as separate ZIP files. This is useful when you cannot access all instances simultaneously or when instances are on different networks.

## Use Cases

### 1. **Different Networks**
Export from production and development instances on isolated networks, then combine on an analysis machine:
```bash
# On Production network:
coverity-export --output exports_prod

# On Development network:
coverity-export --output exports_dev

# On analysis machine (offline):
coverity-dashboard --zip-file exports_prod/*.zip exports_dev/*.zip
```

### 2. **Staggered Exports**
Don't wait for all instances - export when ready, aggregate later:
```bash
# Monday: Export from Instance A
coverity-export --output monday_exports

# Tuesday: Export from Instance B  
coverity-export --output tuesday_exports

# Wednesday: Export from Instance C
coverity-export --output wednesday_exports

# Thursday: Combine all into aggregated dashboard
coverity-dashboard --zip-file monday_exports/*.zip tuesday_exports/*.zip wednesday_exports/*.zip
```

### 3. **Air-Gapped Delivery**
Transfer multiple ZIP files via USB/file share, combine offline:
```bash
# Secure network: Export from all instances
coverity-export --config prod_config.json --output secure_exports
coverity-export --config staging_config.json --output secure_exports

# Transfer ZIPs to air-gapped network via approved media

# Air-gapped network: Generate dashboards
coverity-dashboard --zip-file secure_exports/*.zip --no-browser
```

### 4. **Historical Comparison**
Merge current exports with archived historical snapshots:
```bash
# Combine January and February exports
coverity-dashboard --zip-file \
    archives/2026-01/*.zip \
    archives/2026-02/*.zip
```

## Command Syntax

### Basic Multi-ZIP
```bash
coverity-dashboard --zip-file file1.zip file2.zip file3.zip
```

### With Wildcard
```bash
coverity-dashboard --zip-file exports/*.zip
```

`*` / `?` / `[…]` patterns are expanded inside the tool, so wildcards
work identically on Linux, macOS, and Windows (PowerShell / `cmd`) —
no shell expansion required.

### With Project Filter
Filter for a specific project across all instances:
```bash
coverity-dashboard --zip-file prod.zip dev.zip staging.zip --project MyApp
```

### With Custom Output
```bash
coverity-dashboard --zip-file *.zip --output aggregated_reports --no-browser
```

### Opting In to the Aggregated View
```bash
coverity-dashboard --zip-file *.zip --aggregated-view --output aggregated_reports --no-browser
```

The cross-instance `dashboard_aggregated.html` is **off by default** in ZIP mode.
Enable it either with the CLI flag `--aggregated-view` or by pointing `--config`
at a JSON file with `"zip_files_config": {"aggregated_view": {"enabled": true}}`.
Either source alone is enough — no ordering rules. Instance colors on the
aggregated dashboard are auto-assigned from the built-in palette.

## What Gets Generated

When you provide multiple ZIP files:

1. **Per-Instance Dashboards**: One for each ZIP file
   - `output/InstanceA/dashboard.html`
   - `output/InstanceB/dashboard.html`
   - `output/InstanceC/dashboard.html`

2. **Per-Project Dashboards**: All projects from all instances
   - `output/InstanceA/dashboard_Project1.html`
   - `output/InstanceA/dashboard_Project2.html`
   - `output/InstanceB/dashboard_Project1.html`
   - etc.

3. **Aggregated Dashboard** (opt-in): Combined view across all instances
   - `output/dashboard_aggregated.html` — created only when `--aggregated-view`
     is passed or a `--config` enables it (see above).

## Duplicate Instance Names Across ZIPs

If two or more ZIPs carry the same internal instance name (for example, every
ZIP is labelled `Production` even though the exports came from different
Coverity servers), the aggregated dashboard used to silently collapse them
into a single row because the loader dict was keyed by that name. Duplicates
are now disambiguated by appending the ZIP filename's stem in parentheses —
e.g. `Production (prod_us)`, `Production (prod_eu)` — so each ZIP appears as
its own instance in the aggregated view, its own per-instance output folder,
and its own palette color. Unique instance names are left untouched.

## Current Limitations

- Each ZIP must contain data from a single instance
- The aggregated view is opt-in — the run only produces per-instance
  dashboards unless you pass `--aggregated-view` or enable it in a config
  file passed via `--config`.

## Complete Workflow Example

### Step 1: Export from Each Instance

On **Production** Coverity server:
```bash
coverity-export --config prod_config.json --output exports --days 365
# Creates: exports/coverity_export_20260224_120000.zip
```

On **Development** Coverity server:
```bash
coverity-export --config dev_config.json --output exports --days 365
# Creates: exports/coverity_export_20260224_130000.zip
```

On **Staging** Coverity server:
```bash
coverity-export --config staging_config.json --output exports --days 365
# Creates: exports/coverity_export_20260224_140000.zip
```

### Step 2: Collect All ZIP Files

Transfer all 3 ZIP files to your analysis machine:
```
my_exports/
├── prod_coverity_export_20260224_120000.zip
├── dev_coverity_export_20260224_130000.zip
└── staging_coverity_export_20260224_140000.zip
```

### Step 3: Generate Aggregated Dashboards

```bash
cd my_exports
coverity-dashboard --zip-file *.zip --output combined_dashboards
```

### Step 4: View Results

Open generated dashboards in browser:
```
combined_dashboards/
├── Production/
│   ├── dashboard.html  (Instance overview)
│   ├── dashboard_Project1.html
│   └── dashboard_Project2.html
├── Development/
│   ├── dashboard.html
│   └── dashboard_Project3.html
└── Staging/
    ├── dashboard.html
    └── dashboard_Project4.html
```

## Benefits

✅ **No Simultaneous Database Access Required**: Export from instances at different times  
✅ **Network Isolation**: Combine data from air-gapped or isolated networks  
✅ **Flexible Delivery**: Email/share individual ZIP files, aggregate on receiving end  
✅ **Historical Analysis**: Merge old and new exports for trend comparison  
✅ **Reduced Database Load**: One-time export per instance, multiple dashboard generations  
✅ **Stakeholder Friendly**: No credentials needed for dashboard viewing

## See Also

- [README.md](README.md) - General documentation
- [MULTI_INSTANCE_GUIDE.md](MULTI_INSTANCE_GUIDE.md) - Database multi-instance mode
- [USAGE_GUIDE.md](USAGE_GUIDE.md) - Detailed usage examples

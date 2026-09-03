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

### From PyPI

```bash
pip install coverity-metrics
```

### Installing without admin or root rights

If you don't have permission to install into the system Python (typical on
locked-down corporate machines), use one of the two options below. Both
work the same on Linux, macOS, and Windows, and both use the same package
you already have access to on PyPI.

**Option 1 — User install (simplest, same command + one flag):**

```bash
# Fresh install
python3 -m pip install --user coverity-metrics

# Upgrade an existing user install
python3 -m pip install --user --upgrade coverity-metrics
```

On Windows use `python` (or `py -3`) instead of `python3`. If the CLI
commands aren't found after install, `pip` will print the user-scripts
directory to add to your `PATH`:

- Linux / macOS (bash/zsh, add to `~/.bashrc` or `~/.zshrc`):
  ```bash
  export PATH="$(python3 -m site --user-base)/bin:$PATH"
  ```
- Windows: run `python -m site --user-base` to see the base directory, then
  add its `Scripts` subfolder to your user `PATH` (System Properties →
  Environment Variables → user `Path` → Edit). No admin required.

You can also skip `PATH` entirely and invoke the tool as a module:

```bash
python3 -m coverity_metrics dashboard  # or: report, export
```

**Option 2 — `pipx` (isolated, recommended if you use several Python CLIs):**

```bash
# One-time pipx bootstrap (no admin needed)
python3 -m pip install --user pipx
python3 -m pipx ensurepath

# Then install coverity-metrics into its own venv
pipx install coverity-metrics

# Upgrade later
pipx upgrade coverity-metrics
```

`pipx` gives each CLI its own virtual environment, so `coverity-metrics`
never conflicts with other packages in your Python setup.

### Standalone binary (no Python required on the target host)

Windows and Linux single-file binaries are published on every tagged
release — see
[packaging/README.md](https://github.com/lejouni/coverity_metrics/blob/main/packaging/README.md)
for the download links and the full command reference. They ship their own
Python runtime, so the target machine does not need a Python install.

- Windows: `coverity-metrics-windows-<version>.exe`
- Linux:   `coverity-metrics-linux-<version>`

The Linux binary is built as a PyInstaller **onefile** bundle: at every
launch it extracts its bundled shared libraries (Python runtime, `libz`,
etc.) into a temporary directory and `dlopen()`s them from there. On
hardened hosts where `/tmp` is mounted with `noexec` (or SELinux blocks
executable mappings on tmpfs), this fails at startup — see the
troubleshooting section below.

#### Troubleshooting: `libz.so.1: failed to map segment from shared object`

Full error, seen on locked-down Linux hosts on the first launch of the
standalone binary:

```text
./coverity-metrics-linux-vX.Y.Z: error while loading shared libraries: \
    libz.so.1: failed to map segment from shared object
```

This is **not** the system `libz` — the binary carries its own copy
inside the onefile bundle. The extraction target (`/tmp/_MEIxxxxxx/` by
default) rejects the `mmap` of the shared object with executable pages.

Confirm the cause, then apply the smallest fix that works:

1. **Check whether `/tmp` is mounted `noexec`** (the most common cause):

   ```bash
   mount | grep ' /tmp '
   # look for "noexec" in the options list
   ```

2. **Point PyInstaller at an exec-allowed directory** (no rebuild, no
   admin required — usually enough):

   ```bash
   mkdir -p "$HOME/.cache/coverity-metrics-tmp"
   TMPDIR="$HOME/.cache/coverity-metrics-tmp" \
       ./coverity-metrics-linux-vX.Y.Z --help
   ```

   PyInstaller honours `TMPDIR` for the `_MEI` extraction directory.
   `/var/tmp` also usually works if `$HOME` is on a restrictive mount.
   Persist the setting by exporting `TMPDIR` in `~/.bashrc` /
   `~/.zshrc` or via a wrapper script.

3. **Or remount `/tmp` with `exec`** (system-wide, needs root):

   ```bash
   sudo mount -o remount,exec /tmp
   ```

4. **If step 1 shows `/tmp` is already `exec`**, rule out the other
   two failure modes:

   - **Disk full** — `df -h /tmp` (and `df -h "$TMPDIR"` if you set it).
   - **SELinux / AppArmor** — `getenforce` and `sudo dmesg | tail`;
     look for `AVC` denials against `execmem` on tmpfs. The `TMPDIR`
     workaround in step 2 sidesteps SELinux tmpfs restrictions on most
     distros; policy exceptions are the alternative.

The Windows binary is not affected — Windows has no equivalent of a
`noexec` mount option for the user-writable temp directory.

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

- Python >= 3.10 (required by `pandas` >=3.0)
- PostgreSQL access to Coverity database
- Dependencies (automatically installed):
  - pg8000
  - pandas
  - jinja2
  - plotly
  - tqdm
  - and others (see pyproject.toml)

## Documentation

See the main [README.md](README.md) for detailed feature documentation.

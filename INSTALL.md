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

### Into a Python virtual environment (recommended for keeping installs isolated)

A virtual environment gives `coverity-metrics` its own site-packages tree
so it can't collide with other Python tools on your machine, and lets you
delete the whole install by removing one folder. Works identically on
Linux, macOS, and Windows and needs no admin rights.

**Linux / macOS (bash / zsh):**

```bash
# 1. Create the venv (any directory name works; ".venv" is convention).
python3 -m venv .venv

# 2. Activate it for the current shell.
source .venv/bin/activate

# 3. Install coverity-metrics from PyPI (or from a local wheel / source).
pip install --upgrade pip
pip install coverity-metrics

# 4. Use the CLIs — no PATH tweaking needed while the venv is active.
coverity-dashboard --help
coverity-export --help
coverity-report --help
coverity-delta --help

# 5. When you're done, deactivate. To re-use it later, just re-activate.
deactivate
```

**Windows (PowerShell):**

```powershell
# 1. Create the venv. Prefer the Python launcher to pick a specific version:
#    `py -3.14 -m venv .venv` targets Python 3.14; `python -m venv .venv`
#    uses whichever `python` is first on PATH.
py -3.14 -m venv .venv

# 2. Activate. If PowerShell refuses with an ExecutionPolicy error, run
#    `Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned`
#    once for this shell (no admin required).
.\.venv\Scripts\Activate.ps1

# 3. Install.
python -m pip install --upgrade pip
pip install coverity-metrics

# 4. Use.
coverity-dashboard --help

# 5. Done.
deactivate
```

**Windows (cmd.exe):**

```cmd
py -3.14 -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install coverity-metrics
coverity-dashboard --help
deactivate
```

Notes:

- Requires Python 3.10+ (matching the `pyproject.toml` `requires-python`).
  Newer Python is fine; the packaged wheels are `py3-none-any`.
- The venv folder is entirely self-contained — delete `.venv` to wipe the
  install, no other cleanup needed.
- To pin an exact version: `pip install coverity-metrics==1.1.10`.
- To install from a local wheel or source checkout instead of PyPI, use
  `pip install path/to/coverity_metrics-*.whl` or `pip install .` after
  activating the venv.
- If you'd rather have every Python CLI in its own venv without managing
  them by hand, jump to Option 2 (`pipx`) below — it does the same thing
  under the hood plus keeps the entry-point commands on your `PATH`
  globally.

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
- Linux (modern glibc, >= 2.38):   `coverity-metrics-linux-<version>`
- Linux (legacy glibc, >= 2.35):   `coverity-metrics-linux-glibc2.35-<version>`

**Which Linux binary?** Both ship the same features and use the same
CPython 3.14 runtime; they differ only in the minimum host glibc they
require. Check your host's glibc first:

```bash
ldd --version | head -n1
# e.g. "ldd (Ubuntu GLIBC 2.35-0ubuntu3) 2.35"  → use the -glibc2.35- binary
```

- glibc **>= 2.38** (Ubuntu 24.04+, Debian trixie+, Fedora 39+) → use the
  primary `coverity-metrics-linux-<version>`. Built on Ubuntu 26.04.
- glibc **2.35 – 2.37** (Ubuntu 22.04, Debian 12, Fedora 36–38) → use
  `coverity-metrics-linux-glibc2.35-<version>`. Built on Ubuntu 22.04.
- glibc **< 2.35** (RHEL/Rocky/Alma 9 → 2.34, RHEL/Rocky/Alma 8 → 2.28,
  Amazon Linux 2023 → 2.34, RHEL 7 → 2.17, other enterprise hosts) →
  the standalone binary cannot help. Install via
  `pip install coverity-metrics` from PyPI on a host with Python 3.10+
  (see the "Into a Python virtual environment" section above). A
  `manylinux_2_28`-based third variant was attempted in 1.1.8–1.1.10
  but reverted: the image's CPython 3.14 is linked against
  `libssl.so.1.1` and no amount of `LD_LIBRARY_PATH` gymnastics can
  retarget that at a fresh `libssl.so.3`, so the produced binary
  would have carried OpenSSL 1.1.1k (EOL) baked in. `pip install` is
  the maintained path for those hosts.

If a binary is a mismatch you'll see it at launch:

```text
[PYI-...:ERROR] Failed to load Python shared library '.../libpython3.14.so.1.0': \
    /lib64/libm.so.6: version `GLIBC_2.XX' not found (required by \
    .../libpython3.14.so.1.0)
```

Move down to the next-older-glibc binary in the list above (or, if
already on the `-glibc2.35-` binary, fall back to `pip install`).

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

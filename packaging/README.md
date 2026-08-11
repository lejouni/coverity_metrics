# Standalone binaries

Self-contained `coverity-metrics` executables for **Windows** and **Linux** — no
Python install required on the target machine. Everything (dependencies,
templates, CSS) is bundled with [PyInstaller](https://pyinstaller.org/).

## For end users

1. Download the binary for your OS from the
   [Releases page](https://github.com/lejouni/coverity_metrics/releases):
   - Windows: `coverity-metrics-windows-<version>.exe`
   - Linux: `coverity-metrics-linux-<version>`
2. Place your `config.json` next to the binary (start from
   [`config.json.example`](../config.json.example)).
3. Run any subcommand:

   ```bash
   # Windows
   coverity-metrics-windows-<version>.exe dashboard --config config.json --output ./dashboards

   # Linux
   chmod +x coverity-metrics-linux-<version>
   ./coverity-metrics-linux-<version> dashboard --config config.json --output ./dashboards
   ```

Subcommands: `dashboard`, `export`, `report` (see `--help` on each).

### Notes
- **Linux glibc**: binaries are built on `ubuntu-latest` (glibc 2.39). They
  won't run on RHEL 8 / Ubuntu 20.04. Use the wheel + `pip` on older systems.
- **Windows SmartScreen**: the binary is unsigned, so first-run may show a
  warning. Click "More info" → "Run anyway".
- **Cold start**: onefile binaries extract to a temp directory on first run;
  expect a 2–5 s startup delay. Subsequent runs are cached.

## For maintainers — building locally

Install the project with the `build` extra in an isolated env:

```powershell
# Windows
py -3.12 -m venv .binbuild
.binbuild\Scripts\Activate.ps1
pip install -e .[build]
pwsh -File packaging/build_binary.ps1
```

```bash
# Linux
python3.12 -m venv .binbuild
source .binbuild/bin/activate
pip install -e '.[build]'
bash packaging/build_binary.sh
```

Output lands in `dist/coverity-metrics[.exe]`.

## CI

[.github/workflows/build-binaries.yml](../.github/workflows/build-binaries.yml)
builds both binaries in a matrix on every `v*` tag push and attaches them to
the corresponding GitHub Release. Trigger a manual build via the "Run workflow"
button on the Actions tab (`workflow_dispatch`).

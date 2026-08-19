# Export Quickstart

This guide walks through the two quickstart scripts under
[scripts/](scripts/) that let you run a full Coverity metrics export
**without installing Python**, and then turn the resulting ZIP back into
HTML dashboards using the same downloaded binary.

- Linux: [scripts/coverity-export.sh](scripts/coverity-export.sh)
- Windows: [scripts/coverity-export.ps1](scripts/coverity-export.ps1)

Both scripts do the same three things:

1. Download the `coverity-metrics` standalone binary for a given GitHub
   release tag (or the newest release) into `scripts/bin/`, or re-use a
   cached copy from a previous run.
2. Set the Postgres connection env vars from the block at the top of the
   script (or from a `--config` file you pass in).
3. Run `coverity-metrics export` and write one ZIP per Coverity instance.

For the underlying CLI reference, feature list, and Python API, see
[README.md](README.md) and [USAGE_GUIDE.md](USAGE_GUIDE.md).

## Prerequisites

- **Linux**: `bash`, `curl`. Nothing else — the binary is fully self-
  contained.
- **Windows**: PowerShell 5.1 or newer. Nothing else.
- Network reach to `github.com` (for the first-time binary download) and to
  your Coverity Connect Postgres port (default `5432`).
- Postgres credentials with read access to the Coverity `cim` database.

The binary is cached under `scripts/bin/` after the first run, so
subsequent runs work fully offline as long as you keep the same
`--tag` / `-Tag`.

## First run

> **Review every variable in the "EDIT THESE VALUES" block, not just the
> password.** The defaults are placeholders — `coverity-prod.company.com`
> for the host, `cim` for the database name, `coverity_ro` for the user,
> `Production` for the instance name, etc. — and the host in particular
> is almost certainly wrong for your environment. Walk through all six
> variables (`COVERITY_DB_HOST`, `COVERITY_DB_PORT`, `COVERITY_DB_NAME`,
> `COVERITY_DB_USER`, `COVERITY_DB_PASSWORD`, `COVERITY_INSTANCE_NAME`)
> and set each to a real value before the first run.

### Linux / macOS

```bash
cd scripts
# Open coverity-export.sh and edit the "EDIT THESE VALUES" block at the
# top. Review ALL six variables (see the note above) — the placeholder
# host will not resolve in your network:
#   COVERITY_DB_HOST, COVERITY_DB_PORT, COVERITY_DB_NAME,
#   COVERITY_DB_USER, COVERITY_DB_PASSWORD, COVERITY_INSTANCE_NAME
# (or export those variables in your shell before running — the script
# only assigns defaults when the variable is empty).

chmod +x coverity-export.sh
./coverity-export.sh
```

The script refuses to run while `COVERITY_DB_PASSWORD` is still the
placeholder `change-me`, so an unedited copy fails fast — but the guard
only checks the password, so **it's on you to review the host, port,
database name, user, and instance name.** A wrong host usually shows up
as a `could not translate host name` or connection-timeout error a few
seconds after startup.

### Windows

```powershell
cd scripts
# Open coverity-export.ps1 in an editor and edit the "EDIT THESE VALUES"
# block at the top. Review ALL six variables (same list as Linux above)
# — the placeholder host is not real, OR set them in your PowerShell
# session first (the script only assigns defaults when the variable is
# empty).

# One-time execution-policy prompt for the current session:
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned

./coverity-export.ps1
```

Same placeholder-password guard applies — and the same "check every
variable, not just the password" caveat.

### What you get

By default the script writes to `scripts/exports/` (or wherever you point
`--output` / `-Output`). One ZIP per Coverity instance:

```
scripts/exports/
  Production.zip                # renamed if you set COVERITY_INSTANCE_NAME
  Production.mapping.json       # only present when --anonymize was used
```

The ZIP contains every metric as JSON plus a manifest — small enough to
email or attach to a support ticket.

## Common options

Every flag maps 1:1 to the `coverity-metrics export` CLI (see
[USAGE_GUIDE.md](USAGE_GUIDE.md) for full semantics). The most-used ones:

| Purpose                          | Linux                         | Windows                     |
| -------------------------------- | ----------------------------- | --------------------------- |
| Pin a specific release           | `--tag v1.0.29`               | `-Tag v1.0.29`              |
| Filter to one or more projects   | `--project "AppA,AppB"`       | `-Project "AppA,AppB"`      |
| Change the trend window (days)   | `--days 730`                  | `-Days 730`                 |
| Parallel workers (max 8)         | `--workers 4`                 | `-Workers 4`                |
| Anonymize project / stream names | `--anonymize`                 | `-Anonymize`                |
| Drop leaderboards from the ZIP   | `--no-leaderboards`           | `-NoLeaderboards`           |
| Drop per-snapshot tables         | `--no-snapshots`              | `-NoSnapshots`              |
| Custom output directory          | `--output exports/`           | `-Output exports/`          |
| Use a config file instead of env | `--config config.json`        | `-Config config.json`       |

### Config file mode

If you already maintain a `config.json` (or a multi-instance
`config.multi.json` — see [MULTI_INSTANCE_GUIDE.md](MULTI_INSTANCE_GUIDE.md)),
pass it directly:

```bash
./coverity-export.sh --config /path/to/config.json
```

```powershell
./coverity-export.ps1 -Config C:\path\to\config.json
```

When `--config` / `-Config` is set, the env-var block at the top of the
script is bypassed and the placeholder-password guard is skipped — the
binary reads every connection detail from the file.

### Anonymized exports (recommended before sharing)

```bash
./coverity-export.sh --anonymize
```

```powershell
./coverity-export.ps1 -Anonymize
```

Real project / stream / user / committer names in the ZIP become
`project_001`, `stream_001`, `user_001`, and so on. The mapping is written
to a sibling `*.mapping.json` next to each ZIP so you can decode later —
keep that file private, and only distribute the ZIP.

### Corporate SSL / TLS-inspection proxies

If your organisation's TLS interception makes the GitHub download fail:

```bash
# Preferred: hand curl your corporate root CA
./coverity-export.sh --cacert /etc/ssl/certs/company-root.crt
# Or via env var, no flag needed:
export CURL_CA_BUNDLE=/etc/ssl/certs/company-root.crt
./coverity-export.sh
```

```powershell
# Last-resort escape hatch when the chain is unfixable — skips TLS
# verification on the GitHub download only (nothing else in the session).
./coverity-export.ps1 -Insecure
```

Use `--insecure` / `-Insecure` only when you've verified the download some
other way (checksum, signed release, etc.).

## Rendering dashboards from the exported ZIP

The binary that `coverity-export.*` downloaded also runs
`coverity-metrics dashboard` — the exact same executable supports both
subcommands. So once you have a ZIP you don't need to install anything
else or re-download; just point the cached binary at the ZIP.

The scripts cache the binary at:

- Linux: `scripts/bin/coverity-metrics-linux-<tag>`
- Windows: `scripts\bin\coverity-metrics-windows-<tag>.exe`

Then invoke it with the `dashboard` subcommand and `--zip-file`:

### Linux

```bash
# Adjust the tag suffix to whatever ended up in scripts/bin
./scripts/bin/coverity-metrics-linux-v1.0.29 dashboard \
    --zip-file scripts/exports/Production.zip \
    --output dashboards/

# Multiple ZIPs at once (one dashboard set per ZIP, plus an aggregated view)
./scripts/bin/coverity-metrics-linux-v1.0.29 dashboard \
    --zip-file scripts/exports/Prod.zip scripts/exports/Staging.zip \
    --output dashboards/

# Skip the auto-open of the HTML in a browser (useful in headless / CI)
./scripts/bin/coverity-metrics-linux-v1.0.29 dashboard \
    --zip-file scripts/exports/Production.zip --no-browser
```

### Windows

```powershell
# Adjust the tag suffix to whatever ended up in scripts\bin
& .\scripts\bin\coverity-metrics-windows-v1.0.29.exe dashboard `
    --zip-file .\scripts\exports\Production.zip `
    --output dashboards\

# Multiple ZIPs at once
& .\scripts\bin\coverity-metrics-windows-v1.0.29.exe dashboard `
    --zip-file .\scripts\exports\Prod.zip .\scripts\exports\Staging.zip `
    --output dashboards\
```

### Portable "any latest" invocation

If you don't want to hardcode the tag, resolve the newest cached binary at
call time:

```bash
BIN=$(ls -1t scripts/bin/coverity-metrics-linux-* | head -n1)
"$BIN" dashboard --zip-file scripts/exports/Production.zip --output dashboards/
```

```powershell
$Bin = Get-ChildItem scripts\bin\coverity-metrics-windows-*.exe |
       Sort-Object LastWriteTime -Descending | Select-Object -First 1
& $Bin.FullName dashboard --zip-file .\scripts\exports\Production.zip --output dashboards\
```

### Options that still apply in ZIP mode

Everything that doesn't require a live database connection continues to
work when reading from a ZIP:

- `--project "AppA"` / `--project "AppA,AppB"` — narrow the dashboards to a
  subset of the projects captured in the ZIP.
- `--workers 4` — parallelize per-project rendering.
- `--output <dir>` — where to write the HTML files.
- `--no-browser` — skip auto-open.
- `--cache` / `--cache-dir` / `--cache-ttl` — cache the derived DataFrames
  between renders; see [CACHING_GUIDE.md](CACHING_GUIDE.md).

Trend-window options (`--days`) are still accepted in dashboard-from-ZIP
mode but are capped by what the export baked in: if you exported with
`--days 365`, passing `--days 730` at dashboard time can't invent extra
history. Re-run the export with a wider window if you need more.

## Where things live

After a successful first run:

```
scripts/
├── bin/
│   └── coverity-metrics-<os>-vX.Y.Z[.exe]    # cached binary
├── exports/
│   ├── Production.zip                        # one per instance
│   └── Production.mapping.json               # only with --anonymize
├── coverity-export.ps1
└── coverity-export.sh
```

The `bin/` and `exports/` directories are created on first run. You can
delete either at any time — the next run will re-download / re-export.

## Troubleshooting

**"COVERITY_DB_PASSWORD is still the placeholder value 'change-me'"**
You forgot to edit the env-var block at the top of the script (or you
haven't set the variable in your shell). Fix the block or export the
variable, then re-run. Alternatively use `--config` / `-Config` to point
at a real config file — the placeholder guard is skipped in that mode.

**`could not translate host name "coverity-prod.company.com"` (or similar)**
The placeholder host at the top of the script is a stand-in and is not
your Coverity Connect DB. Open the script, set `COVERITY_DB_HOST` to the
real hostname, and re-check `COVERITY_DB_PORT`, `COVERITY_DB_NAME`, and
`COVERITY_DB_USER` at the same time — the password guard doesn't catch a
placeholder host, so it's easy to miss.

**Download fails with a TLS error**
Corporate TLS interception is intercepting the GitHub CDN. Point curl /
PowerShell at your corporate root CA (`--cacert PATH` on Linux;
[Windows uses the machine cert store automatically](https://docs.microsoft.com/dotnet/framework/network-programming/certificate-and-key)).
As a last resort, `--insecure` / `-Insecure` skips TLS verification on
the GitHub download only.

**"Latest tag" resolution fails from an offline runner**
Pin `--tag vX.Y.Z` / `-Tag vX.Y.Z` explicitly. Once the binary is cached
in `scripts/bin/`, subsequent runs skip both the API call and the
download, so an offline pipeline that reused a previously-downloaded
binary continues to work.

**Dashboard command complains it can't find a database config**
You're missing `--zip-file <path>`. Without it, the dashboard subcommand
falls back to database mode and expects either `--config` or the
`COVERITY_DB_*` env vars.

**Multiple ZIPs but only one dashboard folder appears**
Use one `--output <dir>` and list every ZIP after a single `--zip-file`
flag (both scripts use `nargs='+'`, so
`--zip-file A.zip B.zip C.zip` is one flag with three values). The
binary emits one dashboard folder per ZIP under the shared output
directory.

## See also

- [README.md](README.md) — feature overview and env-var reference.
- [USAGE_GUIDE.md](USAGE_GUIDE.md) — every CLI flag and every Python API
  entry point.
- [CACHING_GUIDE.md](CACHING_GUIDE.md) — cache semantics for dashboards.
- [MULTI_INSTANCE_GUIDE.md](MULTI_INSTANCE_GUIDE.md) — running against
  fleets of Coverity Connect instances.
- [MULTI_ZIP_GUIDE.md](MULTI_ZIP_GUIDE.md) — aggregating dashboards from
  multiple ZIP exports.

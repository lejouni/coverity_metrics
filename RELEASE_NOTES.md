# Release Notes

## Version History

### Version 1.1.4 - YYYY-MM-DD

**New `coverity-delta` CLI: Multi-Snapshot Trend Comparison Report from a Folder of `coverity-export` ZIPs**

#### Added

##### 📊 `coverity-delta` — point at a folder of archived exports, get a trend report
- New standalone CLI ships alongside `coverity-dashboard` / `coverity-metrics` / `coverity-export`. Also exposed as the `delta` subcommand on `python -m coverity_metrics` and on the standalone binary (`coverity-metrics delta ...`). Runs entirely offline — no database access.
- **Single input**: `coverity-delta --archive-dir archive/` — where `archive/` contains **two or more** `coverity-export` ZIPs. There is no `--previous` / `--current` split; the folder is the sole input. Minimum 2 ZIPs, no upper bound. Snapshots are read into a chronological chain and every metric is emitted as a series over that chain, so 3, 4, or N-snapshot reports work identically.
- **Chronological ordering** is derived from `metadata.export_timestamp` inside each ZIP (robust — survives copying / re-archiving), with a fallback to the filename's `YYYYMMDD_HHMMSS` trailer and then to filesystem mtime as a last resort. Snapshot labels auto-derive to `YYYY-QN` from each ZIP's `export_date`; a `--labels a,b,c,...` override maps positionally in chronological order.
- Emits two artifacts under `--output`:
  - `delta.json` — machine-readable, schema v1, per-instance sections for projects, active users, scan activity, snapshot cadence, and defects-by-project. Each metric family carries a per-snapshot `series` array (length = number of ZIPs) plus first→last summary values. Round-trips through `json.dumps` for downstream tooling.
  - `dashboard_delta.html` — self-contained HTML report (inline CSS, no external CDN, no JS charting libraries). Header shows the full snapshot chain (`2026-Q1 → 2026-Q2 → 2026-Q3 → ...`), warnings ribbon if any, and per-instance sections. Every metric family gets a hand-rolled inline SVG line chart in addition to the raw values.
- **Trend metric families**:
  - **Projects** — per-snapshot count series + first→last added / dropped / retained set diff (from `total_defects_by_project.json`).
  - **Active users** — per-stat time series for `total_licensed_users`, `users_with_login`, `active_users`, and the two percentage columns from `user_license_statistics.json`; optionally augmented by a first→last set diff on `top_users_by_fixes.json`.
  - **Scan activity** — per-snapshot window totals for snapshots / files analyzed / defects introduced / defects eliminated (from `scan_activity_trend.json`). Includes a raw-numbers table with a column per snapshot alongside the line charts. When `--days` varies across the archive, a `normalized_per_day` series is emitted alongside raw totals.
  - **Stream activity** — per-snapshot active-stream count series + first→last "newly active" / "went dark" streams (from `snapshot_performance.json` — the underlying metric is a top-N sample, so only presence flips are reported, not per-stream count deltas).
  - **Defects by project** — one row per project (union across the whole window) with a sparkline of `active_defects` values across every snapshot (nulls break the line where the project was absent), first / last active values, first→last Δ + %Δ, and rank movement (▲ climbed, ▼ dropped, `new` / `dropped` for asymmetric appearance). Ranking is recomputed per snapshot via dense-rank on `active_defects`. The sparkline column exposes a numeric `data-sort-value` (the first→last Δ) so the repo's sortable-header autoloader keeps sorting the column even when the cell is a chart.

##### 🛡️ Guardrails (applied across the whole archive, not just adjacent pairs)
- All ZIPs in the archive must cover the **same instance list**. Mismatch between any two → hard-fail, message names the offending pair.
- All ZIPs must use the same **`--days` window**. Mismatch → hard-fail, unless `--allow-window-mismatch` is passed (documented as testing / advanced use only). When the escape hatch is set, the report is emitted anyway with a `window_mismatch` entry in `delta.json.warnings`, ⚠ markers on affected sections in the HTML, and a `normalized_per_day` series alongside raw totals.
- All ZIPs must share the **same anonymization mapping**. Fingerprint is a SHA-256 over the sorted (real → anon) pairs in each sibling `<zip>.mapping.json` — so runs sharing the same `--mapping-file` share the fingerprint, and runs with different files don't. Mismatch → hard-fail, no override; fix by rerunning every export with the same `--mapping-file`. Missing mapping on a subset of the archive is downgraded to a `mapping_missing_some` warning so users trying trend without anonymization still get a report.
- Empty folder / single-ZIP folder / missing folder → clear error messages with fix hints, not a Python traceback.

##### 📝 Recommended workflow (documented in `README.md` and `EXPORT_QUICKSTART.md`)
- At the end of every quarter, run `coverity-export --days 90 --anonymize --mapping-file archive/shared-mapping.json --output archive/` — same `--days` value and same `--mapping-file` every time. The ZIP lands directly in the shared `archive/` folder. Non-overlapping 90-day windows give the cleanest story ("Q1 activity" vs "Q2 activity" vs …); the shared mapping file keeps `project_001` pointing at the same real project across every quarter.
- After 2 or more quarters, run `coverity-delta --archive-dir archive/ --output delta/latest`. As new quarters accumulate, re-run the same command — the report automatically grows a new data point in every trend chart.

##### 🎨 HTML polish

- All three top sections (**Projects**, **Active users**, **Stream activity**) follow the same rhythm: a tile-grid summary of the numeric change, then the line chart, then the detail lists. Reads consistently regardless of which metric you're looking at.
- **SVG hover tooltips** on every marker in every chart and sparkline — hover any data point and the browser shows `{label}: {value}` (e.g. `Q3/26: 4`) via a native `<title>` element. No JavaScript, no external tooltip library, no CSS animation — works in every browser.
- **Timeline metadata on added / dropped / newly active / went dark entries**. Each list item now carries `first_seen_index` / `last_seen_index` in `delta.json` (indices into `delta.snapshots`) and the HTML renders a compact tag next to each name:
  - **`joined Q2/26`** (blue) — project or stream joined mid-window and is still there at the end.
  - **`last seen Q3/26`** (blue) — was present at the start of the window, disappeared after Q3/26.
  - **`Q1/26 → Q3/26 (came & went)`** (yellow) — appeared and disappeared inside the window; the same entry deliberately shows in *both* the Added and Dropped lists so the timeline is honest.
- **"came & went" indicator in the Defects by project ranking column** for projects absent at both endpoints of the window (previously they silently reported rank Δ = 0, hiding the fact that they had been deleted). Complements the existing `new` / `dropped` / ▲ / ▼ / `0` indicators.

##### 🔧 Semantic fixes discovered during smoke-testing against a real 6-quarter archive

- **Added / dropped set diffs now use "ever appeared" semantic across the whole window**, not just first-vs-last endpoints. Concretely: `dropped = union(all snapshots) - last` (catches projects created and deleted between the endpoints) and `added = union(all snapshots) - first` (catches projects that entered at some point, whether or not they stayed). Symmetric — a project that appeared and disappeared mid-window shows in both lists, which is the honest reading. Same rule applied to the Stream activity `newly active` / `went dark` diffs. Regression test: `test_compute_projects_series_catches_added_and_dropped_mid_window`. Without this fix, the count-series line chart correctly showed the intermediate spike but the Dropped tile stayed at 0, because a plain `first - last` diff can't see a project that wasn't in the first snapshot to begin with.
- **Endpoint semantics on the Defects by project table**. `rank_first` / `rank_last` / `active_first` / `active_last` come from the *first snapshot slot* and *last snapshot slot* respectively (`None` if the project was absent at that endpoint), not from the first / last *observed* value in the series. A late-arriving project reports `rank_first = None` (drives HTML "new"); a project removed before the end reports `rank_last = None` (drives "dropped"); a project absent at *both* endpoints drives the new "came & went" indicator. Without this fix a project present only in a middle snapshot reported `rank_first = rank_last` = the middle-snapshot rank, and rank Δ = 0 — hiding the deletion completely. Regression test: `test_defects_by_project_series_endpoint_semantics_for_late_arrival_and_early_departure`.

##### 🧪 Test coverage
- 28 unit + end-to-end tests across `test_delta_metrics.py` (18 tests: diff primitives, `SnapshotLoader` including `order_key` fallback chain, `load_archive_dir` chronological ordering + rejection of empty / single-ZIP dirs, each `compute_*_series` function including per-project `None` slots for missing snapshots, the two new regression tests listed above, trend orchestration) and `test_delta_cli.py` (10 tests: 3-snapshot happy path, empty / single-ZIP / missing-dir errors, mid-archive instance / days / mapping mismatch hard-fails, `--allow-window-mismatch` escape hatch produces warning + `normalized_per_day`, matching-mapping happy path, `--labels` override).
- Existing `test_anonymizer.py` (12 tests) continues to pass — no changes to `anonymizer.py` needed for this feature.

### Version 1.1.3 - 2026-08-20

**Linux Binary Bundles Pristine OpenSSL 3.5.7 + zlib 1.3.2 Built From Source, PowerShell Quickstart Uses `Bypass`**

#### Changed

##### 🔐 Linux binary CI builds OpenSSL 3.5.7 and zlib 1.3.2 from source and bundles them via `LD_LIBRARY_PATH`
- Ubuntu 26.04's system OpenSSL is frozen at the string `libssl3 3.5.5` (Jan 2026 release); Canonical won't rev it, only backport patches within `3.5.5-*ubuntu*`. BDBA against the 1.1.2 Linux binary flagged this as behind upstream 3.5.7. Pinning the runner OS only moves as fast as Ubuntu's package-string cadence, so we now build the newer OpenSSL ourselves.
- New workflow step builds OpenSSL 3.5.7 from the official `openssl/openssl` release tarball into `$HOME/openssl-new` and prepends `$HOME/openssl-new/lib64:$HOME/openssl-new/lib` to `LD_LIBRARY_PATH`. PyInstaller resolves CPython's `_ssl.so` / `_hashlib.so` shared-library deps via `ldd`, which honors `LD_LIBRARY_PATH`, so the bundle picks up the freshly-built `libssl.so.3` / `libcrypto.so.3` instead of the runner's system ones. Kept within the 3.5.x line so the ABI stays compatible with the `_ssl.so` CPython 3.14 was compiled against.
- Same approach for zlib: the runner ships Debian's patched `1:1.3.dfsg+really1.3.1-1ubuntu3`, which some scanners flag against pristine upstream. Workflow now downloads and builds `zlib-1.3.2` from `zlib.net` into `$HOME/zlib-new` and prepends the lib dir to `LD_LIBRARY_PATH`. Bundle gets pristine upstream `libz.so.1` at an ABI-compatible soname.
- `OPENSSL_VER` / `ZLIB_VER` are declared as top-level `env` on the respective build steps so future bumps are a one-line diff — the inline comments point to the upstream sources.
- Verification steps confirm `python -c "import ssl; print(ssl.OPENSSL_VERSION)"` returns the new string and that `ldd` on `_ssl.so` / `zlib.so` resolves to the new lib dirs before PyInstaller runs.
- A "Diagnostic - identify libcrypto/libz sources" step runs first on Linux to log the pre-override paths, versions, and Ubuntu package strings — kept in-place so future BDBA deltas can be root-caused against the actual bundled artifact without reproducing the runner locally.

##### 🪟 Windows binary is unaffected
- Windows CPython bundles OpenSSL and zlib inside its own installer (`Python314\DLLs\libcrypto-3.dll`, `Python314\DLLs\libssl-3.dll`, `Python314\DLLs\zlib.dll`), which track CPython's own release cadence. No `LD_LIBRARY_PATH`-equivalent hack is needed on Windows because PyInstaller pulls those DLLs directly from the CPython install.

#### Fixed

##### 📝 `EXPORT_QUICKSTART.md` and `scripts/coverity-export.ps1` docs now recommend `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`
- `RemoteSigned` allows locally-authored scripts to run but still refuses scripts marked with the NTFS `Zone.Identifier` alternate data stream — which every script downloaded from the release page inherits. Users following the previous docs verbatim hit `File ... cannot be loaded. The file ... is not digitally signed.` and had no obvious fix in the quickstart.
- Both files now explain the two working paths — `Unblock-File .\coverity-export.ps1` to strip the zone marker on the single downloaded script, or use `Bypass` for the whole session — with `Bypass` shown as the default example because it's the one-liner that actually works out of the box for the "download and run" flow the quickstart describes.

### Version 1.1.2 - 2026-08-19

**Linux CI Runner Pinned to Ubuntu 26.04 — Bundled OpenSSL Bumped 3.0.13 → 3.5.x**

#### Changed

##### 🔐 Linux binary CI runner pinned to `ubuntu-26.04` so PyInstaller picks up the runner's newer OpenSSL
- `actions/setup-python@v6`'s Linux CPython 3.14 builds dynamically link to the runner's system OpenSSL. On `ubuntu-latest` → 24.04, that's OpenSSL 3.0.13 (Ubuntu 24.04's LTS-frozen 3.0.x line), which BDBA against the 1.1.1 Linux binary flagged as behind the current upstream 3.0.x / 3.4.x / 3.5.x lines.
- Ubuntu 26.04 (Resolute Rhino, still in preview on [actions/runner-images](https://github.com/actions/runner-images) at time of release) ships OpenSSL 3.5.x. Pinning `runs-on: ubuntu-26.04` for the Linux binary matrix entry moves the bundled `libcrypto` forward without any source-code change.
- Only the Linux binary build is pinned; the `publish-pypi` and `release` jobs stay on `ubuntu-latest` because they only run Python-level tooling.
- Cleanup path: once GitHub flips `ubuntu-latest` to point at 26.04 (expected once the preview is promoted to GA), revert the pin — the inline comment in `.github/workflows/build-binaries.yml` documents this.

##### 🪟 Windows binary is unaffected
- Windows CPython bundles its own OpenSSL from `Python314\DLLs\libcrypto-3.dll`, which tracks CPython's own release cadence and doesn't depend on the CI runner OS.

### Version 1.1.1 - 2026-08-19

**Further PyInstaller Excludes — Drops `libreadline` (GPL-3.0), `libuuid`, `liblzma`, `libtinfo`, `libncurses` From Linux Binary**

#### Changed

##### 📦 PyInstaller `excludes` extended to drop five more transitively-bundled CPython native extensions we never use
- `lzma` + `_lzma` (imported optionally by `pandas.io.common`, `numpy.lib._datasource`, `shutil`, `tarfile`, `zipfile` — all delayed/conditional/optional per PyInstaller's own warn file). We never handle `.xz` payloads.
- `readline` + `_curses` + `_curses_panel` (imported by `cmd` / `code` / `pdb` / `rlcompleter` for interactive REPL support). We never invoke a REPL from the CLI entry points.
- `_uuid` (imported by stdlib `uuid.py` inside a `try/except ImportError`). Stdlib `uuid` falls back to pure-Python UUID generation via `os.urandom`; all consumers in our binary (`pg8000.converters`, `pandas.core.reshape.merge`, `pandas.io.formats.style_render`, `_plotly_utils.basevalidators`, `plotly.io._html`) use `uuid.uuid4()` (random) which is unaffected by removing the C accelerator.

#### Notes on BDBA scan findings

**Additional findings resolved (Linux binary).** These come from CPython bundling native libraries alongside the affected stdlib C extensions on the manylinux CPython build; the accompanying `.cpython-*-linux-gnu.so` files no longer land in the bundle now that PyInstaller excludes the Python modules that would import them:

| Finding | Route into the 1.1.0 Linux binary | How 1.1.1 resolves it |
|---|---|---|
| `liblzma.so.5` | CPython `_lzma.cpython-*-linux-gnu.so` (via pandas / numpy / tarfile / zipfile) | Added `lzma` + `_lzma` to PyInstaller `excludes` |
| `libtinfo.so.6` | CPython `readline.cpython-*-linux-gnu.so` (via `_pyrepl`) → libreadline → libtinfo | Added `readline` + `_curses` + `_curses_panel` to PyInstaller `excludes` |
| `libncurses.so.6` | Same chain as libtinfo | Same excludes |
| **`libreadline.so.8` (GPL-3.0)** | CPython `readline.cpython-*-linux-gnu.so` | Same excludes — dropping this removes the strong-copyleft dependency |
| `libuuid.so.1` | CPython `_uuid.cpython-*-linux-gnu.so` (via pandas / pg8000 / plotly, all using `uuid.uuid4()`) | Added `_uuid` to PyInstaller `excludes` |

- The `libreadline.so.8` finding is worth calling out separately: `libreadline` is licensed **GPL-3.0**, which is strong copyleft, not the permissive licenses covering the other CPython-bundled natives. Excluding `readline` therefore carries actual licensing value beyond the BDBA cleanup, not just a scanner-metadata fix. `libncurses` / `libtinfo` are permissive (X11-like) but drop out for free as transitives of libreadline.
- **Windows binary**: none of the newly-excluded modules had Windows-side native-lib findings (Windows CPython doesn't ship `libreadline` / `libtinfo` / `libncurses` / `libuuid`, and `_lzma.pyd` didn't carry a separate BDBA entry), so Windows binary size is essentially unchanged (~40 MB). Linux binary drops noticeably — exact delta depends on the CPython manylinux artifact.
- No functional change. All five excluded stdlib modules are optional in every consumer's import path per PyInstaller's own annotation (`delayed`, `conditional`, `optional`).

### Version 1.1.0 - 2026-08-19

**Pure-Python Postgres Driver, Dead Deps Dropped, Standalone Binary Down 28%**

#### Changed

##### 🐘 Swapped `psycopg2-binary` → `pg8000` (pure-Python Postgres driver)
- `psycopg2-binary`'s Windows and Linux wheels bundle a full stack of native libraries (OpenSSL, libpq, MIT krb5, PCRE1, and their manylinux siblings) whose versions track whatever the psycopg2 maintainers built their manylinux base image against. Every BDBA report against the 1.0.28 Windows binary and the 1.0.29 Linux binary flagged the same wheel-bundled natives, and none of them were fixable at the project level without giving up the "no Python required on the target machine" property of the standalone binary.
- `pg8000` is a pure-Python driver — zero C extensions, zero bundled natives — that speaks the same DB-API 2.0 surface and the same `format` paramstyle (`%s`) as psycopg2. `config.json` schema is unchanged; the same `host` / `port` / `database` / `user` / `password` kwargs are accepted.
- Trade-off: pure-Python protocol handling is roughly 2–4× slower than libpq for large result sets. This project's workload is aggregation queries returning small result sets, so end-to-end dashboard / export / report runs are within a couple seconds of the psycopg2 baseline on the DB used for smoke-testing.
- Not compatible with GSSAPI / Kerberos authentication. If your Coverity Connect DB requires GSSAPI, pin `<= 1.0.29` and open an issue.
- Kills five of the seven BDBA findings against the 1.0.29 Linux binary (see BDBA notes below).

##### 🧹 Dropped three unused dependencies: `matplotlib`, `seaborn`, `openpyxl`
- Grep for `import matplotlib | pyplot | seaborn | openpyxl | to_excel` across `coverity_metrics/**/*.py` returned empty — all three were declared in `requirements.txt` / `pyproject.toml` for years without a single call site. Dashboard rendering happens via `plotly` (JavaScript, in-browser) and the exporter writes ZIPs of JSON, not `.xlsx`.
- Removing `matplotlib` also removes `Pillow` as a transitive, which kills the `libtiff` finding from the 1.0.29 Windows BDBA report.

##### 📦 PyInstaller build now excludes stdlib modules pulled in transitively but never used
- Added `sqlite3` + `_sqlite3` to the `excludes` list (`pandas.io.sql` delay-imports them; we never call `pd.read_sql` / `pd.to_sql`). Drops `sqlite3.dll` and `_sqlite3.pyd` from the bundle.
- Added `pyexpat` + `_elementtree` to the `excludes` list (`pandas.io.xml` / `pandas.io.formats.xml` import them; we never call `pd.read_xml` / `DataFrame.to_xml`). Drops `pyexpat.pyd` and `_elementtree.pyd` from the bundle.
- Removed the `matplotlib.backends.backend_agg` hidden-import; the full `matplotlib` / `PIL` / `seaborn` / `openpyxl` packages are added to `excludes` as belt-and-suspenders.
- The `pandas.io.sql` / `pandas.io.xml` shim modules stay bundled — `pandas.io.api` hard-imports them and pandas won't load otherwise. They fall through to raising at call time if anything ever tries to actually use them.

##### 📉 Standalone binary size: ~57 MB → ~40 MB (Windows, x86_64), a 28% reduction
- Combined effect of the psycopg2 → pg8000 swap, the three deleted deps, and the PyInstaller exclude list. Linux binary tracks similarly.

#### Fixed

##### 🔧 pg8000 compat: 29 `INTERVAL '%s <unit>'` SQL sites rewritten so parameters land outside the string literal
- Unlike psycopg2, pg8000's `format` paramstyle does not substitute `%s` inside single-quoted SQL string literals. The 29 date-range queries in `coverity_metrics/metrics.py` that used `CURRENT_DATE - INTERVAL '%s days'` (or `'%s weeks'`) were sending the literal `%s` to Postgres and failing with `invalid input syntax for type interval: "%s days"`. `execute_query_dict` caught the exception and returned `[]`, so the dashboard silently rendered zero for every affected metric on the first pg8000 build.
- All 29 sites rewritten to `INTERVAL '1 day' * %s` (and two `INTERVAL '1 week' * %s`), which sends the integer as a proper bound parameter and multiplies against a constant interval. Same execution plan, same numeric result, driver-agnostic.

##### 🔧 pg8000 compat: `db_connection` wrapper now coerces `None` params to `()` before calling `cursor.execute`
- psycopg2 tolerated `cursor.execute(query, None)`; pg8000's `Cursor.execute(operation, args=())` calls `len(args)` internally and raises `object of type 'NoneType' has no len()` on `None`. Both `execute_query` and `execute_query_dict` in `coverity_metrics/db_connection.py` now pass `params or ()` so callers can keep the historical `execute_query(query)` no-params style.

##### 🔧 pg8000 compat: `CoverityDatabase` no longer relies on `psycopg2.connection.closed`
- `pg8000.dbapi.Connection` has no `.closed` attribute (psycopg2's is a driver-specific extension, not part of DB-API 2.0). Replaced the `self.connection.closed` sentinel with a `self.connection is None` check plus a `try/finally` that nulls out the handle in `close()`, giving equivalent semantics for this project's single-connection-per-instance usage pattern with no driver-specific coupling.

##### 🔧 `ZipDataLoader.get_overall_summary()` now accepts the `days=` kwarg for API parity with `CoverityMetrics`
- Every other `metrics.get_*(days=days)` call in `dashboard.py` had a matching kwarg-accepting override on `ZipDataLoader`; `get_overall_summary()` was the one missing signature. Loading a dashboard from a `--zip-file` crashed with `TypeError: ZipDataLoader.get_overall_summary() got an unexpected keyword argument 'days'` on the first pg8000 build. The kwarg is now accepted and ignored — zip data is pre-aggregated at export time so a re-filter isn't possible or meaningful at load time.

#### Notes on BDBA scan findings

**Resolved by the 1.1.0 refactor.** These were tracked as "no action available" in the 1.0.28 and 1.0.29 notes and are now gone from the binary entirely:

| Finding | Route it took into 1.0.29 binary | How 1.1.0 resolves it |
|---|---|---|
| openssl (`libcrypto-3-x64-*.dll`, `libssl-3-x64-*.dll`, `.so` equivalents) | `psycopg2-binary` wheel | Driver swap → `pg8000` (pure Python, no OpenSSL binding) |
| libpq (`libpq-*.dll` / `.so`) | `psycopg2-binary` wheel | Driver swap → `pg8000` (speaks Postgres wire protocol directly) |
| libpcre PCRE1 (`libpcre-*.so.1.2.0`) | `psycopg2-binary` Linux wheel | Driver swap → `pg8000` |
| krb5 (`libgssapi_krb5.so.2`, `libkrb5.so.3`, `libk5crypto.so.3`, `libkrb5support.so.0`) | `psycopg2-binary` Linux wheel | Driver swap → `pg8000` |
| libtiff (`PIL/_imaging.cp314-win_amd64.pyd`) | `Pillow` wheel, transitively via `matplotlib` | `matplotlib` dropped from deps → `Pillow` no longer transitively pulled in |
| `sqlite3.dll` / `_sqlite3.pyd` | CPython, transitively via `pandas.io.sql` | Added `sqlite3` + `_sqlite3` to PyInstaller `excludes` |
| `pyexpat.pyd` | CPython, transitively via `pandas.io.xml` | Added `pyexpat` + `_elementtree` to PyInstaller `excludes` |

**Still upstream-only (no action available at project level).** These come from CPython itself and from the numpy/pandas wheels via pandas, which is still a hard runtime dependency:

| Finding | Bundling package | Our version | Newest upstream artifact |
|---|---|---|---|
| `libscipy_openblas64_-*.dll` (OpenBLAS) | `numpy` wheel (shared with SciPy since NumPy 2.0) | Latest on PyPI | Latest on PyPI |
| `VCRUNTIME140.dll` / `VCRUNTIME140_1.dll` | CPython 3.14.x | Latest patch | Latest patch |
| `msvcp140-*.dll` | `numpy` + `pandas` wheels | Latest on PyPI | Latest on PyPI |

- **On the OpenBLAS finding specifically**: BDBA labels the DLL as "proprietary" — that is a scanner metadata error. OpenBLAS is [BSD-3-Clause licensed](https://github.com/OpenMathLib/OpenBLAS/blob/develop/LICENSE) and freely redistributable; it is the same OpenBLAS binary shipped by every scientific Python distribution and by Anaconda. Since NumPy 2.0 the wheels reuse SciPy's pre-built OpenBLAS artifact (hence the `libscipy_` prefix). It backs `numpy.linalg`, `numpy.fft`, and the random-number generators; numpy loads it unconditionally at package init, so it cannot be excluded without breaking `import pandas`.
- **On the Visual C++ runtime findings**: standard Microsoft VC++ redistributable DLLs required by every Python C extension on Windows and by CPython itself. Covered by Microsoft's [Visual C++ Redistributable license](https://learn.microsoft.com/en-us/cpp/windows/redistributing-the-latest-supported-visual-c-runtime), which explicitly allows free redistribution with your application. They ship with CPython, with every C-extension wheel on PyPI, and cannot be excluded — the binary won't start without them.
- All three refresh naturally when NumPy, pandas, or CPython publish new artifacts.

### Version 1.0.29 - 2026-08-19

**Local Binary Build Matches CI (Python 3.14)**

#### Changed

##### Local `.binbuild` venv now documented as Python 3.14 to match CI
- `.github/workflows/build-binaries.yml` builds the released `coverity-metrics.exe` / `coverity-metrics` on Python 3.14, but `packaging/README.md` still told maintainers to create the local `.binbuild` venv with `py -3.12` / `python3.12`. Locally-built binaries therefore embedded a different CPython (and older bundled sqlite / expat / OpenSSL surface) than the artifacts CI publishes to the GitHub Release.
- `packaging/README.md` now uses `py -3.14 -m venv .binbuild` (Windows) and `python3.14 -m venv .binbuild` (Linux) so the local reproduction matches CI exactly.
- No source-code change — CI-produced binaries are unaffected. Only maintainers rebuilding locally are impacted.

#### Notes on BDBA scan findings against the 1.0.28 Windows binary (no action required)

The BDBA report flagged five bundled native libraries as behind their upstream latest. All five are inside third-party binary artifacts we consume, and each is already at the newest available version:

| Native lib | Bundled by | Our version | Newest upstream artifact |
|---|---|---|---|
| openssl (`libcrypto-3`, `libssl-3`) | `psycopg2-binary` wheel | 2.9.12 | 2.9.12 (latest on PyPI) |
| libpq (postgresql client) | `psycopg2-binary` wheel | 2.9.12 | 2.9.12 (latest on PyPI) |
| libtiff (`PIL/_imaging`) | `Pillow` wheel | 12.3.0 | 12.3.0 (latest on PyPI) |
| `sqlite3.dll` | CPython itself | 3.14.7 | 3.14.7 (latest patch) |
| `pyexpat.pyd` (expat) | CPython itself | 3.14.7 | 3.14.7 (latest patch) |

The deltas will refresh naturally once `psycopg2-binary`, `Pillow`, or CPython publish new artifacts with newer vendored natives. No project-level change can accelerate this without giving up the "no Python required on the target machine" property of the standalone binary. The report's "OpenSSL 4.0.1" latest-version claim is a scanner metadata error — OpenSSL's current stable line is still 3.x. The findings are being tracked as upstream-only in BDBA.

### Version 1.0.28 - 2026-08-18

**Stale-LDS Fallback Now Detects Fixed-Then-Reappeared Defects, Matching Coverity Connect Exactly**

#### Fixed

##### 🔁 Fallback under-counted Active by ~5% on stale-LDS installs because `fixed_snapshot_element_id` isn't cleared on reappearance
- 1.0.27's fallback (`Active iff fixed_snapshot_element_id IS NULL`) correctly classified the vast majority of defects on stale-LDS installs but missed every defect that had been fixed and later re-detected: Coverity's own UI would still show them as Active, but the tool marked them Fixed. Concrete example on the DB used in the 1.0.27 note: the affected stream on `example-project-b` reported 15 unclassified Active by the 1.0.27 rule; Coverity Connect's UI showed 20. The 5 missing defects had all been fixed at snapshot ~40200 and reappeared at snapshot ~100550, and `fixed_snapshot_element_id` never got cleared on the reappearance.
- Fix — add a second disjunct on `stream_defect.introduced_snapshot_element_id`:
  - **Active iff `fixed_snapshot_element_id IS NULL` OR `introduced_snapshot_element_id > fixed_snapshot_element_id`**
  - **Fixed iff `fixed_snapshot_element_id IS NOT NULL` AND (`introduced_snapshot_element_id IS NULL` OR `introduced_snapshot_element_id <= fixed_snapshot_element_id`)**
  - Coverity DOES update `introduced_snapshot_element_id` when it re-detects a previously-fixed defect (unlike `fixed_snapshot_element_id`, which it leaves alone), so comparing the two `snapshot_element` ids — which are monotonic on Coverity's DB — identifies the reappeared cases exactly. No new joins were needed; the comparison is between two columns already on `stream_defect`.
  - Preferred (LDS-populated) branch is unchanged — fully-fresh streams stay on strict `lds.detected_snapshot_id = sn_latest.latest_snap_id` from 1.0.25 / 1.0.26 / 1.0.27. Only the fallback path changed; every call site inherits the fix because all 60+ queries embed the same three shared constants.
- Verified on the affected DB: the stale-LDS stream on `example-project-b` went from 15 unclassified Active → 20 (matching UI); `example-project-b` project total went from 35 → 40 (also matching UI). `example-project-a` (fully-fresh LDS) is unchanged.

### Version 1.0.27 - 2026-08-18

**Active / Fixed Counts Fall Back Gracefully When `last_detected_snapshot` Is Stale**

#### Fixed

##### 🔁 Active and Fixed reported 0 on Coverity installs where `last_detected_snapshot` had stopped being maintained
- Some Coverity Connect installs stop updating the `last_detected_snapshot` (LDS) table after an upgrade or migration: every snapshot committed after that point gets zero LDS coverage. Because 1.0.25 anchored Active/Fixed strictly on LDS (rows without an LDS entry were treated as *unknown* rather than active), those installs saw **Active = 0 and Fixed = 0** on every affected stream while Coverity Connect's UI kept showing correct outstanding counts.
- Concrete example on a two-project DB: `example-project-a` snapshots (up to id 40207) all had LDS rows; `example-project-b` snapshots (id 70379+) had **none**. The tool reported 0 / 0 for `example-project-b`'s 5300 stream_defect rows.
- Fix — per-row fallback anchored on the same signals Coverity Connect uses:
  - `_ACTIVE_COND_SQL` / `_FIXED_COND_SQL` are now CASE expressions. When a defect has an LDS row, the strict rule from 1.0.25 fires (Active iff `lds.detected_snapshot_id = sn_latest.latest_snap_id`, Fixed iff it points at an earlier snapshot). When it doesn't, the CASE falls back to `stream_defect.fixed_snapshot_element_id` (Active iff NULL, Fixed iff NOT NULL).
  - The extremes match a healthy Coverity install: fully-fresh streams stay on strict LDS everywhere (no behaviour change vs 1.0.25 / 1.0.26); fully-stale streams use `fixed_snapshot_element_id` everywhere. The mixed case — a stream in transition where LDS is only partially populated — no longer drops the un-indexed tail from both buckets.
  - Every existing call site inherits the fix because all 60+ queries embed the same three shared constants.
- The fallback column can be ~5% off when Coverity re-detects a previously-fixed defect (Coverity doesn't clear `fixed_snapshot_element_id` in that case) — that's the exact reason 1.0.25 moved away from it in the first place. The per-row design keeps that caveat contained to LDS-missing rows only; whenever LDS is populated for a defect the strict LDS rule wins, so a defect that was fixed then re-detected is correctly counted as Active as soon as Coverity Connect records the reappearance in LDS. (1.0.28 closes this caveat entirely via `introduced_snapshot_element_id`.)
- New `_check_lds_freshness()` probe: runs once per DB signature `(host, port, database, user)` per process, populates `self._lds_stale_streams`, and logs a single WARNING naming the affected streams so silent under-counting can be diagnosed. The probe result is cached in class-level `_LDS_FRESHNESS_CACHE` / `_LDS_WARNING_EMITTED`, so `dashboard`/`export` worker pools that instantiate many `CoverityMetrics` against the same DB pay for it exactly once and don't emit duplicate warnings.

### Version 1.0.26 - 2026-08-17

**Overview Cards Now Agree With Each Other, on a Per-Stream Basis**

#### Fixed

##### ⚖️ Active Defects, Defects by Severity, High Severity, and Defects by Project All Use the Same Per-Stream Count
- The 1.0.25 fix that added `COUNT(DISTINCT COALESCE(sd.merged_defect_id, sd.id))` to `get_defects_by_severity` inadvertently made it disagree with the Active Defects card (still `COUNT(DISTINCT sd.id)`) whenever a project had multiple streams sharing defects — e.g. an `example-project` with two mirror streams (21 active defects each; merge-deduped project total 21, per-stream total 42). The two cards on the Overview tab could show very different numbers for the same project.
- After weighing both approaches, the per-stream sum is the intended one: each stream is analyzed and reported independently, and its active defects count towards the project total once per stream. So a project with two streams that both have 21 active defects reports 42, not 21.
- Reverted the merge-defect deduplication introduced in 1.0.25 across every Overview count so they all use `COUNT(DISTINCT sd.id)` (each `stream_defect` row counted once): `get_overall_summary`'s `total_defects` and `high_severity_defects` (both project-scoped and global branches), `get_defects_by_severity`, and `get_total_defects_by_project`'s `defect_count` / `active_defects` / `fixed_defects` / `dismissed_defects` (all three project-scope branches).
- All queries still exclude classifications `False Positive` and `Intentional`, so the identity `sum(defects_by_severity) == total_defects == high_severity + medium + low + unspecified` holds and matches the sum of the per-stream active counts shown in the `Defects by Project` / stream drill-down table.
- Active Defects tooltip updated to state the per-stream semantics explicitly.

##### 🧾 Code Metrics by Stream Reported an Inflated `Files` Column and a Near-Zero Avg File LOC
- Each `stream_element` accumulates its `stream_file` rows for the entire life of the stream: files that no longer exist in the codebase stay as rows but have all `current_*_line_count` columns zeroed. `COUNT(DISTINCT sf.id)` therefore counted every file that has ever been part of the stream, and `AVG(current_code_line_count)` was diluted by thousands of zero-LOC historical rows. Concrete example on a single stream of an `example-project`: the Code Metrics table showed **11 214 Files** with an avg-file-LOC of **~0.4** while Coverity Connect shows 30 files and 149.5 LOC/file.
- The SUMs (`total_loc`, `total_comment_lines`, `total_blank_lines`) and `comment_ratio_pct` were already correct — zero rows contribute 0 to a SUM, and the ratio is between two such SUMs.
- Added a WHERE filter that requires at least one of `current_code_line_count` / `current_comment_line_count` / `current_blank_line_count` to be > 0 so aggregates count only the files currently present in the stream. `file_count` and `avg_file_loc` now match Coverity Connect's per-stream figures; nothing else changes.

##### 🏷️ Triage Classification by Stream Was Hiding False Positive and Intentional Buckets
- `get_triage_trends` (which powers the *Triage Classification by Stream* chart) explicitly excluded `False Positive` and `Intentional`, so streams with those classifications showed only `Bug` and `Unclassified`. Concrete example on an `example-project`: the project has 2 Intentional-classified defects that never appeared on the chart.
- Removed the `NOT IN ('False Positive','Intentional')` filter and updated the docstring — the metric now shows every triage bucket Coverity Connect displays (Bug, False Positive, Intentional, Pending, Untriaged, …) plus the `Unclassified` bucket for defects that have no triage row yet. The primary ordering by unclassified-count-per-stream is unchanged, so streams needing triage attention still surface at the top.

##### 🧭 Dashboard Back-Navigation Went Straight to the Aggregated View From Every Level
- Both instance-level and project-level dashboards rendered a single *"Back to All Instances"* button pointing at `../dashboard_aggregated.html`. On a project page that skipped the instance dashboard entirely; on single-instance deployments (where no aggregated dashboard is generated) the same button still rendered on the project page and 404'd.
- The button now renders only on the instance-level dashboard, and only when an aggregated dashboard actually exists (guarded by `has_aggregated_dashboard`). Project pages already have a *"Show All"* control next to the project filter for returning to the instance dashboard, so no separate back button is needed there. Single-instance runs correctly render no back button on the instance page either.

##### 📁 Total Files / Lines of Code / Functions Were Reporting Cumulative History Instead of Current Codebase Size
- `get_overall_summary`'s `total_files`, `total_functions`, and `total_loc` queries all counted/summed over `stream_file` and `stream_function` joined through `stream_element`. Because `stream_element` rows are created per snapshot and both child tables attach to a specific `stream_element`, the counts effectively summed every historical snapshot's file / function / LOC records in scope. Concrete example on an `example-project` (2 streams × ~30 files each in the latest snapshot): Coverity Connect's UI shows Total Files = 60, the dashboard was showing 11 244; the same inflation applied to `total_loc` and `total_functions`.
- All three now use the per-snapshot aggregates on the `snapshot` table — `total_file_count`, `function_count`, and `code_line_count` — taken from the latest non-deleted snapshot per stream. These are the exact numbers Coverity Connect displays. Optionally restricted to snapshots committed within the `--days` trend window; streams with no analysis in that window contribute 0. When `days` is not supplied (e.g. the `coverity-metrics` console report) the fallback is "latest non-deleted snapshot per stream regardless of age", which is also correct. Negative sentinel values in `snapshot.code_line_count` are clamped to 0 the same way as elsewhere in the codebase.
- `get_overall_summary` now accepts an optional `days` argument. `coverity-dashboard` and `coverity-export` forward the CLI's `--days` value so ZIP exports carry the windowed numbers and offline dashboards agree with the live-database output.
- The Overview tab's "Total Files", "Lines of Code", and "Functions" tooltips now describe the new semantics and cite the active trend window via `trend_period_text`.

#### Changed

##### ℹ️ Overview → Active Defects Tooltip Clarified
- Previous wording claimed the count excluded "dismissed" defects, but the query only filters classifications `False Positive` and `Intentional` — dismissive triage *actions* such as `Ignore` are **not** filtered. Tooltip now says so explicitly and describes the underlying "still detected in the latest snapshot of each stream" definition. No metric values changed.

### Version 1.0.25 - 2026-08-14

**Active / Fixed Defect Counts Now Match Coverity Connect's UI**

#### Added

##### 🛟 Active / Fixed Defect Counts Anchored on Coverity Connect's Snapshot Aggregates
- The lds-based path over-counted Active whenever `last_detected_snapshot` was empty for some rows (previously-eliminated defects fell through the `IS NULL` branch and got counted as Active). Concrete example from a real run: on `example-project` the latest snapshot had `total_defect_count = 83522` and `newly_eliminated = 12`, but the dashboard reported Active = 83534 (the tool was counting the 12 eliminated defects too).
- `get_total_defects_by_project` now uses `snapshot.total_defect_count` on the latest non-deleted snapshot per stream — the exact same figure Coverity Connect's own UI shows in its "Outstanding" column — and clamps it to `defect_count - dismissed_defects` so Active never exceeds the pool of non-dismissed defects. Fixed is then derived as `defect_count - Active - Dismissed`.
- Works whether `last_detected_snapshot` is populated or not. Healthy databases where the lds-based and snapshot-aggregate paths already agree are a no-op.

#### Fixed

##### ⚖️ Active / Fixed / High-Severity Counts Didn't Match Coverity Connect's UI on Multi-Stream Projects
- Two independent bugs compounded on projects where the same defect appears under multiple streams (e.g. two mirror streams within the same project):
  1. The "active" predicate was flipped around a few times while chasing an unrelated `last_detected_snapshot` symptom, at one point inflating Active by pulling in previously-eliminated defects.
  2. Every defect-count query used `COUNT(DISTINCT sd.id)`, which counted the same defect once per stream instead of once per merged defect — so a mirror stream doubled the number.
- Concrete example on an `example-project`: Coverity Connect shows 21 active defects (3 High / 2 Medium / 16 Low by Impact), the tool was reporting 12 High.
- Fix: `_ACTIVE_COND_SQL` is back to the strict `lds.detected_snapshot_id = sn_latest.latest_snap_id` (rows without a `last_detected_snapshot` entry are treated as *unknown* and fall through both buckets), and every affected count — `get_total_defects_by_project`, `get_defects_by_severity`, `high_severity_defects` — now counts `DISTINCT COALESCE(sd.merged_defect_id, sd.id)` so a defect present in multiple streams is counted once, matching Coverity Connect's project-level UI. `get_defects_by_severity` continues to bucket by `checker_properties.impact` (what Coverity Connect surfaces as "Severity"). Verified on the `example-project`: 3 High / 2 Medium / 16 Low = 21.

##### � Function Complexity Distribution and Most Complex Functions Joined on the Wrong Ids
- Both metrics used `JOIN function_metrics fm ON sf.function_id = fm.id` (or `f.id = fm.id`). Neither `stream_function.function_id` nor `function.id` is a foreign key to `function_metrics.id` — the two id spaces just happen to overlap for a small subset of rows. Concrete example: on `example-project` the tool was reporting **185** functions with complexity metrics when Coverity Connect's latest snapshot shows **21,153**.
- The correct chain in Coverity's schema is `stream_function → function_instance → function_metrics`. `function_instance` records per-snapshot-range metric revisions and is FK-linked to both sides; `function_instance.snapshot_end_id IS NULL` selects instances present in the latest snapshot, and `MAX(complexity)` deduped by `sf.id` handles the rare case where a stream_function has multiple current instances. Verified on `example-project`: 21,153 functions total (19263 Low / 1089 Moderate / 513 High / 246 Very High / 42 Extreme) — matching Coverity Connect exactly.

##### �🧮 Total Lines of Code No Longer Reports a Negative Number
- Coverity Connect uses negative sentinel values (typically `-1`) in `stream_file.current_code_line_count`, `current_comment_line_count`, `current_blank_line_count`, and `snapshot.code_line_count` for files / snapshots where line counting couldn't be done — binary files, generated code, parse failures, etc. On projects with enough such files the sentinels dragged the SUM below zero, so the dashboard's "Total Lines of Code" card and the underlying `total_loc` metric would render as a negative number.
- Every aggregation over those columns now uses `SUM(GREATEST(COALESCE(x, 0), 0))` (and the per-file / per-snapshot readouts use `GREATEST(COALESCE(x, 0), 0)`), so sentinels contribute zero instead of a negative delta. The clamp propagates through the downstream `defects_per_kloc`, `avg_file_loc`, and `comment_ratio_pct` figures too, since they reuse the same aggregate.

### Version 1.0.24 - 2026-08-13

**`--config` Passthrough, TLS Escape Hatches, `--workers` Passthrough, and a Single-Instance Auto-Mode Fix**

#### Fixed

##### 🐞 `coverity-dashboard` Single-Instance Auto Mode No Longer Crashes on `None` Config Path
- When `--config` was not passed (default `config.json` auto-fallback or env-var mode) and a single instance was configured, the auto-generated aggregated dashboard step called `MultiInstanceMetrics(args.config)` with `args.config = None`, which crashed inside `os.path.exists` with `TypeError: _path_exists: path should be string, bytes, os.PathLike or integer, not NoneType`.
- The single-instance auto-mode path now uses the resolved config path (same one used by the multi-instance branch). The aggregated cross-instance dashboard is also correctly skipped when `aggregated_view.enabled` is `false` (or the section is absent), and is always skipped in env-var mode. The dashboard count line no longer promises `1 aggregated` when none will actually be generated.

#### Added

##### 🗄️ `--config` / `-Config` Passthrough on the Quickstart Scripts
- Both quickstart scripts now accept `--config FILE` (bash) / `-Config FILE` (PowerShell) to run against an existing `config.json` instead of the `COVERITY_DB_*` environment-variable block.
- When `--config` is passed the placeholder-password guard is skipped (since credentials come from the file), and the path is forwarded to the binary as `--config <path>`. Multi-instance configuration is supported this way.
- The pre-run banner now includes a `Config : <path>` (or `Config : <env vars>`) line so the mode is unambiguous.

##### 🔒 TLS Escape Hatches on the Quickstart Scripts
- Fixes the common `curl: (60) SSL certificate problem: unable to get local issuer certificate` error on hosts behind SSL-inspection proxies or with an outdated CA bundle.
- [scripts/coverity-export.sh](scripts/coverity-export.sh): new `--cacert PATH` flag (or `CURL_CA_BUNDLE` / `SSL_CERT_FILE` environment variable) forwards a trusted CA bundle to every curl call. New `--insecure` flag adds `curl -k` as a last-resort escape hatch, with a warning printed at startup.
- [scripts/coverity-export.ps1](scripts/coverity-export.ps1): new `-Insecure` switch installs a per-run `ServerCertificateValidationCallback` for the script's `Invoke-RestMethod` / `Invoke-WebRequest` calls, with a warning; nothing outside the script is affected.
- Both TLS options apply only to the GitHub API tag lookup and the binary download — they don't touch the Postgres connection or anything downstream.

##### ⚡ `--workers` / `-Workers` Passthrough on the Quickstart Scripts
- [scripts/coverity-export.sh](scripts/coverity-export.sh) gains a `--workers N` flag; [scripts/coverity-export.ps1](scripts/coverity-export.ps1) gains a `-Workers N` parameter. Both default to `1` (matching the underlying tool) and are forwarded verbatim as `--workers N` to the binary.
- The binary still clamps to 1..8; each worker opens its own Postgres connection so 4–6 typically gives a 4–6× speed-up on large exports.
- The banner printed before the run now includes a `Workers : N` line so it's clear what was passed.

### Version 1.0.23 - 2026-08-13

**Quiet-by-Default Output for `coverity-export`**

#### Added

##### 🔇 Suppress Per-Metric `[SKIP] … No data` Lines by Default
- On large deployments (hundreds of projects) the per-metric `[SKIP] project/metric: No data` lines were burying the useful log output under thousands of lines of noise. Those lines are now suppressed by default.
- A one-line summary is printed at the end of the run instead: `[INFO] Skipped N metrics with no data across M project(s). Pass --verbose to see per-metric details.`
- New `--verbose` / `-v` flag on `coverity-export` restores the previous per-metric logging when you actually want it.
- `[ERROR]` and `[WARNING]` lines are always shown so real problems remain visible.
- Quickstart scripts pass through: `--verbose` on `coverity-export.sh`, and PowerShell's built-in `-Verbose` common parameter on `coverity-export.ps1`.

### Version 1.0.22 - 2026-08-13

**Quickstart Scripts and Env-Var Config for `coverity-export` and `coverity-dashboard`**

#### Added

##### 🚀 Quickstart Scripts for Linux and Windows End Users
- New [scripts/coverity-export.sh](scripts/coverity-export.sh) (bash) and [scripts/coverity-export.ps1](scripts/coverity-export.ps1) (PowerShell) turn "run an export" into a one-shot command for users who don't want to install Python.
- The scripts download the coverity-metrics standalone binary for the requested (or latest) release from GitHub, set the `COVERITY_DB_*` environment variables — with placeholder values users edit at the top of each script — and then run `coverity-metrics export`.
- Flags mirror the underlying CLI: `--tag vX.Y.Z` (default: latest, resolved from the GitHub API), `--output`, `--days`, `--project`, `--anonymize`, `--no-snapshots`, `--no-leaderboards`.
- A guardrail refuses to run while `COVERITY_DB_PASSWORD` is still the placeholder value `change-me`, so nobody triggers a real export with an unedited copy of the script.
- The downloaded binary is cached under `./bin/` next to the script (override with `BIN_DIR` / `-BinDir`), so repeat runs skip the download.

##### 🔐 `coverity-export` and `coverity-dashboard` Read Single-Instance Config from Environment Variables
- When `--config` is not passed (and `--zip-file` is not passed for the dashboard), both tools now look for the connection details in environment variables and run against that instance — no config file, no extra flag needed. Handy for CI pipelines and containers.
- Required env vars: `COVERITY_DB_HOST`, `COVERITY_DB_NAME`, `COVERITY_DB_USER`, `COVERITY_DB_PASSWORD`. Optional: `COVERITY_DB_PORT` (default `5432`), `COVERITY_INSTANCE_NAME` (default `Coverity`).
- Precedence at startup: (1) explicit `--config <file>`; (2) env vars if all required are set (single-instance, prints an `[INFO]` line); (3) a `config.json` in the current directory (backward-compatible auto-fallback); (4) otherwise exits with guidance listing both options.
- Multi-instance configuration is still supported via `--config`; env-var mode is single-instance only.
- ZIP mode (`--zip-file`) for `coverity-dashboard` is unchanged — it never required DB credentials.
- `coverity-metrics` (the console report CLI) is unchanged — it still requires `config.json`.

### Version 1.0.21 - 2026-08-13

**Release Automation — PyPI + GitHub Release from a Single Tag Push**

#### Added

##### 📦 PyPI Publishing from GitHub Actions
- New `publish-pypi` job in `.github/workflows/build-binaries.yml` builds `sdist` + `wheel` and uploads to PyPI whenever a `v*` tag is pushed. PyPI and the GitHub Release now go live at the same version at the same time.
- Uses PyPI **Trusted Publishing (OIDC)** by default — no long-lived token stored in the repo. Falls back automatically to a `PYPI_API_TOKEN` repository secret if one is configured. Runs under a GitHub `pypi` environment so the publish can optionally be gated behind required reviewers.
- A guardrail step verifies that the pushed tag (`v1.2.3`) matches `coverity_metrics/__version__.py` (`1.2.3`) and fails the workflow if they diverge.

##### 📝 CHANGELOG-driven GitHub Release Body
- The `release` job now slices the `## [<version>]` section out of `CHANGELOG.md` with `awk` and passes it as `body_path` to `softprops/action-gh-release`. Release notes always mirror the CHANGELOG.
- Auto-generated "What's Changed" (PR / commit list since the previous tag) is still appended below the CHANGELOG excerpt via `generate_release_notes: true`.
- Falls back to a generic body with a workflow warning if no matching CHANGELOG entry is found.

#### Changed

##### 🪚 `release.ps1` — Simplified to "Bump + Docs + Tag"
- The local script no longer builds wheels, uploads to PyPI, verifies installs in a temp venv, or calls the GitHub Releases API. All of that is now done by GitHub Actions on tag push.
- New responsibilities:
  1. Bump `coverity_metrics/__version__.py` (`-Part patch|minor|major` or explicit `-NewVersion`).
  2. Refresh dates in `CHANGELOG.md` / `RELEASE_NOTES.md`.
  3. `git add` those files, commit with `Release v<version>`, push the current branch.
  4. Create and push the annotated `v<version>` tag that triggers the CI release workflow.
- Aborts by default if the working tree is dirty (`-AllowDirty` overrides). Tolerates "nothing to commit" so re-runs for the same version don't error out. `-DryRun` previews every git command as well.
- New / renamed flags: `-Remote` (default `origin`), `-Branch` (default = current HEAD), `-CommitMessage`, `-SkipCommit`, `-SkipTag`, `-AllowDirty`.
- Removed flags (no longer needed): `-Repository`, `-NoUpload`, `-NoInstallTest`, `-SkipBuild`, `-SkipToolsUpgrade`, `-PipArgs`, `-NoIsolation`, `-Offline`, `-FindLinks`, `-TwineUsername`, `-TwinePassword`, `-CreateGitHubRelease`, `-GitHubRepo`, `-GitHubToken`, `-SkipGitTag`, `-ReleaseNotesPath`.

##### ⏱ `release` Job Now Waits on PyPI Publish
- The GitHub Release job depends on both `build` and `publish-pypi` (`needs: [build, publish-pypi]`), so the GitHub Release page (with attached Windows / Linux binaries) only appears after PyPI has accepted the upload. Same tag → same version live on PyPI and GitHub simultaneously.

### Version 1.0.20 - 2026-08-11

**Release Update**

#### Features
- Added `fetch_all` parameter to metrics methods for complete data retrieval
- Enhanced documentation with CLI parameter reference tables

#### Improvements
- Updated README with comprehensive parameter documentation
- Improved Python library usage examples

### Version 1.0.19 - 2026-08-06

**Sortable Instance-level Defects Table & Release Script CLI-verify Fix**

#### Added

##### ↕ Sortable Columns on the Instance-level "Defects by Project" Table
- Column headers on the instance-level **Defects by Project** table (also **Defects by Stream** on project dashboards) are now clickable
- Each header displays a `▲▼` glyph; clicking toggles ascending / descending order and re-appends the rows in place
- Uses the existing generic `sortTable(columnIndex, tableId, dataType)` helper — Project/Stream Name sorts as text (`localeCompare`), Total Defects / Active / Fixed sort numerically (digits extracted from the badge text)
- No re-export needed — the change is purely in the dashboard template

#### Fixed

##### 🛠 `release.ps1` — Post-Install CLI Verification No Longer Fails on Quoted Paths
- Symptom: the final `Verifying coverity-dashboard CLI...` step in `release.ps1` failed with `'"...\coverity-dashboard.exe"' is not recognized as an internal or external command`, even though the venv was created and the .exe existed at that path
- Root cause: `Invoke-Step` runs every command through `cmd.exe /c $Command`. When the command starts with a quoted path and has trailing arguments (`"C:\...\coverity-dashboard.exe" --help`), cmd.exe's quote-stripping rules can leave the outer quotes attached to the executable name, especially when the venv fell back to the timestamped `.pkgtest_<timestamp>` path (e.g. because the original `.pkgtest` was locked)
- Fix: the two CLI verification calls at the end of `release.ps1` now invoke the .exe directly via PowerShell's `&` operator instead of routing through `cmd.exe`. Exit codes are still checked and any non-zero result throws with a clear message
- Impact: no user-visible impact on the produced release (upload / tag / GitHub release all happen earlier in the script). This just keeps the verification step from producing a spurious failure at the end of an otherwise-successful publish

### Version 1.0.18 - 2026-08-04

**Daily Fix Efficiency % Correctness Fix**

#### Fixed

##### 📉 Daily Fix Efficiency % Was Always 0% When Fixes Landed on a Different Day Than Introductions
- `get_defect_velocity_trend` computed `fix_efficiency_pct = Fixed / New * 100` per day, with an early `WHEN new_count = 0 THEN 0` branch. Since fixes and their originating introductions almost never share the same daily snapshot, most rows collapsed to 0% — including the row where the fix actually landed
- The dashboard tooltip already promised the correct formula: `Fixes / (Fixes + Introductions) × 100%`. The SQL now matches the tooltip: `Fixed / (New + Fixed) * 100`, with a single divide-by-zero guard when both are 0
- Real-world example: project `example-project` — 5 defects introduced 2023-05-08, all 5 fixed 2023-05-17. Before this fix the Daily Fix Velocity table showed 0% on every row (contradicting the 100% shown by the aggregate Fix Rate metric); after, 2023-05-17 correctly shows 100%

### Version 1.0.17 - 2026-08-04

**Scan Activity Chart, Parallel Generation & Reliability Fixes**

#### New Features

##### 📊 Scan / Commit Activity Over Time
- New Trends & Progress section on every project and instance dashboard shows snapshot (scan/commit) counts bucketed over time
- Daily buckets for per-project dashboards, weekly buckets for instance-wide and aggregated views
- Secondary y-axis overlays unique committers per bucket so the same chart shows both cadence and team engagement
- Aggregated multi-instance dashboard adds one overlaid line per instance for cross-instance comparison
- Backed by `CoverityMetrics.get_scan_activity_trend(days, granularity)` and `MultiInstanceMetrics.get_aggregated_scan_activity(days, granularity)`
- ZIP exports now capture `scan_activity_trend.json` at both project and instance levels; pre-1.0.17 ZIPs render the section as hidden (no crash)

##### ⚡ Parallel Per-Project Generation (`--workers`)
- New `--workers N` (`-w`) flag on both `coverity-export` and `coverity-dashboard` — default 1, clamped 1–8
- In database mode each worker owns its own `CoverityMetrics` (and Postgres connection); psycopg2 connections aren't thread-safe
- In ZIP mode each worker owns its own `ZipDataLoader` (ZipFile handles aren't thread-safe)
- Typical speed-ups measured on a 645-project instance:
  - Database export: **4–6× at `--workers 4`**, up to 8× at `--workers 8`
  - ZIP-based dashboards: **~2–3× at `--workers 4`** (CPU-bound rendering shares the GIL less well)
- Per-project errors are logged and the loop continues, matching current behaviour
- Recommendation: start with `--workers 4`; bump to 8 only if the Postgres server has headroom (each worker = one sustained connection)

##### ⏱ Execution Time Reporting
- Both CLIs print `Total execution time: 8.7s` / `1m 23.4s` / `2h 5m 12s` at the end (via a `finally` block, so failures still get timed)
- Export additionally prints per-instance breakdown, e.g. `Time: 4m 12.3s for 645 projects (~0.39s/project)` — makes measuring the `--workers` speedup trivial without external timing

##### 🏷 `--version` on Every CLI
- `coverity-dashboard` now supports `--version`, matching `coverity-export` and `coverity-metrics`. Prints `coverity-dashboard version: X.Y.Z` and exits. Also documented in the parameter tables in the README

##### 📸 Snapshots Tab on Project Dashboards — Recent Analysis Command Lines
- New project-only **📸 Snapshots** tab lists the exact `cov-build` and `cov-analyze` invocations recorded for the most recent 10 snapshots on the project — mirrors the "Command Line" data shown per snapshot in the Coverity Connect UI
- Each snapshot is a collapsible entry with stream, timestamp, invoker (user), host, and platform in the header; expanding reveals the per-element blocks (`Build / Capture`, `Static Analysis`) with runtime, success/failure counts, and the full command in a scrollable preformatted block
- Useful for verifying enabled checkers, aggressiveness level, `--strip-path`, and any custom `--enable` / `--disable` flags after the fact — no need to open Coverity Connect
- Backed by `CoverityMetrics.get_snapshot_commands(limit=20)` which joins `snapshot` → `snapshot_element` and filters by project via `project_stream`/`project`
- ZIP exports include `snapshot_commands.json` under `{instance}/{project}/`; `ZipDataLoader.get_snapshot_commands()` returns an empty DataFrame gracefully on pre-1.0.17 ZIPs, so the tab simply doesn't appear until you re-export

#### Performance Improvements

- **One Postgres connection per instance, not per project**
  - Export and dashboard CLIs now build a single `CoverityMetrics` and rescope via the `.project_name` property between projects
  - Eliminates one connect+auth handshake per project (previously ~645 handshakes on a large deployment)
- **Jinja `Environment` and inline CSS cached at module scope**
  - Template files and the inline CSS payload are read + compiled once per process and reused across every dashboard render, instead of re-parsed hundreds of times

#### Bug Fixes

##### 🛡 Graceful DB Errors
- `CoverityDatabase.execute_query()` / `execute_query_dict()` now wrap queries in `try/except`, log a warning, roll the connection back, and return `[]` on failure
- Callers get an empty DataFrame instead of a traceback — a single query failure no longer aborts the whole export or dashboard run

##### ➗ Division-by-Zero in Leaderboard Queries
- `avg_fixes_per_day` in `get_top_projects_by_fix_rate` no longer crashes when a project has only a single snapshot (or all snapshots share a timestamp) — the denominator `EXTRACT(EPOCH FROM (last - first))` is now wrapped in `NULLIF(..., 0)`, returning `NULL` instead of raising
- Audited every SQL division across `metrics.py` and `multi_instance_metrics.py` — every remaining site is either a constant denominator, guarded by `CASE WHEN ... > 0`, wrapped in `NULLIF`, or gated by a Python `if x > 0` check

##### 🧩 Template `|round()` on `None` Values
- Every leaderboard cell that reads from a `NULLIF`-guarded column (`avg_fixes_per_day`, `avg_triage_per_day`, `avg_comments_per_day`, `triage_percentage`) now uses `{{ field|round(2) if field is not none else 'N/A' }}` — fixes crashes when a NULL value was piped through `|round(...)` in Jinja
- Aggregated dashboard's per-instance `triage_completion` fixed at the source: `dict.get(k, 0)` returns `None` when the key is present with value `None`, so it's now `.get(k) or 0`

##### 📦 `AttributeError` Opening Pre-1.0.17 ZIPs
- `ZipDataLoader` gained `get_scan_activity_trend()` — returns an empty DataFrame when the ZIP predates this metric, so old exports render cleanly and the new section is just hidden until you re-export

##### 🛑 Ctrl+C During Parallel Runs
- Previously Ctrl+C on a `coverity-export --workers N` or `coverity-dashboard --workers N` run appeared to hang for minutes because `ThreadPoolExecutor`'s `with` block waited for every in-flight worker to finish
- All three parallel loops (export, dashboard DB-mode, dashboard ZIP-mode) now catch `KeyboardInterrupt`, cancel every queued future, and call `executor.shutdown(wait=False, cancel_futures=True)` before re-raising
- Both CLIs catch the interrupt at the top level, print `[INTERRUPTED] Aborted by user.`, and exit with code 130. First Ctrl+C drops queued tasks; second Ctrl+C hard-kills.

##### 🏆 Individual Contributors Leaderboards Ignored `--days`
- All five leaderboard queries in `dashboard.py` were hardcoded to `days=30`, so a dashboard generated with `--days 3650` still displayed "Last 30 Days" cards. `top_projects_by_fix_rate`, `top_projects_by_triage`, `top_users_by_fixes`, `top_triagers`, and `most_collaborative_users` now all pass the CLI-supplied `days` value
- Dashboard template subtitles and tooltips replaced literal `Last 30 Days` with `{{ trend_period_text }}`, so cards now show e.g. "Last 3650 Days" matching the actual window
- Removed the stale "improvement percentage (last 90 days)" phrase from the Project Performance tooltip — the Most Improved card was removed in 1.0.13

##### 🕒 `get_top_users_by_fixes` Did Not Honor the Time Window
- The SQL query for Top Fixers ignored the `days` parameter entirely and always aggregated all history, regardless of the requested window
- Added `AND ts.date_created >= CURRENT_DATE - INTERVAL '%s days'` in the `last_triagers` CTE for both project- and instance-scoped branches, and threaded `days` into the parameter tuples

##### 👥 Individual Contributors on Project ZIP Dashboards Showed Instance-Wide Rankings
- `ZipDataLoader.get_top_users_by_fixes`, `get_top_triagers`, and `get_most_collaborative_users` were calling `_read_json_from_zip(self._get_metric_file(...))` directly, bypassing `self.project_name` and always loading the instance-level file
- Switched all three methods to `_read_metric_json(...)`, which reads `{instance}/{project}/{metric}.json` first when a project is selected — matching how `get_defects_by_severity` and other project-scoped metrics behave
- `export_project_specific_metrics` now writes `top_users_by_fixes.json`, `top_triagers.json`, and `most_collaborative_users.json` under `{instance}/{project}/`. Instance-level and project-level exports both use the CLI `days` value instead of hardcoded 30
- **Pre-1.0.17 ZIPs won't contain the per-project user leaderboard files.** On an old ZIP, project-level dashboards will now correctly show *no data* for these cards (the section auto-hides) until you re-export with 1.0.17+.

##### 🧊 Cached Dashboard Path Dropped Individual Contributors Entirely
- `_collect_and_cache_metrics` was setting `top_users_by_fixes`, `top_triagers`, and `most_collaborative_users` to empty lists with a stale "not available without defect_triage_history table" comment — so every cached dashboard rendered without the Individual Contributors section
- Replaced with real metric calls (`metrics.get_top_users_by_fixes(days=days, limit=10)` etc.) and updated `top_projects_by_fix_rate` / `top_projects_by_triage_activity` in the same block to use `days=days` instead of 30. Rebuild cache (or run once without `--use-cache`) to pick up the fix.

##### 🎯 Overview "Active Defects" Card Counted False Positives and Intentionals
- The Overview tab's Active Defects card promised (in its tooltip) to exclude False Positive and Intentional defects, but `get_overall_summary` only filtered on `stream_defect.fixed_snapshot_element_id IS NULL` — so dismissed defects were counted as active, contradicting both the tooltip and the Defects by Stream table's own `active_defects` column
- Both the project-scoped and global branches of `get_overall_summary` now `LEFT JOIN defect_triage` + `dynamic_enum` (`dtype = 'Cls'`) and add `AND (de_cls.name NOT IN ('False Positive', 'Intentional') OR de_cls.name IS NULL)` for `total_defects` and `high_severity_defects`
- Real-world impact: a project with 162 stream_defects all classified as False Positive previously showed `Active Defects: 162`; now correctly shows `0` and matches the "Active" column of the Defects by Stream table beneath it

##### ✅ Dismissed Defects (FP / Intentional) Now Treated as Fixed Everywhere
- The Overview card fix above closed one gap; the same "outstanding = `fixed_snapshot_element_id IS NULL`" pattern was still present in **fourteen** other queries, causing the severity donut, category chart, top-checkers table, defect-density leaderboard, file hotspots, aging distribution, triage progress %, triage-trends stacked bars, current-outstanding in the trend summary, top-projects-by-triage, and all OWASP + CWE Top 25 tables to include dismissed defects while the by-stream table and Overview card excluded them
- Every one of those queries now adds the same triage-classification join and exclusion, so the entire dashboard agrees on the definition of "active"
- Preserved on purpose (these are *about* classifications and would go empty otherwise): `get_checker_classification_breakdown` (Noisy Checkers) and `get_top_projects_by_classification` (Projects Ranked by Intentional). Fix-rate / velocity / cumulative / trend CTEs are also unchanged — those already count FP/Intentional on the *fixed* side of the ledger, which is exactly what the fix-rate metric is supposed to do
- Real-world example: `example-project` has 97 stream_defects with 96 classified as False Positive/Intentional. Before this release the Overview severity donut, category chart, hotspots, aging, OWASP tab and CWE Top 25 tab all showed 97 defects. After the fix they all correctly show **1** truly-active defect, matching the Defects by Stream table

##### 🔁 Refined: Five "Raw Defect" Charts Reverted to Include Dismissed
- Follow-up on the change above: the sweep was too aggressive for five charts whose whole purpose is to visualise *what Coverity is finding*, not what still needs work. Notably, **Current Triage Progress** was collapsing to `total_defects = 0` on projects where every defect had been triaged as False Positive or Intentional, hiding the entire triage picture on the Trend & Progress tab
- Reverted (now include dismissed again):
  - `get_defects_by_severity` — Defects by Severity donut
  - `get_defects_by_checker_category` — Top Defect Categories
  - `get_defects_by_checker_name` — Top Defect Checkers
  - `get_defect_density_by_project` — Defect Density (per KLOC)
  - `get_triage_progress_summary` — Current Triage Progress card and its classification breakdown
- Still enforce "active only" (these are about remediation load, not defect volume):
  - Overview `Active Defects` and `High Severity Defects` cards
  - File Hotspots, Defect Aging Distribution
  - Triage Trends stacked bars (per-stream classification of currently-outstanding defects)
  - OWASP Top 10, CWE Top 25 tabs
  - `get_defect_trend_summary` `current_state` (Current Outstanding count)
  - `get_top_projects_by_triage_activity`

##### 🧭 "Outstanding Defect" Semantic Corrected — `fixed_snapshot_element_id` Is Unreliable
- Root cause: `stream_defect.fixed_snapshot_element_id IS NULL` was used as the "currently outstanding" test in every active-defect query. But Coverity Connect does **not** clear that column when a previously-fixed defect re-appears in a later snapshot — so any defect that was once eliminated and later reintroduced looked "fixed" to us even though the UI still shows it as outstanding
- The Coverity UI itself uses the `last_detected_snapshot` table: a defect is currently outstanding iff `last_detected_snapshot.detected_snapshot_id = <latest non-deleted snapshot.id for its stream>`
- Introduced three class constants on `CoverityMetrics` that codify the correct pattern once — every query now injects them instead of open-coding `fixed_snapshot_element_id`:
  - `_ACTIVE_JOIN_SQL` — joins `last_detected_snapshot` (`lds`) and a per-stream max-snapshot subquery (`sn_latest`) via `stream_element.stream_id`
  - `_ACTIVE_COND_SQL` — `lds.detected_snapshot_id = sn_latest.latest_snap_id`
  - `_FIXED_COND_SQL` — the inverse (`IS NULL OR !=`); used alongside `fixed_snapshot_element_id IS NOT NULL` in code-fixed / fix-time / fix-rate queries so only defects that truly no longer appear are counted as fixed
- Applied to every active-defect SQL site (~20 queries): `get_total_defects_by_project`, `get_defects_by_severity`, `get_defects_by_checker_category`, `get_defects_by_checker_name`, `get_defect_density_by_project`, `get_overall_summary` (project + global branches), `get_file_hotspots`, `get_triage_trends`, `get_checker_classification_breakdown`, `get_top_projects_by_classification`, `get_fix_rate_metrics` (three CTEs), `get_defect_velocity_trend`, `get_cumulative_defect_trend`, `get_defect_trend_summary` (period_triaged + current_state), `get_defect_aging_distribution`, `get_triage_progress_summary`, `get_technical_debt_summary`, `get_top_projects_by_fix_rate`, `get_top_projects_by_triage`, `get_top_users_by_fixes` (both branches), `get_owasp_top10_metrics`, `get_owasp_category_details`, `get_cwe_top25_metrics`, `get_cwe_top25_details`
- `get_triage_progress_summary` was additionally reshaped to start `FROM stream_defect sd` (was `FROM defect_triage dt` with a `LEFT JOIN` to `sd`), so orphan triages that don't belong to a currently-outstanding defect no longer inflate the totals
- Real-world example: project `example-project` — Coverity UI shows 2 outstanding defects (CID 38907 Intentional and CID 39378 Unclassified with a stale `fixed_snapshot_element_id`). Before this fix, `get_triage_progress_summary.total_defects = 1`; after, `total_defects = 2` and the classification breakdown matches the UI exactly
- Rebuild any cached dashboard (`--use-cache` runs) after upgrading — counts for all of the above metrics will change on projects where at least one defect was ever eliminated-then-reintroduced

##### 🧮 Function Complexity Distribution Leaked Instance-wide Numbers into Every Project
- `get_function_complexity_distribution` and `get_most_complex_functions` had no project filter — every project's ZIP export and every DB-mode dashboard showed the *instance-wide* complexity histogram and top-N list, so projects with zero streams still displayed thousands of functions in the "Function Complexity Distribution" chart and the "Most Complex Functions" table
- Both queries now join `stream_file` → `stream_element` → `stream` → `project_stream` → `project` when a project filter is active and add `AND p.name = ANY(%s)`. Projects with no streams (e.g. `example-project`) now correctly return empty
- Re-export required: pre-1.0.17 ZIPs still contain leaky per-project `function_complexity_distribution.json`. Re-run `coverity-export` with 1.0.17+ to get correct per-project numbers in ZIP dashboards

#### Developer Experience

##### 🎯 Empty-state Message on the Scan Activity Chart
- If a project or instance has no snapshots in the analysed `--days` window, the "Scan Activity Over Time" section now stays visible and shows an inline info alert:
  > ℹ️ No scan activity in the last N days. Re-export with a longer `--days` window if you expect older snapshots to be included.
- Same treatment on the aggregated multi-instance dashboard. Makes it obvious the metric ran and returned nothing, versus the section being disabled.

##### 🔖 Single-Source-of-Truth Package Version
- `pyproject.toml` now uses `dynamic = ["version"]` with `[tool.setuptools.dynamic] version = {attr = "coverity_metrics.__version__.__version__"}`
- Both the pip metadata (`pip show coverity-metrics`) and the runtime `--version` output now read from the same file: `coverity_metrics/__version__.py`
- Future releases: bump one file, not two. No more "installed 1.0.16 when 1.0.17 was expected" surprises.

---

### Version 1.0.16 - 2026-05-05

**Module Support & Documentation Release**

#### New Features

##### 🐍 `python -m coverity_metrics` Module Support
- The package can now be invoked as a Python module in addition to the existing CLI entry points
- Usage:
  ```bash
  python -m coverity_metrics dashboard  # equivalent to coverity-dashboard
  python -m coverity_metrics export     # equivalent to coverity-export
  python -m coverity_metrics report     # equivalent to coverity-metrics
  ```
- All arguments are passed through unchanged — every flag documented for the CLI entry points works identically
- Running without a subcommand prints a usage summary listing all available subcommands
- Implemented via a new `coverity_metrics/__main__.py`

#### Documentation

##### 📋 Multi-Project `--project` Parameter Now Documented
- **Issue**: Documentation described `--project` as accepting only a single project name, even though the CLI has always supported comma-separated multiple projects
- **Clarification**: Pass multiple projects as a comma-separated string — e.g. `--project "AppA,AppB,AppC"` — to generate individual per-project dashboards for each, plus an aggregated instance dashboard. Works in both database mode and ZIP file mode.
- **Updated**: README parameter table, database/ZIP mode examples, auto-detection behavior notes, and USAGE_GUIDE quick-start section
- Added `python -m coverity_metrics` usage examples to README and USAGE_GUIDE

---

### Version 1.0.15 - 2026-05-05

**Bug Fix Release**

#### Bug Fixes

##### 📊 Fixed Project-Level Metrics in ZIP Dashboards
- **Issue**: Project-level dashboards generated from ZIP exports showed instance-wide aggregate data instead of project-specific data for "Top Analysis Versions Used" and 7 other metrics
- **Example**: A project dashboard would show all analysis versions used across the entire instance rather than just the versions used for that specific project
- **Root Cause**:
  - 8 methods in `ZipDataLoader` were hardcoded to always read from instance-level files (`self._get_metric_file()`) instead of checking for project-specific files first
  - Project-level metrics were not being exported to ZIP files in the first place
- **Fix**:
  - Updated 8 `ZipDataLoader` methods to use `_read_metric_json()` which properly checks for project-specific data: `get_analysis_versions`, `get_function_complexity_distribution`, `get_snapshot_performance`, `get_commit_time_statistics`, `get_commit_activity_patterns`, `get_defect_discovery_rate`, `get_defect_velocity_trend`, `get_cumulative_defect_trend`
  - Added these metrics to `project_metrics_config` in `export.py` so they are now exported at the project level
- **Impact**: After re-exporting with `coverity-export`, project-level dashboards generated from ZIP files will correctly display project-scoped data instead of instance aggregates

##### ⏰ Fixed Negative Database Uptime Display
- **Issue**: Database uptime showed negative values like "-1d 23h 24m" along with the start time showing as future date
- **Root Cause**: `get_instance_info()` in `metrics.py` was stripping timezone information from PostgreSQL's `pg_postmaster_start_time()` (which returns a timezone-aware datetime) and comparing it with naive local time from `datetime.now()`, causing timezone offset mismatches where the database start time appeared to be in the future
- **Fix**:
  - Updated calculation to use UTC consistently: `datetime.now(timezone.utc)` for current time
  - Convert database start time to UTC using `.astimezone(timezone.utc)` to handle timezone offsets correctly
  - Added guard to detect and display "Invalid (negative)" if negative uptime occurs (edge case protection)
- **Impact**: Database uptime now calculates correctly regardless of database timezone configuration or system local timezone

---

### Version 1.0.14 - 2026-03-19

**Parameter Enhancement & Documentation**

#### Added
- **`fetch_all` Parameter**: Added `fetch_all` parameter to metrics methods — pass `fetch_all=True` to any method with a `limit` parameter to retrieve the complete result set instead of just the top N results

#### Improvements
- **CLI Parameter Documentation**: Enhanced CLI parameter documentation in README with comprehensive reference tables for all tools (`coverity-dashboard`, `coverity-metrics`, `coverity-export`)
- **Python Library Examples**: Updated Python library usage examples in README to reflect current API and features

---

### Version 1.0.13 - 2026-03-13

**Leaderboard Cleanup**

#### Changes

##### 🗑️ Removed "Most Improved" Leaderboard Card
- **Change**: The "Most Improved" leaderboard card has been removed from the Team Leaderboards section
- **Reason**: Improvement percentage was unreliable for sparse snapshot data — projects with only one snapshot had no meaningful baseline to compare against, making the metric misleading
- **Impact**: Removed `get_most_improved_projects` from all dashboard generation paths (`dashboard.py`) and from the ZIP export config (`export.py`); the "Improvement" entry has also been removed from the Leaderboard Metrics Explained legend

---

### Version 1.0.12 - 2026-03-05

**Packaging Maintenance**

#### Changes

##### 🧹 Removed Stale `~overity_metrics` dist-info Artefact
- **Issue**: pip printed `WARNING: Ignoring invalid distribution ~overity-metrics` on every invocation due to a corrupted `~overity_metrics-1.0.8.dist-info` directory left behind by a previously interrupted install
- **Fix**: Removed the stale directory from site-packages; no source code changes
- **Impact**: pip no longer emits the spurious warning

---

### Version 1.0.11 - 2026-03-05

**Bug Fix: PostgreSQL ROUND Compatibility**

#### Bug Fixes

##### 🐛 Fixed `ROUND(double precision, integer)` Error in Top Projects by Fix Rate
- **Issue**: `coverity-dashboard` crashed with `psycopg2.errors.UndefinedFunction: function round(double precision, integer) does not exist` when generating the dashboard
- **Root Cause**: In `metrics.py` `get_top_projects_by_fix_rate`, `EXTRACT(EPOCH FROM ...)` returns `double precision` in PostgreSQL. Dividing a `numeric` value by `double precision` yields `double precision`, and PostgreSQL only defines `ROUND(numeric, integer)` — not `ROUND(double precision, integer)`
- **Fix**: Added `::numeric` cast to the `EXTRACT(EPOCH FROM (last_snapshot - first_snapshot))` expression so the result is `numeric` throughout and `ROUND(x, 2)` resolves correctly
- **Impact**: Dashboard generation now completes successfully on all PostgreSQL versions

---

### Version 1.0.10 - 2026-03-04

**Documentation & Project Structure Improvements**

#### Changes

##### � Upgraded Python Dependencies to Latest Versions
All minimum version pins in `requirements.txt` have been bumped to the latest available releases:

| Package | Previous | Updated |
|---|---|---|
| `psycopg2-binary` | `>=2.9.0` | `>=2.9.11` |
| `pandas` | `>=2.0.0` | `>=3.0.1` |
| `matplotlib` | `>=3.7.0` | `>=3.10.8` |
| `seaborn` | `>=0.12.0` | `>=0.13.2` |
| `python-dateutil` | `>=2.8.0` | `>=2.9.0.post0` |
| `openpyxl` | `>=3.1.0` | `>=3.1.5` |
| `jinja2` | `>=3.1.0` | `>=3.1.6` |
| `plotly` | `>=5.18.0` | `>=6.6.0` |
| `tqdm` | `>=4.66.0` | `>=4.67.3` |

##### �📁 Refactored Project Structure Documentation
- Updated README with new file paths and project layout to accurately reflect the current source tree
- Improved organization and clarity of repository structure descriptions

##### 📊 Updated Presentation Guide
- Added Python script option for generating presentations from the command line
- Revised slide structure details for improved accuracy and usability

---

### Version 1.0.9 - 2026-03-03

**ZIP Export, Progress Tracking & Aggregated Dashboard Fixes**

#### Bug Fixes

##### 📦 Fixed Missing Classification Charts in ZIP-based Dashboards
- **Issue**: Dashboards generated from ZIP files (offline/export mode) were missing the "Checker Classification Breakdown" and "Top Projects/Streams by Triage Classification" sections
- **Root Cause**: The two metrics (`checker_classification_breakdown`, `top_projects_by_classification`) were never added to the export metric configs in `export.py` when the feature was created — `ZipDataLoader` had the reader methods, the templates had the chart sections, but the JSON files were never written into the ZIP
- **Fix**: Added both metrics to `export_instance_to_json()` and `export_project_specific_metrics()` in `export.py`
- **Impact**: Re-export with `coverity-export` to get ZIPs with the new JSON files; ZIP-based dashboards will then show the missing chart sections

##### ▶️ Implemented `--track-progress` and `--resume`
- **Issue**: `--track-progress` and `--resume` CLI flags were accepted but did nothing — `ProgressTracker` was instantiated but never used in any generation loop
- **Fix**: Fully wired progress tracking into all 7 generation paths in `dashboard.py`
  - `--track-progress`: prints a session ID at the start of generation; records each completed dashboard; call `complete_session()` at the end
  - `--resume SESSION_ID`: loads the previously completed dashboard set from `cache/progress/progress_{SESSION_ID}.json`; skips already-finished items with a `[SKIP]` message; continues from the interruption point
- **Label scheme**:
  - Aggregated view: `"Aggregated View"`
  - Instance overview: `"{instance_name}"` (multi-instance) or `"{instance_name} - All Projects"` (single-instance)
  - Per-project: `"{instance_name} - {project_name}"`
- **Impact**: Large multi-instance / multi-project runs that are interrupted (network drop, timeout, etc.) can now be resumed without regenerating already-finished dashboards

##### 📅 Fixed Hardcoded "Last 90 Days" in Aggregated Dashboard
- **Issue**: The aggregated dashboard always showed "Last 90 Days" in the User Activity section title, card labels, table headers, and tooltips, regardless of the `--days` argument passed
- **Root Cause**: `dashboard_aggregated.html` was written with `90` hardcoded in 5 places; the `trend_period_text` Jinja2 variable was available but the template was never updated to use it
- **Fix**: Replaced all 5 hardcoded occurrences with `{{ trend_period_text }}` / `{{ trend_period_text|lower }}`
  - Section title: `Last 90 Days` → dynamic
  - Card labels: `Total New (90d)` / `Total Fixed (90d)` → dynamic
  - Table headers: `New Defects (90d)` / `Fixed (90d)` → dynamic
  - Active Users and Inactive Licenses tooltips: `last 90 days` → dynamic
- **Impact**: The aggregated dashboard now correctly reflects `--days 365` (or any other value) throughout

### Version 1.0.8 - 2026-03-02

**OWASP Top 10 Count Consistency Fix**

#### Bug Fixes

##### 🛠️ Fixed OWASP Top 10 Summary / Detail Count Inconsistency
- **Issue**: OWASP Top 10 category sections showed contradictory numbers in the same panel
  - Example (A09: Security Logging and Monitoring Failures): "Total Defects: 5" in the header, "Defects (6 total)" in the table heading, and "1 CWE mapped" when the table listed 2 different CWEs
- **Root Cause 1 — Last-Writer-Wins CWE Mapping**:
  - 31 CWEs appear in more than one OWASP category in the mapping table
  - The aggregation code built a flat `cwe_to_owasp` dict: each duplicate key silently overwrote the previous entry
  - CWE-918 (SSRF) is in both A09 and A10; A10 is iterated last, so `cwe_to_owasp[918]` pointed only to A10
  - Defects with CWE-918 were excluded from A09's summary count but the detail query (which used `cp.cwe IN (all A09 CWEs)`) correctly included them — producing the mismatch
- **Root Cause 2 — Different Deduplication in Summary vs Detail**:
  - Summary counted `COUNT(DISTINCT sd.id)` — physical stream-defect rows, which can be duplicated for merged defects
  - Detail table used `SELECT DISTINCT ON (sd.merged_defect_id)` — one row per logical defect
  - For projects with merged defects the two counts diverge
- **Fix**:
  - Changed `cwe_to_owasp` to a **multi-value mapping** (`CWE → [list of all matching categories]`)
  - Aggregation loop now iterates over every matching category for each CWE, so shared CWEs contribute to all of their categories
  - Changed summary SQL to `COUNT(DISTINCT sd.merged_defect_id)` with `AND sd.merged_defect_id IS NOT NULL` to mirror the detail table's deduplication
- **Impact**: "Total Defects" in the OWASP category header, the defect table row count, and the CWE count now always match

### Version 1.0.7 - 2026-02-25

**New Features & Fixes**

#### Features
- **Script Execution Time**: Script now prints total execution time after dashboard generation, helping users measure performance for large datasets.

#### Bug Fixes & Improvements
- **Accurate Active Users**: Instance-level "Active Users" now deduplicates by activity (triage, comment, commit) and matches project-level logic for consistency.
- **Dashboard Bug Fix**: Dashboard now displays the correct "Active Users" count at all levels (instance, project, aggregated).
- **HTML Escaping**: Defect file/function fields are now HTML-escaped in dashboards to prevent invalid HTML/JS errors from untrusted content.

### Version 1.0.6 - 2026-02-24

**ZIP Export Critical Bug Fixes**

#### Bug Fixes

##### 🛠️ Fixed Project-Level Dashboard Data Filtering from ZIP Files
- **Issue**: Project-level dashboards generated from ZIP files were showing instance-level aggregate data instead of project-specific data
  - Example: Project dashboard showed 90 defects (instance total) instead of 5 defects (project actual)
- **Root Cause**: 
  - Export only created project-level files for OWASP and CWE metrics
  - ZipDataLoader always read from instance-level files regardless of `project_name` setting
  - Core metrics (overall_summary, defects_by_severity, trends, etc.) were missing at project level
- **Fix**:
  - **Updated export.py**: Now exports complete project-specific versions of all core metrics
    - overall_summary.json
    - defects_by_severity.json
    - defect_trends.json
    - triage_progress_summary.json
    - fix_rate_metrics.json
    - defect_aging_distribution.json
    - technical_debt_summary.json
    - All other dashboard metrics
  - **Updated zip_data_loader.py**: Added intelligent file path resolution
    - New `_read_metric_json()` method checks for project-specific files first
    - Falls back to instance-level files if project file doesn't exist
    - All metric getter methods now use this smart lookup
- **Impact**: Project dashboards from ZIP files now correctly show filtered data matching database mode behavior

##### 📊 Fixed Triage Progress Aggregation Discrepancy
- **Issue**: Aggregated triage progress showed different numbers between database and ZIP sources
  - Database: 36 Classified, 234 Unclassified, 13.3% Completion ✅
  - ZIP (before): 57 Classified, 213 Unclassified, 21.1% Completion ❌
- **Root Cause**: Aggregation code incorrectly summed individual triage state counts (bug_count + false_positive_count + intentional_count + action_assigned_count = 57) instead of using the `classified_count` field
  - Problem: `action_assigned_count` includes defects with actions assigned but still marked as "Unclassified"
  - The `classified_count` field correctly counts only defects with actual classifications
- **Fix**: Changed aggregation in dashboard.py to use `total_triaged` (sum of `classified_count` from each instance) instead of `sum(triage_by_state_agg.values())`
- **Impact**: ZIP and database sources now produce identical triage statistics

#### Technical Details
- ZIP file structure now includes project subdirectories with complete metric sets
  - `{instance}/{metric}.json` - instance-level data
  - `{instance}/{project}/{metric}.json` - project-specific data
- ZipDataLoader maintains backward compatibility with older ZIP exports
- No changes to database query logic - already correct

---

### Version 1.0.5 - 2026-02-20

**Enhanced Security Reporting & Complete Coverage**

#### Major Enhancements

##### 🛡️ Complete OWASP Top 10 2025 Security Coverage
- **All 10 Categories Always Visible**: Dashboard now shows all OWASP Top 10 categories regardless of defects
- **PASS/FAILED Status Badges**:
  - 🟢 **PASS** (green): No defects for this category - safe!
  - 🔴 **FAILED** (red): Has defects requiring attention
- **Interactive Defect Exploration**:
  - Click FAILED rows to expand and see ALL defects (no limits)
  - PASS rows are non-clickable and visually faded
- **Complete Security Posture**: Instantly see which OWASP categories are clean vs problematic
- **Summary Metrics**: "X/10 Failed" counts for quick assessment

##### 🏆 Complete CWE Top 25 2025 Weakness Coverage
- **All 25 CWEs Always Visible**: Shows complete MITRE CWE Top 25 list
- **Status Column**: Each CWE entry has PASS/FAILED badge
- **Ranked by Danger**: Industry-standard rankings (1-25) from MITRE
- **Same Interactive Experience**: Click FAILED entries to see all defect details
- **Summary Metrics**: "X/25 Failed" counts

##### 📝 Enhanced Defect Detail Tables
- **Comprehensive Information**:
  - **CID**: Actual Coverity ID (now correctly using merged_defect_id)
  - **Type**: Checker name describing defect type
  - **Severity**: Color-coded High/Med/Low badges
  - **File**: Full file path (with overflow handling)
  - **Function**: Function name where defect occurs
  - **CWE**: CWE identifier (OWASP report only)
- **Show ALL Defects**: Removed 10-per-CWE limits - see complete defect lists
- **Scrollable Tables**: Clean 400px height containers for large lists
- **Fixed Headers**: Sticky headers with proper visibility
- **Simplified Display**:
  - Removed aggregated "CWE Breakdown" sections
  - Removed "Top Checkers" summary from CWE Top 25
  - Focus on actionable defect details

#### Visual Improvements
- **Color-Coded Rows**:
  - FAILED: Red-tinted background, clickable, pointer cursor
  - PASS: Green-tinted faded background, non-clickable
- **Fixed Table Headers**: Proper text color (#2c3e50) on white background
- **Responsive Design**: Tables adapt to content with scrolling

#### Database & Performance
- **Corrected CID Field**: Now uses `stream_defect.merged_defect_id` (actual user-visible CID)
- **Fixed Schema Joins**:
  - Checker names via `checker_type` table
  - Function names via `stream_defect_occurrence.function_id`
  - Removed invalid `stream_file` joins
- **Performance Optimization**: Only loads details for FAILED entries (not PASS)

#### Bug Fixes
- Fixed table header visibility in security reports
- Resolved undefined CSS variable issues
- Fixed UnboundLocalError for commit_activity

#### Use Cases
- **Security Audits**: Instant view of OWASP/CWE compliance status
- **Remediation Planning**: Click FAILED categories to see all defects needing fixes
- **Compliance Reporting**: Show complete coverage for security frameworks
- **Team Communication**: Clear PASS/FAIL badges for stakeholder presentations

---

### Version 1.0.4 - 2026-02-19

**Progress Tracking & User Experience Update**

#### New Features
- **Comprehensive Progress Tracking for Multi-Instance Dashboards**
  - Added tqdm-based progress bars for all multi-instance dashboard generation workflows
  - Real-time visibility into long-running operations (10+ instances with hundreds of projects)
  - Pre-calculates total work items before execution (1 aggregated + N instances + M projects)
  - Dynamic progress descriptions showing current instance and project being processed
  - Automatic time estimation (elapsed time, remaining time, completion ETA)
  - Processing speed metrics (dashboards/second)
  
- **Three Progress Tracking Scenarios**
  - **Specific Instance + All Projects**: Shows "1 instance + N projects" with project counter
  - **All Instances + Specific Project**: Shows "Instance X/Y: {name}" for each instance
  - **Full Auto Mode (All Instances + All Projects)**: Overall progress bar tracking all dashboard types
    - Pre-flight calculation displays: "1 aggregated + N instances + M projects"
    - Single unified progress bar showing completion across all work
    - Postfix strings display current item: "{project} (X/Y)"

- **Commit Activity Patterns Analysis**
  - Added `get_commit_activity_patterns()` method to analyze when commits occur
  - Groups commits by hour of day (0-23) and day of week (0-6, Sunday-Saturday)
  - Creates 3-hour time blocks: 00-02, 03-05, 06-08, 09-11, 12-14, 15-17, 18-20, 21-23
  - Identifies busiest and quietest 3-hour windows with commit counts and statistics
  - Identifies busiest and quietest days of the week
  - Calculates average duration, files changed, and new defects per commit window
  - Multi-instance aggregation support with `get_aggregated_commit_activity()`
  - Integrated into both single-instance and aggregated dashboards
  - Display format: "14:00-16:00 (2 PM - 4 PM)" with 12-hour AM/PM conversion

#### User Experience Improvements
- Progress bars provide immediate feedback for operations that previously showed blank screen
- Users can see exactly how many dashboards will be generated before work begins
- Clear visibility into which instance and project is currently being processed
- Professional enterprise-grade experience for large multi-instance deployments
- Accurate completion percentage and time estimates help users plan their workflow

#### Technical Details
- **Files modified**: `dashboard.py` (lines 665-775), `metrics.py` (lines 1082-1210), `multi_instance_metrics.py` (lines 296-424)
- **Progress tracking implementation**:
  - Lines 665-686: Specific instance + all projects mode with total calculation
  - Lines 688-704: All instances + specific project mode with instance counter
  - Lines 706-775: Full auto mode with comprehensive work calculation and overall progress bar
- **Example output**:
  ```
  Calculating total work for progress tracking...
    Total dashboards to generate: 47
    - 1 aggregated dashboard
    - 10 instance dashboards
    - 36 project dashboards
  
  Overall Progress: 23/47 [=========>...] 48% [04:36<04:48, 12.0s/dashboard]
  Instance 5/10: Staging projects
  project_alpha (3/8)
  ```
- **Commit activity patterns**:
  - SQL queries use `EXTRACT(HOUR FROM sn.date_created)` and `EXTRACT(DOW FROM sn.date_created)`
  - Qualified column names with table alias (sn.date_created) to avoid ambiguous references
  - 3-hour block aggregation with weighted averages for statistics
  - Returns: busiest_hours, quietest_hours, busiest_day, quietest_day with commit counts

#### Bug Fixes
- Fixed SQL ambiguous column error in commit activity queries by qualifying all column references
- Progress bars now use `tqdm.write()` for clean output without interfering with progress display

### Version 1.0.3 - 2026-02-19

**Security & Technical Debt Update**

#### New Features
- **Technical Debt Estimation**
  - Added `get_technical_debt_summary()` method for effort estimation
  - Industry-standard formulas: High=4h, Medium=2h, Low=1h, Unspecified=0.5h per defect
  - Displays total hours, work days, work weeks, and breakdown by impact level
  - Integrated into "Trends & Progress" dashboard tab
  - Based on Coverity's `checker_properties.impact` field (High/Medium/Low)

- **CWE Top 25 2025 Update**
  - Updated from CWE Top 25 2024 to 2025 version (MITRE)
  - All 25 CWE rankings updated with new scores
  - Major ranking changes: CWE-306 (#20→#8), CWE-416 (#4→#18), CWE-787 (#5→#21)
  - New entries: CWE-120 (Classic Buffer Overflow #19), CWE-327 (Broken Crypto #23)
  - Removed entries: CWE-94 (Code Injection), CWE-276 (Incorrect Permissions)
  - Dashboard tab updated to show "CWE Top 25 2025"

#### Enhanced Documentation
- Updated README.md with "Latest Enhancements (2025)" section
- Added technical debt, OWASP Top 10, CWE Top 25 to features list
- Added Security Compliance Metrics section
- Added "For Security Teams" use cases
- Updated Python API examples with new methods
- Documented all 7 dashboard tabs (Overview, Code Quality, Performance, Trends & Progress, Leaderboards, OWASP Top 10, CWE Top 25)

#### Dashboard Enhancements
- Technical Debt Summary section in "Trends & Progress" tab
  - 4 primary cards: Total Hours, Work Days, Work Weeks, Avg per Defect
  - 4 breakdown cards: High/Medium/Low/Unspecified impact with color-coded severity
  - Info alert explaining estimation formula
- CWE Top 25 tab displays 2025 rankings and scores

#### Technical Details
- Files modified: `cwe_top25_mapping.py`, `metrics.py`, `dashboard.py`, `dashboard.html`
- New method: `CoverityMetrics.get_technical_debt_summary()`
- Database query: Joins `stream_defect` with `checker_properties` for impact levels
- Calculation: CASE statement for effort estimation based on impact
- Returns: Dictionary with totals (hours/days/weeks), defect count, breakdown by impact, average per defect

### Version 1.0.2 - 2026-02-18

**Feature Update**

#### Features
- Added `fetch_all` parameter support
- Enhanced documentation

### Version 1.0.0 - 2026-02-18

**Initial Release**

#### Features
- Full Python package structure with CLI commands
- Three CLI tools: `coverity-dashboard`, `coverity-metrics`, `coverity-export`
- Interactive HTML dashboard with Plotly charts
- Multi-instance aggregation support
- Performance caching system
- Progress tracking for large datasets
- CSV/JSON export functionality
- PostgreSQL database integration

#### CLI Commands
- `coverity-dashboard` - Generate interactive HTML dashboards
- `coverity-metrics` - Console text reports
- `coverity-export` - Export data to CSV files

#### Configuration
- Uses `config.json` for database configuration
- Auto-detects single vs multi-instance mode
- Support for multiple Coverity instances

#### Documentation
- Complete README with installation and usage
- Multi-instance setup guide
- Caching performance guide
- Usage examples and workflows

---

## Future Releases

Document changes here for upcoming versions.

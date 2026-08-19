# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.30] - YYYY-MM-DD

### Changed
- **Swapped the PostgreSQL driver from `psycopg2-binary` to `pg8000` (pure-Python)**
  - `psycopg2-binary`'s Windows and Linux wheels bundle a full stack of native libraries (OpenSSL, libpq, MIT krb5, PCRE1, and their manylinux siblings — openldap / sasl / com_err / keyutils / selinux). Every one of those tracks against whatever the psycopg2 maintainers built their manylinux base image against, so BDBA reports on the standalone binary flagged them as behind upstream repeatedly (1.0.28 Windows report, 1.0.29 Linux report). None of them were fixable at the project level without giving up the "no Python required on the target machine" property of the binary.
  - `pg8000` is a pure-Python Postgres driver — zero C extensions, zero bundled natives — that speaks the same DB-API 2.0 surface and the same `format` paramstyle (`%s`) as psycopg2. Confirmed `connect()` accepts the same `host` / `port` / `database` / `user` / `password` kwargs, so `config.json` schema is unchanged.
  - Trade-off: pure-Python protocol handling is roughly 2–4× slower than libpq for large result sets. This project's workload is aggregation queries returning small result sets (defect counts, top-N lists, weekly trends), so end-to-end dashboard / export / report runs are within a couple seconds of the psycopg2 baseline on the DB used for smoke-testing.
  - Not compatible with GSSAPI / Kerberos authentication — pg8000 supports plaintext, MD5, and SCRAM-SHA-256 only. If your Coverity Connect DB requires GSSAPI, pin `<= 1.0.29` and open an issue.
  - Kills five of the seven BDBA findings against the 1.0.29 Linux binary (see the "BDBA scan findings" section below).
- **Dropped three dependencies that were declared but never imported: `matplotlib`, `seaborn`, `openpyxl`**
  - Grep for `import matplotlib | pyplot | seaborn | openpyxl | to_excel` across `coverity_metrics/**/*.py` returned empty — all three were declared in `requirements.txt` / `pyproject.toml` for years without a single call site. All dashboard rendering happens via `plotly` (JavaScript, in-browser) and the exporter writes ZIPs of JSON, not `.xlsx`.
  - Removing `matplotlib` also removes `Pillow` as a transitive, which kills the `libtiff` finding from the 1.0.29 Windows BDBA report.
- **PyInstaller build now excludes stdlib modules pulled in transitively but never used**
  - `sqlite3` / `_sqlite3` (imported delayed by `pandas.io.sql`): drops `sqlite3.dll` and `_sqlite3.pyd` from the bundle. We never call `pd.read_sql` / `pd.to_sql`.
  - `pyexpat` / `_elementtree` (imported by `pandas.io.xml` and `pandas.io.formats.xml`): drops `pyexpat.pyd` and `_elementtree.pyd`. We never call `pd.read_xml` / `DataFrame.to_xml`.
  - `matplotlib.backends.backend_agg` hidden-import line removed. The full `matplotlib` / `PIL` / `seaborn` / `openpyxl` packages are also added to the `excludes` list as belt-and-suspenders in case the build venv accidentally has them installed.
  - The `pandas.io.sql` / `pandas.io.xml` shim modules themselves stay bundled — `pandas.io.api` hard-imports them and pandas won't load otherwise. They fall through to raising at call time if anything ever tries to actually use them, which nothing does.
- **Standalone binary size dropped from ~57 MB to ~40 MB (Windows, x86_64) — a 28 % reduction** — from the combined effect of the psycopg2 → pg8000 swap, the three deleted deps, and the PyInstaller exclude list. Linux binary tracks similarly.

### Fixed
- **pg8000 compat: 29 `INTERVAL '%s <unit>'` SQL sites rewritten so parameters land outside the string literal**
  - Unlike psycopg2, pg8000's `format` paramstyle does not substitute `%s` inside single-quoted SQL string literals. The 29 date-range queries in `coverity_metrics/metrics.py` that used `CURRENT_DATE - INTERVAL '%s days'` (or `'%s weeks'`) were sending the literal `%s` to Postgres and failing with `invalid input syntax for type interval: "%s days"`. `execute_query_dict` caught the exception and returned `[]`, so the dashboard silently rendered zero for every affected metric on the first pg8000 build.
  - All 29 sites rewritten to `INTERVAL '1 day' * %s` (and two `INTERVAL '1 week' * %s`), which sends the integer as a proper bound parameter and multiplies against a constant interval. Same execution plan, same numeric result, driver-agnostic.
- **pg8000 compat: `db_connection` wrapper now coerces `None` params to `()` before calling `cursor.execute`**
  - psycopg2 tolerated `cursor.execute(query, None)`; pg8000's `Cursor.execute(operation, args=())` calls `len(args)` internally and raises `object of type 'NoneType' has no len()` on `None`. Both `execute_query` and `execute_query_dict` in `coverity_metrics/db_connection.py` now pass `params or ()` so callers can keep the historical `execute_query(query)` no-params style.
- **pg8000 compat: `CoverityDatabase` no longer relies on `psycopg2.connection.closed`**
  - `pg8000.dbapi.Connection` has no `.closed` attribute (psycopg2's is a driver-specific extension, not part of DB-API 2.0). Replaced the `self.connection.closed` sentinel with a `self.connection is None` check plus a `try/finally` that nulls out the handle in `close()`, giving equivalent semantics for this project's single-connection-per-instance usage pattern with no driver-specific coupling.
- **`ZipDataLoader.get_overall_summary()` now accepts the `days=` kwarg for API parity with `CoverityMetrics`**
  - Every other `metrics.get_*(days=days)` call in `dashboard.py` had a matching kwarg-accepting override on `ZipDataLoader`; `get_overall_summary()` was the one missing signature. Loading a dashboard from a `--zip-file` crashed with `TypeError: ZipDataLoader.get_overall_summary() got an unexpected keyword argument 'days'` on the first pg8000 build. The kwarg is now accepted and ignored — zip data is pre-aggregated at export time so a re-filter isn't possible or meaningful at load time.

### Notes on BDBA scan findings

**Resolved by the 1.0.30 refactor.** These were tracked as "no action available" in the 1.0.28 and 1.0.29 notes and are now gone from the binary entirely:

| Finding | Route it took into 1.0.29 binary | How 1.0.30 resolves it |
| --- | --- | --- |
| `openssl` (`libcrypto-3-x64-*.dll`, `libssl-3-x64-*.dll`, `.so` equivalents) | `psycopg2-binary` wheel | Driver swap → `pg8000` (pure Python, no OpenSSL binding) |
| `libpq` (`libpq-*.dll` / `.so`) | `psycopg2-binary` wheel | Driver swap → `pg8000` (speaks Postgres wire protocol directly) |
| `libpcre` PCRE1 (`libpcre-*.so.1.2.0`) | `psycopg2-binary` Linux wheel | Driver swap → `pg8000` |
| `krb5` (`libgssapi_krb5.so.2`, `libkrb5.so.3`, `libk5crypto.so.3`, `libkrb5support.so.0`) | `psycopg2-binary` Linux wheel | Driver swap → `pg8000` |
| `libtiff` (`PIL/_imaging.cp314-win_amd64.pyd`) | `Pillow` wheel, transitively via `matplotlib` in `requirements.txt` | `matplotlib` dropped from deps → `Pillow` no longer transitively pulled in |
| `sqlite3.dll` / `_sqlite3.pyd` | CPython, transitively via `pandas.io.sql` delayed import | Added `sqlite3` + `_sqlite3` to PyInstaller `excludes` |
| `pyexpat.pyd` | CPython, transitively via `pandas.io.xml` | Added `pyexpat` + `_elementtree` to PyInstaller `excludes` |

**Still upstream-only (no action available at project level).** These come from CPython itself and from the numpy/pandas wheels via pandas, which is still a hard runtime dependency:

| Finding | Bundling package | Our version | Newest upstream artifact |
| --- | --- | --- | --- |
| `libscipy_openblas64_-*.dll` (OpenBLAS) | `numpy` wheel (shared with SciPy since NumPy 2.0) | Latest on PyPI | Latest on PyPI |
| `VCRUNTIME140.dll` / `VCRUNTIME140_1.dll` | CPython 3.14.x | Latest patch | Latest patch |
| `msvcp140-*.dll` | `numpy` + `pandas` wheels | Latest on PyPI | Latest on PyPI |

- **On the OpenBLAS finding specifically**: BDBA labels the DLL as "proprietary" — that is a scanner metadata error. OpenBLAS is [BSD-3-Clause licensed](https://github.com/OpenMathLib/OpenBLAS/blob/develop/LICENSE) and freely redistributable; it is the same OpenBLAS binary shipped by every scientific Python distribution and by Anaconda. Since NumPy 2.0 the Windows/Linux wheels reuse SciPy's pre-built OpenBLAS artifact (hence the `libscipy_` prefix on the filename). It backs `numpy.linalg`, `numpy.fft`, and the random-number generators; numpy loads it unconditionally at package init, so it cannot be excluded without breaking `import pandas`.
- **On the Visual C++ runtime findings**: these are the standard Microsoft VC++ redistributable DLLs required by every Python C extension on Windows and by CPython itself. They are covered by Microsoft's [Visual C++ Redistributable license](https://learn.microsoft.com/en-us/cpp/windows/redistributing-the-latest-supported-visual-c-runtime), which explicitly allows free redistribution with your application; they ship with CPython, with every C-extension wheel on PyPI, and with countless Windows applications. They cannot be excluded — the binary won't start without them.
- All three refresh naturally when NumPy, pandas, or CPython publish new artifacts.


## [1.0.29] - 2026-08-19

### Changed
- **Local binary-build instructions bumped from Python 3.12 → 3.14 to match CI**
  - `.github/workflows/build-binaries.yml` has been building the `coverity-metrics` / `coverity-metrics.exe` binaries on Python 3.14 since that runner was upgraded, but `packaging/README.md` still told maintainers to create the local `.binbuild` venv with `py -3.12` / `python3.12`. Anyone following the doc ended up producing a binary against a different CPython than what CI ships to the GitHub Release, and a locally-built exe embedded an older `python3XX.dll` (older bundled sqlite3 / expat / OpenSSL surface) than the released artifact.
  - `packaging/README.md` now instructs `py -3.14 -m venv .binbuild` on Windows and `python3.14 -m venv .binbuild` on Linux so the local reproduction matches the CI matrix exactly.
  - No source-code change — the released binaries produced by CI are unaffected. Only maintainers rebuilding locally are impacted.

### Notes on BDBA scan findings (no action required)
- The 1.0.28 Windows binary produced a BDBA report flagging five bundled native libraries as behind their upstream latest:
  - `openssl` (bundled in `psycopg2_binary.libs/libcrypto-3-x64-*.dll` and `libssl-3-x64-*.dll`) — comes from the `psycopg2-binary` wheel; PyPI already ships the latest `psycopg2-binary==2.9.12`, no newer wheel available.
  - `libpq` / postgresql client (bundled in `psycopg2_binary.libs/libpq-*.dll`) — same wheel, same story.
  - `libtiff` (bundled in `PIL/_imaging.cp314-win_amd64.pyd`) — comes from the `Pillow` wheel; already on the latest `pillow==12.3.0`.
  - `sqlite3.dll` — vendored by CPython itself; already on the latest patch (3.14.7).
  - `pyexpat.pyd` (expat) — vendored by CPython itself; already on the latest patch (3.14.7).
- All five will refresh naturally when the upstream projects (`psycopg2-binary`, `Pillow`, CPython) publish new artifacts. No project-level change can accelerate this without giving up the "no Python required on the target machine" property of the standalone binary; the findings are being treated as suppressed / upstream-tracked in BDBA.

## [1.0.28] - 2026-08-18

### Fixed
- **Fallback path still under-counted Active by ~5% when `last_detected_snapshot` (LDS) was stale, because Coverity leaves `stream_defect.fixed_snapshot_element_id` pointing at the old fix when a defect reappears**
  - 1.0.27's fallback (`Active iff fixed_snapshot_element_id IS NULL`) correctly classified the vast majority of defects on stale-LDS installs but missed every defect that had been fixed and later re-detected in a subsequent snapshot: Coverity's own UI would still show them as Active, but the tool marked them Fixed. Concrete example on the same DB used in the 1.0.27 note: the affected stream on `example-project-b` reported 15 unclassified Active by the 1.0.27 rule; Coverity Connect's UI showed 20. The 5 missing defects had all been fixed at snapshot ~40200 and reappeared at snapshot ~100550, and `fixed_snapshot_element_id` never got cleared on the reappearance.
  - Extended the fallback branch of both `_ACTIVE_COND_SQL` and `_FIXED_COND_SQL` with a second disjunct: `stream_defect.introduced_snapshot_element_id > stream_defect.fixed_snapshot_element_id`. Coverity DOES update `introduced_snapshot_element_id` when it re-detects a previously-fixed defect (unlike `fixed_snapshot_element_id`, which it leaves alone), so comparing the two `snapshot_element` ids — which are monotonic on Coverity's DB — identifies the reappeared cases exactly. New rule:
    - Active iff `fixed_snapshot_element_id IS NULL` OR `introduced_snapshot_element_id > fixed_snapshot_element_id`
    - Fixed iff `fixed_snapshot_element_id IS NOT NULL` AND (`introduced_snapshot_element_id IS NULL` OR `introduced_snapshot_element_id <= fixed_snapshot_element_id`)
  - Preferred (LDS-populated) branch is unchanged — fully-fresh streams stay on strict `lds.detected_snapshot_id = sn_latest.latest_snap_id` from 1.0.25 / 1.0.26 / 1.0.27. Only the fallback path changed; every call site inherits the fix because all 60+ queries embed the same three shared constants.
  - Verified on the affected DB: the stale-LDS stream on `example-project-b` went from 15 unclassified Active → 20 (matching UI); `example-project-b` project total went from 35 → 40 (also matching UI). `example-project-a` (fully-fresh LDS) is unchanged.

## [1.0.27] - 2026-08-18

### Fixed
- **Active / Fixed defect counts silently reported zero on Coverity installs where `last_detected_snapshot` (LDS) had stopped being maintained**
  - Some Coverity Connect installs stop updating the `last_detected_snapshot` table after an upgrade or migration: every snapshot committed after that point gets zero LDS coverage. Because 1.0.25 anchored Active/Fixed strictly on LDS (and treated missing rows as *unknown* rather than active), those installs saw Active = 0 and Fixed = 0 for every affected stream. Concrete example: on a two-project DB where `example-project-a`'s snapshots (up to id 40207) all had LDS rows but `example-project-b`'s snapshots (70379+) had none, the tool reported 0/0 for `example-project-b`'s 5300 stream_defect rows while Coverity Connect's UI kept showing correct outstanding counts.
  - `_ACTIVE_COND_SQL` and `_FIXED_COND_SQL` became CASE expressions with a per-row fallback: when a defect has an LDS row the strict 1.0.25 rule is used (Active iff `lds.detected_snapshot_id = sn_latest.latest_snap_id`), and when it doesn't the CASE falls back to `stream_defect.fixed_snapshot_element_id` (Active iff NULL, Fixed iff NOT NULL). The extremes are unchanged from a healthy Coverity install (fully-fresh streams stay on strict LDS everywhere; fully-stale streams use `fixed_snapshot_element_id` everywhere) and the mixed case — a stream in transition where LDS is only partially populated — no longer drops the un-indexed tail from both buckets. Every existing call site inherits the fix because all 60+ queries embed the same three shared constants.
  - The fallback column carries a documented ~5% caveat: Coverity doesn't clear `fixed_snapshot_element_id` when a previously-fixed defect reappears, so a defect that was fixed then re-detected can look "fixed" via that column even though LDS knows it's active. On a healthy stream the LDS branch fires first per row so the caveat only applies to LDS-missing rows; the tool matches Coverity Connect's UI exactly whenever LDS is populated for the defect. (1.0.28 closes this caveat entirely via `introduced_snapshot_element_id`.)
  - Added `_check_lds_freshness()`: a lightweight probe run once per DB signature `(host, port, database, user)` per process. It populates `self._lds_stale_streams` and logs a single WARNING naming the affected streams so silent under-counting on a stale-LDS install can be diagnosed. The probe result is cached in class-level `_LDS_FRESHNESS_CACHE` / `_LDS_WARNING_EMITTED` so `dashboard`/`export` worker pools that instantiate many `CoverityMetrics` against the same DB pay for it exactly once and don't spam duplicate warnings.

## [1.0.26] - 2026-08-17

### Fixed
- **Overview → Active Defects, Defects by Severity, High Severity, and Defects by Project now agree, and all use per-stream summation**
  - The 1.0.25 fix that added `COUNT(DISTINCT COALESCE(sd.merged_defect_id, sd.id))` to `get_defects_by_severity` inadvertently made it disagree with the Active Defects card (still `COUNT(DISTINCT sd.id)`) whenever a project has multiple streams sharing defects — e.g. an `example-project` with two mirror streams (21 active defects each; merge-deduped project total 21, per-stream total 42).
  - After weighing both approaches, the per-stream sum is the intended one: each stream is analyzed and reported independently, and its active defects count towards the project total once per stream. So a project with two streams that both have 21 active defects reports 42, not 21.
  - Reverted the merge-defect deduplication introduced in 1.0.25 across every Overview count so they all use `COUNT(DISTINCT sd.id)` (each `stream_defect` row counted once): `get_overall_summary`'s `total_defects` and `high_severity_defects` (both project-scoped and global branches), `get_defects_by_severity`, and `get_total_defects_by_project`'s `defect_count` / `active_defects` / `fixed_defects` / `dismissed_defects` (all three project-scope branches).
  - All queries still exclude classifications `False Positive` and `Intentional`, so the identity `sum(defects_by_severity) == total_defects == high_severity + medium + low + unspecified` holds and matches the sum of the per-stream active counts shown in `Defects by Project` (single-project drill-down).
  - Active Defects tooltip updated to state the per-stream semantics explicitly.

- **Code Quality → Code Metrics by Stream reported an inflated `file_count` and diluted `avg_file_loc`**
  - Each `stream_element` accumulates its `stream_file` rows for the entire life of the stream: files that no longer exist in the codebase stay as rows but have all `current_*_line_count` columns zeroed. `COUNT(DISTINCT sf.id)` therefore counted every file that has ever been part of the stream, and `AVG(current_code_line_count)` was diluted by thousands of zero-LOC historical rows. Concrete example on a single stream of an `example-project`: the table showed **11 214 Files** with an avg-file-LOC of **~0.4** while Coverity Connect shows 30 files and 149.5 LOC/file.
  - The SUMs (`total_loc`, `total_comment_lines`, `total_blank_lines`) were already correct because zero rows contribute 0 to a SUM, and `comment_ratio_pct` was also correct because it's a ratio of those SUMs.
  - Added a WHERE filter `GREATEST(current_code, 0) + GREATEST(current_comment, 0) + GREATEST(current_blank, 0) > 0` so aggregates count only the files currently present in the stream. `file_count` and `avg_file_loc` now match Coverity Connect's per-stream figures; nothing else changes.

- **Triage Classification by Stream was hiding False Positive and Intentional buckets**
  - `get_triage_trends` (which powers the *Triage Classification by Stream* chart) explicitly excluded `False Positive` and `Intentional`, so streams with those classifications showed only `Bug` and `Unclassified`. Concrete example on an `example-project`: the project has 2 Intentional-classified defects that never appeared on the chart.
  - Removed the `de.name NOT IN ('False Positive','Intentional')` filter and updated the docstring — the metric now shows every triage bucket Coverity Connect displays (Bug, False Positive, Intentional, Pending, Untriaged, …) plus the `Unclassified` bucket for defects that have no triage row yet. The primary ordering by unclassified-count-per-stream is unchanged, so streams needing triage attention still surface at the top.

- **Dashboard back-navigation went straight to the aggregated view from every level**
  - Project-level and instance-level dashboards both rendered a single *"Back to All Instances"* button that pointed at `../dashboard_aggregated.html`. On a project page this skipped over the instance dashboard entirely, and on single-instance deployments (where no aggregated dashboard is generated) the same button would still render on the project page and 404.
  - The button is now only rendered on the instance-level dashboard (when an aggregated dashboard actually exists) and links to `../dashboard_aggregated.html`. Project pages already surface the *"Show All"* control next to the project filter for returning to the instance dashboard, so no separate back button is needed there. Single-instance runs correctly render no back button on the instance page either.

- **Overview → Total Files / Lines of Code / Functions were reporting cumulative history instead of current codebase size**
  - `get_overall_summary`'s `total_files`, `total_functions`, and `total_loc` queries counted / summed over `stream_file` and `stream_function` joined through `stream_element`. Because `stream_element` rows are created per snapshot and both child tables attach to a specific `stream_element`, the counts summed every historical snapshot's file / function / LOC records in scope. Concrete example on an `example-project` (2 streams × ~30 files each in the latest snapshot): Coverity Connect's UI shows Total Files = 60, the dashboard was showing 11 244; the same inflation applied to `total_loc` and `total_functions`.
  - All three now use the per-snapshot aggregates on the `snapshot` table (`total_file_count`, `function_count`, `code_line_count`) taken from the latest non-deleted snapshot per stream — the exact numbers Coverity Connect displays. Optionally restricted to snapshots committed within the `--days` trend window; streams with no snapshot in the window contribute 0. When `days` is not supplied (e.g. `coverity-metrics` console report) the query falls back to "latest non-deleted snapshot per stream regardless of age", which is also correct. Negative sentinel values in `snapshot.code_line_count` are clamped to 0 the same way as elsewhere in the codebase.
  - `get_overall_summary` now accepts an optional `days` argument. `coverity-dashboard` and `coverity-export` forward the CLI's `--days` value; other callers keep working with the unwindowed fallback.
  - The Overview tab's "Total Files", "Lines of Code", and "Functions" tooltips now describe the new semantics and cite the active trend window via `trend_period_text`.

### Changed
- **Overview → Active Defects tooltip clarified**
  - Previous wording claimed the count excluded "dismissed" defects, but the query only filters classifications `False Positive` and `Intentional` — dismissive triage actions such as `Ignore` are *not* filtered. Tooltip now says so explicitly and describes the underlying "still detected in the latest snapshot of each stream" definition.

## [1.0.25] - 2026-08-14

### Added
- **Active / Fixed defect counts are now anchored on Coverity Connect's own snapshot aggregates**
  - `get_total_defects_by_project` now uses `snapshot.total_defect_count` on the latest non-deleted snapshot per stream (summed across the streams in scope) as the source of truth for Active — the exact same figure Coverity Connect's own UI shows in its "Outstanding" column
  - Fixed is derived as `defect_count - Active - Dismissed` so the row invariant still holds; Active is clamped so it can't exceed `defect_count - dismissed_defects`
  - Works whether `last_detected_snapshot` is populated or not; healthy DBs where the two paths already agree are a no-op
  - Applies to all three variants (multi-project, single-project per-stream drill-down, all-projects)
  - Verified against the example-project case: latest snapshot `total_defect_count = 83522`, newly eliminated `= 12`, stream_defect count `= 83534` → Active = 83522, Fixed = 12 (previously reported 83534 / 0)

### Fixed
- **Active / Fixed / High-severity defect counts didn't match Coverity Connect's UI on multi-stream projects**
  - Two independent bugs compounded: (a) the "active" predicate was flipped around a few times while chasing this, and (b) `COUNT(DISTINCT sd.id)` counted the same defect once per stream instead of once per merged defect. Concrete example on an `example-project` (two mirror streams): Coverity Connect shows 21 active defects (3 High / 2 Medium / 16 Low by Impact), the tool was reporting 12 High.
  - Fix: (1) `_ACTIVE_COND_SQL` is back to the strict `lds.detected_snapshot_id = sn_latest.latest_snap_id`; `_FIXED_COND_SQL` is the strict `IS NOT NULL AND != latest`. Rows where `last_detected_snapshot` has no entry (a small tail on typical DBs) are treated as unknown and fall through both buckets rather than being force-fed into one. (2) Every defect-count query in `get_total_defects_by_project`, `get_defects_by_severity`, and `high_severity_defects` now counts `DISTINCT COALESCE(sd.merged_defect_id, sd.id)`, so a defect present in multiple streams is counted once — matching Coverity Connect's project-level UI.
  - `get_defects_by_severity` continues to bucket by `checker_properties.impact` (which Coverity Connect surfaces as "Severity" in the UI). Verified on the `example-project`: 3 / 2 / 16.
  - Removed the snapshot-aggregate fallback (`_apply_snapshot_active_fallback`, `_snapshot_active_by_project`, `_LATEST_SNAPSHOT_PER_STREAM_SQL`) that was introduced as a workaround — it can't de-duplicate merged defects across streams and is no longer needed once the primary path is correct.

- **Function Complexity Distribution and Most Complex Functions were joining on the wrong ids**
  - Both metrics did `JOIN function_metrics fm ON sf.function_id = fm.id` (or `f.id = fm.id`). Neither `stream_function.function_id` nor `function.id` is a foreign key to `function_metrics.id` — the two id spaces just happen to overlap coincidentally for a small subset of rows. On `example-project` the tool was reporting **185 functions with complexity metrics** when Coverity Connect's latest snapshot shows **21,153**.
  - The correct linkage in Coverity's schema is `stream_function -> function_instance -> function_metrics`, where `function_instance` records per-snapshot-range metric revisions and is FK-linked to both sides. Filtering to `function_instance.snapshot_end_id IS NULL` restricts to instances present in the latest snapshot; deduping to `MAX(complexity)` per `sf.id` collapses the rare case where a stream_function has multiple current instances.
  - Both `get_function_complexity_distribution` and `get_most_complex_functions` now use the corrected joins. Verified on `example-project`: 21,153 functions total, split 19263 Low / 1089 Moderate / 513 High / 246 Very High / 42 Extreme — matching Coverity Connect exactly.

- **Total Lines of Code (and derived KLOC ratios) could render as a negative number**
  - Coverity Connect uses negative sentinel values (typically `-1`) in `stream_file.current_code_line_count` / `current_comment_line_count` / `current_blank_line_count` and `snapshot.code_line_count` for files or snapshots where line counting couldn't be done (binary files, generated code, parse failures, etc.). On projects with enough such files the sentinels dragged the SUM below zero
  - Every aggregation over those columns now uses `SUM(GREATEST(COALESCE(x, 0), 0))` (and the per-file / per-snapshot readouts use `GREATEST(COALESCE(x, 0), 0)`), so sentinels contribute zero instead of a negative delta. Affected metrics: `get_defect_density_by_project`, `get_code_metrics_by_stream`, `get_overall_summary` (both project-scoped and global `total_loc`), `get_file_hotspots`, `get_snapshot_details`
  - Downstream `defects_per_kloc`, `avg_file_loc`, and `comment_ratio_pct` figures inherit the fix automatically since they reuse the same clamped aggregate

## [1.0.24] - 2026-08-13

### Added
- **`--config` / `-Config` passthrough on the quickstart scripts**
  - Both quickstart scripts now accept `--config FILE` (bash) / `-Config FILE` (PowerShell) to run against an existing `config.json` instead of the `COVERITY_DB_*` environment-variable block
  - When `--config` is passed the placeholder-password guard is skipped (since credentials come from the file), and the path is forwarded to the binary as `--config <path>`. Multi-instance configuration is supported this way
  - The pre-run banner now includes a `Config : <path>` (or `Config : <env vars>`) line so the mode is unambiguous

### Documentation
- README now has a "Finding the database credentials in your Coverity Connect installation" section that maps `cim.properties` keys onto `config.json` fields / `COVERITY_DB_*` env vars, with `grep` / `Select-String` recipes for Linux and Windows and a note about the bundled Postgres port being `5433` by default

### Fixed
- **`coverity-dashboard` single-instance auto mode crashed with `_path_exists: path should be string, bytes, os.PathLike or integer, not NoneType`**
  - When `--config` was not passed (default `config.json` auto-fallback or env-var mode) and a single instance was configured, the auto-generated aggregated dashboard step called `MultiInstanceMetrics(args.config)` with `args.config = None`, which crashed inside `os.path.exists`
  - Now uses the resolved config path (same one used by the multi-instance branch). The aggregated cross-instance dashboard is also correctly skipped when `aggregated_view.enabled` is `false` or absent, and always skipped in env-var mode (which has no file to hand to `MultiInstanceMetrics`)
  - The dashboard count line no longer promises `1 aggregated` when none will be generated

- **TLS escape hatches on the quickstart scripts**
  - Fixes `curl: (60) SSL certificate problem: unable to get local issuer certificate` on hosts behind SSL-inspection proxies or with an outdated CA bundle
  - [scripts/coverity-export.sh](scripts/coverity-export.sh): new `--cacert PATH` flag (or `CURL_CA_BUNDLE` / `SSL_CERT_FILE` env var) forwards a trusted CA bundle to every curl call. New `--insecure` flag adds `curl -k` as a last-resort escape hatch, with a warning
  - [scripts/coverity-export.ps1](scripts/coverity-export.ps1): new `-Insecure` switch installs a per-run `ServerCertificateValidationCallback` for the script's `Invoke-RestMethod` / `Invoke-WebRequest` calls, with a warning; nothing outside the script is affected
  - Both TLS options apply only to the GitHub API tag lookup and the binary download — they don't affect the Postgres connection or anything downstream

- **`--workers` / `-Workers` passthrough on the quickstart scripts**
  - [scripts/coverity-export.sh](scripts/coverity-export.sh) gains a `--workers N` flag; [scripts/coverity-export.ps1](scripts/coverity-export.ps1) gains a `-Workers N` parameter
  - Both default to `1` (matching the underlying `coverity-metrics export` default) and are forwarded verbatim as `--workers N` to the binary. The binary still clamps to 1..8; each worker opens its own Postgres connection
  - The banner printed before the run now includes a `Workers : N` line so it's clear what was passed

## [1.0.23] - 2026-08-13

### Added
- **Quiet-by-default output for `coverity-export`**
  - The per-metric `[SKIP] project/metric: No data` lines are no longer printed by default — on large instances they were burying the useful log output under thousands of lines of noise
  - A one-line summary is printed at the end: `[INFO] Skipped N metrics with no data across M project(s). Pass --verbose to see per-metric details.`
  - New `--verbose` / `-v` flag restores the previous per-metric logging when you actually want it
  - `[ERROR]` and `[WARNING]` lines are always shown, so real problems remain visible
  - Quickstart scripts pass through: `--verbose` on `coverity-export.sh`, PowerShell's built-in `-Verbose` common parameter on `coverity-export.ps1`

## [1.0.22] - 2026-08-13

### Added
- **Quickstart scripts for end users (Linux + Windows)**
  - New [scripts/coverity-export.sh](scripts/coverity-export.sh) (bash) and [scripts/coverity-export.ps1](scripts/coverity-export.ps1) (PowerShell) download the coverity-metrics standalone binary for the given release tag from GitHub Releases, set the required `COVERITY_DB_*` environment variables (with placeholder values users edit at the top of each script), and run `coverity-metrics export` — no Python install needed on the host
  - Flags mirror the underlying CLI: `--tag vX.Y.Z` (default: latest, resolved via the GitHub API), `--output`, `--days`, `--project`, `--anonymize`, `--no-snapshots`, `--no-leaderboards`
  - Refuses to run while `COVERITY_DB_PASSWORD` is still the placeholder value so an unedited copy can't accidentally trigger a real export
  - Downloaded binary is cached under `./bin/` next to the script (override with `BIN_DIR` env var / `-BinDir` parameter) so subsequent runs skip the download

- **`coverity-export` and `coverity-dashboard` single-instance configuration via environment variables**
  - When `--config` is not passed (and `--zip-file` is not passed for the dashboard), both tools now look for `COVERITY_DB_HOST`, `COVERITY_DB_NAME`, `COVERITY_DB_USER`, and `COVERITY_DB_PASSWORD` in the environment and run against that instance — no config file needed. Optional: `COVERITY_DB_PORT` (default `5432`), `COVERITY_INSTANCE_NAME` (default `Coverity`)
  - Precedence at startup: (1) explicit `--config <file>`; (2) env vars if all required are set (single-instance, prints an `[INFO]` line); (3) a `config.json` in the current directory (backward-compatible auto-fallback); (4) otherwise exits with an error listing both options
  - Multi-instance configuration is still supported via `--config`; env-var mode is single-instance only
  - For `coverity-dashboard`, ZIP mode (`--zip-file`) is unchanged — it never required DB credentials
  - `coverity-metrics` (the console report CLI) is unchanged and still requires `config.json`

## [1.0.21] - 2026-08-13

### Added
- **PyPI publishing from GitHub Actions on tag push**
  - New `publish-pypi` job in `.github/workflows/build-binaries.yml` builds `sdist` + `wheel` and uploads to PyPI whenever a `v*` tag is pushed, so the PyPI release and the GitHub Release land at the same version at the same time
  - Uses PyPI **Trusted Publishing (OIDC)** by default (no long-lived token in the repo); automatically falls back to a `PYPI_API_TOKEN` repository secret if one is set (job-level `HAS_PYPI_TOKEN` flag decides which publish step runs)
  - Runs under a GitHub `pypi` environment so you can gate the publish behind required reviewers if desired
  - Guardrail step verifies that the pushed tag (`v1.2.3`) matches `coverity_metrics/__version__.py` (`1.2.3`) and fails the workflow if they diverge

- **CHANGELOG-driven GitHub Release body**
  - New "Extract CHANGELOG section for this version" step in the `release` job uses `awk` to slice the section for `${GITHUB_REF_NAME#v}` from `CHANGELOG.md` (from `## [<ver>]` up to the next `## [` heading) into `release-notes.md`
  - The GitHub Release now uses that file as `body_path`, so release notes always mirror the CHANGELOG. Auto-generated "What's Changed" (PR/commit list) is still appended below via `generate_release_notes: true`
  - Falls back to a generic `Release <tag>.` body with a workflow warning if no matching CHANGELOG entry is found

### Changed
- **`release.ps1` simplified to "bump + docs + tag" only**
  - The script no longer builds wheels, uploads to PyPI, verifies installs in a temp venv, or calls the GitHub Releases API — all of that is now done by GitHub Actions on tag push
  - New responsibilities: bump `coverity_metrics/__version__.py`, refresh dates in `CHANGELOG.md` / `RELEASE_NOTES.md`, `git add` those files, commit with `Release v<version>`, push the current branch, then create and push the annotated `v<version>` tag that triggers the CI release workflow
  - Aborts by default if the working tree is dirty (`-AllowDirty` overrides). Tolerates "nothing to commit" so re-runs for the same version don't error out
  - New / renamed flags: `-Remote` (default `origin`), `-Branch` (default = current HEAD), `-CommitMessage`, `-SkipCommit`, `-SkipTag`, `-AllowDirty`. Removed all PyPI / twine / install-verify / GitHub-API / TestPyPI flags
  - `-DryRun` now previews every git command as well, without running any of them

- **`release` job now waits on PyPI publish**
  - The `release` job depends on both `build` and `publish-pypi` (`needs: [build, publish-pypi]`), so the GitHub Release page (with attached Windows/Linux binaries) only appears after PyPI has accepted the upload. Same tag → same version live on PyPI and GitHub simultaneously

## [1.0.20] - 2026-08-11

### Added
- Added `fetch_all` parameter to metrics methods for retrieving all data instead of just top N results
- Enhanced CLI parameter documentation in README

### Changed
- Updated Python library usage examples in README

### Fixed
- Bug fixes and improvements

## [1.0.19] - 2026-08-06

### Added
- **Optional Snapshots (`coverity-export --no-snapshots`)**
  - New `--no-snapshots` opt-out flag on `coverity-export` skips the `snapshot_commands` metric (recorded `cov-build`/`cov-analyze` command lines, invoker, host, platform). Useful when build-machine hostnames, usernames, or filesystem paths embedded in command lines should not leave the environment
  - Project dashboards rendered from the resulting ZIP auto-hide the 📸 Snapshots tab (button + content). No dashboard-side flag needed — the existing template guard on `snapshot_commands` handles it

- **Optional Leaderboards (`coverity-export --no-leaderboards`)**
  - New `--no-leaderboards` opt-out flag on `coverity-export` skips the five leaderboard metrics — `top_projects_by_fix_rate`, `top_projects_by_triage_activity`, `top_users_by_fixes`, `top_triagers`, `most_collaborative_users` — at both instance and project scope. Useful when user identities (usernames, real names, committer info) must not leave the environment, or to shrink export size / runtime
  - `coverity-dashboard` auto-detects the absence of leaderboard data (either because `--no-leaderboards` was used or because the ZIP predates leaderboard export): the 🏆 Leaderboards tab button and its tab content are hidden via a new `has_leaderboards` template flag. No config knob to set on the dashboard side — it just works
  - Individual `--project` dashboards inherit the same behavior; nothing else on the page changes

- **Anonymized exports for safe sharing (`coverity-export --anonymize`)**
  - New `--anonymize` opt-in flag on `coverity-export` replaces every real project name with a sequential `project_NNN` id and every real stream name with `stream_NNN` inside the produced ZIP — directory names, `metadata.json` (`projects` list + `project_specific_exports` keys), and every `project_name`/`stream_name` column in the exported JSON files are all rewritten in one pass
  - The reverse mapping is written to a **sibling** file next to the ZIP: `coverity_export_<instance>_<timestamp>.mapping.json`. The ZIP alone cannot be de-anonymized — keep the mapping file private
  - Optional `--mapping-file <path>` loads an existing mapping so ids stay stable across re-exports (same project always gets the same `project_NNN`). New projects get the next available id and the (extended) mapping is written back to the same path
  - New `coverity_metrics.anonymizer.Anonymizer` module provides the underlying `project_id()` / `stream_id()` / `apply_to_dataframe()` / `save()` / `load()` primitives (unit tests in `test_anonymizer.py`)
  - Instance names, host, database, and user/committer names are **not** anonymized (out of scope for this release)
  - Dashboard side is untouched: an anonymized ZIP is just a ZIP with cryptic names, and `coverity-dashboard` renders `project_001`, `stream_001`, … as-is

- **Sort control on the OWASP Top 10:2025 category cards**
  - New toolbar above the category cards on project dashboards lets you re-order the ten cards in-place: `Category (A01 → A10)` (default) or `Priority Score (highest first)`
  - Sort is entirely client-side via `data-category` / `data-priority` attributes on each card and a small `sortOwaspCards()` function — no re-render, no server round-trip. Ties on priority fall back to A01→A10 for a stable order
  - Priority Score = `defects × Exploit × Impact ÷ 100`, where `Exploit` and `Impact` are the **Avg Weighted Exploit** and **Avg Weighted Impact** columns from each category's Score table on <https://owasp.org/Top10/2025/> (CVSS-derived, 0–10). Attribution is shown to the right of the toolbar
  - Interpretation: A03 (Software Supply Chain Failures) has the highest per-defect multiplier (0.427) because Exploit=8.17, Impact=5.23 — one supply-chain defect ≈ 2.2× the risk of one Broken-Access-Control defect (0.270). This gives teams evidence-based ordering rather than "fix A01 first because it's #1"

- **Exploit / Impact / Priority mini-badges on every FAILED category card**
  - Each FAILED card (A01…A10) now renders three additional inline badges next to the High/Medium/Low severity badges: `Exploit: X.XX`, `Impact: Y.YY`, `Priority: Z.Z`, styled with the existing `severity-badge severity-{high,medium,low}` classes (thresholds — Exploit: ≥7.5 high / 5.0–7.5 medium / else low; Impact: ≥4.5 / 3.0–4.5 / else)
  - PASS cards (0 defects) intentionally omit these badges to keep the "everything green" view uncluttered

### Changed
- **`OWASP_TOP_10_2025` entries now carry a `score_data` sub-dict**
  - Every category now has `"score_data": {"exploit_score": float, "impact_score": float}` alongside the existing `description` and `cwe_ids` fields. Values are copied verbatim from the "Avg Weighted Exploit" and "Avg Weighted Impact" columns of each category's Score table on owasp.org/Top10/2025/
  - `get_owasp_top10_metrics()` in `metrics.py` now emits three new DataFrame columns (`exploit_score`, `impact_score`, `priority_score`); existing columns and the A01→A10 sort order are unchanged
  - Public helpers `get_owasp_category_for_cwe()` and `get_all_owasp_categories()` untouched — no downstream call-sites needed to change

- **Sortable columns on the instance-level "Defects by Project" table**
  - Column headers (Project/Stream Name, Total Defects, Active, Fixed, Dismissed) are now clickable; click toggles ascending/descending order using the existing generic `sortTable()` helper
  - Also applies to the "Defects by Stream" variant of the same table on project dashboards
  - Numeric columns sort numerically (extracting digits from the badge text); the name column sorts as text via `localeCompare`

- **Dismissed defects column on "Defects by Project / by Stream" table**
  - New `Dismissed` badge column (styled `severity-medium`, sortable) added to both project and instance dashboards
  - Backed by `dismissed_defects` in `CoverityMetrics.get_total_defects_by_project()` — counts rows whose classification is `False Positive` or `Intentional`
  - Table tooltip updated to note that Active / Fixed / Dismissed are now mutually exclusive and sum to Total

- **Avg Scans / Week on the "Scan Activity Over Time" section**
  - Project and instance dashboards render two summary cards ("Avg Scans / Week", "Total Scans") above the chart. Computed by new `_compute_avg_scans_per_week(scan_activity_trend, days)` helper in the dashboard CLI as `total_scans / span_weeks`, where `span_weeks` is the distance between the first and last observed scan bucket (floored at one week). Using the active span rather than the full `--days` window keeps sparse legacy projects from rounding to 0 (e.g. 9 scans across a ~9-day span with `--days 3650` now renders 7.0, not 0.0). Falls back to `days / 7` when `period` values are missing or unparseable
  - Multi-instance aggregated dashboard adds a per-instance summary table (Instance / Total Scans / Avg Scans/Week) above `#agg-scan-activity-chart`, with a color swatch matching each instance's line in the chart. Enrichment done in `generate_aggregated_dashboard` (reuses the same helper)

### Changed
- **`fixed_defects` no longer double-counts dismissed defects**
  - `get_total_defects_by_project()` previously counted "False Positive" and "Intentional" as *both* fixed and dismissed, which broke the invariant `active + fixed + dismissed == total`
  - `fixed_defects` is now strictly `defect_state = 'Fixed'` (excluding dismissed); dismissed lives only in the new `dismissed_defects` column

### Fixed
- **`--anonymize` mapping file contained phantom `project_NNN` entries for stream names**
  - `get_total_defects_by_project()` re-uses the alias `SELECT s.name AS project_name` when scoped to a single project — the `project_name` column then holds *stream* names, not project names. The anonymizer was routing those values through `project_id()` and creating a new `project_NNN` entry per stream, inflating the mapping (e.g. 645 real projects grew into 1,652 project entries in a full production export)
  - `Anonymizer.apply_to_dataframe` now accepts a per-metric `_EXTRA_COLUMNS` override: at single-project scope, `total_defects_by_project`'s `project_name` column is treated as a stream, so those names map to `stream_NNN` and the projects map contains only real projects
  - `export_instance_to_json` also switches to single-project semantics when `--project X` selects exactly one project (that mode causes several metrics — `total_defects_by_project`, `top_projects_by_classification` — to emit stream-per-row data under project-column aliases even at instance scope)
  - `pip install -e .` is required to pick this up if you had previously done `pip install .`. Existing `.mapping.json` files carrying phantom entries are unusable as `--mapping-file` inputs — delete them so a fresh mapping is built

- **`owasp_mapping.py` was OWASP Top 10:2021 spec mislabeled as 2025**
  - Category strings claimed `A01:2025`–`A10:2025` but content matched the 2021 ranking — e.g. `A03:2025-Injection`, `A10:2025-Server-Side Request Forgery`, `A09:2025-Security Logging and Monitoring Failures`, none of which are correct for 2025
  - Fully rewrote against https://owasp.org/Top10/2025/. All 10 categories now match the official 2025 ranking and CWE lists exactly (249 unique CWEs total; per-category counts verified against each page's Score table: 40/16/6/32/37/39/36/14/5/24)
  - Key semantic corrections: **CWE-476 (NULL Pointer Dereference)** now correctly maps to `A10:2025-Mishandling of Exceptional Conditions` (new 2025 category) instead of being unmapped; **CWE-918 (SSRF)** now maps to `A01:2025-Broken Access Control` (SSRF folded into A01 for 2025); `A03` is now `Software Supply Chain Failures` (2021 A06 broadened); `A06` is now `Insecure Design` (moved down from 2021 A04); the 2021 categories `Vulnerable and Outdated Components` (was A06) and `SSRF` (was A10) are gone
  - `OWASP_TOP_10_2025` variable name and public helpers `get_owasp_category_for_cwe()` / `get_all_owasp_categories()` preserved — no downstream callers in `metrics.py` had to change

- **`release.ps1` post-install CLI verification failed with "not recognized as an internal or external command"**
  - `Invoke-Step` runs its command via `cmd.exe /c $Command`. When the venv path had spaces or was on the fallback `.pkgtest_<timestamp>` path (used when the primary `.pkgtest` couldn't be deleted), cmd.exe's quote-stripping mangled `"C:\...\coverity-dashboard.exe" --help` and reported the whole quoted path as an unknown command
  - The two CLI verification calls at the end of the script now bypass `Invoke-Step` and invoke the .exe directly with PowerShell's `&` operator, which handles paths with spaces natively. Exit codes are still checked and propagated as before
  - Note: the rest of the release (build, upload, tag, GitHub release) had already completed before the old verify step failed, so 1.0.18 was actually published — this fix simply keeps the verification step from producing a spurious failure on subsequent releases

## [1.0.18] - 2026-08-04

### Fixed
- **Daily Fix Efficiency % always showed 0% when fixes and introductions happened on different days**
  - `get_defect_velocity_trend` computed `fix_efficiency_pct = Fixed / New * 100` with an early `WHEN new_count = 0 THEN 0` branch, so any day that had fixes but no newly-introduced defects collapsed to 0% — which is the common case, since fixes rarely land in the same daily snapshot as the defects they resolve
  - The dashboard tooltip already promised the correct formula: `Fixes / (Fixes + Introductions) × 100%`. The SQL now matches: `Fixed / (New + Fixed) * 100`, with a single divide-by-zero guard when both are 0
  - Real-world example: `example-project` — 5 new defects introduced 2023-05-08, all 5 fixed 2023-05-17. Old behaviour: fix efficiency = 0% on every row of the trend. New behaviour: 2023-05-17 correctly shows 100%, matching the aggregate `fix_rate_metrics.fix_rate_percentage = 100%`

## [1.0.17] - 2026-08-04

### Added
- **Scan Activity Over Time Chart**
  - New Trends & Progress section on every project and instance dashboard showing snapshot/commit counts bucketed over time (daily for per-project, weekly for instance-wide)
  - Secondary y-axis overlays unique committers per bucket so the chart tells both "how often" and "who"
  - Aggregated multi-instance dashboard adds a per-instance overlay chart — one colored line per instance — for cross-instance cadence comparison
  - Backed by new `CoverityMetrics.get_scan_activity_trend(days, granularity)` and `MultiInstanceMetrics.get_aggregated_scan_activity(days, granularity)`
  - ZIP exports now include `scan_activity_trend.json` at both project and instance levels; `ZipDataLoader` exposes `get_scan_activity_trend()` and returns an empty DataFrame gracefully when reading pre-1.0.17 ZIPs

- **Parallel Per-Project Export & Dashboard Generation**
  - New `--workers N` (`-w`) flag on both `coverity-export` and `coverity-dashboard` — default 1, clamped to 1–8
  - In database mode each worker gets its own `CoverityMetrics` instance (and therefore its own Postgres connection); psycopg2 connections aren't thread-safe, so no sharing
  - In ZIP mode each worker gets its own `ZipDataLoader` (ZipFile handles aren't thread-safe)
  - Auto-mode dashboard generation and per-instance export loops both parallelized with `concurrent.futures.ThreadPoolExecutor`
  - Typical wins: 4–6× at `--workers 4` for the database export path, ~2–3× for the ZIP dashboard path
  - Per-project exceptions are logged and the loop continues, matching current behaviour

- **Execution Time Reporting**
  - Both `coverity-export` and `coverity-dashboard` print `Total execution time: …` at the end (via a `finally` block, so it fires even on failure)
  - Export additionally prints per-instance timing, e.g. `Time: 4m 12.3s for 645 projects (~0.39s/project)`
  - Human-readable format: `8.7s`, `2m 5.3s`, or `1h 15m 23s`

- **`--version` Flag on `coverity-dashboard`**
  - Prints `coverity-dashboard version: X.Y.Z` and exits. Brings the dashboard CLI in line with `coverity-export` and `coverity-metrics`, which already supported `--version`. Handler short-circuits before the timing wrapper so no execution-time line is printed.

- **📸 Snapshots Tab on Project Dashboards — Recent Analysis Command Lines**
  - New project-only tab (📸 Snapshots) shows the exact `cov-build` and `cov-analyze` invocations recorded for the most recent 10 snapshots on the project — mirrors the "Command Line" data shown per snapshot in the Coverity Connect UI
  - Each snapshot is a collapsible entry displaying stream, timestamp, invoker (user), host, and platform; expanding reveals a per-element block (`Build / Capture` and `Static Analysis`) with runtime, success/failure counts, and the full command in a preformatted block
  - Backed by new `CoverityMetrics.get_snapshot_commands(limit=20)` which joins `snapshot` → `snapshot_element` and filters by project via `project_stream`/`project`
  - ZIP exports now include `snapshot_commands.json` under `{instance}/{project}/`; `ZipDataLoader.get_snapshot_commands()` reads it and returns an empty DataFrame gracefully when opening pre-1.0.17 ZIPs
  - Tab button and section are hidden automatically when there are no command rows to show (e.g. instance-level dashboards or projects with no committed snapshots)

### Changed
- **Instance-scoped `CoverityMetrics` reuse across projects**
  - Both the export CLI and the dashboard CLI now build one `CoverityMetrics` per instance and rescope via the `.project_name` property between projects
  - Eliminates ~N-1 redundant Postgres connect + auth handshakes per instance (previously one per project)
  - Redundant `get_available_projects()` call at the top of the per-instance export loop removed
- **Jinja `Environment` and inline CSS cached at module scope**
  - `Environment(loader=FileSystemLoader(...))`, template loading, and the inline CSS payload are now built once per process and reused across every project dashboard render, instead of re-created hundreds of times
- **"Scan Activity Over Time" empty-state message**
  - When there are no snapshots in the analysed window, project and instance dashboards now show an inline info alert ("No scan activity in the last N days") instead of silently hiding the section — makes it clear the metric ran and returned nothing, versus the section being disabled
- **Single-source-of-truth for the package version**
  - `pyproject.toml` now uses `dynamic = ["version"]` + `[tool.setuptools.dynamic] version = {attr = "coverity_metrics.__version__.__version__"}` — the wheel metadata is stamped from `__version__.py` at build time, so future releases only need to bump one file

### Fixed
- **Graceful DB errors**
  - `CoverityDatabase.execute_query()` and `execute_query_dict()` now wrap the query with `try/except`, log a warning via the module logger, roll the connection back, and return `[]` on any error. Callers receive an empty DataFrame instead of a traceback; the process no longer aborts if a single query fails
- **Division-by-zero in leaderboard queries**
  - `avg_fixes_per_day` in `get_top_projects_by_fix_rate` wrapped in `NULLIF(EXTRACT(EPOCH FROM ...), 0)` so projects with a single snapshot or same-timestamp snapshots return `NULL` instead of raising `division by zero`
  - Audited every other SQL division in `metrics.py` and `multi_instance_metrics.py` — all remaining sites are either dividing by a constant, guarded by `CASE WHEN ... > 0`, wrapped in `NULLIF`, or guarded by a Python `if x > 0` check
- **Jinja `|round()` on `None` values**
  - Every leaderboard cell that reads from a `NULLIF`-guarded SQL column (`avg_fixes_per_day`, `avg_triage_per_day`, `avg_comments_per_day`, `triage_percentage`) now uses `{{ field|round(2) if field is not none else 'N/A' }}` — fixes crashes when a NULLIF returns `NULL` and the template tries to round it
  - Aggregated dashboard's per-instance `triage_completion` fixed at the source (`multi_instance_metrics.py`) — `dict.get(k, 0)` returns `None` when the key exists with value `None`, so callers now use `.get(k) or 0` to convert `None`/missing to `0`
- **`AttributeError: 'ZipDataLoader' object has no attribute 'get_scan_activity_trend'`** when opening a dashboard from a pre-1.0.17 ZIP export — `ZipDataLoader` gained the method and returns an empty DataFrame if the metric isn't in the ZIP

- **Ctrl+C responsiveness during parallel runs**
  - `ThreadPoolExecutor`'s implicit `shutdown(wait=True)` at the `with` block exit was blocking Ctrl+C until every in-flight worker finished — on a 645-project run that made the CLI look frozen for minutes
  - All three parallel sites (export, dashboard DB-mode, dashboard ZIP-mode) now build the executor explicitly, catch `KeyboardInterrupt` around the `as_completed` loop, cancel every pending future, call `executor.shutdown(wait=False, cancel_futures=True)`, and re-raise
  - Both `coverity-export` and `coverity-dashboard` catch `KeyboardInterrupt` at the top level and exit cleanly with code 130 (`[INTERRUPTED] Aborted by user.`)
  - Effect: first Ctrl+C now drops all queued tasks immediately; only currently-executing DB queries or renders need to finish (typically seconds). A second Ctrl+C hard-kills the process.

- **Individual Contributors leaderboards ignored `--days`**
  - All five leaderboard queries in `dashboard.py` were hardcoded to `days=30`, so a dashboard generated with `--days 3650` still showed "Last 30 Days" cards. Now `top_projects_by_fix_rate`, `top_projects_by_triage`, `top_users_by_fixes`, `top_triagers`, and `most_collaborative_users` all pass the CLI-supplied `days` value
  - Template subtitles and tooltips replaced literal "Last 30 Days" with `{{ trend_period_text }}` so the cards match the dashboard's actual analysis window
  - Removed stale "improvement percentage (last 90 days)" fragment from the Project Performance tooltip — the Most Improved card was removed in 1.0.13
- **`get_top_users_by_fixes` did not filter by the `days` window at all**
  - The SQL for Top Fixers ignored the `days` parameter entirely — it aggregated all history regardless of the requested window
  - Added `AND ts.date_created >= CURRENT_DATE - INTERVAL '%s days'` to the `last_triagers` CTE in both the project and instance branches, and threaded `days` into the parameter tuples
- **Individual Contributors on project ZIP dashboards showed instance-wide rankings**
  - `ZipDataLoader.get_top_users_by_fixes`, `get_top_triagers`, and `get_most_collaborative_users` called `_read_json_from_zip(self._get_metric_file(...))` directly, bypassing `self.project_name`, so project-level dashboards always displayed instance-wide user rankings
  - Switched all three methods to `_read_metric_json(...)`, which checks `{instance}/{project}/{metric}.json` first and falls back to empty when the project file is absent — matching how other project-scoped metrics behave
  - `export_project_specific_metrics` now writes `top_users_by_fixes.json`, `top_triagers.json`, and `most_collaborative_users.json` under `{instance}/{project}/` so the project-scoped files exist in new ZIPs. **Pre-1.0.17 ZIPs won't contain these files**, so project user leaderboards will be hidden until the ZIP is re-exported
  - Instance-level and project-level leaderboard exports now use the CLI `days` value instead of hardcoded 30
- **Cached dashboard path dropped the Individual Contributors cards entirely**
  - `_collect_and_cache_metrics` in `dashboard.py` was setting `top_users_by_fixes`, `top_triagers`, and `most_collaborative_users` to empty lists with an outdated "not available without defect_triage_history table" comment — so every cached dashboard hid the Individual Contributors section
  - Replaced with real calls (`metrics.get_top_users_by_fixes(days=days, limit=10)`, etc.) and updated `top_projects_by_fix_rate` / `top_projects_by_triage_activity` in the same block to use `days=days` instead of hardcoded 30
- **Overview tab "Active Defects" card counted False Positive and Intentional as active**
  - `get_overall_summary` computed `total_defects` and `high_severity_defects` from `stream_defect` with only `fixed_snapshot_element_id IS NULL`, so dismissed defects (classified as `False Positive` or `Intentional`) were included even though the card's tooltip promised they were excluded and the Defects by Stream table's `active_defects` column already excluded them
  - Both the project-scoped and global branches now `LEFT JOIN defect_triage` + `dynamic_enum` (`dtype = 'Cls'`) and add `AND (de_cls.name NOT IN ('False Positive', 'Intentional') OR de_cls.name IS NULL)`, making the Overview card match the rest of the dashboard
  - Example: a project with 162 stream_defects where 162 were classified as False Positive previously showed `Active Defects: 162`; now correctly shows `0`
- **Dismissed defects (False Positive / Intentional) now treated as fixed EVERYWHERE**
  - Extended the same triage-classification exclusion to every remaining query that counted "outstanding" defects, so all Overview / Hotspots / Aging / Triage / OWASP / CWE metrics now agree on what counts as active
  - Updated queries: `get_defects_by_severity`, `get_defects_by_checker_category`, `get_defects_by_checker_name`, `get_defect_density_by_project`, `get_file_hotspots`, `get_triage_trends`, `get_defect_trend_summary` (current_state CTE), `get_defect_aging_distribution`, `get_triage_progress_summary`, `get_top_projects_by_triage_activity`, `get_owasp_top10_metrics`, `get_owasp_category_details`, `get_cwe_top25_metrics`, `get_cwe_top25_details`
  - Intentionally **not** changed: `get_checker_classification_breakdown` and `get_top_projects_by_classification` — these metrics are *about* the classification distribution itself (they surface noisy checkers / projects that dismiss a lot) and would produce empty results if dismissed were filtered out
  - Also intentionally not changed: the triaged-fix CTEs in `get_defect_trends`, `get_fix_rate_metrics`, `get_defect_velocity_trend`, `get_cumulative_defect_trend`, `get_defect_trend_summary` (period totals) — these deliberately *include* dismissed defects on the "fixed" side of the ledger, which is what the fix rate metric is supposed to show
  - Real-world example: `example-project` (97 stream_defects with 96 classified as FP/Intentional) previously showed 97 in every Overview chart; now correctly shows 1 truly-active defect everywhere
  - **Follow-up refinement**: Five of these charts were reverted to still include dismissed because they exist specifically to show *what Coverity found*, not just what remains actionable — see next entry
- **Reverted dismissed-exclusion on five "raw defect" visibility charts**
  - `get_defects_by_severity`, `get_defects_by_checker_category`, `get_defects_by_checker_name`, `get_defect_density_by_project`, and `get_triage_progress_summary` now include dismissed defects again
  - Rationale: these are Overview / Trend & Progress charts that answer "which severities / categories / checkers is Coverity firing on?" and "how much has been classified?" — hiding dismissed makes them incomplete. In particular, `get_triage_progress_summary` was showing `total_defects = 0` for projects where every defect had been triaged as FP/Intentional, making the Current Triage Progress card look like there was nothing to see
  - "Active only" is still enforced on the metrics whose purpose is remediation load: Overview `Active Defects` card, File Hotspots, Defect Aging, Triage Trends (per-stream classification bars of *outstanding* defects), OWASP Top 10, CWE Top 25, and the current-outstanding count in `get_defect_trend_summary`
- **"Outstanding defect" semantic corrected across every active-defect query — `stream_defect.fixed_snapshot_element_id` is unreliable**
  - Discovered `fixed_snapshot_element_id IS NULL` misses defects that were once removed from code but then re-appeared in a later snapshot: Coverity does not clear the field when the defect returns, so counts based purely on this column understate outstanding defects. Coverity Connect's UI uses the `last_detected_snapshot` table instead — a defect is currently outstanding iff its `last_detected_snapshot.detected_snapshot_id` equals the latest non-deleted `snapshot.id` for its stream
  - Introduced three class constants on `CoverityMetrics` that codify the correct pattern: `_ACTIVE_JOIN_SQL` (join `last_detected_snapshot` + per-stream max snapshot), `_ACTIVE_COND_SQL` (`lds.detected_snapshot_id = sn_latest.latest_snap_id`), and `_FIXED_COND_SQL` (its inverse). Every active-defect query now injects these instead of relying on `fixed_snapshot_element_id`
  - Rewrote all ~20 active-defect SQL sites in `metrics.py` to use the new pattern: `get_total_defects_by_project`, `get_defects_by_severity`, `get_defects_by_checker_category`, `get_defects_by_checker_name`, `get_defect_density_by_project`, `get_overall_summary` (project + global branches), `get_file_hotspots`, `get_triage_trends`, `get_checker_classification_breakdown`, `get_top_projects_by_classification`, `get_fix_rate_metrics` (all three CTEs), `get_defect_velocity_trend`, `get_cumulative_defect_trend`, `get_defect_trend_summary` (period_triaged + current_state), `get_defect_aging_distribution`, `get_triage_progress_summary`, `get_technical_debt_summary`, `get_top_projects_by_fix_rate`, `get_top_projects_by_triage`, `get_top_users_by_fixes` (project + global), `get_owasp_top10_metrics`, `get_owasp_category_details`, `get_cwe_top25_metrics`, `get_cwe_top25_details`
  - `get_triage_progress_summary` was additionally reshaped to start `FROM stream_defect sd` (was `FROM defect_triage dt` with a `LEFT JOIN` to `sd`), so orphan triages that never belonged to a currently-outstanding defect no longer inflate the totals
  - Real-world example: `example-project` — Coverity UI shows 2 outstanding defects (CID 38907 Intentional, CID 39378 Unclassified). Old behaviour: `get_triage_progress_summary.total_defects = 1` (CID 39378 hidden because its `fixed_snapshot_element_id` was stale). New behaviour: `total_defects = 2`, matching the UI
- **Function Complexity Distribution leaked instance-wide numbers into project dashboards**
  - `get_function_complexity_distribution` and `get_most_complex_functions` had no project filter at all — every project's ZIP export and DB dashboard showed the *instance-wide* complexity histogram / top-N list, so projects with zero streams still displayed thousands of functions
  - Both queries now join `stream_file` → `stream_element` → `stream` → `project_stream` → `project` when `_project_names` is set and filter with `AND p.name = ANY(%s)`. Projects without streams now correctly return empty
  - Pre-1.0.17 ZIPs still contain the leaky per-project `function_complexity_distribution.json` files — re-export with 1.0.17+ to get correct per-project numbers

## [1.0.16] - 2026-05-05

### Added
- **`python -m coverity_metrics` Module Support**: The package can now be run as a Python module — `python -m coverity_metrics dashboard`, `python -m coverity_metrics export`, `python -m coverity_metrics report`. Added `__main__.py` which dispatches to the appropriate CLI entry point, stripping the subcommand from `sys.argv` so all existing arguments pass through unchanged

### Documentation
- **Multi-Project `--project` Parameter**: Documented that `--project` accepts comma-separated values for filtering multiple projects simultaneously (e.g. `--project "AppA,AppB,AppC"`); updated README parameter table, CLI examples, and USAGE_GUIDE
- Updated README, USAGE_GUIDE with `python -m coverity_metrics` usage examples

## [1.0.15] - 2026-05-05

### Fixed
- **Project-Level Metrics in ZIP Dashboards**
  - Fixed "Top Analysis Versions Used" and other metrics showing instance-level data on project-level reports generated from ZIP files
  - Updated 8 `ZipDataLoader` methods to properly check for project-specific data files: `get_analysis_versions`, `get_function_complexity_distribution`, `get_snapshot_performance`, `get_commit_time_statistics`, `get_commit_activity_patterns`, `get_defect_discovery_rate`, `get_defect_velocity_trend`, `get_cumulative_defect_trend`
  - Added missing project-level metrics to export configuration so they are included in ZIP exports
  - Project dashboards now correctly display project-specific analysis versions, snapshot performance, and commit activity instead of instance-wide aggregates
- **Negative Database Uptime**
  - Fixed database uptime showing negative values (e.g., "-1d 23h 24m") due to timezone handling issues
  - Updated `get_instance_info` to use UTC consistently for both current time and PostgreSQL start time
  - Added timezone-aware conversion using `.astimezone(timezone.utc)` to handle timezone offsets correctly
  - Added guard against negative uptimes with "Invalid (negative)" display for edge cases
  - Database uptime now calculates correctly regardless of database timezone or system local timezone

## [1.0.14] - 2026-03-19

### Added
- Added `fetch_all` parameter to metrics methods for retrieving all data instead of just top N results
- Enhanced CLI parameter documentation in README

### Changed
- Updated Python library usage examples in README

### Fixed
- Bug fixes and improvements

## [1.0.13] - 2026-03-13

### Changed
- **Removed "Most Improved" Leaderboard Card**
  - The "Most Improved" leaderboard card has been removed from the Team Leaderboards section
  - Improvement percentage was unreliable for sparse snapshot data (projects with only one snapshot had no meaningful baseline to compare against)
  - Removed the corresponding `get_most_improved_projects` call from all dashboard generation paths (`dashboard.py`) and from the ZIP export config (`export.py`)
  - Removed the "Improvement" entry from the Leaderboard Metrics Explained legend in the dashboard template
  - The leaderboard section visibility condition (`{% if ... %}`) updated accordingly

### Fixed
- **`most_improved_projects` No Longer Exported to ZIP**
  - Removed from `export.py` metric config so ZIP archives are no longer populated with data that was not being displayed

## [1.0.12] - 2026-03-05

### Fixed
- **Stale `~overity_metrics` dist-info Artefact**
  - An interrupted install left a `~overity_metrics-1.0.8.dist-info` directory in site-packages, causing pip to emit `WARNING: Ignoring invalid distribution ~overity-metrics` on every invocation
  - Removed the corrupted directory; no source code changes

## [1.0.11] - 2026-03-05

### Fixed
- **PostgreSQL `ROUND` Compatibility in `get_top_projects_by_fix_rate`**
  - `EXTRACT(EPOCH FROM ...)` returns `double precision`; dividing `numeric` by it produces `double precision`, for which `ROUND(x, integer)` is undefined in PostgreSQL
  - Added `::numeric` cast to the `EXTRACT` expression in `metrics.py` so `ROUND(defects_fixed::numeric / EXTRACT(...)::numeric * 86400, 2)` resolves correctly
  - Resolves `psycopg2.errors.UndefinedFunction: function round(double precision, integer) does not exist` crash on dashboard generation

## [1.0.10] - 2026-03-04

### Changed
- **Dependency Upgrades**
  - `psycopg2-binary` `>=2.9.0` → `>=2.9.11`
  - `pandas` `>=2.0.0` → `>=3.0.1`
  - `matplotlib` `>=3.7.0` → `>=3.10.8`
  - `seaborn` `>=0.12.0` → `>=0.13.2`
  - `python-dateutil` `>=2.8.0` → `>=2.9.0.post0`
  - `openpyxl` `>=3.1.0` → `>=3.1.5`
  - `jinja2` `>=3.1.0` → `>=3.1.6`
  - `plotly` `>=5.18.0` → `>=6.6.0`
  - `tqdm` `>=4.66.0` → `>=4.67.3`

- **Project Structure Documentation**
  - Refactored project structure for improved organization and clarity
  - Updated README with new file paths and project layout reflecting the current structure

- **Presentation Guide**
  - Updated `PRESENTATION_GUIDE.md` with Python script option for generating presentations
  - Revised slide structure details for improved clarity and usability

## [1.0.9] - 2026-03-03

### Fixed
- **Missing Classification Charts in ZIP-based Dashboards**
  - `checker_classification_breakdown` and `top_projects_by_classification` were never written to ZIP export files
  - Both metrics are now exported at instance level and project level in `export.py`
  - `ZipDataLoader` getter methods already existed and read from the correct JSON paths — only the export side was missing
  - Dashboards generated with `--zip-file` now include the "Checker Classification Breakdown" and "Top Projects/Streams by Triage Classification" sections

- **`--track-progress` and `--resume` Were No-ops**
  - `ProgressTracker` class in `metrics_cache.py` was fully implemented but never wired into dashboard generation
  - `--track-progress` now creates a progress session before generation, prints the session ID, and records each completed dashboard
  - `--resume SESSION_ID` now loads the completed set from the session file and skips already-generated dashboards, printing `[SKIP]` for each
  - All 7 generation paths in `dashboard.py` are covered: single/multi-instance × specific/all projects × aggregated
  - Label scheme: `"Aggregated View"` / `"{instance}"` / `"{instance} - {project}"`

- **Hardcoded "Last 90 Days" in Aggregated Dashboard**
  - Section title, card labels (`Total New (90d)` / `Total Fixed (90d)`), Trends by Instance table headers, and tooltip texts all showed a hardcoded 90 regardless of the `--days` argument
  - All 5 occurrences in `dashboard_aggregated.html` replaced with `{{ trend_period_text }}` / `{{ trend_period_text|lower }}`
  - `generate_aggregated_dashboard()` already passed `trend_period_text=f"Last {days} Days"` — only the template was stale

## [1.0.8] - 2026-03-02

### Fixed
- **OWASP Top 10 Summary / Detail Count Inconsistency**
  - Fixed bug where "Total Defects" in the OWASP category summary did not match the defect table row count and CWE count shown below it
  - Example: A09 showed "Total Defects: 5", "Defects (6 total)", and "1 CWE mapped" when the table actually listed 6 defects across 2 different CWEs
  - Root cause 1: `cwe_to_owasp` was a flat dict — CWEs listed in multiple OWASP categories were silently dropped for all but the last category encountered (last-writer-wins). CWE-918 appears in both A09 and A10; because A10 is iterated last it stole the defects from A09's summary while A09's detail query still correctly included them.
  - Root cause 2: Summary used `COUNT(DISTINCT sd.id)` (physical stream-defect rows) while the detail table used `DISTINCT ON (sd.merged_defect_id)` (logical merged defects), so counts diverged for merged duplicates.
  - Fix: Changed `cwe_to_owasp` to a multi-value mapping (`CWE → [list of categories]`) so every shared CWE contributes to all matching categories
  - Fix: Changed summary SQL to `COUNT(DISTINCT sd.merged_defect_id)` with `AND sd.merged_defect_id IS NOT NULL` to match detail-table deduplication logic

## [1.0.7] - 2026-02-25

### Added
- **Script Execution Time**
  - Script now prints total execution time after dashboard generation

### Fixed
- **Instance-Level Active Users Deduplication**
  - Instance-level "Active Users" now deduplicates by activity (triage, comment, commit) and matches project-level logic
- **Dashboard Bug: Active Users Count**
  - Dashboard now displays correct "Active Users" count at all levels
- **HTML Escaping for Defect Fields**
  - Defect file/function fields are now HTML-escaped to prevent invalid HTML/JS errors in dashboards

## [1.0.6] - 2026-02-24

### Fixed
- **Project-Level Dashboard Data Filtering from ZIP Files**
  - Fixed issue where project-level dashboards generated from ZIP files showed instance-level aggregate data
  - Example: Project dashboard previously showed 90 defects (instance total) instead of 5 defects (project actual)
  - Root cause: Export only created project-level files for OWASP/CWE metrics, not core metrics
  - Solution:
    - Updated `export.py`: Now exports complete project-specific versions of all core metrics
      - overall_summary.json, defects_by_severity.json, defect_trends.json
      - triage_progress_summary.json, fix_rate_metrics.json, defect_aging_distribution.json
      - technical_debt_summary.json, and all other dashboard metrics
    - Updated `zip_data_loader.py`: Added intelligent file path resolution
      - New `_read_metric_json()` method checks for project-specific files first
      - Falls back to instance-level files if project file doesn't exist
      - All metric getter methods now use this smart lookup
  - ZIP structure now includes: `{instance}/{project}/{metric}.json` for all metrics
  - Project dashboards from ZIP files now correctly show filtered data matching database mode

- **Triage Progress Aggregation Discrepancy**
  - Fixed inconsistency between database and ZIP-based aggregated dashboards
  - Database showed: 36 Classified, 234 Unclassified, 13.3% Completion Ã¢Å“â€¦
  - ZIP showed (before fix): 57 Classified, 213 Unclassified, 21.1% Completion Ã¢ÂÅ’
  - Root cause: Aggregation incorrectly summed triage state counts including `action_assigned_count`
    - Problem: `action_assigned_count` includes defects with actions but still marked as "Unclassified"
    - The `classified_count` field correctly counts only actually classified defects
  - Solution: Changed aggregation in `dashboard.py` to use `total_triaged` (sum of `classified_count`) instead of `sum(triage_by_state_agg.values())`
  - ZIP and database sources now produce identical triage statistics

### Changed
- **Export Behavior - Separate ZIP Files per Instance**
  - `coverity-export` now creates a **separate ZIP file for each configured instance** instead of a single combined ZIP
  - Each ZIP file is named: `coverity_export_{InstanceName}_{timestamp}.zip`
  - Benefits:
    - Easier to share individual instance data
    - Smaller file sizes for selective distribution
    - Better organization and identification
    - Supports selective instance transfers
  - Multi-ZIP aggregation still supported: provide multiple ZIPs to `coverity-dashboard --zip-file`
  - Example: Config with 3 instances now creates 3 separate ZIPs:
    - `coverity_export_Production_20260224_113111.zip`
    - `coverity_export_Development_20260224_113111.zip`
    - `coverity_export_Emergency_20260224_113111.zip`

### Added
- **Aggregated Dashboard from ZIP Files**
  - `coverity-dashboard --zip-file` now **always generates an aggregated dashboard** (`dashboard_aggregated.html`)
  - Works with both single and multiple ZIP files
  - Aggregated dashboard shows:
    - Combined metrics across all instances in ZIP file(s)
    - Defects by instance breakdown
    - Aggregated severity distribution
    - Total defect counts and fix rates
  - Single ZIP: Generates 1 aggregated + instance/project dashboards
  - Multiple ZIPs: Generates 1 aggregated + all instance/project dashboards
  - Example: 3 ZIP files Ã¢â€ â€™ 16 dashboards total (1 aggregated + 15 instance/project)
  - **Automatic color assignment**: Each instance gets a distinct color in aggregated view (red, blue, green, orange, etc.)
    - No need for config.json when using ZIP files - colors are auto-assigned
    - 15 distinct colors available, cycles if more instances

## [1.0.5] - 2026-02-20

### Enhanced
- **OWASP Top 10 2025 Report - Complete Security Coverage**
  - Now displays all 10 OWASP categories regardless of whether defects exist
  - Added PASS/FAILED status badges for each category:
    - ÃƒÂ°Ã…Â¸Ã…Â¸Ã‚Â¢ **PASS**: No defects found for this category (green badge, non-clickable)
    - ÃƒÂ°Ã…Â¸Ã¢â‚¬ÂÃ‚Â´ **FAILED**: Has defects mapped to this category (red badge, clickable to expand)
  - Visual differentiation:
    - FAILED rows: Clickable with red-tinted background and pointer cursor
    - PASS rows: Non-clickable with green-tinted faded background
  - Summary cards show pass/fail counts (e.g., "3/10 Failed")
  - Complete security posture visibility at a glance

- **CWE Top 25 2025 Report - Complete Weakness Coverage**
  - Now displays all 25 CWE Top 25 entries with Status column
  - Added PASS/FAILED status badges matching OWASP report format
  - Same visual differentiation and clickable behavior as OWASP
  - Summary cards show failed CWE counts (e.g., "5/25 Failed")
  - Ranks 1-25 based on MITRE's danger scores

- **Enhanced Defect Details for Security Reports**
  - Removed aggregated "CWE Breakdown" sections for cleaner display
  - Removed "Top Checkers" summary from CWE Top 25 report
  - Now shows ALL defects for each failed category/CWE (no 10-per-CWE limit)
  - Detailed defect tables include:
    - **CID**: Actual Coverity ID (merged_defect_id from database)
    - **CWE**: CWE identifier (OWASP report only)
    - **Type**: Checker name (e.g., "Resource leak", "Null pointer dereference")
    - **Severity**: High/Med/Low badges
    - **File**: Full file path with overflow handling
    - **Function**: Function name where defect occurs
  - Scrollable table containers (max 400px height) for large defect lists
  - Fixed table header visibility with proper text colors (#2c3e50 on white background)

- **Database Schema Corrections**
  - Fixed CID mapping: Uses `stream_defect.merged_defect_id` (actual user-visible CID)
  - Corrected checker joins via `checker_type` table
  - Fixed function joins using `stream_defect_occurrence.function_id`
  - Removed invalid `stream_file` table joins

### Fixed
- Table header visibility in OWASP and CWE Top 25 defect tables
- Replaced undefined CSS variables (`var(--text-color)`, `var(--card-bg)`) with actual color values
- UnboundLocalError for commit_activity variable in dashboard generation

### Performance
- Optimized to only load detailed defect breakdowns for FAILED categories/CWEs
- PASS entries don't trigger database queries for details
- Significant performance improvement for large deployments

## [1.0.4] - 2026-02-19

### Added
- **Comprehensive Progress Tracking for Multi-Instance Dashboards**
  - Implemented tqdm-based progress bars for all multi-instance dashboard generation workflows
  - Pre-calculates total work items (1 aggregated + N instances + M projects) before execution
  - Real-time progress updates with completion percentage, elapsed time, and ETA
  - Dynamic descriptions showing current instance and project being processed
  - Processing speed metrics (e.g., "12.0s/dashboard")
  - Three tracking scenarios:
    1. **Specific Instance + All Projects**: Total calculation shows "1 instance + N projects"
       - Progress bar updates for instance overview + each project
       - Description format: "{instance} - {project}"
       - Postfix shows project counter: "X/Y"
    2. **All Instances + Specific Project**: Shows "Instance X/Y: {name}" 
       - One progress update per instance processed
    3. **All Instances + All Projects (Full Auto)**:
       - Displays pre-flight breakdown: "1 aggregated + N instances + M projects"
       - Single overall progress bar tracking all dashboard types
       - Dynamic descriptions for each phase: aggregated ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ instances ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢ projects
       - Postfix strings: "{project} (X/Y)" showing current item within instance
  - Example output:
    ```
    Total dashboards to generate: 47
    - 1 aggregated dashboard
    - 10 instance dashboards  
    - 36 project dashboards
    
    Overall Progress: 23/47 [=========>...] 48% [04:36<04:48, 12.0s/dashboard]
    Instance 5/10: Staging projects
    project_alpha (3/8)
    ```

- **Commit Activity Patterns Analysis**
  - New `get_commit_activity_patterns()` method in `CoverityMetrics` class (lines 1082-1210)
  - Analyzes temporal patterns in commit behavior by hour and day of week
  - Groups commits into 3-hour time blocks:
    - 00:00-02:00, 03:00-05:00, 06:00-08:00, 09:00-11:00
    - 12:00-14:00, 15:00-17:00, 18:00-20:00, 21:00-23:00
  - Identifies busiest and quietest 3-hour windows with:
    - Commit counts
    - Average commit duration (seconds)
    - Average files changed per commit
    - Average new defects introduced per commit
  - Identifies busiest and quietest days of week (Sunday-Saturday)
  - SQL implementation:
    - Uses `EXTRACT(HOUR FROM sn.date_created)` for hourly grouping
    - Uses `EXTRACT(DOW FROM sn.date_created)` for day-of-week grouping (0=Sunday)
    - Qualified column names (sn.date_created, sn.duration_commit_total) to avoid ambiguity
    - Aggregates with COUNT, AVG, SUM for comprehensive statistics
  - Multi-instance aggregation support:
    - New `get_aggregated_commit_activity()` in `MultiInstanceMetrics` (lines 296-424)
    - Combines commit data across all instances using defaultdict
    - Weighted averages for duration and statistics
    - Same output structure as single-instance for template compatibility
  - Display format: "14:00-16:00 (2 PM - 4 PM)" with 12-hour AM/PM conversion
  - Integrated into dashboards:
    - Single-instance: `dashboard.html` lines 1063-1121
    - Aggregated: `dashboard_aggregated.html` lines 549-607
  - Dashboard displays 4 summary cards:
    - Busiest 3-Hour Window (info color)
    - Quietest 3-Hour Window (default color)
    - Busiest Day (success color)
    - Quietest Day (default color)

### Changed
- **Dashboard Generation User Experience**
  - All multi-instance workflows now show detailed progress instead of blank screen
  - Users receive upfront information about total work before generation starts
  - Progress bars use `tqdm.write()` for clean console output
  - Context manager pattern ensures progress bars close properly
  - `dashboard.py` lines 665-775 refactored for comprehensive progress tracking

- **Console Output Improvements**
  - Replaced `print()` statements with `tqdm.write()` throughout `dashboard.py`
  - Prevents progress bar corruption from concurrent output
  - Professional-looking output for enterprise deployments

### Fixed
- **SQL Ambiguous Column References**
  - Fixed "column reference 'date_created' is ambiguous" error in commit activity queries
  - All columns now properly qualified with table alias (e.g., `sn.date_created`)
  - Affects queries in `get_commit_activity_patterns()` method

### Technical Details
- **Modified files**:
  - `coverity_metrics/cli/dashboard.py` (lines 665-775): Progress tracking implementation
  - `coverity_metrics/metrics.py` (lines 1082-1210): Commit activity patterns method
  - `coverity_metrics/multi_instance_metrics.py` (lines 296-424): Aggregated commit activity
  - `coverity_metrics/templates/dashboard.html` (lines 1063-1121): Commit activity display
  - `coverity_metrics/templates/dashboard_aggregated.html` (lines 549-607): Aggregated display

- **API signatures**:
  - `CoverityMetrics.get_commit_activity_patterns() -> dict`
    - Returns: `{'busiest_hours': {...}, 'quietest_hours': {...}, 'busiest_day': {...}, 'quietest_day': {...}}`
  - `MultiInstanceMetrics.get_aggregated_commit_activity() -> dict`
    - Same structure as single-instance for consistent template rendering

## [1.0.3] - 2026-02-19

### Added
- **Technical Debt Estimation Feature**
  - New `get_technical_debt_summary()` method in `CoverityMetrics` class
  - Analyzes defect impact levels from Coverity's `checker_properties.impact` field
  - Calculates estimated remediation effort using industry-standard formulas:
    - High impact: 4 hours per defect
    - Medium impact: 2 hours per defect
    - Low impact: 1 hour per defect
    - Unspecified impact: 0.5 hours per defect
  - Returns comprehensive breakdown:
    - Total hours, work days (ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â·8), work weeks (ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â·40)
    - Total defect count
    - Breakdown by impact level (count, hours, percentage)
    - Average hours per defect
  - Integrated into "Trends & Progress" dashboard tab
  - Dashboard displays:
    - 4 summary cards: Total Hours, Work Days, Work Weeks, Average per Defect
    - 4 breakdown cards: High/Medium/Low/Unspecified with color-coded severity
    - Info alert explaining estimation methodology

- **CWE Top 25 2025 Support**
  - Updated CWE Top 25 rankings from 2024 to 2025 version (MITRE)
  - Updated `cwe_top25_mapping.py` with all 25 new rankings and scores
  - Major ranking changes:
    - CWE-306 (Missing Authentication): #20 ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ #8 (significant jump)
    - CWE-416 (Use After Free): #4 ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ #18 (dropped)
    - CWE-787 (Out-of-bounds Write): #5 ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ #21 (dropped)
    - CWE-862 (Missing Authorization): #3 ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ #5
    - CWE-269 (Improper Privilege Management): #8 ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ #12
  - New CWE entries in 2025:
    - CWE-120 (Classic Buffer Overflow) at #19
    - CWE-327 (Broken or Risky Crypto Algorithm) at #23
  - Removed from 2025 list:
    - CWE-94 (Improper Control of Code Generation)
    - CWE-276 (Incorrect Default Permissions)
  - Dashboard tab title updated: "CWE Top 25 2024" ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ "CWE Top 25 2025"

### Changed
- **Documentation Enhancements**
  - Updated `README.md` with comprehensive "Latest Enhancements (2025)" section
  - Added quick reference for new features (ÃƒÆ’Ã‚Â°Ãƒâ€¦Ã‚Â¸ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢Ãƒâ€šÃ‚Â° Technical Debt, ÃƒÆ’Ã‚Â°Ãƒâ€¦Ã‚Â¸ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ OWASP, ÃƒÆ’Ã‚Â°Ãƒâ€¦Ã‚Â¸ÃƒÂ¢Ã¢â€šÂ¬Ã‚ÂºÃƒâ€šÃ‚Â¡ÃƒÆ’Ã‚Â¯Ãƒâ€šÃ‚Â¸Ãƒâ€šÃ‚Â CWE, ÃƒÆ’Ã‚Â°Ãƒâ€¦Ã‚Â¸Ãƒâ€šÃ‚ÂÃƒÂ¢Ã¢â€šÂ¬Ã‚Â  Leaderboards)
  - Expanded Features section with Security Compliance Metrics and Leaderboards
  - Added "For Security Teams" use cases section
  - Updated Available Metric Methods with technical debt and security APIs
  - Updated Database Schema documentation with CWE code information
  - Updated Project Structure showing new mapping files
  - Enhanced Python API examples with technical debt, OWASP, CWE, and leaderboard methods
  - Documented all 7 dashboard tabs with detailed descriptions

- **Dashboard Improvements**
  - "Trends & Progress" tab now includes Technical Debt Summary section
  - CWE Top 25 tab displays 2025 rankings with updated scores
  - Enhanced visual presentation of technical debt metrics with color-coded severity

### Fixed
- Fixed `Decimal` to `float` type conversion in technical debt calculations to avoid TypeError
- Ensured all CWE Top 25 references point to 2025 data

### Technical Details
- **Modified Files**:
  - `coverity_metrics/cwe_top25_mapping.py`: Updated CWE_TOP_25_2025 dictionary
  - `coverity_metrics/metrics.py`: Added `get_technical_debt_summary()` method (lines 1530-1611)
  - `coverity_metrics/cli/dashboard.py`: Integrated technical debt data retrieval
  - `coverity_metrics/templates/dashboard.html`: Added Technical Debt Summary section (lines 593-657)
  - `README.md`: Comprehensive documentation updates

- **Database Schema**:
  - Utilizes existing `checker_properties.impact` field
  - Joins `stream_defect` with `checker_properties` on checker name
  - SQL CASE statement for effort calculation based on impact level

- **API Enhancement**:
  - New method: `CoverityMetrics.get_technical_debt_summary()`
  - Returns: `dict` with keys: `total_hours`, `total_days`, `total_weeks`, `total_defects`, `breakdown`, `avg_hours_per_defect`
  - Breakdown structure: `{impact_level: {'count': int, 'hours': float, 'percentage': float}}`

## [1.0.2] - 2026-02-18

### Added
- Added `fetch_all` parameter to metrics methods

### Changed
- Updated documentation

## [1.0.0] - 2026-02-18

### Added
- **Full Python Package Structure**
  - Created installable package with `pip install -e .`
  - Modern `pyproject.toml` based packaging (PEP 621)
  - Three CLI entry points: `coverity-dashboard`, `coverity-metrics`, `coverity-export`
  - Package can be used as both CLI tool and importable library
  - Proper package structure with `coverity_metrics/` module
  - Version management via `__version__.py`
  - Comprehensive `.gitignore` for Python projects
  - Installation guide in `INSTALL.md`

- **CLI Commands**
  - `coverity-dashboard`: Main dashboard generator (replaces `python generate_dashboard.py`)
  - `coverity-metrics`: Console metrics report (replaces `python main.py`)
  - `coverity-export`: CSV/JSON export utility (replaces `python export_metrics.py`)

- **Python Library API**
  - Can import with: `from coverity_metrics import CoverityMetrics, MultiInstanceMetrics`
  - Programmatic access to all metrics functionality
  - Supports both single and multi-instance configurations

### Changed
- **Configuration Simplification**
  - Removed dependency on `cim.properties` configuration file
  - All configuration now exclusively uses `config.json`
  - Removed `config.py` module (functionality merged into other modules)
  - Database connection parameters now passed as dictionaries

- **CLI Simplification**
  - Removed legacy flags: `--multi-instance`, `--aggregated`, `--all-projects`, `--all-instances`
  - Multi-instance mode now auto-detected from `config.json` (2+ instances)
  - Single-instance mode auto-detected from `config.json` (1 instance)
  - Cleaner, more intuitive command-line interface

- **Project Structure**
  - Moved all Python modules into `coverity_metrics/` package
  - Moved CLI scripts into `coverity_metrics/cli/` subdirectory
  - Moved templates into `coverity_metrics/templates/`
  - Moved static assets into `coverity_metrics/static/`
  - All imports now use package-relative paths (`coverity_metrics.*`)

- **Documentation**
  - Updated `README.md` with new installation and usage instructions
  - Updated `MULTI_INSTANCE_GUIDE.md` to reflect auto-detection behavior
  - Updated `CACHING_GUIDE.md` with current CLI commands
  - Updated `USAGE_GUIDE.md` with new command syntax
  - Added installation guide (`INSTALL.md`) with CLI and library examples

### Removed
- **Development/Testing Scripts** (Workspace Cleanup)
  - Removed 15+ database exploration scripts (`check_*.py`, `explore_*.py`, `find_*.py`, etc.)
  - Removed legacy test scripts that were for development only
  - Cleaner workspace focused on production code

- **Legacy Configuration**
  - Removed `cim.properties` file support
  - Removed `config.py` module
  - Removed dual-configuration system

- **Legacy CLI Flags**
  - Removed `--multi-instance` (auto-detected)
  - Removed `--aggregated` (auto-detected)
  - Removed `--all-projects` (default behavior)
  - Removed `--all-instances` (default behavior)

### Fixed
- Package imports now use absolute paths from package root
- Template paths corrected for package structure
- All references to old script names updated in documentation

### Technical Details
- **Package Name**: `coverity-metrics`
- **Version**: 1.0.0
- **Python Support**: >=3.8
- **Dependencies**: psycopg2-binary, pandas, matplotlib, seaborn, jinja2, plotly, tqdm, python-dateutil, openpyxl
- **Installation**: `pip install -e .` for editable/development mode
- **Entry Points**: 
  - `coverity-dashboard` ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¾ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ `coverity_metrics.cli.dashboard:main`
  - `coverity-metrics` ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¾ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ `coverity_metrics.cli.report:main`
  - `coverity-export` ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¾ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ `coverity_metrics.cli.export:main`

---

## [0.9.0] - Previous Version

### Features from Previous Development
- Interactive HTML dashboard with tabbed interface
- Multi-instance aggregation support
- Performance metrics and analysis
- Caching system for improved performance
- Progress tracking for large datasets
- CSV/JSON export functionality
- PostgreSQL database integration
- Project filtering and navigation

"""Trend computation over ``coverity-export`` ZIPs.

Consumes an ordered list of snapshot ZIPs (oldest → newest) produced by
:mod:`coverity_metrics.cli.export` and returns per-instance time series
for adoption metrics: projects, active users, scan activity, snapshot
cadence (stream activity), and defects-by-project (with per-snapshot
ranking movement). Nothing here talks to the database — every input
comes from the per-metric JSONs bundled inside the export ZIPs.

Kept separate from ``multi_instance_metrics.py`` because that module owns
cross-instance aggregation at a single point in time, while this module
owns single-instance comparison across N points in time.
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import re
import zipfile
from datetime import datetime
from typing import Dict, List, Optional, Sequence

import pandas as pd

from coverity_metrics.anonymizer import default_mapping_path


DELTA_SCHEMA_VERSION = 1


# Recognizes the timestamp trailer that ``export.py`` appends to every ZIP
# filename: ``coverity_export_<sanitized_name>_YYYYMMDD_HHMMSS.zip``.
_FILENAME_TIMESTAMP_RE = re.compile(r"(\d{8})_(\d{6})(?:\.zip)?$", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Snapshot loader
# ---------------------------------------------------------------------------


class SnapshotLoader:
    """Read-only view over a ``coverity-export`` ZIP.

    Loads ``metadata.json`` eagerly (cheap) and per-metric JSONs on demand,
    caching them so a metric consulted by multiple compute functions is
    only parsed once.
    """

    def __init__(self, zip_path: str):
        self.zip_path = zip_path
        self._zf = zipfile.ZipFile(zip_path, "r")
        self._metadata: Optional[dict] = None
        self._records_cache: Dict[str, pd.DataFrame] = {}
        self._dict_cache: Dict[str, dict] = {}

    # -- Metadata ----------------------------------------------------------

    @property
    def metadata(self) -> dict:
        if self._metadata is None:
            try:
                with self._zf.open("metadata.json") as f:
                    self._metadata = json.load(f)
            except (KeyError, json.JSONDecodeError):
                self._metadata = {}
        return self._metadata

    @property
    def instance_names(self) -> List[str]:
        snap = self.metadata.get("config_snapshot") or {}
        names = snap.get("instance_names") or []
        return [str(n) for n in names]

    @property
    def days(self) -> int:
        try:
            return int(self.metadata.get("days") or 0)
        except (TypeError, ValueError):
            return 0

    @property
    def export_date(self) -> str:
        return str(self.metadata.get("export_date") or "")

    @property
    def export_timestamp(self) -> str:
        return str(self.metadata.get("export_timestamp") or "")

    @property
    def order_key(self) -> datetime:
        """Chronological sort key: ``export_timestamp`` → filename → mtime."""
        for source in (self.export_timestamp, os.path.basename(self.zip_path)):
            dt = _parse_filename_timestamp(source)
            if dt is not None:
                return dt
        try:
            return datetime.fromtimestamp(os.path.getmtime(self.zip_path))
        except OSError:
            return datetime.min

    # -- Per-metric loading -----------------------------------------------

    def _arcpath(self, instance_name: str, metric_name: str) -> str:
        return f"{instance_name}/{metric_name}.json"

    def has_metric(self, instance_name: str, metric_name: str) -> bool:
        try:
            self._zf.getinfo(self._arcpath(instance_name, metric_name))
            return True
        except KeyError:
            return False

    def load_records(self, instance_name: str, metric_name: str) -> pd.DataFrame:
        """Load a metric that ``export.py`` wrote via ``to_dict(orient='records')``.

        Returns an empty DataFrame if the file is missing or the payload is
        not a list — makes downstream diff code safe to call unconditionally.
        """
        arc = self._arcpath(instance_name, metric_name)
        if arc in self._records_cache:
            return self._records_cache[arc]
        try:
            with self._zf.open(arc) as f:
                data = json.load(f)
        except KeyError:
            df = pd.DataFrame()
        else:
            df = pd.DataFrame(data) if isinstance(data, list) else pd.DataFrame()
        self._records_cache[arc] = df
        return df

    def load_dict(self, instance_name: str, metric_name: str) -> dict:
        """Load a metric that ``export.py`` wrote as a plain dict (e.g. ``user_license_statistics``)."""
        arc = self._arcpath(instance_name, metric_name)
        if arc in self._dict_cache:
            return self._dict_cache[arc]
        try:
            with self._zf.open(arc) as f:
                data = json.load(f)
        except KeyError:
            data = {}
        if not isinstance(data, dict):
            data = {}
        self._dict_cache[arc] = data
        return data

    # -- Anonymization mapping fingerprint --------------------------------

    def mapping_path(self) -> Optional[str]:
        """Sibling ``<zip>.mapping.json`` if it exists, else ``None``."""
        path = default_mapping_path(self.zip_path)
        return path if os.path.exists(path) else None

    def mapping_fingerprint(self) -> Optional[str]:
        """Hash of the (real → anon) pairs in the sibling mapping file.

        Snapshots produced with the same ``--mapping-file`` share this
        fingerprint. Returns ``None`` when no mapping exists.
        """
        path = self.mapping_path()
        if path is None:
            return None
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        parts = []
        for anon, real in sorted((data.get("projects") or {}).items()):
            parts.append(f"P:{real}={anon}")
        for anon, real in sorted((data.get("streams") or {}).items()):
            parts.append(f"S:{real}={anon}")
        h = hashlib.sha256()
        h.update("\n".join(parts).encode("utf-8"))
        return h.hexdigest()

    # -- Lifecycle ---------------------------------------------------------

    def close(self) -> None:
        try:
            self._zf.close()
        except Exception:
            pass

    def __enter__(self) -> "SnapshotLoader":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


def _parse_filename_timestamp(source: str) -> Optional[datetime]:
    """Parse a ``YYYYMMDD_HHMMSS`` fragment out of a metadata field or filename."""
    if not source:
        return None
    m = _FILENAME_TIMESTAMP_RE.search(source)
    if not m:
        return None
    try:
        return datetime.strptime(f"{m.group(1)}_{m.group(2)}", "%Y%m%d_%H%M%S")
    except ValueError:
        return None


def load_archive_dir(dir_path: str) -> List[SnapshotLoader]:
    """Open every ``*.zip`` in ``dir_path`` (non-recursive) and return them in chronological order.

    Ordering key: ``metadata.export_timestamp`` → filename ``YYYYMMDD_HHMMSS``
    → filesystem mtime. Caller is responsible for closing each loader (use
    ``contextlib.ExitStack``). Raises ``ValueError`` if the directory holds
    fewer than 2 ZIPs — a trend needs at least two data points.
    """
    if not os.path.isdir(dir_path):
        raise ValueError(f"Archive directory does not exist or is not a directory: {dir_path}")
    zip_paths = sorted(glob.glob(os.path.join(dir_path, "*.zip")))
    if len(zip_paths) < 2:
        raise ValueError(
            f"Archive directory must contain at least 2 export ZIPs to build a trend "
            f"({len(zip_paths)} found in {dir_path}). "
            "Add more coverity-export ZIPs to the folder and retry."
        )
    loaders = [SnapshotLoader(p) for p in zip_paths]
    loaders.sort(key=lambda ldr: ldr.order_key)
    return loaders


# ---------------------------------------------------------------------------
# Diff primitives
# ---------------------------------------------------------------------------


def diff_project_set(prev_df: pd.DataFrame, curr_df: pd.DataFrame,
                     key: str = "project_name") -> Dict[str, List[str]]:
    """Set diff on a single key column. Returns sorted ``added / dropped / retained`` lists."""
    prev = set(prev_df[key].dropna().astype(str)) if key in getattr(prev_df, "columns", []) else set()
    curr = set(curr_df[key].dropna().astype(str)) if key in getattr(curr_df, "columns", []) else set()
    return {
        "added": sorted(curr - prev),
        "dropped": sorted(prev - curr),
        "retained": sorted(curr & prev),
    }


# ---------------------------------------------------------------------------
# Time-series compute functions (one per metric family)
# ---------------------------------------------------------------------------


def compute_projects_series(snapshots: Sequence[SnapshotLoader], instance: str) -> dict:
    """Per-snapshot project count series + across-window added/dropped set diff.

    Source: ``total_defects_by_project.json`` (one row per project).

    ``added_first_to_last`` = projects present in *any* snapshot but absent
    from the first snapshot (i.e. entered the window at some point).
    ``dropped_first_to_last`` = projects present in *any* snapshot but
    absent from the last snapshot (i.e. left the window at some point).
    This "ever appeared / ever removed" semantic catches projects that
    were created and then deleted between the endpoints — which
    ``first - last`` would miss but the count series line chart makes
    visible. Each entry in the two lists is a dict carrying the
    ``first_seen_index`` / ``last_seen_index`` (into ``delta.snapshots``)
    plus a ``snapshot_count`` so the HTML can show when the project
    joined and when it left.
    """
    per_snapshot: List[dict] = []
    project_sets: List[set] = []
    for ldr in snapshots:
        df = ldr.load_records(instance, "total_defects_by_project")
        names = set(df["project_name"].dropna().astype(str)) if "project_name" in df.columns else set()
        project_sets.append(names)
        per_snapshot.append({"count": len(names), "projects": sorted(names)})

    first = project_sets[0]
    last = project_sets[-1]
    union_all: set = set().union(*project_sets)
    return {
        "series": per_snapshot,
        "count_series": [row["count"] for row in per_snapshot],
        "added_first_to_last": _timeline_events(project_sets, sorted(union_all - first)),
        "dropped_first_to_last": _timeline_events(project_sets, sorted(union_all - last)),
        "retained_count": len(first & last),
        "first_count": len(first),
        "last_count": len(last),
        "count_delta": len(last) - len(first),
    }


def compute_active_users_series(snapshots: Sequence[SnapshotLoader], instance: str) -> dict:
    """Per-stat time series for user-license metrics + first→last top-fixers diff."""
    stat_keys = ("total_licensed_users", "users_with_login", "active_users",
                 "active_user_percentage", "login_user_percentage")

    per_stat_series: Dict[str, List[Optional[float]]] = {k: [] for k in stat_keys}
    for ldr in snapshots:
        d = ldr.load_dict(instance, "user_license_statistics") or {}
        for k in stat_keys:
            per_stat_series[k].append(_to_number(d.get(k)))

    stats: Dict[str, dict] = {}
    for k in stat_keys:
        series = per_stat_series[k]
        stats[k] = {
            "series": series,
            "first": series[0],
            "last": series[-1],
            "delta": None if series[0] is None or series[-1] is None else series[-1] - series[0],
            "pct_delta": _pct(series[0], series[-1]),
        }

    result: dict = {"stats": stats}

    # Top-fixers set diff uses the same union-based "ever appeared / ever
    # dropped" semantic as compute_projects_series — catches fixers who
    # entered the leaderboard mid-window and later fell off.
    all_top: List[pd.DataFrame] = [
        ldr.load_records(instance, "top_users_by_fixes") for ldr in snapshots
    ]
    if any("username" in df.columns for df in all_top):
        first_set = _column_set(all_top[0], "username")
        last_set = _column_set(all_top[-1], "username")
        union_set: set = set()
        for df in all_top:
            union_set |= _column_set(df, "username")
        result["top_users_by_fixes_first_to_last"] = {
            "added": sorted(union_set - first_set),
            "dropped": sorted(union_set - last_set),
            "retained": sorted(first_set & last_set),
        }
    return result


def compute_scan_activity_series(snapshots: Sequence[SnapshotLoader], instance: str,
                                 window_mismatch: bool) -> dict:
    """Per-snapshot window totals for scan activity + first→last summary.

    Source: ``scan_activity_trend.json``. Values are summed across each
    snapshot's whole window. When ``window_mismatch=True`` a
    ``normalized_per_day`` block is returned alongside raw totals.
    """
    metric_keys = ("scan_count", "total_files_analyzed",
                   "total_new_defects", "total_eliminated_defects")

    per_metric_series: Dict[str, List[float]] = {k: [] for k in metric_keys}
    per_metric_per_day: Dict[str, List[float]] = {k: [] for k in metric_keys}
    window_days = [ldr.days for ldr in snapshots]

    for ldr in snapshots:
        df = ldr.load_records(instance, "scan_activity_trend")
        days = max(ldr.days, 1)
        for k in metric_keys:
            total = _sum_col(df, k)
            per_metric_series[k].append(total)
            per_metric_per_day[k].append(round(total / days, 3))

    totals: Dict[str, dict] = {}
    for k in metric_keys:
        series = per_metric_series[k]
        totals[k] = {
            "series": series,
            "first": series[0],
            "last": series[-1],
            "delta": series[-1] - series[0],
            "pct_delta": _pct(series[0], series[-1]),
        }

    out: dict = {
        "window_days_per_snapshot": window_days,
        "totals": totals,
    }
    if window_mismatch:
        out["normalized_per_day"] = {
            k: {
                "series": per_metric_per_day[k],
                "first": per_metric_per_day[k][0],
                "last": per_metric_per_day[k][-1],
            }
            for k in metric_keys
        }
    else:
        out["normalized_per_day"] = None
    return out


def compute_snapshot_cadence_series(snapshots: Sequence[SnapshotLoader], instance: str) -> dict:
    """Per-snapshot active-stream count + across-window stream set diff.

    Source: ``snapshot_performance.json`` — a top-N-recent sample. Per-stream
    scan-count deltas from this sample are noisy (see v1.1.4 note), so we
    only surface which streams had *any* activity in the sample.

    ``newly_active_first_to_last`` = streams active in any snapshot but not
    the first (entered the window). ``went_dark_first_to_last`` = streams
    active in any snapshot but not the last (left the window). Symmetric
    with ``compute_projects_series`` so streams that briefly appeared and
    then went silent are captured.
    """
    per_snapshot: List[dict] = []
    stream_sets: List[set] = []
    for ldr in snapshots:
        df = ldr.load_records(instance, "snapshot_performance")
        streams = _unique_streams(df)
        stream_sets.append(streams)
        per_snapshot.append({
            "active_stream_count": len(streams),
            "sample_size": int(len(df)) if isinstance(df, pd.DataFrame) else 0,
        })

    first = stream_sets[0]
    last = stream_sets[-1]
    union_all: set = set().union(*stream_sets)
    return {
        "stream_activity_series": per_snapshot,
        "active_stream_count_series": [row["active_stream_count"] for row in per_snapshot],
        "newly_active_first_to_last": _timeline_events(stream_sets, sorted(union_all - first)),
        "went_dark_first_to_last": _timeline_events(stream_sets, sorted(union_all - last)),
        "retained_count": len(first & last),
        "first_stream_count": len(first),
        "last_stream_count": len(last),
        "note": (
            "Streams count as \"active\" here if they had at least one scan "
            "in the recent-activity window each export captured (the 100 most "
            "recent snapshots across all streams at the moment of export). "
            "Per-stream scan-count deltas from this source are noisy — one "
            "new scan on any stream evicts the oldest row for another — so "
            "only the set of streams with any recent scans is reported."
        ),
    }


def _unique_streams(df: pd.DataFrame) -> set:
    if not isinstance(df, pd.DataFrame) or df.empty or "stream_name" not in df.columns:
        return set()
    return set(df["stream_name"].dropna().astype(str).unique())


def _column_set(df: pd.DataFrame, col: str) -> set:
    if not isinstance(df, pd.DataFrame) or df.empty or col not in df.columns:
        return set()
    return set(df[col].dropna().astype(str))


def _timeline_events(sets_by_snapshot: Sequence[set], names: Sequence[str]) -> List[dict]:
    """Build ``{name, first_seen_index, last_seen_index, snapshot_count}``
    entries so the HTML can render "joined Q2/26" / "last seen Q3/26"
    tags on added/dropped lists.

    Indices reference positions in ``delta.snapshots`` (0-based). The
    HTML resolves them to labels at render time. Order preserves the
    input ``names`` sequence.
    """
    events: List[dict] = []
    for name in names:
        first_i: Optional[int] = None
        last_i: Optional[int] = None
        count = 0
        for i, s in enumerate(sets_by_snapshot):
            if name in s:
                if first_i is None:
                    first_i = i
                last_i = i
                count += 1
        events.append({
            "name": name,
            "first_seen_index": first_i,
            "last_seen_index": last_i,
            "snapshot_count": count,
        })
    return events


def compute_defects_by_project_series(snapshots: Sequence[SnapshotLoader], instance: str) -> dict:
    """One row per project (union across the window) with active/rank series.

    Missing snapshots for a given project → ``None`` in that slot in
    ``active_series`` and ``rank_series``. Ranking is recomputed per
    snapshot via dense-rank on ``active_defects``.
    """
    per_snap_active: List[Dict[str, Optional[float]]] = []
    per_snap_ranks: List[Dict[str, int]] = []

    for ldr in snapshots:
        df = ldr.load_records(instance, "total_defects_by_project")
        active_map: Dict[str, Optional[float]] = {}
        ranks_map: Dict[str, int] = {}
        if isinstance(df, pd.DataFrame) and not df.empty and "project_name" in df.columns:
            work = df.copy()
            work["project_name"] = work["project_name"].astype(str)
            if "active_defects" in work.columns:
                work["active_defects"] = pd.to_numeric(work["active_defects"], errors="coerce")
                for _, row in work.iterrows():
                    active_map[row["project_name"]] = _to_number(row["active_defects"])
                work["_rank"] = work["active_defects"].rank(ascending=False, method="dense")
                for _, row in work.iterrows():
                    r = row["_rank"]
                    if pd.notna(r):
                        ranks_map[row["project_name"]] = int(r)
            else:
                for name in work["project_name"]:
                    active_map[name] = None
        per_snap_active.append(active_map)
        per_snap_ranks.append(ranks_map)

    all_projects: set = set()
    for m in per_snap_active:
        all_projects.update(m.keys())

    per_project: List[dict] = []
    n = len(snapshots)
    for name in sorted(all_projects):
        active_series: List[Optional[float]] = [per_snap_active[i].get(name) for i in range(n)]
        rank_series: List[Optional[int]] = [per_snap_ranks[i].get(name) for i in range(n)]

        # Endpoints reflect the actual first and last snapshot slots — a
        # project absent at either end reports None there. This is what
        # drives the "new" / "dropped" / "came & went" indicators in the
        # HTML; using the first/last *observed* values would hide
        # transient projects.
        first_active = active_series[0]
        last_active = active_series[-1]
        first_rank = rank_series[0]
        last_rank = rank_series[-1]

        appeared_at = _first_present_index(active_series)
        # ``dropped_at`` only meaningful if the project is absent at the end.
        dropped_index = None
        if active_series[-1] is None:
            dropped_index = _last_present_index(active_series)

        per_project.append({
            "project_name": name,
            "active_series": active_series,
            "rank_series": rank_series,
            "active_first": first_active,
            "active_last": last_active,
            "active_delta": (None if first_active is None or last_active is None
                             else last_active - first_active),
            "active_pct_delta": _pct(first_active, last_active),
            "rank_first": first_rank,
            "rank_last": last_rank,
            "rank_delta": (None if first_rank is None or last_rank is None
                           else first_rank - last_rank),
            "appeared_at_index": appeared_at if appeared_at not in (None, 0) else None,
            "dropped_at_index": dropped_index,
        })

    return {"per_project": per_project}


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def build_trend(snapshots: Sequence[SnapshotLoader],
                labels: Sequence[str],
                warnings: List[dict],
                allow_window_mismatch: bool) -> dict:
    """Assemble the top-level trend document across all instances.

    ``snapshots`` must be in chronological order (oldest first) and
    ``labels`` must be the same length. All loaders are guaranteed to
    share the same instance list by the validation gate.
    """
    if len(snapshots) < 2:
        raise ValueError("build_trend requires at least 2 snapshots")
    if len(labels) != len(snapshots):
        raise ValueError(
            f"labels length {len(labels)} does not match snapshots length {len(snapshots)}"
        )

    days_values = {ldr.days for ldr in snapshots}
    window_mismatch = len(days_values) > 1

    instances_out: Dict[str, dict] = {}
    for instance in snapshots[0].instance_names:
        instances_out[instance] = {
            "projects": compute_projects_series(snapshots, instance),
            "active_users": compute_active_users_series(snapshots, instance),
            "scan_activity": compute_scan_activity_series(
                snapshots, instance, window_mismatch=window_mismatch
            ),
            "snapshot_cadence": compute_snapshot_cadence_series(snapshots, instance),
            "defects_by_project": compute_defects_by_project_series(snapshots, instance),
        }

    return {
        "schema_version": DELTA_SCHEMA_VERSION,
        "generated": datetime.now().isoformat(timespec="seconds"),
        "snapshots": [
            {
                "label": labels[i],
                "zip": os.path.basename(snapshots[i].zip_path),
                "export_date": snapshots[i].export_date,
                "export_timestamp": snapshots[i].export_timestamp,
                "days": snapshots[i].days,
            }
            for i in range(len(snapshots))
        ],
        "instances": instances_out,
        "warnings": list(warnings),
    }


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _sum_col(df: pd.DataFrame, col: str) -> float:
    if not isinstance(df, pd.DataFrame) or col not in df.columns:
        return 0.0
    total = pd.to_numeric(df[col], errors="coerce").fillna(0).sum()
    return float(total)


def _to_number(v):
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if pd.isna(f):
        return None
    if f.is_integer():
        return int(f)
    return f


def _pct(prev, curr) -> Optional[float]:
    pv = _to_number(prev)
    cv = _to_number(curr)
    if pv is None or cv is None or pv == 0:
        return None
    return round((cv - pv) / pv * 100.0, 2)


def _first_present_index(series):
    for i, v in enumerate(series):
        if v is not None:
            return i
    return None


def _last_present_index(series):
    for i in range(len(series) - 1, -1, -1):
        if series[i] is not None:
            return i
    return None

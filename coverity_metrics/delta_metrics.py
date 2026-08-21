"""Quarter-over-quarter delta computation over ``coverity-export`` ZIPs.

Consumes two snapshot ZIPs produced by :mod:`coverity_metrics.cli.export` and
returns per-instance adoption deltas: projects added/dropped, active users,
scan activity, snapshot cadence, and defects-by-project (with ranking
movement). Nothing here talks to the database — every input comes from
the per-metric JSONs bundled inside the export ZIP.

Kept separate from ``multi_instance_metrics.py`` because that module owns
cross-instance aggregation at a single point in time, while this module
owns single-instance comparison across two points in time. They will
eventually meet, but not in v1.1.4.
"""
from __future__ import annotations

import hashlib
import json
import os
import zipfile
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd

from coverity_metrics.anonymizer import default_mapping_path


DELTA_SCHEMA_VERSION = 1


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
            with self._zf.open("metadata.json") as f:
                self._metadata = json.load(f)
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

        Two snapshots produced with the same ``--mapping-file`` share this
        fingerprint. Returns ``None`` when no mapping exists (non-anonymized
        export).
        """
        path = self.mapping_path()
        if path is None:
            return None
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Only the (anon → real) pairs affect ID stability; ignore
        # ``created`` timestamp and ``instance`` (the latter can legitimately
        # differ across snapshots that reuse the same shared mapping file
        # across multiple instances).
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


def diff_numeric(prev_df: pd.DataFrame, curr_df: pd.DataFrame,
                 key: str, value_cols: List[str]) -> pd.DataFrame:
    """Outer-join two frames on *key* and add per-value-col ``delta`` / ``pct_delta``.

    Keys that appear in only one snapshot get NaN on the missing side and
    the delta is computed with the missing side treated as 0 (so an "added"
    project shows ``curr - 0``). ``pct_delta`` is NaN when the previous
    value is 0 or missing — avoids div-by-zero without dropping the row.
    """
    prev = _ensure_key_frame(prev_df, key, value_cols)
    curr = _ensure_key_frame(curr_df, key, value_cols)
    merged = prev.merge(curr, on=key, how="outer", suffixes=("_prev", "_curr"))
    for col in value_cols:
        prev_col = f"{col}_prev"
        curr_col = f"{col}_curr"
        merged[prev_col] = pd.to_numeric(merged.get(prev_col), errors="coerce")
        merged[curr_col] = pd.to_numeric(merged.get(curr_col), errors="coerce")
        merged[f"{col}_delta"] = merged[curr_col].sub(merged[prev_col], fill_value=0)
        prev_safe = merged[prev_col].where(merged[prev_col] != 0)
        merged[f"{col}_pct_delta"] = (merged[f"{col}_delta"] / prev_safe) * 100.0
    return merged


def diff_ranking(prev_df: pd.DataFrame, curr_df: pd.DataFrame,
                 key: str, rank_col: str) -> pd.DataFrame:
    """Compute ``rank_prev`` / ``rank_curr`` (1 = highest ``rank_col``) and
    ``rank_delta`` = ``rank_prev - rank_curr`` (positive = climbed).

    Ties get the same rank via dense ranking so a two-way tie for #1 is
    reported as rank 1 twice, not 1 and 2.
    """
    prev = _rank_frame(prev_df, key, rank_col, suffix="_prev")
    curr = _rank_frame(curr_df, key, rank_col, suffix="_curr")
    merged = prev.merge(curr, on=key, how="outer")
    merged["rank_prev"] = merged["rank_prev"].astype("Int64")
    merged["rank_curr"] = merged["rank_curr"].astype("Int64")
    merged["rank_delta"] = merged["rank_prev"] - merged["rank_curr"]
    return merged


def _ensure_key_frame(df: pd.DataFrame, key: str, value_cols: List[str]) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or key not in df.columns:
        return pd.DataFrame({key: pd.Series(dtype="object"),
                             **{c: pd.Series(dtype="float64") for c in value_cols}})
    cols = [key] + [c for c in value_cols if c in df.columns]
    return df[cols].copy()


def _rank_frame(df: pd.DataFrame, key: str, col: str, suffix: str) -> pd.DataFrame:
    rank_col = f"rank{suffix}"
    if (not isinstance(df, pd.DataFrame) or df.empty
            or key not in df.columns or col not in df.columns):
        return pd.DataFrame({key: pd.Series(dtype="object"),
                             rank_col: pd.Series(dtype="Int64")})
    out = df[[key, col]].copy()
    out[col] = pd.to_numeric(out[col], errors="coerce")
    out[rank_col] = out[col].rank(ascending=False, method="dense")
    return out[[key, rank_col]]


# ---------------------------------------------------------------------------
# MVP metric-family compute functions
# ---------------------------------------------------------------------------


def compute_projects_delta(prev: SnapshotLoader, curr: SnapshotLoader,
                           instance: str) -> dict:
    """Projects present in each snapshot — added / dropped / retained.

    Source: ``total_defects_by_project.json`` (instance-scope rows keyed by
    ``project_name``).
    """
    prev_df = prev.load_records(instance, "total_defects_by_project")
    curr_df = curr.load_records(instance, "total_defects_by_project")
    partition = diff_project_set(prev_df, curr_df, key="project_name")
    return {
        "prev_count": _project_count(prev_df),
        "curr_count": _project_count(curr_df),
        "added": partition["added"],
        "dropped": partition["dropped"],
        "retained_count": len(partition["retained"]),
    }


def _project_count(df: pd.DataFrame) -> int:
    if not isinstance(df, pd.DataFrame) or "project_name" not in df.columns:
        return 0
    return int(df["project_name"].dropna().astype(str).nunique())


def compute_active_users_delta(prev: SnapshotLoader, curr: SnapshotLoader,
                               instance: str) -> dict:
    """Active-user scalar delta from ``user_license_statistics.json``.

    Optionally augmented by a set diff on the ``top_users_by_fixes.json``
    ``username`` column when that metric is present in both snapshots.
    """
    p = prev.load_dict(instance, "user_license_statistics") or {}
    c = curr.load_dict(instance, "user_license_statistics") or {}
    stats = {}
    for key in ("total_licensed_users", "users_with_login", "active_users",
                "active_user_percentage", "login_user_percentage"):
        stats[key] = _scalar_delta(p.get(key), c.get(key))

    result: dict = {"stats": stats}

    tup_prev = prev.load_records(instance, "top_users_by_fixes")
    tup_curr = curr.load_records(instance, "top_users_by_fixes")
    if "username" in tup_prev.columns or "username" in tup_curr.columns:
        result["top_users_by_fixes"] = diff_project_set(tup_prev, tup_curr, key="username")
    return result


def compute_scan_activity_delta(prev: SnapshotLoader, curr: SnapshotLoader,
                                instance: str, window_mismatch: bool) -> dict:
    """Scan-activity totals across each snapshot's window.

    Source: ``scan_activity_trend.json`` (time-series of per-period totals).
    We sum each numeric column across the whole series and report the raw
    total delta. When the two snapshots' ``days`` windows differ the caller
    passes ``window_mismatch=True`` and this function surfaces a
    ``normalized_per_day`` block so the numbers stay meaningful.
    """
    p = prev.load_records(instance, "scan_activity_trend")
    c = curr.load_records(instance, "scan_activity_trend")
    metric_keys = ("scan_count", "total_files_analyzed",
                   "total_new_defects", "total_eliminated_defects")
    totals_prev = {k: _sum_col(p, k) for k in metric_keys}
    totals_curr = {k: _sum_col(c, k) for k in metric_keys}

    out = {
        "window_days_prev": prev.days,
        "window_days_curr": curr.days,
        "totals": {
            k: {
                "prev": totals_prev[k],
                "curr": totals_curr[k],
                "delta": totals_curr[k] - totals_prev[k],
                "pct_delta": _pct(totals_prev[k], totals_curr[k]),
            }
            for k in metric_keys
        },
    }
    if window_mismatch:
        pd_days = max(prev.days, 1)
        cd_days = max(curr.days, 1)
        out["normalized_per_day"] = {
            k: {
                "prev": round(totals_prev[k] / pd_days, 3),
                "curr": round(totals_curr[k] / cd_days, 3),
            }
            for k in metric_keys
        }
    return out


def compute_snapshot_cadence_delta(prev: SnapshotLoader, curr: SnapshotLoader,
                                   instance: str) -> dict:
    """Which streams have activity in each snapshot's recent-sample.

    Source: ``snapshot_performance.json`` — a top-N-recent sample (default
    ``limit=100`` at instance scope) of the most recent snapshots across all
    streams. This is a perf-inspection sample, **not** a full snapshot
    history, so per-stream *count* deltas from this source are dominated by
    top-N sliding: one new snapshot on any stream evicts the oldest one,
    so Checker's count can drop from 97 → 96 without any real change on
    Checkers. We therefore only surface a **set diff** on stream names
    ("did this stream have any activity in the recent sample?") — the
    noise cancels out and the surviving signal is genuinely useful
    ("stream X went dark", "stream Y newly active").
    """
    prev_df = prev.load_records(instance, "snapshot_performance")
    curr_df = curr.load_records(instance, "snapshot_performance")

    prev_streams = _unique_streams(prev_df)
    curr_streams = _unique_streams(curr_df)

    added = sorted(curr_streams - prev_streams)
    dropped = sorted(prev_streams - curr_streams)
    retained = sorted(curr_streams & prev_streams)

    return {
        "stream_activity": {
            "added": added,
            "dropped": dropped,
            "retained_count": len(retained),
            "prev_stream_count": len(prev_streams),
            "curr_stream_count": len(curr_streams),
        },
        "sample_size": {
            "prev": int(len(prev_df)) if isinstance(prev_df, pd.DataFrame) else 0,
            "curr": int(len(curr_df)) if isinstance(curr_df, pd.DataFrame) else 0,
        },
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



def compute_defects_by_project_delta(prev: SnapshotLoader, curr: SnapshotLoader,
                                     instance: str) -> dict:
    """Per-project defect Δ + %Δ + ranking movement.

    Source: ``total_defects_by_project.json``. Ranking is on
    ``active_defects`` (dense rank, highest count = #1). ``rank_delta > 0``
    means the project climbed the outstanding-defects ranking; ``< 0`` means
    it dropped. Rows added or dropped between snapshots carry ``<NA>`` on
    the missing side.
    """
    prev_df = prev.load_records(instance, "total_defects_by_project")
    curr_df = curr.load_records(instance, "total_defects_by_project")
    numeric = diff_numeric(
        prev_df, curr_df, key="project_name",
        value_cols=["defect_count", "active_defects", "fixed_defects"],
    )
    ranking = diff_ranking(prev_df, curr_df, key="project_name",
                           rank_col="active_defects")
    merged = numeric.merge(ranking, on="project_name", how="outer")
    return {"per_project": _df_to_records(merged)}


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def build_delta(prev: SnapshotLoader, curr: SnapshotLoader,
                label_prev: str, label_curr: str,
                warnings: List[dict],
                allow_window_mismatch: bool) -> dict:
    """Assemble the top-level ``delta.json`` document across all instances.

    ``warnings`` is a mutable list already populated by the validation gate
    (window mismatch, mapping mismatch, missing mapping on one side); this
    function may append its own entries as it walks each instance.
    """
    window_mismatch = prev.days != curr.days
    instances_out: Dict[str, dict] = {}
    # Both loaders must agree on instance list (guarded by validate_snapshots),
    # so it's safe to iterate either side.
    for instance in prev.instance_names:
        instances_out[instance] = {
            "projects": compute_projects_delta(prev, curr, instance),
            "active_users": compute_active_users_delta(prev, curr, instance),
            "scan_activity": compute_scan_activity_delta(
                prev, curr, instance, window_mismatch=window_mismatch
            ),
            "snapshot_cadence": compute_snapshot_cadence_delta(prev, curr, instance),
            "defects_by_project": compute_defects_by_project_delta(prev, curr, instance),
        }

    return {
        "schema_version": DELTA_SCHEMA_VERSION,
        "generated": datetime.now().isoformat(timespec="seconds"),
        "previous": {
            "label": label_prev,
            "zip": os.path.basename(prev.zip_path),
            "export_date": prev.export_date,
            "days": prev.days,
        },
        "current": {
            "label": label_curr,
            "zip": os.path.basename(curr.zip_path),
            "export_date": curr.export_date,
            "days": curr.days,
        },
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


def _scalar_delta(prev, curr) -> dict:
    pv = _to_number(prev)
    cv = _to_number(curr)
    return {
        "prev": pv,
        "curr": cv,
        "delta": None if pv is None or cv is None else cv - pv,
        "pct_delta": _pct(pv, cv),
    }


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


def _df_to_records(df: pd.DataFrame) -> List[dict]:
    """Serialize a DataFrame to a JSON-safe list of dicts.

    Replaces ``NaN`` / ``<NA>`` with ``None`` so ``json.dumps`` accepts the
    payload without a custom encoder.
    """
    if not isinstance(df, pd.DataFrame) or df.empty:
        return []
    return json.loads(df.to_json(orient="records"))

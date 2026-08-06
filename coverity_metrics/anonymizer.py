"""Deterministic anonymization of project and stream names for exports.

Real names are replaced with sequential ``project_NNN`` / ``stream_NNN`` ids.
The mapping is persisted next to the ZIP so the user can decode later, while
the ZIP itself contains no real names and can be safely shared.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Dict, Iterable, List, Optional

import pandas as pd


MAPPING_SCHEMA_VERSION = 1


# Extra column-name treatments for metrics whose SQL uses a non-canonical alias.
# Maps metric name → dict with optional "project_cols" / "stream_cols" lists.
# ``top_projects_by_classification`` uses ``name`` for either the project name
# (instance scope) or the stream name (project scope); ``is_project_scope`` at
# call time decides which. ``total_defects_by_project`` reuses the
# ``project_name`` alias for **stream** names when scoped to a single project
# (SQL: ``SELECT s.name AS project_name ... GROUP BY s.name``), so at project
# scope its ``project_name`` column must be anonymized as a stream instead.
_EXTRA_COLUMNS = {
    "triage_trends": {"stream_cols": ["stream"]},
    "top_projects_by_classification": {
        "project_cols_instance": ["name"],
        "stream_cols_project": ["name"],
    },
    "total_defects_by_project": {
        "project_cols_project_suppress": ["project_name"],
        "stream_cols_project": ["project_name"],
    },
}


class Anonymizer:
    """Assign stable anonymous ids to real project/stream names.

    Ordering is first-seen: the first name passed to ``project_id`` becomes
    ``project_001``, the second becomes ``project_002``, and so on. When an
    existing mapping is loaded via :meth:`load`, the counters continue from
    the highest previously-assigned id so re-exports keep the same ids.
    """

    def __init__(self, project_prefix: str = "project_",
                 stream_prefix: str = "stream_", width: int = 3):
        self.project_prefix = project_prefix
        self.stream_prefix = stream_prefix
        self.width = width
        self._projects: Dict[str, str] = {}
        self._streams: Dict[str, str] = {}
        self._project_counter = 0
        self._stream_counter = 0
        self._instance: Optional[str] = None

    @property
    def is_active(self) -> bool:
        return bool(self._projects or self._streams)

    def set_instance(self, instance_name: str) -> None:
        self._instance = instance_name

    def _format_id(self, prefix: str, n: int) -> str:
        width = max(self.width, len(str(n)))
        return f"{prefix}{n:0{width}d}"

    def project_id(self, real_name) -> str:
        if real_name is None or (isinstance(real_name, float) and pd.isna(real_name)):
            return real_name
        key = str(real_name)
        if key in self._projects:
            return self._projects[key]
        self._project_counter += 1
        anon = self._format_id(self.project_prefix, self._project_counter)
        self._projects[key] = anon
        return anon

    def stream_id(self, real_name) -> str:
        if real_name is None or (isinstance(real_name, float) and pd.isna(real_name)):
            return real_name
        key = str(real_name)
        if key in self._streams:
            return self._streams[key]
        self._stream_counter += 1
        anon = self._format_id(self.stream_prefix, self._stream_counter)
        self._streams[key] = anon
        return anon

    def preload_projects(self, real_names: Iterable[str]) -> Dict[str, str]:
        """Assign ids for a whole list up front (preserving input order)."""
        return {name: self.project_id(name) for name in real_names}

    def apply_to_dataframe(self, df, metric_name: Optional[str] = None,
                           is_project_scope: bool = False):
        """Return a copy of *df* with project/stream columns anonymized.

        By default swaps ``project_name`` and ``stream_name``. If *metric_name*
        matches an entry in :data:`_EXTRA_COLUMNS`, additional columns are also
        swapped:

        - ``triage_trends`` → ``stream`` column is treated as a stream.
        - ``top_projects_by_classification`` → ``name`` column is a project name
          at instance scope, or a stream name at project scope (per
          *is_project_scope*).
        """
        if not isinstance(df, pd.DataFrame) or df.empty:
            return df
        project_cols: List[str] = ["project_name"]
        stream_cols: List[str] = ["stream_name"]
        extras = _EXTRA_COLUMNS.get(metric_name or "", {})
        project_cols += extras.get("project_cols", [])
        stream_cols += extras.get("stream_cols", [])
        if is_project_scope:
            stream_cols += extras.get("stream_cols_project", [])
            # A metric may re-alias a stream column as ``project_name`` when
            # project-scoped; suppress the default project sweep for those.
            for col in extras.get("project_cols_project_suppress", []):
                if col in project_cols:
                    project_cols.remove(col)
        else:
            project_cols += extras.get("project_cols_instance", [])

        touched = False
        out = df
        for col in project_cols:
            if col in df.columns:
                if not touched:
                    out = df.copy()
                    touched = True
                out[col] = out[col].map(
                    lambda v: self.project_id(v) if v is not None and not (isinstance(v, float) and pd.isna(v)) else v
                )
        for col in stream_cols:
            if col in df.columns:
                if not touched:
                    out = df.copy()
                    touched = True
                out[col] = out[col].map(
                    lambda v: self.stream_id(v) if v is not None and not (isinstance(v, float) and pd.isna(v)) else v
                )
        return out

    # --- Persistence -----------------------------------------------------

    def to_dict(self) -> dict:
        # projects/streams are written as anon_id -> real_name for easy human decoding.
        return {
            "version": MAPPING_SCHEMA_VERSION,
            "created": datetime.now().isoformat(timespec="seconds"),
            "instance": self._instance,
            "projects": {anon: real for real, anon in self._projects.items()},
            "streams": {anon: real for real, anon in self._streams.items()},
        }

    def save(self, path: str) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, path: str, project_prefix: str = "project_",
             stream_prefix: str = "stream_", width: int = 3) -> "Anonymizer":
        inst = cls(project_prefix=project_prefix, stream_prefix=stream_prefix, width=width)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        version = data.get("version", 1)
        if version != MAPPING_SCHEMA_VERSION:
            raise ValueError(f"Unsupported mapping file version: {version}")
        inst._instance = data.get("instance")
        projects = data.get("projects", {}) or {}
        streams = data.get("streams", {}) or {}
        # Rehydrate real -> anon; recompute counters from numeric suffixes.
        for anon, real in projects.items():
            inst._projects[str(real)] = str(anon)
        for anon, real in streams.items():
            inst._streams[str(real)] = str(anon)
        inst._project_counter = _max_suffix(projects.keys(), project_prefix)
        inst._stream_counter = _max_suffix(streams.keys(), stream_prefix)
        return inst

    @classmethod
    def load_or_new(cls, path: Optional[str], **kwargs) -> "Anonymizer":
        if path and os.path.exists(path):
            return cls.load(path, **kwargs)
        return cls(**kwargs)


def _max_suffix(ids: Iterable[str], prefix: str) -> int:
    highest = 0
    for anon in ids:
        if not anon.startswith(prefix):
            continue
        tail = anon[len(prefix):]
        if tail.isdigit():
            highest = max(highest, int(tail))
    return highest


def default_mapping_path(zip_path: str) -> str:
    """Return the sibling mapping-file path for *zip_path*.

    ``coverity_export_Production_20260805.zip`` →
    ``coverity_export_Production_20260805.mapping.json``
    """
    stem, _ = os.path.splitext(zip_path)
    return f"{stem}.mapping.json"

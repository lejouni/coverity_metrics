"""``coverity-delta`` — multi-snapshot trend comparison report.

Consumes every ``*.zip`` inside a folder produced by iterated
:mod:`coverity_metrics.cli.export` runs and emits an adoption-focused
trend report as JSON (``delta.json``) and an HTML dashboard
(``dashboard_delta.html``). Runs entirely offline — no database access.

See ``coverity_metrics/delta_metrics.py`` for the compute engine and
``coverity_metrics/templates/dashboard_delta.html`` for the rendered layout.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
from datetime import date, datetime
from typing import List, Optional, Sequence

from jinja2 import Environment, FileSystemLoader

from coverity_metrics.delta_metrics import (
    SnapshotLoader,
    build_trend,
    load_archive_dir,
)


def _load_inline_css() -> str:
    """Return the dashboard CSS so the delta HTML is self-contained."""
    css_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "static", "css", "dashboard.css",
    )
    try:
        with open(css_path, "r", encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def _template_env() -> Environment:
    template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
    return Environment(loader=FileSystemLoader(template_dir))


# ---------------------------------------------------------------------------
# Validation gate
# ---------------------------------------------------------------------------


def _validate(snapshots: Sequence[SnapshotLoader],
              allow_window_mismatch: bool) -> List[dict]:
    """Enforce cross-snapshot compatibility rules across the whole archive.

    Hard-fails on incompatible snapshots (differing instance sets,
    conflicting anonymization mappings, mismatched windows without opt-in).
    Returns a warnings list for conditions we surface but not block on
    (missing mapping on a subset, opt-in window mismatch).
    """
    warnings: List[dict] = []

    # Instance list must be identical across every snapshot.
    baseline_names = set(snapshots[0].instance_names)
    for ldr in snapshots[1:]:
        other = set(ldr.instance_names)
        if other != baseline_names:
            only_baseline = sorted(baseline_names - other)
            only_other = sorted(other - baseline_names)
            raise SystemExit(
                "[ERROR] Snapshot instance lists differ across the archive — cannot compare.\n"
                f"        Baseline ({os.path.basename(snapshots[0].zip_path)}): "
                f"{sorted(baseline_names)}\n"
                f"        Offender ({os.path.basename(ldr.zip_path)}): {sorted(other)}\n"
                f"        Only in baseline: {only_baseline or '<none>'}\n"
                f"        Only in offender: {only_other or '<none>'}\n"
                "        Re-run every export against the same config.json."
            )

    # ``--days`` window must match across every snapshot.
    days_values = {ldr.days for ldr in snapshots}
    if len(days_values) > 1:
        per_snapshot = ", ".join(
            f"{os.path.basename(ldr.zip_path)}:--days {ldr.days}" for ldr in snapshots
        )
        if not allow_window_mismatch:
            raise SystemExit(
                "[ERROR] Snapshot windows differ across the archive — windowed metrics "
                "(scan activity, snapshot cadence) are not directly comparable.\n"
                f"        Per snapshot: {per_snapshot}\n"
                "        Recommended: re-export the odd-one-out with matching --days.\n"
                "        Testing / advanced: re-run with --allow-window-mismatch to "
                "produce a report anyway; affected metrics will be tagged."
            )
        warnings.append({
            "code": "window_mismatch",
            "message": (
                f"Snapshot windows differ across the archive ({per_snapshot}). "
                "Windowed metric series are not directly comparable; a normalized "
                "per-day view is included alongside the raw totals."
            ),
            "days_per_snapshot": [ldr.days for ldr in snapshots],
        })

    # Anonymization mapping fingerprints must match across every snapshot that has one.
    fingerprints = [ldr.mapping_fingerprint() for ldr in snapshots]
    present = [(i, fp) for i, fp in enumerate(fingerprints) if fp is not None]
    absent = [i for i, fp in enumerate(fingerprints) if fp is None]
    if present:
        distinct_fps = {fp for _, fp in present}
        if len(distinct_fps) > 1:
            raise SystemExit(
                "[ERROR] Anonymization mappings differ between snapshots — "
                "anonymized ids point at different real names, so a trend "
                "report would be meaningless.\n"
                "        Fix: re-run every export with the same --mapping-file "
                "so the id assignments stay stable across time."
            )
        if absent:
            missing_names = [os.path.basename(snapshots[i].zip_path) for i in absent]
            warnings.append({
                "code": "mapping_missing_some",
                "message": (
                    "Anonymization mapping present on some snapshots but missing on "
                    f"{len(absent)}: {missing_names}. Identifier stability across the "
                    "archive cannot be verified for those; treat added/dropped project "
                    "lists with caution."
                ),
            })

    return warnings


# ---------------------------------------------------------------------------
# Label derivation
# ---------------------------------------------------------------------------


def _derive_label(export_date: str, fallback: str) -> str:
    """Turn an ISO ``export_date`` into a ``YYYY-QN`` label."""
    if not export_date:
        return fallback
    try:
        dt = datetime.fromisoformat(export_date)
    except ValueError:
        try:
            dt = datetime.fromisoformat(export_date[:19])
        except ValueError:
            return export_date or fallback
    quarter = (dt.month - 1) // 3 + 1
    return f"{dt.year}-Q{quarter}"


def _derive_labels(snapshots: Sequence[SnapshotLoader],
                   cli_labels: Optional[Sequence[str]]) -> List[str]:
    """Merge CLI-supplied labels with auto-derived ``YYYY-QN`` labels.

    ``cli_labels`` map positionally to snapshots in chronological order.
    Fewer labels than snapshots → the tail is auto-derived. Extras are
    ignored with a note in stderr.
    """
    labels: List[str] = []
    supplied = list(cli_labels or [])
    if len(supplied) > len(snapshots):
        print(
            f"[WARN] {len(supplied)} labels supplied for {len(snapshots)} snapshots — "
            f"ignoring the last {len(supplied) - len(snapshots)}.",
            file=sys.stderr,
        )
        supplied = supplied[: len(snapshots)]

    used_defaults: set = set()
    for i, ldr in enumerate(snapshots):
        if i < len(supplied) and supplied[i]:
            labels.append(supplied[i])
            continue
        default = _derive_label(ldr.export_date, f"snapshot_{i + 1}")
        # Disambiguate duplicate auto-labels by appending an index suffix.
        if default in used_defaults:
            default = f"{default} #{i + 1}"
        used_defaults.add(default)
        labels.append(default)
    return labels


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _render_html(delta: dict, output_path: str) -> None:
    env = _template_env()
    template = env.get_template("dashboard_delta.html")
    html = template.render(
        delta=delta,
        inline_css=_load_inline_css(),
        generated=delta.get("generated") or datetime.now().isoformat(timespec="seconds"),
    )
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)


def _write_json(delta: dict, output_path: str) -> None:
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(delta, f, indent=2, default=_json_fallback)


def _json_fallback(obj):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="coverity-delta",
        description=(
            "Compare every coverity-export snapshot ZIP in a folder and emit a "
            "trend report (JSON + HTML). Snapshots are ordered chronologically by "
            "the export_timestamp inside each ZIP. Runs offline; no database access."
        ),
    )
    parser.add_argument(
        "--archive-dir", "-a", required=False,
        help=("Folder containing two or more coverity-export ZIPs. Ordering key: "
              "metadata.export_timestamp inside each ZIP, then filename YYYYMMDD_HHMMSS, "
              "then filesystem mtime."),
    )
    parser.add_argument("--output", "-o", default="delta",
                        help="Output directory (default: delta/)")
    parser.add_argument("--format", "-f", choices=("json", "html", "both"), default="both",
                        help="Which artifact(s) to produce (default: both)")
    parser.add_argument(
        "--labels", default=None,
        help=("Comma-separated labels for snapshots in chronological order. "
              "Fewer labels than snapshots → the tail is auto-derived from export_date "
              "(YYYY-QN). Example: --labels 2026-Q1,2026-Q2,2026-Q3"),
    )
    parser.add_argument(
        "--allow-window-mismatch", action="store_true",
        help=("Allow comparing snapshots whose --days windows differ. Windowed metrics "
              "are tagged with a warning in the output and a normalized per-day series "
              "is included. Intended for testing / advanced use, not production reports."),
    )
    parser.add_argument("--version", action="store_true", help="Print version and exit")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = _parse_args(argv)

    if args.version:
        try:
            from coverity_metrics.__version__ import __version__
            print(f"coverity-metrics delta version: {__version__}")
        except Exception:
            print("coverity-metrics delta version: unknown")
        return 0

    if not args.archive_dir:
        print("[ERROR] --archive-dir is required. Point it at a folder of coverity-export "
              "ZIPs (2 or more).", file=sys.stderr)
        return 2

    if not os.path.isdir(args.archive_dir):
        print(f"[ERROR] Archive directory not found or not a directory: {args.archive_dir}",
              file=sys.stderr)
        return 2

    os.makedirs(args.output, exist_ok=True)

    try:
        loaders = load_archive_dir(args.archive_dir)
    except ValueError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 2

    cli_labels: Optional[List[str]] = None
    if args.labels:
        cli_labels = [s.strip() for s in args.labels.split(",") if s.strip()]

    with contextlib.ExitStack() as stack:
        for ldr in loaders:
            stack.callback(ldr.close)

        warnings = _validate(loaders, allow_window_mismatch=args.allow_window_mismatch)
        labels = _derive_labels(loaders, cli_labels)

        delta = build_trend(
            loaders,
            labels=labels,
            warnings=warnings,
            allow_window_mismatch=args.allow_window_mismatch,
        )

    written: List[str] = []
    if args.format in ("json", "both"):
        json_path = os.path.join(args.output, "delta.json")
        _write_json(delta, json_path)
        written.append(json_path)
    if args.format in ("html", "both"):
        html_path = os.path.join(args.output, "dashboard_delta.html")
        _render_html(delta, html_path)
        written.append(html_path)

    chain = " → ".join(labels)
    print(f"[OK] Delta trend report generated across {len(loaders)} snapshots ({chain}):")
    for p in written:
        print(f"     {p}")
    if warnings:
        print(f"[INFO] {len(warnings)} warning(s) recorded in the report:")
        for w in warnings:
            print(f"     - {w.get('code')}: {w.get('message')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

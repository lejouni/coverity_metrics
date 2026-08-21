"""``coverity-delta`` — quarter-over-quarter comparison report.

Consumes two ZIPs produced by :mod:`coverity_metrics.cli.export` and emits an
adoption-focused delta report as JSON (``delta.json``) and an HTML dashboard
(``dashboard_delta.html``). Runs entirely offline — no database access.

See ``coverity_metrics/delta_metrics.py`` for the compute engine and
``coverity_metrics/templates/dashboard_delta.html`` for the rendered layout.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime
from typing import List, Optional

from jinja2 import Environment, FileSystemLoader

from coverity_metrics.delta_metrics import (
    SnapshotLoader,
    build_delta,
)


def _load_inline_css() -> str:
    """Return the dashboard CSS so the delta HTML is self-contained.

    Follows the same "read once, inline into ``<style>``" pattern used by
    :mod:`coverity_metrics.cli.dashboard`. Falls back to an empty string
    when the CSS is missing (unusual — bundled with the package).
    """
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


def _validate(prev: SnapshotLoader, curr: SnapshotLoader,
              allow_window_mismatch: bool) -> List[dict]:
    """Enforce cross-snapshot compatibility rules.

    Hard-fails on incompatible snapshots (differing instance sets,
    conflicting anonymization mappings, mismatched windows without opt-in).
    Returns a warnings list for conditions we choose to surface but not
    block on (missing mapping on one side, opt-in window mismatch).
    """
    warnings: List[dict] = []

    prev_instances = set(prev.instance_names)
    curr_instances = set(curr.instance_names)
    if prev_instances != curr_instances:
        only_prev = sorted(prev_instances - curr_instances)
        only_curr = sorted(curr_instances - prev_instances)
        raise SystemExit(
            "[ERROR] Snapshot instance lists differ — cannot compare.\n"
            f"        Only in --previous: {only_prev or '<none>'}\n"
            f"        Only in --current:  {only_curr or '<none>'}\n"
            "        Re-run both exports against the same config.json."
        )

    if prev.days != curr.days:
        if not allow_window_mismatch:
            raise SystemExit(
                f"[ERROR] Snapshot windows differ — previous used --days {prev.days}, "
                f"current used --days {curr.days}.\n"
                "        Windowed metrics (scan activity, snapshot cadence) are not "
                "directly comparable.\n"
                "        Recommended: re-export one snapshot with matching --days.\n"
                "        Testing / advanced: re-run with --allow-window-mismatch to "
                "produce a report anyway; affected metrics will be tagged."
            )
        warnings.append({
            "code": "window_mismatch",
            "message": (
                f"Snapshot windows differ (previous --days {prev.days}, current --days {curr.days}). "
                "Windowed metric deltas are not directly comparable; a normalized per-day view "
                "is included alongside the raw totals."
            ),
            "previous_days": prev.days,
            "current_days": curr.days,
        })

    prev_fp = prev.mapping_fingerprint()
    curr_fp = curr.mapping_fingerprint()
    if prev_fp is not None and curr_fp is not None:
        if prev_fp != curr_fp:
            raise SystemExit(
                "[ERROR] Anonymization mappings differ between snapshots — "
                "anonymized ids in the two ZIPs point at different real names, "
                "so a delta report would be meaningless.\n"
                "        Fix: re-run both exports with the same --mapping-file "
                "so the id assignments stay stable across quarters."
            )
    elif (prev_fp is None) != (curr_fp is None):
        side = "current" if prev_fp is not None else "previous"
        warnings.append({
            "code": "mapping_missing_one_side",
            "message": (
                f"Anonymization mapping present on one side only ({side} snapshot lacks a sibling "
                "<zip>.mapping.json). Identifier stability across the two snapshots cannot be "
                "verified; treat added/dropped project lists with caution."
            ),
        })

    return warnings


# ---------------------------------------------------------------------------
# Label derivation
# ---------------------------------------------------------------------------


def _derive_label(export_date: str, fallback: str) -> str:
    """Turn an ISO ``export_date`` into a ``YYYY-QN`` label.

    ``2026-04-01T12:34:56`` → ``2026-Q2``. Falls back to the raw string or
    ``fallback`` when the date can't be parsed.
    """
    if not export_date:
        return fallback
    try:
        dt = datetime.fromisoformat(export_date)
    except ValueError:
        # Some ISO strings include timezone info; try trimming to seconds.
        try:
            dt = datetime.fromisoformat(export_date[:19])
        except ValueError:
            return export_date or fallback
    quarter = (dt.month - 1) // 3 + 1
    return f"{dt.year}-Q{quarter}"


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
            "Compare two coverity-export snapshot ZIPs and emit a quarter-over-quarter "
            "delta report (JSON + HTML). Runs offline; no database access."
        ),
    )
    parser.add_argument("--previous", "-p", required=False,
                        help="Path to the earlier snapshot ZIP (e.g. archive/2026-Q1/...)")
    parser.add_argument("--current", "-c", required=False,
                        help="Path to the later snapshot ZIP (e.g. archive/2026-Q2/...)")
    parser.add_argument("--output", "-o", default="delta",
                        help="Output directory (default: delta/)")
    parser.add_argument("--format", "-f", choices=("json", "html", "both"), default="both",
                        help="Which artifact(s) to produce (default: both)")
    parser.add_argument("--label-previous", dest="label_previous", default=None,
                        help="Label for the previous snapshot (default: derived YYYY-QN from export_date)")
    parser.add_argument("--label-current", dest="label_current", default=None,
                        help="Label for the current snapshot (default: derived YYYY-QN from export_date)")
    parser.add_argument("--allow-window-mismatch", action="store_true",
                        help=("Allow comparing snapshots whose --days windows differ. "
                              "Windowed metrics are tagged with a warning in the output. "
                              "Intended for testing / advanced use, not production reports."))
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

    if not args.previous or not args.current:
        print("[ERROR] --previous and --current are required.", file=sys.stderr)
        return 2

    for label, path in (("--previous", args.previous), ("--current", args.current)):
        if not os.path.exists(path):
            print(f"[ERROR] {label} snapshot not found: {path}", file=sys.stderr)
            return 2

    os.makedirs(args.output, exist_ok=True)

    with SnapshotLoader(args.previous) as prev, SnapshotLoader(args.current) as curr:
        warnings = _validate(prev, curr, allow_window_mismatch=args.allow_window_mismatch)

        label_prev = args.label_previous or _derive_label(prev.export_date, "previous")
        label_curr = args.label_current or _derive_label(curr.export_date, "current")

        delta = build_delta(
            prev, curr,
            label_prev=label_prev,
            label_curr=label_curr,
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

    print(f"[OK] Delta report generated ({label_prev} → {label_curr}):")
    for p in written:
        print(f"     {p}")
    if warnings:
        print(f"[INFO] {len(warnings)} warning(s) recorded in the report:")
        for w in warnings:
            print(f"     - {w.get('code')}: {w.get('message')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

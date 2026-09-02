"""
Coverity Metrics HTML Dashboard Generator
Creates a beautiful HTML dashboard using Jinja2 templates
Supports single-instance and multi-instance deployments
Supports reading from database or exported ZIP files
"""
import os
import sys
import argparse
import glob
import logging
import json
import time
from datetime import date, datetime
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from coverity_metrics.metrics import CoverityMetrics
from coverity_metrics.zip_data_loader import ZipDataLoader
import webbrowser
from tqdm import tqdm
from coverity_metrics.metrics_cache import MetricsCache, ProgressTracker, collect_metrics_with_cache


def _format_duration(seconds):
    """Format a duration in seconds into a compact human-readable string.

    Examples: '8.7s', '1m 23.4s', '2h 5m 12s'.
    """
    if seconds < 60:
        return f"{seconds:.1f}s"
    if seconds < 3600:
        minutes, secs = divmod(seconds, 60)
        return f"{int(minutes)}m {secs:.1f}s"
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{int(hours)}h {int(minutes)}m {int(secs)}s"


def _backfill_owasp_scores(owasp_metrics):
    """Fill missing exploit/impact/priority fields on cached (pre-1.0.19) rows."""
    if not owasp_metrics:
        return owasp_metrics
    from coverity_metrics.owasp_mapping import OWASP_TOP_10_2025
    for item in owasp_metrics:
        if 'exploit_score' in item and 'impact_score' in item and 'priority_score' in item:
            continue
        sd = OWASP_TOP_10_2025.get(item.get('category'), {}).get('score_data', {})
        e = sd.get('exploit_score', 0.0)
        i = sd.get('impact_score', 0.0)
        item.setdefault('exploit_score', e)
        item.setdefault('impact_score', i)
        item.setdefault(
            'priority_score',
            round(item.get('total_defects', 0) * e * i / 100.0, 1),
        )
    return owasp_metrics

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Color palette for automatic instance color assignment
INSTANCE_COLOR_PALETTE = [
    "#e74c3c",  # Red
    "#3498db",  # Blue
    "#2ecc71",  # Green
    "#f39c12",  # Orange
    "#9b59b6",  # Purple
    "#1abc9c",  # Turquoise
    "#e67e22",  # Carrot
    "#34495e",  # Dark gray
    "#16a085",  # Green Sea
    "#c0392b",  # Dark red
    "#2980b9",  # Belize blue
    "#8e44ad",  # Wisteria
    "#27ae60",  # Nephritis
    "#d35400",  # Pumpkin
    "#7f8c8d",  # Asbestos
]

def assign_instance_colors(instance_names):
    """Automatically assign distinct colors to instances
    
    Args:
        instance_names: List of instance names
        
    Returns:
        dict: Mapping of instance name to color hex code
    """
    color_map = {}
    for i, name in enumerate(instance_names):
        # Cycle through colors if we have more instances than colors
        color_map[name] = INSTANCE_COLOR_PALETTE[i % len(INSTANCE_COLOR_PALETTE)]
    return color_map


def _expand_zip_globs(zip_files, logger=None):
    """Expand shell-style glob patterns in ``--zip-file`` arguments.

    Windows shells (`cmd`, PowerShell) do not expand `*` / `?` / `[...]`
    before invoking the tool, so patterns arrive verbatim in ``argv``.
    Entries without glob metacharacters pass through unchanged. Each glob
    is sorted for deterministic ordering; the overall list preserves the
    argv order of the surrounding literal / glob entries. A pattern that
    matches nothing is left in-place — the existing "ZIP file not found"
    check reports it with the offending pattern.
    """
    if logger is None:
        logger = tqdm.write

    expanded = []
    for entry in zip_files:
        if any(ch in entry for ch in '*?['):
            matches = sorted(glob.glob(entry))
            if matches:
                logger(f"  [OK] Glob '{entry}' matched {len(matches)} ZIP(s)")
                expanded.extend(matches)
            else:
                # Preserve the pattern so the caller's existence check reports it clearly.
                expanded.append(entry)
        else:
            expanded.append(entry)
    return expanded


def _build_zip_loader_map(zip_files, loader_cls=ZipDataLoader, logger=None):
    """Load each ZIP, take its first instance name, and disambiguate collisions.

    Multiple ZIPs can carry the same internal instance name (for example, all
    labelled ``Production`` even when they come from different Coverity
    servers). The previous implementation used the raw name as a dict key,
    which silently overwrote earlier entries. Here we resolve collisions by
    appending the ZIP filename's stem in parentheses — e.g.
    ``Production (prod_us)`` — and, in the pathological case where two ZIPs
    also share a stem, by appending an ordinal.

    Each loader keeps ``instance_name`` at its raw (ZIP-metadata) value — that
    attribute doubles as the folder prefix inside the ZIP, so overwriting it
    with the display name would break every downstream metric read. The
    disambiguated label is exposed as ``loader.display_name`` and also flows
    through the returned dict key / list.

    Args:
        zip_files: List of ZIP file paths (argv order preserved).
        loader_cls: Loader class to instantiate. Defaults to ``ZipDataLoader``;
            tests override this with a stub.
        logger: Callable used for progress / warning lines. Defaults to
            ``tqdm.write`` so the caller sees the same output as before.

    Returns:
        tuple: ``(zip_loaders, all_instances, days)`` — a dict of
        ``display_name -> loader`` (insertion-ordered), the display-name list
        in argv order, and the last ``days`` value read from any ZIP's
        metadata (or ``None`` when no ZIP contributed one).
    """
    if logger is None:
        logger = tqdm.write

    raw_entries = []
    days = None
    for zip_file in zip_files:
        loader = loader_cls(zip_file)
        metadata = loader.get_metadata()
        available_instances = loader.list_available_instances()
        if not available_instances:
            logger(f"[WARNING] No instances found in {zip_file}, skipping")
            continue
        raw_entries.append({
            'zip_file': zip_file,
            'raw_name': available_instances[0],
            'loader': loader,
        })
        d = metadata.get('days')
        if d is not None:
            days = d

    name_counts = {}
    for entry in raw_entries:
        name_counts[entry['raw_name']] = name_counts.get(entry['raw_name'], 0) + 1

    zip_loaders = {}
    all_instances = []
    collision_reported = set()
    for entry in raw_entries:
        raw_name = entry['raw_name']
        zip_file = entry['zip_file']
        loader = entry['loader']

        if name_counts[raw_name] == 1:
            display_name = raw_name
        else:
            stem = Path(zip_file).stem or 'zip'
            candidate = f"{raw_name} ({stem})"
            # Residual collision fallback: two ZIPs share both the raw name and
            # the filename stem (someone passed the same ZIP twice or copies of
            # it under different folders). Add an ordinal so display names are
            # still unique.
            if candidate in zip_loaders:
                ordinal = 2
                while f"{candidate} ({ordinal})" in zip_loaders:
                    ordinal += 1
                candidate = f"{candidate} ({ordinal})"
            display_name = candidate
            if raw_name not in collision_reported:
                collision_reported.add(raw_name)
                dupes = [os.path.basename(e['zip_file']) for e in raw_entries if e['raw_name'] == raw_name]
                logger(
                    f"  [INFO] Duplicate instance name '{raw_name}' across {len(dupes)} ZIP(s) "
                    f"({', '.join(dupes)}); disambiguating by ZIP filename stem."
                )

        loader.display_name = display_name
        # NOTE: do NOT overwrite loader.instance_name — ZipDataLoader uses it as
        # the folder prefix inside the ZIP (see zip_data_loader.py::_get_filename).
        # It must stay at the raw name from the ZIP metadata or every metric read
        # returns empty.
        zip_loaders[display_name] = loader
        all_instances.append(display_name)
        logger(f"  [OK] Loaded instance '{display_name}' from {os.path.basename(zip_file)}")

    return zip_loaders, all_instances, days


def _compute_avg_scans_per_week(scan_activity_trend, days):
    """Average snapshots (scans) per week over the observed activity span.

    Computed over the span from the first to the last dated bucket in the
    data (floored at one week), not the full requested ``days`` window.
    Otherwise projects with sparse but real activity — e.g. 9 scans across
    a 10-year window — would round to 0.0. Falls back to ``days`` when no
    parseable periods are available. Returns 0.0 when there is no activity.
    """
    if not scan_activity_trend:
        return 0.0

    def _to_date(v):
        if isinstance(v, datetime):
            return v.date()
        if isinstance(v, date):
            return v
        try:
            return datetime.fromisoformat(str(v)[:10]).date()
        except (TypeError, ValueError):
            return None

    total = 0
    dates = []
    for row in scan_activity_trend:
        try:
            total += int(row.get('scan_count', 0) or 0)
        except (TypeError, ValueError):
            pass
        d = _to_date(row.get('period'))
        if d:
            dates.append(d)

    if total <= 0:
        return 0.0

    if dates:
        span_days = (max(dates) - min(dates)).days + 1
        weeks = max(1.0, span_days / 7.0)
    elif days:
        weeks = max(1.0, days / 7.0)
    else:
        return 0.0

    return round(total / weeks, 1)

def load_inline_css():
    """
    Load CSS content from static directory to embed inline in HTML

    Cached at module level after first call — the CSS is static across the
    whole run, so we don't want to re-read + re-parse it for every project
    dashboard (there can be hundreds).

    Returns:
        str: CSS content to embed in HTML style tags
    """
    global _CACHED_INLINE_CSS
    if _CACHED_INLINE_CSS is not None:
        return _CACHED_INLINE_CSS

    # Get the package directory (where this file is located)
    package_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    css_path = os.path.join(package_dir, 'static', 'css', 'dashboard.css')

    # Load CSS file content
    if os.path.exists(css_path):
        with open(css_path, 'r', encoding='utf-8') as f:
            _CACHED_INLINE_CSS = f.read()
    else:
        tqdm.write(f"  [WARNING] CSS file not found at {css_path}")
        _CACHED_INLINE_CSS = "/* CSS file not found */"
    return _CACHED_INLINE_CSS


# Module-level caches populated on first use so we don't re-read the CSS
# file or re-parse the Jinja templates for every per-project dashboard.
_CACHED_INLINE_CSS = None
_CACHED_JINJA_ENV = None
_CACHED_TEMPLATES = {}


def _get_template(template_name):
    """Return a compiled Jinja2 template, initialising the shared Environment
    on first use. Both the environment and each template are cached at module
    scope; Jinja2 templates are thread-safe for ``render()`` after loading."""
    global _CACHED_JINJA_ENV
    if _CACHED_JINJA_ENV is None:
        template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates')
        _CACHED_JINJA_ENV = Environment(loader=FileSystemLoader(template_dir))
    if template_name not in _CACHED_TEMPLATES:
        _CACHED_TEMPLATES[template_name] = _CACHED_JINJA_ENV.get_template(template_name)
    return _CACHED_TEMPLATES[template_name]


def _sanitize_for_template(value):
    """Recursively replace float NaN with None inside dicts / lists / tuples.

    Jinja interpolates ``float('nan')`` as the bare token ``nan``, which is
    an undefined reference in JavaScript. When such a value lands inside a
    Plotly chart's ``y: [...]`` literal at the top of the ``<script>`` block,
    parsing raises ``ReferenceError: nan is not defined`` and aborts the
    entire script — killing every listener registered lower down (tab
    switching, sortable headers, filters). Sanitizing NaN → None at render
    time means ``{{ row.foo or 0 }}`` collapses to ``0`` as originally
    intended (``nan or 0`` returns ``nan`` because NaN is truthy).
    """
    if isinstance(value, dict):
        return {k: _sanitize_for_template(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_for_template(v) for v in value]
    if isinstance(value, tuple):
        return tuple(_sanitize_for_template(v) for v in value)
    if isinstance(value, float) and value != value:
        return None
    return value


def _render_template(template, **kwargs):
    """Render ``template`` with NaN values scrubbed from every kwarg."""
    return template.render(**{k: _sanitize_for_template(v) for k, v in kwargs.items()})


def detect_multi_instance_config(config_file='config.json'):
    """
    Detect if multi-instance configuration exists and has multiple instances
    
    Returns:
        tuple: (is_multi_instance, instance_count, config_data)
    """
    if not config_file or not os.path.exists(config_file):
        return False, 0, None

    try:
        with open(config_file, 'r') as f:
            config_data = json.load(f)
        
        instances = config_data.get('instances', [])
        enabled_instances = [inst for inst in instances if inst.get('enabled', True)]
        instance_count = len(enabled_instances)
        
        return instance_count > 1, instance_count, config_data
    except Exception as e:
        tqdm.write(f"[WARNING] Failed to read config file {config_file}: {e}")
        return False, 0, None


def _resolve_dashboard_config(config_file):
    """Resolve the DB-mode configuration for coverity-dashboard.

    Precedence (mirrors coverity-export):
      1. Explicit ``config_file`` (from ``--config``) -> load JSON, fail if missing.
      2. All required env vars set -> single-instance env-var mode (with an [INFO] line).
      3. ``config.json`` in the current directory -> load JSON.
      4. Otherwise -> exit with guidance listing both options.

    Returns:
        tuple: ``(config_data, enabled_instances, effective_path)``. ``effective_path``
        is the JSON file that was actually loaded (needed for MultiInstanceMetrics),
        or ``None`` when env-var mode was used (which is single-instance only).
    """
    from coverity_metrics.cli.export import (
        load_config, load_config_from_env, _env_vars_present,
        ENV_HOST, ENV_PORT, ENV_INSTANCE_NAME, _ENV_REQUIRED,
    )

    if config_file:
        cfg, insts = load_config(config_file)
        return cfg, insts, config_file
    if _env_vars_present():
        tqdm.write(f"[INFO] Using {ENV_HOST}/... environment variables for single-instance configuration.")
        cfg, insts = load_config_from_env()
        return cfg, insts, None
    if os.path.exists('config.json'):
        cfg, insts = load_config('config.json')
        return cfg, insts, 'config.json'
    tqdm.write("[ERROR] No configuration provided.")
    tqdm.write("Pass --config <file> pointing at a config.json (see config.json.example),")
    tqdm.write("or set the following environment variables for single-instance mode:")
    tqdm.write(f"  Required: {', '.join(_ENV_REQUIRED)}")
    tqdm.write(f"  Optional: {ENV_PORT} (default 5432), {ENV_INSTANCE_NAME} (default 'Coverity')")
    sys.exit(1)

def generate_html_dashboard(output_file="output/dashboard.html", project_name=None, 
                           instance_name=None, metrics_instance=None, cache=None, use_cache=True, days=90,
                           has_aggregated_dashboard=True, has_instance_dashboard=True):
    """Generate HTML dashboard with all metrics
    
    Args:
        output_file: Path to output HTML file
        project_name: Optional project name to filter metrics
        instance_name: Optional instance name for multi-instance mode
        metrics_instance: Optional CoverityMetrics instance (for multi-instance)
        cache: Optional MetricsCache instance for caching support
        use_cache: Whether to use cached data if available
        days: Number of days for trend analysis (default: 90)
        has_aggregated_dashboard: Whether an aggregated dashboard was generated (controls Back button)
        has_instance_dashboard: Whether an instance-level dashboard.html exists (controls Show All button)
    """
    tqdm.write("\nGenerating Coverity Metrics HTML Dashboard...")
    if instance_name:
        tqdm.write(f"Instance: {instance_name}")
    if project_name:
        tqdm.write(f"Filtering by project: {project_name}")
    tqdm.write("=" * 80)
    
    # Initialize metrics with project filter
    if metrics_instance:
        metrics = metrics_instance
        if project_name:
            metrics.project_name = project_name
    else:
        # This shouldn't happen anymore, but handle gracefully
        raise ValueError("metrics_instance is required. Please pass CoverityMetrics instance to generate_html_dashboard()")
    
    # Try to use cached data if cache is provided
    if cache and use_cache:
        cache_key = f"{instance_name}_{project_name}_days{days}" if instance_name else f"default_{project_name if project_name else 'all'}_days{days}"
        cached_metrics = cache.get_cached_metrics(instance_name or 'default', project_name, days)
        
        if cached_metrics:
            tqdm.write("  [CACHE] Using cached metrics data")
            metrics_data = cached_metrics['data']
            
            # Extract from cache
            summary = metrics_data.get('summary', {})
            defects_by_severity = metrics_data.get('defects_by_severity', [])
            defects_by_project = metrics_data.get('defects_by_project', [])
            defects_by_category = metrics_data.get('defects_by_category', [])
            top_checkers = metrics_data.get('top_checkers', [])
            defect_density = metrics_data.get('defect_density', [])
            file_hotspots = metrics_data.get('file_hotspots', [])
            code_metrics = metrics_data.get('code_metrics', [])
            complexity_distribution = metrics_data.get('complexity_distribution', [])
            db_stats = metrics_data.get('db_stats', {})
            instance_info = metrics_data.get('instance_info', {})
            analysis_versions = metrics_data.get('analysis_versions', [])
            largest_tables = metrics_data.get('largest_tables', [])
            snapshot_performance = metrics_data.get('snapshot_performance', [])
            snapshot_commands = metrics_data.get('snapshot_commands', [])
            commit_stats = metrics_data.get('commit_stats', {})
            commit_activity = metrics_data.get('commit_activity', {})
            defect_discovery = metrics_data.get('defect_discovery', [])
            projects_list = metrics_data.get('all_projects', [])
            defect_trends = metrics_data.get('defect_trends', [])
            triage_trends = metrics_data.get('triage_trends', [])
            checker_classification = metrics_data.get('checker_classification', [])
            top_projects_classification = metrics_data.get('top_projects_classification', [])
            fix_rate_metrics = metrics_data.get('fix_rate_metrics', {})
            defect_aging = metrics_data.get('defect_aging', [])
            triage_summary = metrics_data.get('triage_summary', {})
            defect_velocity = metrics_data.get('defect_velocity', [])
            cumulative_trends = metrics_data.get('cumulative_trends', [])
            trend_summary = metrics_data.get('trend_summary', {})
            trend_period_text = metrics_data.get('trend_period_text', f'Last {days} Days')
            user_activity_stats = metrics_data.get('user_activity_stats', {})
            top_projects_by_fix_rate = metrics_data.get('top_projects_by_fix_rate', [])
            top_projects_by_triage = metrics_data.get('top_projects_by_triage', [])
            top_users_by_fixes = metrics_data.get('top_users_by_fixes', [])
            top_triagers = metrics_data.get('top_triagers', [])
            most_collaborative_users = metrics_data.get('most_collaborative_users', [])
            owasp_metrics = _backfill_owasp_scores(metrics_data.get('owasp_metrics', []))
            owasp_details = metrics_data.get('owasp_details', {})
            cwe_top25_metrics = metrics_data.get('cwe_top25_metrics', [])
            cwe_top25_details = metrics_data.get('cwe_top25_details', {})
            tech_debt_summary = metrics_data.get('tech_debt_summary', {})
            scan_activity_trend = metrics_data.get('scan_activity_trend', [])
        else:
            # Collect from database and cache
            metrics_data = _collect_and_cache_metrics(metrics, instance_name, project_name, cache, days)
            summary = metrics_data['summary']
            defects_by_severity = metrics_data['defects_by_severity']
            defects_by_project = metrics_data['defects_by_project']
            defects_by_category = metrics_data['defects_by_category']
            top_checkers = metrics_data['top_checkers']
            defect_density = metrics_data['defect_density']
            file_hotspots = metrics_data['file_hotspots']
            code_metrics = metrics_data['code_metrics']
            complexity_distribution = metrics_data['complexity_distribution']
            db_stats = metrics_data['db_stats']
            instance_info = metrics_data.get('instance_info', {})
            analysis_versions = metrics_data.get('analysis_versions', [])
            largest_tables = metrics_data['largest_tables']
            snapshot_performance = metrics_data['snapshot_performance']
            snapshot_commands = metrics_data.get('snapshot_commands', [])
            commit_stats = metrics_data['commit_stats']
            commit_activity = metrics_data.get('commit_activity', {})
            defect_discovery = metrics_data['defect_discovery']
            projects_list = metrics_data['all_projects']
            defect_trends = metrics_data.get('defect_trends', [])
            triage_trends = metrics_data.get('triage_trends', [])
            checker_classification = metrics_data.get('checker_classification', [])
            top_projects_classification = metrics_data.get('top_projects_classification', [])
            fix_rate_metrics = metrics_data.get('fix_rate_metrics', {})
            defect_aging = metrics_data.get('defect_aging', [])
            triage_summary = metrics_data.get('triage_summary', {})
            defect_velocity = metrics_data.get('defect_velocity', [])
            cumulative_trends = metrics_data.get('cumulative_trends', [])
            trend_summary = metrics_data.get('trend_summary', {})
            trend_period_text = metrics_data.get('trend_period_text', f'Last {days} Days')
            user_activity_stats = metrics_data.get('user_activity_stats', {})
            top_projects_by_fix_rate = metrics_data.get('top_projects_by_fix_rate', [])
            top_projects_by_triage = metrics_data.get('top_projects_by_triage', [])
            top_users_by_fixes = metrics_data.get('top_users_by_fixes', [])
            top_triagers = metrics_data.get('top_triagers', [])
            most_collaborative_users = metrics_data.get('most_collaborative_users', [])
            owasp_metrics = _backfill_owasp_scores(metrics_data.get('owasp_metrics', []))
            owasp_details = metrics_data.get('owasp_details', {})
            cwe_top25_metrics = metrics_data.get('cwe_top25_metrics', [])
            cwe_top25_details = metrics_data.get('cwe_top25_details', {})
            tech_debt_summary = metrics_data.get('tech_debt_summary', {})
            scan_activity_trend = metrics_data.get('scan_activity_trend', [])
    else:
        # Collect without caching
        all_projects = metrics.get_available_projects()
        projects_list = all_projects['project_name'].tolist() if not all_projects.empty else []
        
        # Collect all metrics data
        tqdm.write("Collecting metrics data...")
        
        summary = metrics.get_overall_summary(days=days)
        defects_by_severity = metrics.get_defects_by_severity().to_dict('records')
        defects_by_project = metrics.get_total_defects_by_project().to_dict('records')
        defects_by_category = metrics.get_defects_by_checker_category(limit=20).to_dict('records')
        top_checkers = metrics.get_defects_by_checker_name(limit=20).to_dict('records')
        defect_density = metrics.get_defect_density_by_project().to_dict('records')
        file_hotspots = metrics.get_file_hotspots(limit=20).to_dict('records')
        code_metrics = metrics.get_code_metrics_by_stream().to_dict('records')
        complexity_distribution = metrics.get_function_complexity_distribution().to_dict('records')
        
        # Collect performance metrics
        db_stats = metrics.get_database_statistics()
        instance_info = metrics.get_instance_info()
        analysis_versions = metrics.get_analysis_versions(limit=10, days=days)
        largest_tables = metrics.get_largest_tables(limit=10).to_dict('records')
        snapshot_performance = metrics.get_snapshot_performance(limit=15).to_dict('records')
        # Analysis command lines are only meaningful on project dashboards
        snapshot_commands = (
            metrics.get_snapshot_commands(limit=10).to_dict('records')
            if project_name else []
        )
        commit_stats = metrics.get_commit_time_statistics()
        commit_activity = metrics.get_commit_activity_patterns()
        defect_discovery = metrics.get_defect_discovery_rate(days=days).to_dict('records')
        
        # Collect user activity statistics
        user_activity_stats = metrics.get_user_license_statistics(days=days)
        
        # Collect trend analysis data
        # Use daily granularity for project-level reports, weekly for instance-level
        granularity = 'day' if project_name else 'week'
        defect_trends = metrics.get_defect_trends(days=days, granularity=granularity).to_dict('records')
        triage_trends = metrics.get_triage_trends(days=days, granularity=granularity).to_dict('records')
        checker_classification = metrics.get_checker_classification_breakdown(limit=15).to_dict('records')
        top_projects_classification = metrics.get_top_projects_by_classification(limit=10).to_dict('records')
        fix_rate_metrics = metrics.get_fix_rate_metrics(days=days)
        defect_aging = metrics.get_defect_aging_distribution().to_dict('records')
        triage_summary = metrics.get_triage_progress_summary()
        
        # Collect enhanced velocity and cumulative trends
        defect_velocity = metrics.get_defect_velocity_trend(days=days).to_dict('records')
        cumulative_trends = metrics.get_cumulative_defect_trend(days=days).to_dict('records')
        trend_summary = metrics.get_defect_trend_summary(days=days)

        # Collect scan/commit activity trend (snapshots over time)
        scan_activity_trend = metrics.get_scan_activity_trend(days=days, granularity=granularity).to_dict('records')

        # Collect technical debt summary
        tech_debt_summary = metrics.get_technical_debt_summary()
        
        # Collect leaderboard data (now using triage_state table for user metrics)
        top_projects_by_fix_rate = metrics.get_top_projects_by_fix_rate(days=days, limit=10).to_dict('records')
        top_projects_by_triage = metrics.get_top_projects_by_triage_activity(days=days, limit=10).to_dict('records')
        top_users_by_fixes = metrics.get_top_users_by_fixes(days=days, limit=10).to_dict('records')
        top_triagers = metrics.get_top_triagers(days=days, limit=10).to_dict('records')
        most_collaborative_users = metrics.get_most_collaborative_users(days=days, limit=10).to_dict('records')
        
        # Collect OWASP Top 10 2025 metrics (project-level only)
        owasp_metrics = metrics.get_owasp_top10_metrics().to_dict('records') if project_name else []
        
        # Collect detailed breakdown for FAILED OWASP categories
        owasp_details = {}
        if project_name and owasp_metrics:
            for item in owasp_metrics:
                if item.get('status') == 'FAILED':
                    category_id = item['category']
                    owasp_details[category_id] = metrics.get_owasp_category_details(category_id)
        
        # Collect CWE Top 25 2024 metrics (project-level only)
        cwe_top25_metrics = metrics.get_cwe_top25_metrics().to_dict('records') if project_name else []
        
        # Collect detailed breakdown for FAILED CWE Top 25 entries only
        cwe_top25_details = {}
        if project_name and cwe_top25_metrics:
            for item in cwe_top25_metrics:
                if item.get('status') == 'FAILED':
                    cwe_id = item['cwe_id']
                    cwe_top25_details[cwe_id] = metrics.get_cwe_top25_details(cwe_id)
        
        # Calculate actual date range from trend data
        trend_period_text = f"Last {days} Days"
        
        tqdm.write(f"  [OK] Summary statistics")
        tqdm.write(f"  [OK] Defects by severity: {len(defects_by_severity)} records")
        tqdm.write(f"  [OK] Defects by project: {len(defects_by_project)} records")
        tqdm.write(f"  [OK] Defects by category: {len(defects_by_category)} records")
        tqdm.write(f"  [OK] File hotspots: {len(file_hotspots)} records")
        tqdm.write(f"  [OK] Code quality metrics: {len(code_metrics)} records")
        tqdm.write(f"  [OK] Performance metrics: {len(snapshot_performance)} snapshots")
        tqdm.write(f"  [OK] Trend analysis: {len(defect_trends)} periods")
        active_users = user_activity_stats.get('active_users', 0) if user_activity_stats else 0
        tqdm.write(f"  [OK] User activity: {active_users} active users")
    
    # Check for high severity alert
    high_severity_alert = summary.get('high_severity_defects', 0) > 0
    
    # Load CSS content for inline embedding (module-cached)
    inline_css = load_inline_css()

    # Load Jinja template (module-cached — Environment created once)
    template = _get_template('dashboard.html')

    has_leaderboards = bool(
        top_projects_by_fix_rate or top_projects_by_triage
        or top_users_by_fixes or top_triagers or most_collaborative_users
    )

    # Render template with data (NaN scrubbed to None — see _sanitize_for_template)
    html_content = _render_template(
        template,
        inline_css=inline_css,
        timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        summary=summary,
        defects_by_severity=defects_by_severity,
        defects_by_project=defects_by_project,
        defects_by_category=defects_by_category,
        top_checkers=top_checkers,
        defect_density=defect_density,
        file_hotspots=file_hotspots,
        code_metrics=code_metrics,
        complexity_distribution=complexity_distribution,
        high_severity_alert=high_severity_alert,
        current_project=project_name,
        current_instance=instance_name,
        all_projects=projects_list,
        # Performance metrics
        db_stats=db_stats,
        instance_info=instance_info,
        analysis_versions=analysis_versions,
        largest_tables=largest_tables,
        snapshot_performance=snapshot_performance,
        snapshot_commands=snapshot_commands,
        commit_stats=commit_stats,
        commit_activity=commit_activity,
        defect_discovery=defect_discovery,
        # Trend analysis
        defect_trends=defect_trends,
        triage_trends=triage_trends,
        checker_classification=checker_classification,
        top_projects_classification=top_projects_classification,
        fix_rate_metrics=fix_rate_metrics,
        defect_aging=defect_aging,
        triage_summary=triage_summary,
        defect_velocity=defect_velocity,
        cumulative_trends=cumulative_trends,
        trend_summary=trend_summary,
        tech_debt_summary=tech_debt_summary,
        trend_period_text=trend_period_text,
        user_activity_stats=user_activity_stats,
        # Leaderboards
        top_projects_by_fix_rate=top_projects_by_fix_rate,
        top_projects_by_triage=top_projects_by_triage,
        top_users_by_fixes=top_users_by_fixes,
        top_triagers=top_triagers,
        most_collaborative_users=most_collaborative_users,
        has_leaderboards=has_leaderboards,
        # OWASP Top 10 2025 (project-level only)
        owasp_metrics=owasp_metrics,
        owasp_details=owasp_details,
        # CWE Top 25 2024 (project-level only)
        cwe_top25_metrics=cwe_top25_metrics,
        cwe_top25_details=cwe_top25_details,
        # Scan / commit activity over time
        scan_activity_trend=scan_activity_trend,
        avg_scans_per_week=_compute_avg_scans_per_week(scan_activity_trend, days),
        has_aggregated_dashboard=has_aggregated_dashboard,
        has_instance_dashboard=has_instance_dashboard
    )
    
    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    # Write HTML file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    # Get absolute path for display
    abs_path = os.path.abspath(output_file)
    
    tqdm.write("\n" + "=" * 80)
    tqdm.write(f"[SUCCESS] Dashboard generated successfully!")
    tqdm.write(f"Location: {abs_path}")
    tqdm.write(f"File size: {os.path.getsize(output_file):,} bytes")
    tqdm.write("=" * 80)
    
    return abs_path


def _collect_and_cache_metrics(metrics, instance_name, project_name, cache, days=90):
    """Helper function to collect metrics and cache them"""
    tqdm.write(f"Collecting metrics data from database (trend period: {days} days)...")
    
    all_projects = metrics.get_available_projects()
    projects_list = all_projects['project_name'].tolist() if not all_projects.empty else []
    
    summary = metrics.get_overall_summary(days=days)
    defects_by_severity = metrics.get_defects_by_severity().to_dict('records')
    defects_by_project = metrics.get_total_defects_by_project().to_dict('records')
    defects_by_category = metrics.get_defects_by_checker_category(limit=20).to_dict('records')
    top_checkers = metrics.get_defects_by_checker_name(limit=20).to_dict('records')
    defect_density = metrics.get_defect_density_by_project().to_dict('records')
    file_hotspots = metrics.get_file_hotspots(limit=20).to_dict('records')
    code_metrics = metrics.get_code_metrics_by_stream().to_dict('records')
    complexity_distribution = metrics.get_function_complexity_distribution().to_dict('records')
    db_stats = metrics.get_database_statistics()
    instance_info = metrics.get_instance_info()
    analysis_versions = metrics.get_analysis_versions(limit=10, days=days)
    largest_tables = metrics.get_largest_tables(limit=10).to_dict('records')
    snapshot_performance = metrics.get_snapshot_performance(limit=15).to_dict('records')
    # Analysis command lines are only meaningful on project dashboards
    snapshot_commands = (
        metrics.get_snapshot_commands(limit=10).to_dict('records')
        if project_name else []
    )
    commit_stats = metrics.get_commit_time_statistics()
    commit_activity = metrics.get_commit_activity_patterns()
    defect_discovery = metrics.get_defect_discovery_rate(days=days).to_dict('records')
    
    # Collect user activity statistics
    user_activity_stats = metrics.get_user_license_statistics(days=days)
    
    # Collect trend analysis data
    # Use daily granularity for project-level reports, weekly for instance-level
    granularity = 'day' if project_name else 'week'
    defect_trends = metrics.get_defect_trends(days=days, granularity=granularity).to_dict('records')
    triage_trends = metrics.get_triage_trends(days=days, granularity=granularity).to_dict('records')
    checker_classification = metrics.get_checker_classification_breakdown(limit=15).to_dict('records')
    top_projects_classification = metrics.get_top_projects_by_classification(limit=10).to_dict('records')
    fix_rate_metrics = metrics.get_fix_rate_metrics(days=days)
    defect_aging = metrics.get_defect_aging_distribution().to_dict('records')
    triage_summary = metrics.get_triage_progress_summary()
    
    # Collect enhanced velocity and cumulative trends
    defect_velocity = metrics.get_defect_velocity_trend(days=days).to_dict('records')
    cumulative_trends = metrics.get_cumulative_defect_trend(days=days).to_dict('records')
    trend_summary = metrics.get_defect_trend_summary(days=days)

    # Collect scan/commit activity trend (snapshots over time)
    scan_activity_trend = metrics.get_scan_activity_trend(days=days, granularity=granularity).to_dict('records')

    # Collect leaderboard data (project-scoped when metrics.project_name is set)
    top_projects_by_fix_rate = metrics.get_top_projects_by_fix_rate(days=days, limit=10).to_dict('records')
    top_projects_by_triage = metrics.get_top_projects_by_triage_activity(days=days, limit=10).to_dict('records')
    top_users_by_fixes = metrics.get_top_users_by_fixes(days=days, limit=10).to_dict('records')
    top_triagers = metrics.get_top_triagers(days=days, limit=10).to_dict('records')
    most_collaborative_users = metrics.get_most_collaborative_users(days=days, limit=10).to_dict('records')
    
    # Collect OWASP Top 10 2025 metrics (project-level only)
    owasp_metrics = metrics.get_owasp_top10_metrics().to_dict('records') if project_name else []
    
    # Collect detailed breakdown for FAILED OWASP categories
    owasp_details = {}
    if project_name and owasp_metrics:
        for item in owasp_metrics:
            if item.get('status') == 'FAILED':
                category_id = item['category']
                owasp_details[category_id] = metrics.get_owasp_category_details(category_id)
    
    # Collect CWE Top 25 2024 metrics (project-level only)
    cwe_top25_metrics = metrics.get_cwe_top25_metrics().to_dict('records') if project_name else []
    
    # Collect detailed breakdown for FAILED CWE Top 25 entries only
    cwe_top25_details = {}
    if project_name and cwe_top25_metrics:
        for item in cwe_top25_metrics:
            if item.get('status') == 'FAILED':
                cwe_id = item['cwe_id']
                cwe_top25_details[cwe_id] = metrics.get_cwe_top25_details(cwe_id)
    
    # Collect technical debt summary
    tech_debt_summary = metrics.get_technical_debt_summary()
    
    # Calculate actual date range from trend data
    trend_period_text = f"Last {days} Days"
    
    tqdm.write(f"  [OK] Summary statistics")
    tqdm.write(f"  [OK] Defects by severity: {len(defects_by_severity)} records")
    tqdm.write(f"  [OK] Defects by project: {len(defects_by_project)} records")
    tqdm.write(f"  [OK] Defects by category: {len(defects_by_category)} records")
    tqdm.write(f"  [OK] File hotspots: {len(file_hotspots)} records")
    tqdm.write(f"  [OK] Code quality metrics: {len(code_metrics)} records")
    tqdm.write(f"  [OK] Performance metrics: {len(snapshot_performance)} snapshots")
    tqdm.write(f"  [OK] Trend analysis: {len(defect_trends)} periods")
    active_users = user_activity_stats.get('active_users', 0) if user_activity_stats else 0
    tqdm.write(f"  [OK] User activity: {active_users} active users")
    
    metrics_data = {
        'summary': summary,
        'defects_by_severity': defects_by_severity,
        'defects_by_project': defects_by_project,
        'defects_by_category': defects_by_category,
        'top_checkers': top_checkers,
        'defect_density': defect_density,
        'file_hotspots': file_hotspots,
        'code_metrics': code_metrics,
        'complexity_distribution': complexity_distribution,
        'db_stats': db_stats,
        'instance_info': instance_info,
        'analysis_versions': analysis_versions,
        'largest_tables': largest_tables,
        'snapshot_performance': snapshot_performance,
        'snapshot_commands': snapshot_commands,
        'commit_stats': commit_stats,
        'commit_activity': commit_activity,
        'defect_discovery': defect_discovery,
        'all_projects': projects_list,
        'defect_trends': defect_trends,
        'triage_trends': triage_trends,
        'checker_classification': checker_classification,
        'top_projects_classification': top_projects_classification,
        'fix_rate_metrics': fix_rate_metrics,
        'defect_aging': defect_aging,
        'triage_summary': triage_summary,
        'defect_velocity': defect_velocity,
        'cumulative_trends': cumulative_trends,
        'trend_summary': trend_summary,
        'trend_period_text': trend_period_text,
        'user_activity_stats': user_activity_stats,
        'top_projects_by_fix_rate': top_projects_by_fix_rate,
        'top_projects_by_triage': top_projects_by_triage,
        'top_users_by_fixes': top_users_by_fixes,
        'top_triagers': top_triagers,
        'most_collaborative_users': most_collaborative_users,
        'owasp_metrics': owasp_metrics,
        'owasp_details': owasp_details,
        'cwe_top25_metrics': cwe_top25_metrics,
        'cwe_top25_details': cwe_top25_details,
        'tech_debt_summary': tech_debt_summary,
        'scan_activity_trend': scan_activity_trend
    }
    
    # Cache the data
    if cache:
        cache.save_metrics_to_cache(instance_name or 'default', metrics_data, project_name)
    
    return metrics_data


def generate_aggregated_dashboard(multi_metrics, output_file="output/dashboard_aggregated.html", days=365):
    """Generate aggregated dashboard across all Coverity instances
    
    Args:
        multi_metrics: MultiInstanceMetrics instance
        output_file: Path to output HTML file
        days: Number of days for trend analysis (default: 365)
    """
    tqdm.write("\nGenerating Aggregated Multi-Instance Dashboard...")
    tqdm.write("=" * 80)
    
    # Get aggregated data
    tqdm.write("Collecting aggregated metrics data...")
    summary = multi_metrics.get_aggregated_summary()
    defects_by_instance = multi_metrics.get_defects_by_instance().to_dict('records')
    defects_by_severity = multi_metrics.get_aggregated_defects_by_severity().to_dict('records')
    analysis_versions = multi_metrics.get_aggregated_analysis_versions(limit=10)
    user_statistics = multi_metrics.get_aggregated_user_statistics(days=days)
    database_statistics = multi_metrics.get_aggregated_database_statistics()
    commit_activity = multi_metrics.get_aggregated_commit_activity()
    aggregated_trends = multi_metrics.get_aggregated_trends(days=days)
    scan_activity_series = multi_metrics.get_aggregated_scan_activity(days=days, granularity='week')

    # Enrich each per-instance series with total + average scans/week over the
    # observed activity span (mirrors the per-project logic in
    # _compute_avg_scans_per_week so sparse legacy data still surfaces a
    # non-zero rate).
    for series in scan_activity_series:
        periods = series.get('periods', [])
        scan_counts = series.get('scan_counts', [])
        series['total_scans'] = sum(int(v or 0) for v in scan_counts)
        trend_rows = [{'period': p, 'scan_count': c} for p, c in zip(periods, scan_counts)]
        series['avg_scans_per_week'] = _compute_avg_scans_per_week(trend_rows, days)
    
    # Get instance names with colors
    instance_configs = []
    for instance in multi_metrics.instances:
        instance_configs.append({
            'name': instance.name,
            'description': instance.description,
            'color': instance.color
        })
    
    tqdm.write(f"  [OK] Aggregated summary across {summary['total_instances']} instances")
    tqdm.write(f"  [OK] Defects by instance: {len(defects_by_instance)} instances")
    tqdm.write(f"  [OK] User activity: {user_statistics['active_users']} active users across all instances")
    tqdm.write(f"  [OK] Database statistics: {database_statistics['total_db_size']} total size, {database_statistics['total_snapshots']} snapshots")
    tqdm.write(f"  [OK] Trends & Progress: {aggregated_trends['trend_summary']['total_new']} new, {aggregated_trends['trend_summary']['total_fixed']} fixed")
    
    # Load CSS content for inline embedding
    inline_css = load_inline_css()

    # Load aggregated template (module-cached — Environment created once)
    template = _get_template('dashboard_aggregated.html')

    # Render template with data (NaN scrubbed to None — see _sanitize_for_template)
    html_content = _render_template(
        template,
        inline_css=inline_css,
        timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        summary=summary,
        defects_by_instance=defects_by_instance,
        defects_by_severity=defects_by_severity,
        analysis_versions=analysis_versions,
        instance_configs=instance_configs,
        user_statistics=user_statistics,
        database_statistics=database_statistics,
        commit_activity=commit_activity,
        triage_summary=aggregated_trends['triage_summary'],
        trend_summary=aggregated_trends['trend_summary'],
        fix_rate_metrics=aggregated_trends['fix_rate_metrics'],
        trends_by_instance=aggregated_trends['by_instance'],
        scan_activity_series=scan_activity_series,
        trend_period_text=f"Last {days} Days",
        multi_instance_mode=True
    )
    
    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    # Write HTML file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    # Get absolute path for display
    abs_path = os.path.abspath(output_file)
    
    tqdm.write("\n" + "=" * 80)
    tqdm.write(f"[SUCCESS] Aggregated dashboard generated successfully!")
    tqdm.write(f"Location: {abs_path}")
    tqdm.write(f"File size: {os.path.getsize(output_file):,} bytes")
    tqdm.write("=" * 80)
    
    return abs_path


def generate_aggregated_dashboard_from_zips(zip_loaders, instance_configs, output_file="output/dashboard_aggregated.html", days=365):
    """Generate aggregated dashboard from ZIP file data loaders
    
    Args:
        zip_loaders: Dict mapping instance names to ZipDataLoader objects
        instance_configs: List of dicts with instance config (name, description, color)
        output_file: Path to output HTML file
        days: Number of days for trend analysis
    """
    tqdm.write("\nGenerating Aggregated Dashboard from ZIP files...")
    tqdm.write("=" * 80)
    
    # Collect aggregated data from all ZIP loaders
    tqdm.write("Collecting aggregated metrics from ZIP files...")
    
    # Initialize aggregated statistics
    total_defects = 0
    total_outstanding = 0
    total_fixed = 0
    total_dismissed = 0
    total_triaged = 0
    total_new = 0
    total_projects = 0
    total_high_severity = 0
    total_licensed_users = 0
    total_users_with_login = 0
    total_active_users = 0
    total_snapshots = 0
    total_db_size_bytes = 0
    total_commits = 0
    min_duration_seconds = None
    max_duration_seconds = None
    weighted_duration_sum = 0  # For calculating weighted average
    
    defects_by_instance_list = []
    defects_by_severity_agg = {}
    analysis_versions_agg = {}
    user_statistics_by_instance = []
    database_statistics_by_instance = []
    trends_by_instance = []
    triage_by_state_agg = {}
    commit_activity_by_hour = {}
    commit_activity_by_day = {}
    
    # Aggregate data from each instance
    for instance_name, loader in zip_loaders.items():
        try:
            summary = loader.get_overall_summary()
            
            # Get trend summary for this instance
            trend_data = loader.get_defect_trend_summary(days=days)
            
            # Get triage summary for this instance
            triage_data = loader.get_triage_progress_summary()
            
            # Aggregate totals from summary
            total_defects += summary.get('total_defects', 0)
            total_projects += summary.get('total_projects', 0)
            
            # Aggregate totals from trend data
            if trend_data:
                total_new += trend_data.get('total_new', 0)
                total_fixed += trend_data.get('total_fixed', 0)
                total_outstanding += trend_data.get('current_outstanding', summary.get('total_defects', 0))
            else:
                total_outstanding += summary.get('total_defects', 0)
            
            # Aggregate triage data
            if triage_data:
                total_triaged += triage_data.get('classified_count', 0)
            
            # Note: dismissed_defects is typically tracked in trend data or separate metrics
            # For now, using total_dismissed from available data
            total_dismissed += 0  # Not typically in summary; would need separate metric
            
            # Get severity breakdown for this instance
            severity_df = loader.get_defects_by_severity()
            high_severity = 0
            medium_severity = 0
            low_severity = 0
            
            if not severity_df.empty:
                for _, row in severity_df.iterrows():
                    severity = row.get('impact', row.get('severity', 'Unknown'))
                    count = row.get('defect_count', row.get('count', 0))
                    
                    # Count for instance-level metrics
                    if severity == 'High':
                        high_severity += count
                        total_high_severity += count
                    elif severity == 'Medium':
                        medium_severity += count
                    elif severity == 'Low':
                        low_severity += count
                    
                    # Aggregate for overall severity
                    if severity in defects_by_severity_agg:
                        defects_by_severity_agg[severity] += count
                    else:
                        defects_by_severity_agg[severity] = count
            
            # Get instance description and color from config
            instance_config = next((cfg for cfg in instance_configs if cfg['name'] == instance_name), None)
            description = instance_config.get('description', '') if instance_config else ''
            color = instance_config.get('color', '#3498db') if instance_config else '#3498db'
            
            # Per-instance defect count with all fields needed by template
            defects_by_instance_list.append({
                'instance_name': instance_name,
                'description': description,
                'color': color,
                'total_defects': summary.get('total_defects', 0),
                'high_severity': high_severity,
                'medium_severity': medium_severity,
                'low_severity': low_severity,
                'total_projects': summary.get('total_projects', 0),
                'total_streams': summary.get('total_streams', 0)
            })
            
            # Collect user statistics from each instance
            try:
                user_stats = loader.get_user_license_statistics(days=90)
                if user_stats:
                    licensed_users = user_stats.get('total_licensed_users', 0)
                    users_with_login = user_stats.get('users_with_login', 0)
                    active_users = user_stats.get('active_users', 0)
                    
                    total_licensed_users += licensed_users
                    total_users_with_login += users_with_login
                    total_active_users += active_users
                    
                    active_percentage = round((active_users / licensed_users * 100) if licensed_users > 0 else 0, 1)
                    
                    user_statistics_by_instance.append({
                        'instance_name': instance_name,
                        'color': color,
                        'licensed_users': licensed_users,
                        'users_with_login': users_with_login,
                        'active_users': active_users,
                        'active_percentage': active_percentage
                    })
            except Exception as e:
                tqdm.write(f"  [WARNING] Failed to load user statistics from {instance_name}: {e}")
            
            # Collect database statistics from each instance
            try:
                db_stats = loader.get_database_statistics()
                if db_stats:
                    # Use db_size_bytes if available, otherwise try to parse db_size
                    db_size = db_stats.get('db_size_bytes', 0)
                    if db_size == 0:
                        db_size_str = db_stats.get('total_db_size', db_stats.get('db_size', '0'))
                        if isinstance(db_size_str, str):
                            # Try to extract bytes from formatted string (e.g., "123.45 MB")
                            import re
                            match = re.search(r'([\d.]+)\s*(GB|MB|KB|B)', db_size_str, re.IGNORECASE)
                            if match:
                                value = float(match.group(1))
                                unit = match.group(2).upper()
                                if unit == 'GB':
                                    db_size = int(value * 1024 * 1024 * 1024)
                                elif unit == 'MB':
                                    db_size = int(value * 1024 * 1024)
                                elif unit == 'KB':
                                    db_size = int(value * 1024)
                                else:
                                    db_size = int(value)
                    
                    snapshots = db_stats.get('total_snapshots', 0)
                    
                    total_db_size_bytes += db_size
                    total_snapshots += snapshots
                    
                    # Store for per-instance table (will add commit stats later)
                    db_instance_entry = {
                        'instance_name': instance_name,
                        'color': color,
                        'db_size': db_size,
                        'total_snapshots': snapshots
                    }
                    database_statistics_by_instance.append(db_instance_entry)
            except Exception as e:
                tqdm.write(f"  [WARNING] Failed to load database statistics from {instance_name}: {e}")
            
            # Collect commit time statistics from each instance
            try:
                commit_stats = loader.get_commit_time_statistics()
                if commit_stats:
                    commits = commit_stats.get('total_commits', 0)
                    avg_duration = commit_stats.get('avg_duration_seconds', 0)
                    min_duration = commit_stats.get('min_duration_seconds', 0)
                    max_duration = commit_stats.get('max_duration_seconds', 0)
                    
                    total_commits += commits
                    weighted_duration_sum += avg_duration * commits
                    
                    # Track global min/max
                    if min_duration_seconds is None or (min_duration > 0 and min_duration < min_duration_seconds):
                        min_duration_seconds = min_duration
                    if max_duration_seconds is None or max_duration > max_duration_seconds:
                        max_duration_seconds = max_duration
                    
                    # Update database_statistics_by_instance entry with commit stats
                    if database_statistics_by_instance:
                        database_statistics_by_instance[-1]['total_commits'] = commits
                        database_statistics_by_instance[-1]['avg_duration_seconds'] = round(avg_duration, 2)
            except Exception as e:
                tqdm.write(f"  [WARNING] Failed to load commit statistics from {instance_name}: {e}")
            
            # Collect commit activity patterns from each instance
            try:
                activity_patterns = loader.get_commit_activity_patterns()
                if activity_patterns:
                    # Aggregate by hour
                    by_hour = activity_patterns.get('by_hour', [])
                    for hour_data in by_hour:
                        hour = int(hour_data.get('hour', 0))
                        commit_count = hour_data.get('commit_count', 0)
                        avg_duration = hour_data.get('avg_duration_seconds', 0)
                        
                        if hour in commit_activity_by_hour:
                            commit_activity_by_hour[hour]['commit_count'] += commit_count
                            commit_activity_by_hour[hour]['total_duration'] += avg_duration * commit_count
                        else:
                            commit_activity_by_hour[hour] = {
                                'hour': hour,
                                'commit_count': commit_count,
                                'total_duration': avg_duration * commit_count
                            }
                    
                    # Aggregate by day
                    by_day = activity_patterns.get('by_day_of_week', [])
                    for day_data in by_day:
                        day_name = day_data.get('day_name', 'Unknown')
                        day_num = int(day_data.get('day_num', 0))
                        commit_count = day_data.get('commit_count', 0)
                        avg_duration = day_data.get('avg_duration_seconds', 0)
                        
                        if day_name in commit_activity_by_day:
                            commit_activity_by_day[day_name]['commit_count'] += commit_count
                            commit_activity_by_day[day_name]['total_duration'] += avg_duration * commit_count
                        else:
                            commit_activity_by_day[day_name] = {
                                'day_num': day_num,
                                'day_name': day_name,
                                'commit_count': commit_count,
                                'total_duration': avg_duration * commit_count
                            }
            except Exception as e:
                tqdm.write(f"  [WARNING] Failed to load commit activity patterns from {instance_name}: {e}")
            
            # Collect analysis versions from each instance
            try:
                versions = loader.get_analysis_versions(limit=10, days=days)
                if versions and len(versions) > 0:
                    for ver in versions:
                        version = ver.get('version', ver.get('analysis_version', 'Unknown'))
                        snapshot_count = ver.get('snapshot_count', 1)
                        first_used = ver.get('first_used')
                        last_used = ver.get('last_used')
                        
                        if version in analysis_versions_agg:
                            # Merge data
                            analysis_versions_agg[version]['snapshot_count'] += snapshot_count
                            analysis_versions_agg[version]['instances'].add(instance_name)
                            
                            # Update first/last used dates
                            if first_used:
                                if analysis_versions_agg[version]['first_used'] is None or first_used < analysis_versions_agg[version]['first_used']:
                                    analysis_versions_agg[version]['first_used'] = first_used
                            if last_used:
                                if analysis_versions_agg[version]['last_used'] is None or last_used > analysis_versions_agg[version]['last_used']:
                                    analysis_versions_agg[version]['last_used'] = last_used
                        else:
                            analysis_versions_agg[version] = {
                                'version': version,
                                'snapshot_count': snapshot_count,
                                'instances': {instance_name},
                                'first_used': first_used,
                                'last_used': last_used
                            }
            except Exception as e:
                tqdm.write(f"  [WARNING] Failed to load analysis versions from {instance_name}: {e}")
            
            # Collect triage trends from each instance
            if triage_data:
                # Use triage_progress_summary data
                for key in ['bug_count', 'false_positive_count', 'intentional_count', 'action_assigned_count']:
                    state_name = key.replace('_count', '').replace('_', ' ').title()
                    count = triage_data.get(key, 0)
                    if count > 0:
                        if state_name in triage_by_state_agg:
                            triage_by_state_agg[state_name] += count
                        else:
                            triage_by_state_agg[state_name] = count
            
            # Collect defect trends for per-instance breakdown
            if trend_data:
                trends_by_instance.append({
                    'instance_name': instance_name,
                    'color': color,
                    'triage_completion': round((triage_data.get('classified_count', 0) / summary.get('total_defects', 1) * 100) if summary.get('total_defects', 0) > 0 else 0, 1),
                    'classified': triage_data.get('classified_count', 0) if triage_data else 0,
                    'total_new': trend_data.get('total_new', 0),
                    'total_fixed': trend_data.get('total_fixed', 0),
                    'net_change': trend_data.get('net_change', 0),
                    'trend_direction': trend_data.get('trend_direction', 'unknown').lower()
                })
        
        except Exception as e:
            tqdm.write(f"  [WARNING] Failed to load metrics from {instance_name}: {e}")
    
    # Calculate aggregated triage summary
    # Use total_triaged which correctly sums classified_count from each instance
    # Don't use sum(triage_by_state_agg.values()) as it includes action_assigned_count which may include unclassified defects
    total_classified = total_triaged
    total_unclassified = total_defects - total_classified if total_defects > total_classified else 0
    triage_completion_pct = round((total_classified / total_defects * 100) if total_defects > 0 else 0, 1)
    
    # Count by specific triage states
    bug_count = triage_by_state_agg.get('Bug', 0) + triage_by_state_agg.get('Action Required', 0)
    false_positive_count = triage_by_state_agg.get('False Positive', 0)
    intentional_count = triage_by_state_agg.get('Intentional', 0)
    action_assigned_count = triage_by_state_agg.get('Action Assigned', 0)
    
    # Calculate trend metrics
    avg_new_per_day = round(total_new / days, 1) if days > 0 else 0
    avg_fixed_per_day = round(total_fixed / days, 1) if days > 0 else 0
    net_change = total_new - total_fixed
    fix_rate_pct = round((total_fixed / (total_fixed + total_new) * 100) if (total_fixed + total_new) > 0 else 0, 1)
    
    if total_fixed > total_new:
        trend_direction = 'improving'
    elif total_new > total_fixed:
        trend_direction = 'declining'
    else:
        trend_direction = 'stable'
    
    # Format aggregated summary
    summary = {
        'total_instances': len(zip_loaders),
        'total_defects': total_defects,
        'outstanding_defects': total_outstanding,
        'fixed_defects': total_fixed,
        'dismissed_defects': total_dismissed,
        'triaged_defects': total_triaged,
        'new_defects': total_new,
        'total_projects': total_projects,
        'high_severity_defects': total_high_severity,
        'fix_rate': round((total_fixed / total_defects * 100) if total_defects > 0 else 0, 1),
        'triage_rate': round((total_triaged / total_defects * 100) if total_defects > 0 else 0, 1)
    }
    
    # Format defects by severity for template
    defects_by_severity = [
        {'severity': severity, 'count': count}
        for severity, count in defects_by_severity_agg.items()
    ]
    
    # Format analysis versions for template (sorted by snapshot count)
    analysis_versions = sorted([
        {
            'version': data['version'],
            'snapshot_count': data['snapshot_count'],
            'instances': list(data['instances']),
            'first_used': data['first_used'],
            'last_used': data['last_used']
        }
        for data in analysis_versions_agg.values()
    ], key=lambda x: x['snapshot_count'], reverse=True)
    
    # Format user statistics
    user_statistics = {
        'total_licensed_users': total_licensed_users,
        'users_with_login': total_users_with_login,
        'login_user_percentage': round((total_users_with_login / total_licensed_users * 100) if total_licensed_users > 0 else 0, 1),
        'active_users': total_active_users,
        'active_user_percentage': round((total_active_users / total_licensed_users * 100) if total_licensed_users > 0 else 0, 1),
        'top_fixers': [],
        'top_triagers': [],
        'by_instance': user_statistics_by_instance
    }
    
    # Format database statistics
    def format_db_size(bytes_size):
        if bytes_size >= 1024 * 1024 * 1024:
            return f"{bytes_size / (1024 * 1024 * 1024):.2f} GB"
        elif bytes_size >= 1024 * 1024:
            return f"{bytes_size / (1024 * 1024):.2f} MB"
        elif bytes_size >= 1024:
            return f"{bytes_size / 1024:.2f} KB"
        else:
            return f"{bytes_size} B"
    
    # Calculate weighted average commit duration
    avg_duration_seconds = round(weighted_duration_sum / total_commits, 2) if total_commits > 0 else 0
    
    # Format per-instance database statistics (add formatted db_size)
    for inst in database_statistics_by_instance:
        inst['db_size'] = format_db_size(inst['db_size'])
    
    database_statistics = {
        'total_db_size': format_db_size(total_db_size_bytes),
        'total_snapshots': total_snapshots,
        'total_commits': total_commits,
        'avg_duration_seconds': avg_duration_seconds,
        'min_duration_seconds': round(min_duration_seconds, 2) if min_duration_seconds is not None else 0,
        'max_duration_seconds': round(max_duration_seconds, 2) if max_duration_seconds is not None else 0,
        'by_instance': database_statistics_by_instance
    }
    
    # Calculate commit activity patterns
    # Find busiest and quietest hours (3-hour blocks)
    busiest_hours = None
    quietest_hours = None
    if commit_activity_by_hour:
        # Calculate 3-hour rolling windows
        hours_sorted = sorted(commit_activity_by_hour.keys())
        best_window = {'commit_count': 0}
        worst_window = {'commit_count': float('inf')}
        
        for start_hour in hours_sorted:
            window_commits = 0
            window_duration = 0
            hours_in_window = []
            
            for h in range(start_hour, min(start_hour + 3, 24)):
                if h in commit_activity_by_hour:
                    window_commits += commit_activity_by_hour[h]['commit_count']
                    window_duration += commit_activity_by_hour[h]['total_duration']
                    hours_in_window.append(h)
            
            if len(hours_in_window) >= 2:  # At least 2 hours of data
                if window_commits > best_window['commit_count']:
                    best_window = {
                        'block_start': start_hour,
                        'block_end': min(start_hour + 2, 23),
                        'hours_display': f"{start_hour:02d}:00-{min(start_hour + 2, 23):02d}:00 ({start_hour % 12 or 12} {'AM' if start_hour < 12 else 'PM'} - {(min(start_hour + 2, 23)) % 12 or 12} {'AM' if min(start_hour + 2, 23) < 12 else 'PM'})",
                        'commit_count': window_commits,
                        'avg_duration_seconds': round(window_duration / window_commits, 2) if window_commits > 0 else 0
                    }
                
                if window_commits < worst_window['commit_count'] and window_commits > 0:
                    worst_window = {
                        'block_start': start_hour,
                        'block_end': min(start_hour + 2, 23),
                        'hours_display': f"{start_hour:02d}:00-{min(start_hour + 2, 23):02d}:00 ({start_hour % 12 or 12} {'AM' if start_hour < 12 else 'PM'} - {(min(start_hour + 2, 23)) % 12 or 12} {'AM' if min(start_hour + 2, 23) < 12 else 'PM'})",
                        'commit_count': window_commits,
                        'avg_duration_seconds': round(window_duration / window_commits, 2) if window_commits > 0 else 0
                    }
        
        if best_window['commit_count'] > 0:
            busiest_hours = best_window
        if worst_window['commit_count'] < float('inf'):
            quietest_hours = worst_window
    
    # Find busiest and quietest days
    busiest_day = None
    quietest_day = None
    if commit_activity_by_day:
        for day_name, day_data in commit_activity_by_day.items():
            commit_count = day_data['commit_count']
            avg_duration = round(day_data['total_duration'] / commit_count, 2) if commit_count > 0 else 0
            
            day_entry = {
                'day_num': day_data['day_num'],
                'day_name': day_name,
                'commit_count': commit_count,
                'avg_duration_seconds': avg_duration
            }
            
            if busiest_day is None or commit_count > busiest_day['commit_count']:
                busiest_day = day_entry
            
            if (quietest_day is None or commit_count < quietest_day['commit_count']) and commit_count > 0:
                quietest_day = day_entry
    
    commit_activity = {
        'total_commits': total_commits,
        'commits_by_hour': [],
        'by_instance': [],
        'busiest_hours': busiest_hours,
        'quietest_hours': quietest_hours,
        'busiest_day': busiest_day,
        'quietest_day': quietest_day
    }
    
    # Triage summary
    triage_summary = {
        'total': total_classified,
        'total_defects': total_defects,
        'classified_count': total_classified,
        'unclassified_count': total_unclassified,
        'triage_completion_percentage': triage_completion_pct,
        'bug_count': bug_count,
        'false_positive_count': false_positive_count,
        'intentional_count': intentional_count,
        'action_assigned_count': action_assigned_count,
        'by_state': [
            {'state': state, 'count': count}
            for state, count in triage_by_state_agg.items()
        ]
    }
    
    # Trend summary
    trend_summary = {
        'total_new': total_new,
        'total_fixed': total_fixed,
        'total_dismissed': total_dismissed,
        'avg_new_per_day': avg_new_per_day,
        'avg_fixed_per_day': avg_fixed_per_day,
        'net_change': net_change,
        'fix_rate_pct': fix_rate_pct,
        'trend_direction': trend_direction,
        'current_outstanding': total_outstanding
    }
    
    # Fix rate metrics
    fix_rate_metrics = {
        'total_defects': total_defects,
        'fixed_defects': total_fixed,
        'fix_rate_percentage': round((total_fixed / total_defects * 100) if total_defects > 0 else 0, 1)
    }
    
    tqdm.write(f"  [OK] Aggregated summary across {summary['total_instances']} instances")
    tqdm.write(f"  [OK] Total defects: {total_defects:,}")
    tqdm.write(f"  [OK] Outstanding: {total_outstanding:,}, Fixed: {total_fixed:,}")
    
    # Load CSS content for inline embedding
    inline_css = load_inline_css()
    
    # Load aggregated template (module-cached — Environment created once)
    template = _get_template('dashboard_aggregated.html')

    # Render template with data (NaN scrubbed to None — see _sanitize_for_template)
    html_content = _render_template(
        template,
        inline_css=inline_css,
        timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        summary=summary,
        defects_by_instance=defects_by_instance_list,
        defects_by_severity=defects_by_severity,
        analysis_versions=analysis_versions,
        instance_configs=instance_configs,
        user_statistics=user_statistics,
        database_statistics=database_statistics,
        commit_activity=commit_activity,
        triage_summary=triage_summary,
        trend_summary=trend_summary,
        fix_rate_metrics=fix_rate_metrics,
        trends_by_instance=trends_by_instance,
        scan_activity_series=[],
        trend_period_text=f"Last {days} Days",
        multi_instance_mode=True,
        zip_mode=True  # Flag to indicate ZIP mode (some features unavailable)
    )
    
    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_file) if os.path.dirname(output_file) else '.', exist_ok=True)
    
    # Write HTML file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    # Get absolute path for display
    abs_path = os.path.abspath(output_file)
    
    tqdm.write("\n" + "=" * 80)
    tqdm.write(f"[SUCCESS] Aggregated dashboard generated successfully!")
    tqdm.write(f"Location: {abs_path}")
    tqdm.write(f"File size: {os.path.getsize(output_file):,} bytes")
    tqdm.write("=" * 80)
    
    return abs_path


def main():
    """Main entry point with automatic multi-instance detection"""
    parser = argparse.ArgumentParser(
        description='Generate Coverity Metrics HTML Dashboard (auto-detects multi-instance from config.json)\n'
                    'Supports reading from database or exported ZIP files.',
        epilog='Examples:\n'
               '  coverity-dashboard                          # Auto-detect and generate all (database)\n'
               '  coverity-dashboard --project MyApp          # Filter by project (database)\n'
               '  coverity-dashboard --project AppA,AppB,AppC  # Multiple projects: per-project + aggregated instance dashboard\n'
               '  coverity-dashboard --instance Prod          # Specific instance only (database)\n'
               '  coverity-dashboard --zip-file export.zip    # Generate from ZIP export\n'
               '  coverity-dashboard --zip-file export1.zip export2.zip export3.zip  # Multi-ZIP aggregation\n'
               '  coverity-dashboard --zip-file a.zip b.zip --aggregated-view  # Opt in to aggregated view without config.json\n'
               '  coverity-dashboard --zip-file export.zip --instance Prod --project MyApp\n'
               '  coverity-dashboard --days 365               # Change trend period\n'
               '  coverity-dashboard --instance-only           # Skip per-project dashboards, generate instance-level only\n',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--project', '-p', type=str,
                       help='Filter metrics by project name(s). Use comma-separated values for multiple projects (e.g. AppA,AppB,AppC). Multiple projects generate per-project dashboards plus an aggregated instance dashboard.')
    parser.add_argument('--output', '-o', type=str, default='output', 
                       help='Output folder path (default: output)')
    parser.add_argument('--no-browser', action='store_true',
                       help='Do not open dashboard in browser')
    parser.add_argument('--workers', '-w', type=int, default=1,
                       help='Number of parallel workers for per-project dashboard generation (default: 1, capped at 8). '
                            'In database mode each worker uses its own Postgres connection; in ZIP mode each worker uses its own ZipDataLoader.')
    
    # Data source arguments
    parser.add_argument('--zip-file', '-z', type=str, nargs='+',
                       help='Use exported ZIP file(s) as data source instead of database (supports multiple files for aggregation)')

    parser.add_argument('--aggregated-view', action='store_true',
                       help='Generate a cross-instance aggregated dashboard (dashboard_aggregated.html) in ZIP mode. '
                            'Off by default. Also enabled if a passed --config has '
                            '"zip_files_config.aggregated_view.enabled": true (either source is sufficient). '
                            'Instance colors are auto-assigned; duplicate instance names across ZIPs are '
                            'disambiguated by appending the ZIP filename stem in parentheses.')

    # Multi-instance arguments (mostly for backward compatibility and override)
    parser.add_argument('--config', '-c', type=str, default=None,
                       help=('Path to configuration file. If omitted (and --zip-file is also omitted), the following are '
                             'tried in order: the environment variables COVERITY_DB_HOST / COVERITY_DB_NAME / '
                             'COVERITY_DB_USER / COVERITY_DB_PASSWORD (optional: COVERITY_DB_PORT, '
                             'COVERITY_INSTANCE_NAME), then a config.json in the current directory.'))
    parser.add_argument('--instance', '-i', type=str,
                       help='Generate dashboard for specific instance only')
    parser.add_argument('--single-instance-mode', action='store_true',
                       help='Force single-instance mode even if config.json has multiple instances')
    
    # Caching arguments
    parser.add_argument('--cache', action='store_true',
                       help='Enable caching to speed up subsequent generations')
    parser.add_argument('--cache-dir', type=str, default='cache',
                       help='Directory for cache files (default: cache)')
    parser.add_argument('--cache-ttl', type=int, default=24,
                       help='Cache time-to-live in hours (default: 24)')
    parser.add_argument('--clear-cache', action='store_true',
                       help='Clear all cached data before generating')
    parser.add_argument('--cache-stats', action='store_true',
                       help='Display cache statistics and exit')
    parser.add_argument('--no-cache', action='store_true',
                       help='Force refresh data from database, bypass cache')
    
    # Trend analysis arguments
    parser.add_argument('--days', '-d', type=int, default=365,
                       help='Number of days for trend analysis (default: 365)')
    
    # Progress tracking arguments
    parser.add_argument('--track-progress', action='store_true',
                       help='Enable progress tracking for large operations')
    parser.add_argument('--resume', type=str,
                       help='Resume from interrupted session (provide session ID)')

    parser.add_argument('--instance-only', '--no-projects', dest='instance_only', action='store_true',
                       help='Generate only instance-level dashboard(s); skip per-project dashboards. '
                            'Combine with --project A,B,... to scope the instance dashboard to selected projects. '
                            'Not valid with a single --project value.')

    parser.add_argument('--version', action='store_true',
                       help='Print version and exit')

    args = parser.parse_args()

    if args.version:
        try:
            from coverity_metrics.__version__ import __version__
            print(f"coverity-dashboard version: {__version__}")
        except Exception:
            print("coverity-dashboard version: unknown")
        return

    # Normalize --project to a list (split comma-separated input)
    if args.project:
        args.project = [p.strip() for p in args.project.split(',') if p.strip()]
        if not args.project:
            args.project = None

    if args.instance_only and args.project and len(args.project) == 1:
        print("[ERROR] --instance-only is incompatible with a single --project value (that would produce a project-level dashboard). "
              "Drop --project, or pass multiple comma-separated projects to scope the instance dashboard.")
        sys.exit(2)

    t0 = time.perf_counter()
    try:
        _run_main(args)
    finally:
        total_elapsed = time.perf_counter() - t0
        print(f"\nTotal execution time: {_format_duration(total_elapsed)}")


def _run_main(args):
    """Main body split out so the top-level main() can wrap it with timing."""
    tqdm.write("\nCoverity Metrics HTML Dashboard Generator")
    tqdm.write("=" * 80)
    
    # ========================================================================
    # ZIP FILE MODE - Read from exported ZIP instead of database
    # ========================================================================
    if args.zip_file:
        zip_files = args.zip_file if isinstance(args.zip_file, list) else [args.zip_file]
        # Windows shells (cmd, PowerShell) do not expand globs — do it here so
        # `--zip-file archive/*.zip` behaves the same on every platform.
        zip_files = _expand_zip_globs(zip_files)

        # Aggregated view opts in via CLI flag OR config; either source is enough.
        _, _, _zip_cfg = detect_multi_instance_config(args.config)
        _zip_agg_cfg = (_zip_cfg or {}).get('aggregated_view', {})
        zip_aggregated_view_enabled = bool(args.aggregated_view) or bool(_zip_agg_cfg.get('enabled', False))

        # Validate all ZIP files exist
        for zip_file in zip_files:
            if not os.path.exists(zip_file):
                tqdm.write(f"[ERROR] ZIP file not found: {zip_file}")
                sys.exit(1)
        
        # ==============================================================
        # MULTI-ZIP AGGREGATION MODE - Multiple ZIP files provided
        # ==============================================================
        if len(zip_files) > 1:
            tqdm.write(f"\n[Multi-ZIP Aggregation Mode] Combining {len(zip_files)} ZIP files:")
            for zip_file in zip_files:
                tqdm.write(f"  - {zip_file}")
            
            try:
                zip_loaders, all_instances, loaded_days = _build_zip_loader_map(zip_files)
                days = loaded_days if loaded_days is not None else 365

                if not zip_loaders:
                    tqdm.write("[ERROR] No valid instances found in any ZIP file")
                    sys.exit(1)
                
                tqdm.write(f"\nTotal instances loaded: {len(all_instances)}")
                tqdm.write(f"Instances: {', '.join(all_instances)}")
                
                generated_files = []
                
                # Generate aggregated dashboard (if no project filter and enabled in config)
                if not args.project and zip_aggregated_view_enabled:
                    tqdm.write("\n[1/3] Generating aggregated dashboard...")
                    aggregated_output = f"{args.output}/dashboard_aggregated.html"
                    
                    # Get instance configs from metadata with auto-assigned colors
                    color_map = assign_instance_colors(all_instances)
                    instance_configs = []
                    for instance_name in all_instances:
                        instance_configs.append({
                            'name': instance_name,
                            'description': f'{instance_name} Instance',
                            'color': color_map[instance_name]
                        })
                    
                    # Generate aggregated dashboard
                    dashboard_path = generate_aggregated_dashboard_from_zips(
                        zip_loaders,
                        instance_configs,
                        aggregated_output,
                        days
                    )
                    generated_files.append(("Aggregated View", dashboard_path))
                
                # Generate per-instance dashboards
                instance_num = 0 if args.project else 2
                total_steps = len(all_instances) + instance_num
                current_step = instance_num
                
                tqdm.write(f"\n[{current_step+1}/{total_steps}] Generating per-instance dashboards...")
                for instance_name in all_instances:
                    loader = zip_loaders[instance_name]
                    
                    output_folder = f"{args.output}/{instance_name.replace(' ', '_')}"
                    os.makedirs(output_folder, exist_ok=True)
                    
                    # Get projects for this instance
                    loader.project_name = None
                    available_projects = loader.list_available_projects()
                    
                    # Filter by project if specified
                    if args.project:
                        projects_filter = args.project  # list
                        # Check which of the requested projects exist in this instance
                        found = [p for p in projects_filter if p in available_projects]
                        if not found:
                            tqdm.write(f"  [SKIP] Instance '{instance_name}': None of the requested projects found")
                            continue

                        if len(found) > 1:
                            # Aggregated instance dashboard for selected projects
                            tqdm.write(f"  Generating instance dashboard for {instance_name} - {', '.join(found)}")
                            loader.project_name = found
                            output_file = f"{output_folder}/dashboard.html"
                            dashboard_path = generate_html_dashboard(
                                output_file, None, instance_name, loader,
                                cache=None, use_cache=False, days=days,
                                has_aggregated_dashboard=False
                            )
                            generated_files.append((f"{instance_name} - Selected Projects", dashboard_path))

                            if not args.instance_only:
                                # Per-project dashboards
                                for proj in found:
                                    tqdm.write(f"  Generating dashboard for {instance_name} - {proj}")
                                    loader.project_name = proj
                                    proj_output = f"{output_folder}/dashboard_{proj.replace(' ', '_')}.html"
                                    dashboard_path = generate_html_dashboard(
                                        proj_output, proj, instance_name, loader,
                                        cache=None, use_cache=False, days=days,
                                        has_aggregated_dashboard=False
                                    )
                                    generated_files.append((f"{instance_name} - {proj}", dashboard_path))
                        else:
                            # Single project found: existing behavior
                            proj = found[0]
                            tqdm.write(f"  Generating dashboard for {instance_name} - {proj}")
                            loader.project_name = proj
                            output_file = f"{output_folder}/dashboard_{proj.replace(' ', '_')}.html"
                            dashboard_path = generate_html_dashboard(
                                output_file, proj, instance_name, loader,
                                cache=None, use_cache=False, days=days,
                                has_aggregated_dashboard=False
                            )
                            generated_files.append((f"{instance_name} - {proj}", dashboard_path))
                    else:
                        # Instance-level dashboard
                        tqdm.write(f"  Generating instance dashboard: {instance_name}")
                        output_file = f"{output_folder}/dashboard.html"
                        dashboard_path = generate_html_dashboard(
                            output_file, 
                            None, 
                            instance_name, 
                            loader, 
                            cache=None, 
                            use_cache=False, 
                            days=days,
                            has_aggregated_dashboard=zip_aggregated_view_enabled,
                        )
                        generated_files.append((f"{instance_name} - All Projects", dashboard_path))
                        
                        if not args.instance_only:
                            # Project-level dashboards
                            for project_name in available_projects:
                                tqdm.write(f"    • Project: {project_name}")
                                loader.project_name = project_name
                                output_file = f"{output_folder}/dashboard_{project_name.replace(' ', '_')}.html"
                                dashboard_path = generate_html_dashboard(
                                    output_file, 
                                    project_name, 
                                    instance_name, 
                                    loader, 
                                    cache=None, 
                                    use_cache=False, 
                                    days=days,
                                    has_aggregated_dashboard=zip_aggregated_view_enabled,
                                )
                                generated_files.append((f"{instance_name} - {project_name}", dashboard_path))
                
                # Summary
                tqdm.write("\n" + "=" * 80)
                tqdm.write(f"[SUCCESS] Multi-instance dashboards generated successfully!")
                tqdm.write(f"  Total ZIP files: {len(zip_files)}")
                tqdm.write(f"  Total instances: {len(all_instances)}")
                tqdm.write(f"  Total dashboards: {len(generated_files)}")
                tqdm.write("\nGenerated dashboards:")
                for name, path in generated_files:
                    tqdm.write(f"  • {name}: {path}")
                
                # Open in browser
                if not args.no_browser and generated_files:
                    main_dashboard = generated_files[0][1]
                    tqdm.write(f"\nOpening dashboard in browser: {main_dashboard}")
                    webbrowser.open('file://' + os.path.abspath(main_dashboard))
                
                return
            
            except Exception as e:
                tqdm.write(f"[ERROR] Failed to process ZIP files: {str(e)}")
                import traceback
                traceback.print_exc()
                sys.exit(1)
        
        # ==============================================================
        # SINGLE-ZIP MODE - One ZIP file provided
        # ==============================================================
        else:
            zip_file = zip_files[0]
            tqdm.write(f"\n[ZIP File Mode] Using exported data: {zip_file}")
            
            # Load ZIP data
            try:
                zip_loader = ZipDataLoader(zip_file, instance_name=args.instance)
                metadata = zip_loader.get_metadata()
                
                tqdm.write(f"  Export date: {metadata.get('export_date', 'Unknown')}")
                tqdm.write(f"  Trend period: {metadata.get('days', 'Unknown')} days")
                
                available_instances = zip_loader.list_available_instances()
                tqdm.write(f"  Available instances: {', '.join(available_instances)}")
                
                # Auto-select instance if not specified
                if not args.instance and available_instances:
                    args.instance = available_instances[0]
                    tqdm.write(f"  Auto-selected instance: {args.instance}")
                    zip_loader.instance_name = args.instance
                
                # Get available projects
                available_projects = zip_loader.list_available_projects()
                tqdm.write(f"  Available projects: {', '.join(available_projects) if available_projects else 'None'}")
                
                generated_files = []
                
                if args.project:
                    # Generate dashboards for specified project(s)
                    projects_filter = args.project  # list
                    output_folder = f"{args.output}/{args.instance.replace(' ', '_')}" if args.instance else args.output
                    os.makedirs(output_folder, exist_ok=True)

                    # Validate all projects exist
                    missing = [p for p in projects_filter if p not in available_projects]
                    if missing:
                        tqdm.write(f"\n[ERROR] Project(s) not found in ZIP file: {', '.join(missing)}")
                        tqdm.write(f"Available projects: {', '.join(available_projects)}")
                        sys.exit(1)

                    if len(projects_filter) > 1:
                        # Aggregated instance dashboard for selected projects
                        tqdm.write(f"\nGenerating dashboards for {len(projects_filter)} projects: {', '.join(projects_filter)}")
                        zip_loader.project_name = projects_filter
                        inst_output = f"{output_folder}/dashboard.html"
                        dashboard_path = generate_html_dashboard(
                            inst_output, None, args.instance, zip_loader,
                            cache=None, use_cache=False, days=metadata.get('days', 365),
                            has_aggregated_dashboard=False
                        )
                        generated_files.append((f"{args.instance} - Selected Projects", dashboard_path))

                        if not args.instance_only:
                            # Per-project dashboards
                            for proj in projects_filter:
                                tqdm.write(f"  Generating dashboard for project: {proj}")
                                zip_loader.project_name = proj
                                proj_output = f"{output_folder}/dashboard_{proj.replace(' ', '_')}.html"
                                dashboard_path = generate_html_dashboard(
                                    proj_output, proj, args.instance, zip_loader,
                                    cache=None, use_cache=False, days=metadata.get('days', 365),
                                    has_aggregated_dashboard=False
                                )
                                generated_files.append((f"{args.instance} - {proj}", dashboard_path))
                    else:
                        # Single project: existing behavior
                        project = projects_filter[0]
                        tqdm.write(f"\nGenerating dashboard for project: {project}")
                        zip_loader.project_name = project
                        output_file = f"{output_folder}/dashboard_{project.replace(' ', '_')}.html"
                        dashboard_path = generate_html_dashboard(
                            output_file, project, args.instance, zip_loader,
                            cache=None, use_cache=False, days=metadata.get('days', 365),
                            has_aggregated_dashboard=False
                        )
                        generated_files.append((f"{args.instance} - {project}", dashboard_path))
                else:
                    # Generate dashboards for all projects
                    tqdm.write(f"\nGenerating dashboards for all projects in {args.instance}...")
                    
                    output_folder = f"{args.output}/{args.instance.replace(' ', '_')}" if args.instance else args.output
                    os.makedirs(output_folder, exist_ok=True)
                    
                    # Generate aggregated dashboard only if enabled in config
                    if zip_aggregated_view_enabled:
                        tqdm.write(f"  Generating aggregated dashboard...")
                        zip_loaders_dict = {args.instance: zip_loader}
                        # Auto-assign color for single instance
                        color_map = assign_instance_colors([args.instance])
                        instance_configs = [{
                            'name': args.instance,
                            'description': f'{args.instance} Instance',
                            'color': color_map[args.instance]
                        }]
                        aggregated_output = f"{args.output}/dashboard_aggregated.html"
                        dashboard_path = generate_aggregated_dashboard_from_zips(
                            zip_loaders_dict,
                            instance_configs,
                            aggregated_output,
                            metadata.get('days', 365)
                        )
                        generated_files.append(("Aggregated View", dashboard_path))
                    
                    # Instance-level dashboard (all projects)
                    tqdm.write(f"  Generating instance dashboard: {args.instance}")
                    output_file = f"{output_folder}/dashboard.html"
                    zip_loader.project_name = None
                    dashboard_path = generate_html_dashboard(
                        output_file, 
                        None, 
                        args.instance, 
                        zip_loader, 
                        cache=None, 
                        use_cache=False, 
                        days=metadata.get('days', 365),
                        has_aggregated_dashboard=zip_aggregated_view_enabled,
                    )
                    generated_files.append((f"{args.instance} - All Projects", dashboard_path))
                    
                    if args.instance_only:
                        available_projects = []  # skip per-project dashboards below
                    # Project-level dashboards
                    requested_workers = max(1, min(getattr(args, 'workers', 1) or 1, 8))
                    effective_workers = max(1, min(requested_workers, len(available_projects))) if available_projects else 1
                    if not available_projects:
                        pass
                    elif effective_workers == 1:
                        for project_name in available_projects:
                            tqdm.write(f"  Generating project dashboard: {project_name}")
                            zip_loader.project_name = project_name
                            output_file = f"{output_folder}/dashboard_{project_name.replace(' ', '_')}.html"
                            dashboard_path = generate_html_dashboard(
                                output_file,
                                project_name,
                                args.instance,
                                zip_loader,
                                cache=None,
                                use_cache=False,
                                days=metadata.get('days', 365),
                                has_aggregated_dashboard=zip_aggregated_view_enabled,
                            )
                            generated_files.append((f"{args.instance} - {project_name}", dashboard_path))
                    else:
                        # Parallel: one ZipDataLoader per worker (ZipFile
                        # handle isn't thread-safe, so open extras rather
                        # than sharing with a lock).
                        from concurrent.futures import ThreadPoolExecutor, as_completed
                        from queue import Queue

                        loader_pool = Queue()
                        loader_pool.put(zip_loader)
                        extras = []
                        for _ in range(effective_workers - 1):
                            extras.append(ZipDataLoader(zip_file, instance_name=args.instance))
                            loader_pool.put(extras[-1])

                        def _render(project_name):
                            output_file = f"{output_folder}/dashboard_{project_name.replace(' ', '_')}.html"
                            loader = loader_pool.get()
                            try:
                                loader.project_name = project_name
                                path = generate_html_dashboard(
                                    output_file,
                                    project_name,
                                    args.instance,
                                    loader,
                                    cache=None,
                                    use_cache=False,
                                    days=metadata.get('days', 365),
                                    has_aggregated_dashboard=zip_aggregated_view_enabled,
                                )
                                return project_name, path, None
                            except Exception as exc:
                                return project_name, output_file, exc
                            finally:
                                loader_pool.put(loader)

                        tqdm.write(f"  Generating {len(available_projects)} project dashboards (workers={effective_workers})...")
                        executor = ThreadPoolExecutor(max_workers=effective_workers)
                        try:
                            futures = [executor.submit(_render, p) for p in available_projects]
                            try:
                                for future in tqdm(as_completed(futures), total=len(futures),
                                                    desc="  Projects", unit="dashboard"):
                                    project_name, path, err = future.result()
                                    if err is not None:
                                        tqdm.write(f"    [ERROR] {project_name}: {err}")
                                    else:
                                        generated_files.append((f"{args.instance} - {project_name}", path))
                            except KeyboardInterrupt:
                                tqdm.write("\n[INTERRUPTED] Cancelling pending dashboards (in-flight ones will still finish)...")
                                for f in futures:
                                    f.cancel()
                                executor.shutdown(wait=False, cancel_futures=True)
                                raise
                        finally:
                            executor.shutdown(wait=True)
                
                # Summary
                tqdm.write("\n" + "=" * 80)
                tqdm.write(f"[SUCCESS] Dashboard(s) generated successfully!")
                tqdm.write(f"  Total dashboards: {len(generated_files)}")
                for name, path in generated_files:
                    tqdm.write(f"    {name}: {path}")
                
                # Open in browser
                if not args.no_browser and generated_files:
                    main_dashboard = generated_files[0][1]
                    tqdm.write(f"\nOpening dashboard in browser: {main_dashboard}")
                    webbrowser.open('file://' + os.path.abspath(main_dashboard))
                
                return
            
            except Exception as e:
                tqdm.write(f"[ERROR] Failed to process ZIP file: {str(e)}")
                import traceback
                traceback.print_exc()
                sys.exit(1)
    
    # ========================================================================
    # DATABASE MODE - Continue with normal database logic
    # ========================================================================

    # Resolve DB-mode config (explicit --config -> env vars -> default config.json -> guidance).
    config_data, enabled_instances, effective_config_path = _resolve_dashboard_config(args.config)
    instance_count = len(enabled_instances)
    is_multi_instance = instance_count > 1
    config_source_label = effective_config_path or 'environment variables'

    # Determine whether an aggregated dashboard will be generated.
    # It is only shown when config explicitly has aggregated_view.enabled = true.
    aggregated_view_cfg = (config_data or {}).get('aggregated_view', {})
    aggregated_view_enabled = aggregated_view_cfg.get('enabled', False)
    
    # Override detection if single-instance mode forced
    if args.single_instance_mode:
        is_multi_instance = False
        tqdm.write("\n[Single-Instance Mode] Forced by --single-instance-mode flag")
    elif is_multi_instance:
        tqdm.write(f"\n[Multi-Instance Mode] Auto-detected {instance_count} instances in {config_source_label}")
    else:
        tqdm.write(f"\n[Single-Instance Mode] Using first instance from {config_source_label}")
    
    # Handle cache stats request
    if args.cache_stats:
        cache = MetricsCache(cache_dir=args.cache_dir, cache_ttl_hours=args.cache_ttl)
        stats = cache.get_cache_stats()
        tqdm.write("\nCache Statistics:")
        tqdm.write(f"  Location: {stats['cache_dir']}")
        tqdm.write(f"  Total entries: {stats['total_entries']}")
        tqdm.write(f"  Valid entries: {stats['valid_entries']}")
        tqdm.write(f"  Expired entries: {stats['expired_entries']}")
        tqdm.write(f"  Total size: {stats['total_size_mb']} MB")
        
        if stats['expired_entries'] > 0:
            tqdm.write(f"\nRun with --clear-cache to remove expired entries")
        return
    
    # Initialize cache if enabled
    cache = None
    use_cache = not args.no_cache
    if args.cache or args.clear_cache:
        cache = MetricsCache(cache_dir=args.cache_dir, cache_ttl_hours=args.cache_ttl)
        tqdm.write(f"\n[Cache Enabled] Location: {cache.cache_dir}, TTL: {args.cache_ttl} hours")
        
        if args.clear_cache:
            cache.clear_cache()
            tqdm.write("[Cache Cleared] All cached data removed")
    
    # Initialize progress tracker if enabled
    progress_tracker = None
    session_id = None
    completed_names = set()
    if args.track_progress or args.resume:
        progress_tracker = ProgressTracker(cache_dir=args.cache_dir)
        
        if args.resume:
            # Load existing session
            tqdm.write(f"\n[Resume Mode] Loading session: {args.resume}")
            progress_data = progress_tracker.get_progress(args.resume)
            if not progress_data:
                tqdm.write(f"[ERROR] Session not found: {args.resume}")
                sys.exit(1)
            session_id = args.resume
            completed_names = {item['name'] for item in progress_data.get('completed_items', [])}
            tqdm.write(f"  Completed: {len(completed_names)}/{progress_data['total_tasks']}")
            tqdm.write(f"  Failed: {progress_data['failed_tasks']}")
            tqdm.write(f"  Skipping {len(completed_names)} already-completed dashboard(s)")
    
    try:
        # ========================================================================
        # MULTI-INSTANCE MODE (automatic)
        # ========================================================================
        if is_multi_instance and not args.single_instance_mode:
            from coverity_metrics.multi_instance_metrics import MultiInstanceMetrics
            
            multi_metrics = MultiInstanceMetrics(effective_config_path)
            instance_names = multi_metrics.get_instance_names()
            tqdm.write(f"  Instances: {', '.join(instance_names)}")
            
            generated_files = []
            
            # Check if filtering by specific instance
            if args.instance:
                # SPECIFIC INSTANCE MODE
                if args.instance not in instance_names:
                    tqdm.write(f"\n[ERROR] Unknown instance: {args.instance}")
                    tqdm.write(f"Available instances: {', '.join(instance_names)}")
                    sys.exit(1)
                
                tqdm.write(f"\nGenerating dashboards for instance: {args.instance}")
                
                if args.project:
                    # Specific instance + project filter (one or more projects)
                    projects_filter = args.project  # list
                    instance_folder = f"{args.output}/{args.instance.replace(' ', '_')}"
                    os.makedirs(instance_folder, exist_ok=True)

                    if len(projects_filter) > 1:
                        # Multiple projects: aggregated instance dashboard + per-project dashboards
                        project_names_str = ', '.join(projects_filter)
                        tqdm.write(f"  Project filter: {project_names_str}")
                        total_work = 1 + (0 if args.instance_only else len(projects_filter))
                        if progress_tracker and not session_id:
                            session_id = progress_tracker.create_session(total_work)
                            tqdm.write(f"  [Progress] Session ID: {session_id}  (use --resume {session_id} to resume if interrupted)")

                        # Aggregated instance dashboard for selected projects
                        output_file = f"{instance_folder}/dashboard.html"
                        _label = f"{args.instance} - Selected Projects"
                        if _label not in completed_names:
                            metrics = multi_metrics.get_metrics_for_instance(args.instance, projects_filter)
                            dashboard_path = generate_html_dashboard(output_file, None, args.instance, metrics, cache, use_cache, args.days, has_aggregated_dashboard=aggregated_view_enabled)
                            generated_files.append((_label, dashboard_path))
                            if progress_tracker and session_id:
                                progress_tracker.update_progress(session_id, _label)
                        else:
                            tqdm.write(f"  [SKIP] {_label}")
                            generated_files.append((_label, output_file))

                        if not args.instance_only:
                            # Per-project dashboards
                            for proj in projects_filter:
                                proj_output = f"{instance_folder}/dashboard_{proj.replace(' ', '_')}.html"
                                _proj_label = f"{args.instance} - {proj}"
                                if _proj_label not in completed_names:
                                    metrics_proj = multi_metrics.get_metrics_for_instance(args.instance, proj)
                                    dashboard_path = generate_html_dashboard(proj_output, proj, args.instance, metrics_proj, cache, use_cache, args.days)
                                    generated_files.append((_proj_label, dashboard_path))
                                    if progress_tracker and session_id:
                                        progress_tracker.update_progress(session_id, _proj_label)
                                else:
                                    tqdm.write(f"  [SKIP] {_proj_label}")
                                    generated_files.append((_proj_label, proj_output))

                        if progress_tracker and session_id:
                            progress_tracker.complete_session(session_id)
                    else:
                        # Single project: existing behavior
                        project = projects_filter[0]
                        tqdm.write(f"  Project filter: {project}")
                        metrics = multi_metrics.get_metrics_for_instance(args.instance, project)
                        output_file = f"{instance_folder}/dashboard_{project.replace(' ', '_')}.html"
                        _label = f"{args.instance} - {project}"
                        if progress_tracker and not session_id:
                            session_id = progress_tracker.create_session(1)
                            tqdm.write(f"  [Progress] Session ID: {session_id}  (use --resume {session_id} to resume if interrupted)")
                        if _label not in completed_names:
                            dashboard_path = generate_html_dashboard(output_file, project, args.instance, metrics, cache, use_cache, args.days, has_aggregated_dashboard=False, has_instance_dashboard=False)
                            generated_files.append((_label, dashboard_path))
                            if progress_tracker and session_id:
                                progress_tracker.update_progress(session_id, _label)
                        else:
                            tqdm.write(f"  [SKIP] {_label}")
                            generated_files.append((_label, output_file))
                        if progress_tracker and session_id:
                            progress_tracker.complete_session(session_id)
                else:
                    # Specific instance + all projects (AUTO)
                    tqdm.write(f"  Generating all projects (auto-mode)")
                    metrics = multi_metrics.get_metrics_for_instance(args.instance)
                    projects = metrics.get_available_projects()
                    
                    project_dashboards = 0 if args.instance_only else (len(projects) if not projects.empty else 0)
                    # Calculate total work
                    total_dashboards = 1 + project_dashboards  # 1 instance + N projects
                    tqdm.write(f"  Total dashboards to generate: {total_dashboards} (1 instance + {project_dashboards} projects)")
                    
                    if progress_tracker and not session_id:
                        session_id = progress_tracker.create_session(total_dashboards)
                        tqdm.write(f"  [Progress] Session ID: {session_id}  (use --resume {session_id} to resume if interrupted)")
                    with tqdm(total=total_dashboards, desc=f"{args.instance}", unit="dashboard") as pbar:
                        # Generate instance-level dashboard (all projects)
                        instance_folder = f"{args.output}/{args.instance.replace(' ', '_')}"
                        os.makedirs(instance_folder, exist_ok=True)
                        pbar.set_description(f"{args.instance} - Overview")
                        output_file = f"{instance_folder}/dashboard.html"
                        _inst_label = f"{args.instance} - All Projects"
                        if _inst_label not in completed_names:
                            dashboard_path = generate_html_dashboard(output_file, None, args.instance, metrics, cache, use_cache, args.days, has_aggregated_dashboard=aggregated_view_enabled)
                            generated_files.append((_inst_label, dashboard_path))
                            if progress_tracker and session_id:
                                progress_tracker.update_progress(session_id, _inst_label)
                        else:
                            tqdm.write(f"  [SKIP] {_inst_label}")
                            generated_files.append((_inst_label, output_file))
                        pbar.update(1)

                        # Generate project-level dashboards
                        if not args.instance_only and not projects.empty:
                            for idx, project in enumerate(projects['project_name'], 1):
                                pbar.set_description(f"{args.instance} - {project}")
                                pbar.set_postfix_str(f"{idx}/{len(projects)}")
                                _proj_label = f"{args.instance} - {project}"
                                output_file = f"{instance_folder}/dashboard_{project.replace(' ', '_')}.html"
                                if _proj_label not in completed_names:
                                    metrics_proj = multi_metrics.get_metrics_for_instance(args.instance, project)
                                    dashboard_path = generate_html_dashboard(output_file, project, args.instance, metrics_proj, cache, use_cache, args.days)
                                    generated_files.append((_proj_label, dashboard_path))
                                    if progress_tracker and session_id:
                                        progress_tracker.update_progress(session_id, _proj_label)
                                else:
                                    tqdm.write(f"  [SKIP] {_proj_label}")
                                    generated_files.append((_proj_label, output_file))
                                pbar.update(1)
                    if progress_tracker and session_id:
                        progress_tracker.complete_session(session_id)
                    
            else:
                # ALL INSTANCES MODE (AUTO-AGGREGATED)
                if args.project:
                    # All instances filtered by project(s)
                    projects_filter = args.project  # list
                    project_names_str = ', '.join(projects_filter)
                    tqdm.write(f"\nGenerating dashboards for all instances, project(s): {project_names_str}")
                    tqdm.write(f"  Total instances: {len(instance_names)}")

                    # total work: per instance = 1 instance dashboard (if multi-project) + N project dashboards
                    if args.instance_only:
                        total_per_instance = 1 if len(projects_filter) > 1 else 0
                    else:
                        total_per_instance = (1 + len(projects_filter)) if len(projects_filter) > 1 else 1
                    if progress_tracker and not session_id:
                        session_id = progress_tracker.create_session(len(instance_names) * total_per_instance)
                        tqdm.write(f"  [Progress] Session ID: {session_id}  (use --resume {session_id} to resume if interrupted)")
                    with tqdm(total=len(instance_names) * total_per_instance, desc="Instances", unit="dashboard") as pbar:
                        for idx, instance_name in enumerate(instance_names, 1):
                            pbar.set_description(f"Instance {idx}/{len(instance_names)}: {instance_name}")
                            instance_folder = f"{args.output}/{instance_name.replace(' ', '_')}"
                            os.makedirs(instance_folder, exist_ok=True)

                            if len(projects_filter) > 1:
                                # Aggregated instance dashboard for selected projects
                                _inst_label = f"{instance_name} - Selected Projects"
                                inst_output = f"{instance_folder}/dashboard.html"
                                if _inst_label not in completed_names:
                                    metrics = multi_metrics.get_metrics_for_instance(instance_name, projects_filter)
                                    dashboard_path = generate_html_dashboard(inst_output, None, instance_name, metrics, cache, use_cache, args.days)
                                    generated_files.append((_inst_label, dashboard_path))
                                    if progress_tracker and session_id:
                                        progress_tracker.update_progress(session_id, _inst_label)
                                else:
                                    tqdm.write(f"  [SKIP] {_inst_label}")
                                    generated_files.append((_inst_label, inst_output))
                                pbar.update(1)

                                # Per-project dashboards — reuse ONE CoverityMetrics
                                # for the instance, rescoping via .project_name to
                                # avoid a fresh Postgres connection per project.
                                if not args.instance_only:
                                    instance_metrics = multi_metrics.get_metrics_for_instance(instance_name)
                                    for proj in projects_filter:
                                        _proj_label = f"{instance_name} - {proj}"
                                        proj_output = f"{instance_folder}/dashboard_{proj.replace(' ', '_')}.html"
                                        if _proj_label not in completed_names:
                                            instance_metrics.project_name = proj
                                            dashboard_path = generate_html_dashboard(proj_output, proj, instance_name, instance_metrics, cache, use_cache, args.days)
                                            generated_files.append((_proj_label, dashboard_path))
                                            if progress_tracker and session_id:
                                                progress_tracker.update_progress(session_id, _proj_label)
                                        else:
                                            tqdm.write(f"  [SKIP] {_proj_label}")
                                            generated_files.append((_proj_label, proj_output))
                                        pbar.update(1)
                            else:
                                # Single project: existing per-instance behavior
                                project = projects_filter[0]
                                _label = f"{instance_name} - {project}"
                                output_file = f"{instance_folder}/dashboard_{project.replace(' ', '_')}.html"
                                if _label not in completed_names:
                                    metrics = multi_metrics.get_metrics_for_instance(instance_name, project)
                                    dashboard_path = generate_html_dashboard(output_file, project, instance_name, metrics, cache, use_cache, args.days, has_aggregated_dashboard=False, has_instance_dashboard=False)
                                    generated_files.append((_label, dashboard_path))
                                    if progress_tracker and session_id:
                                        progress_tracker.update_progress(session_id, _label)
                                else:
                                    tqdm.write(f"  [SKIP] {_label}")
                                    generated_files.append((_label, output_file))
                                pbar.update(1)
                    if progress_tracker and session_id:
                        progress_tracker.complete_session(session_id)
                else:
                    # All instances + all projects (FULL AUTO MODE)
                    # Calculate total work for progress tracking
                    tqdm.write("\nCalculating total work for progress tracking...")
                    total_work_items = 1  # Aggregated dashboard
                    total_work_items += len(instance_names)  # Instance-level dashboards
                    
                    # Count projects per instance for accurate progress
                    instance_project_counts = {}
                    for instance_name in instance_names:
                        metrics_temp = multi_metrics.get_metrics_for_instance(instance_name)
                        projects_temp = metrics_temp.get_available_projects()
                        project_count = len(projects_temp) if not projects_temp.empty else 0
                        instance_project_counts[instance_name] = project_count
                        if not args.instance_only:
                            total_work_items += project_count
                    
                    tqdm.write(f"  Total dashboards to generate: {total_work_items}")
                    tqdm.write(f"  - 1 aggregated dashboard")
                    tqdm.write(f"  - {len(instance_names)} instance dashboards")
                    if args.instance_only:
                        tqdm.write(f"  - 0 project dashboards (--instance-only)")
                    else:
                        tqdm.write(f"  - {sum(instance_project_counts.values())} project dashboards")
                    
                    if progress_tracker and not session_id:
                        session_id = progress_tracker.create_session(total_work_items)
                        tqdm.write(f"  [Progress] Session ID: {session_id}  (use --resume {session_id} to resume if interrupted)")
                    
                    # Create overall progress bar
                    with tqdm(total=total_work_items, desc="Overall Progress", unit="dashboard", position=0) as pbar_overall:
                        # Generate aggregated dashboard
                        tqdm.write("\nGenerating aggregated dashboard across all instances...")
                        os.makedirs(args.output, exist_ok=True)
                        output_file = f"{args.output}/dashboard_aggregated.html"
                        _agg_label = "Aggregated View"
                        if _agg_label not in completed_names:
                            dashboard_path = generate_aggregated_dashboard(multi_metrics, output_file, args.days)
                            generated_files.append((_agg_label, dashboard_path))
                            if progress_tracker and session_id:
                                progress_tracker.update_progress(session_id, _agg_label)
                        else:
                            tqdm.write(f"  [SKIP] {_agg_label}")
                            generated_files.append((_agg_label, output_file))
                        pbar_overall.update(1)
                        
                        # Also generate instance-level dashboards for navigation
                        tqdm.write("\nGenerating instance-level dashboards for navigation...")
                        for idx, instance_name in enumerate(instance_names, 1):
                            pbar_overall.set_description(f"Instance {idx}/{len(instance_names)}: {instance_name}")
                            _inst_label = instance_name
                            instance_folder = f"{args.output}/{instance_name.replace(' ', '_')}"
                            os.makedirs(instance_folder, exist_ok=True)
                            output_file = f"{instance_folder}/dashboard.html"
                            if _inst_label not in completed_names:
                                metrics = multi_metrics.get_metrics_for_instance(instance_name)
                                dashboard_path = generate_html_dashboard(output_file, None, instance_name, metrics, cache, use_cache, args.days, has_aggregated_dashboard=aggregated_view_enabled)
                                generated_files.append((_inst_label, dashboard_path))
                                if progress_tracker and session_id:
                                    progress_tracker.update_progress(session_id, _inst_label)
                            else:
                                tqdm.write(f"  [SKIP] {_inst_label}")
                                generated_files.append((_inst_label, output_file))
                            pbar_overall.update(1)
                        
                        tqdm.write(f"\n[OK] Generated aggregated view + {len(instance_names)} instance dashboards")
                        
                        if args.instance_only:
                            tqdm.write("\n[--instance-only] Skipping per-project dashboards")
                        # Auto-generate project-level dashboards for each instance
                        tqdm.write("\nGenerating project-level dashboards for all instances...")
                        total_projects = 0
                        requested_workers = max(1, min(getattr(args, 'workers', 1) or 1, 8))
                        for idx, instance_name in enumerate(instance_names, 1):
                            if args.instance_only:
                                break
                            base_metrics = multi_metrics.get_metrics_for_instance(instance_name)
                            projects = base_metrics.get_available_projects()

                            if projects.empty:
                                continue

                            project_list = list(projects['project_name'])
                            pbar_overall.set_description(f"Instance {idx}/{len(instance_names)}: {instance_name} projects")

                            instance_folder = f"{args.output}/{instance_name.replace(' ', '_')}"
                            os.makedirs(instance_folder, exist_ok=True)

                            effective_workers = max(1, min(requested_workers, len(project_list)))
                            if effective_workers == 1:
                                # Sequential path — reuse one CoverityMetrics for all projects.
                                for proj_idx, project in enumerate(project_list, 1):
                                    pbar_overall.set_postfix_str(f"{project} ({proj_idx}/{len(project_list)})")
                                    _proj_label = f"{instance_name} - {project}"
                                    output_file = f"{instance_folder}/dashboard_{project.replace(' ', '_')}.html"
                                    if _proj_label not in completed_names:
                                        base_metrics.project_name = project
                                        try:
                                            dashboard_path = generate_html_dashboard(output_file, project, instance_name, base_metrics, cache, use_cache, args.days)
                                            generated_files.append((_proj_label, dashboard_path))
                                            if progress_tracker and session_id:
                                                progress_tracker.update_progress(session_id, _proj_label)
                                        except Exception as exc:
                                            tqdm.write(f"  [ERROR] {_proj_label}: {exc}")
                                    else:
                                        tqdm.write(f"  [SKIP] {_proj_label}")
                                        generated_files.append((_proj_label, output_file))
                                    total_projects += 1
                                    pbar_overall.update(1)
                                base_metrics.project_name = None
                            else:
                                # Parallel path — one worker owns one
                                # CoverityMetrics (Postgres conns aren't
                                # thread-safe). Reuse ``base_metrics`` as
                                # worker #0 and open extras for the rest.
                                from concurrent.futures import ThreadPoolExecutor, as_completed
                                from queue import Queue
                                import threading

                                instance_config = multi_metrics.get_instance_config(instance_name)
                                conn_params = instance_config.get_connection_params() if instance_config else None

                                worker_pool = Queue()
                                base_metrics.project_name = None
                                worker_pool.put(base_metrics)
                                extras = []
                                for _ in range(effective_workers - 1):
                                    extras.append(CoverityMetrics(connection_params=conn_params))
                                    worker_pool.put(extras[-1])

                                progress_lock = threading.Lock()

                                def _process(project):
                                    _label = f"{instance_name} - {project}"
                                    output_file = f"{instance_folder}/dashboard_{project.replace(' ', '_')}.html"
                                    if _label in completed_names:
                                        return _label, output_file, True  # skipped
                                    m = worker_pool.get()
                                    try:
                                        m.project_name = project
                                        path = generate_html_dashboard(output_file, project, instance_name, m, cache, use_cache, args.days)
                                        return _label, path, False
                                    finally:
                                        worker_pool.put(m)

                                pbar_overall.set_postfix_str(f"parallel x{effective_workers}")
                                executor = ThreadPoolExecutor(max_workers=effective_workers)
                                try:
                                    futures = [executor.submit(_process, p) for p in project_list]
                                    try:
                                        for future in as_completed(futures):
                                            try:
                                                _label, path, was_skipped = future.result()
                                                generated_files.append((_label, path))
                                                if was_skipped:
                                                    tqdm.write(f"  [SKIP] {_label}")
                                                elif progress_tracker and session_id:
                                                    with progress_lock:
                                                        progress_tracker.update_progress(session_id, _label)
                                            except Exception as exc:
                                                tqdm.write(f"  [ERROR] {exc}")
                                            total_projects += 1
                                            pbar_overall.update(1)
                                    except KeyboardInterrupt:
                                        tqdm.write("\n[INTERRUPTED] Cancelling pending dashboards (in-flight ones will still finish)...")
                                        for f in futures:
                                            f.cancel()
                                        executor.shutdown(wait=False, cancel_futures=True)
                                        raise
                                finally:
                                    executor.shutdown(wait=True)
                                    for extra in extras:
                                        try:
                                            extra.db.close()
                                        except Exception:
                                            pass

                        pbar_overall.set_description("Complete")
                        pbar_overall.set_postfix_str("")
                    
                    if progress_tracker and session_id:
                        progress_tracker.complete_session(session_id)
                    tqdm.write(f"\n[OK] Generated {total_projects} project-level dashboards across {len(instance_names)} instances")
                
            # Summary and completion
            tqdm.write("\n" + "=" * 80)
            tqdm.write(f"[SUCCESS] Generated {len(generated_files)} dashboards!")
            tqdm.write("=" * 80)
            
            if generated_files and not args.no_browser:
                tqdm.write("\nOpening aggregated dashboard in browser...")
                webbrowser.open('file://' + os.path.abspath(generated_files[0][1]))
            
            tqdm.write("\n" + "=" * 80)
            tqdm.write("Dashboard generation completed successfully!")
            tqdm.write("=" * 80 + "\n")
            return

        
        # ========================================================================
        # SINGLE-INSTANCE MODE
        # ========================================================================
        # For single-instance mode, we still generate aggregated dashboard for consistency
        from coverity_metrics.multi_instance_metrics import MultiInstanceMetrics
        
        # Read first enabled instance from config.json
        connection_params = None
        instance_name = None
        if config_data and config_data.get('instances'):
            enabled_instances = [inst for inst in config_data['instances'] if inst.get('enabled', True)]
            if enabled_instances:
                first_instance = enabled_instances[0]
                connection_params = {
                    'host': first_instance['database']['host'],
                    'port': first_instance['database']['port'],
                    'database': first_instance['database']['database'],
                    'user': first_instance['database']['user'],
                    'password': first_instance['database']['password']
                }
                instance_name = first_instance['name']
                tqdm.write(f"  Using instance: {instance_name}")
        
        if not connection_params:
            tqdm.write(f"\n[ERROR] No database configuration found in {config_source_label}")
            tqdm.write("Please configure at least one instance, or set the COVERITY_DB_* environment variables")
            sys.exit(1)
        
        # Create metrics instance with connection params from config.json
        metrics = CoverityMetrics(connection_params=connection_params)
        
        # Use same folder structure as multi-instance mode
        generated_files = []
        
        if args.project:
            projects_filter = args.project  # list of project names
            instance_folder = f"{args.output}/{instance_name.replace(' ', '_')}"
            os.makedirs(instance_folder, exist_ok=True)

            if len(projects_filter) > 1:
                # Multiple projects: generate aggregated instance dashboard + per-project dashboards
                project_names_str = ', '.join(projects_filter)
                tqdm.write(f"\nGenerating dashboards for {len(projects_filter)} projects: {project_names_str}")
                total_work = 1 + (0 if args.instance_only else len(projects_filter))
                if progress_tracker and not session_id:
                    session_id = progress_tracker.create_session(total_work)
                    tqdm.write(f"  [Progress] Session ID: {session_id}")

                # Aggregated instance dashboard filtered to selected projects
                output_file = f"{instance_folder}/dashboard.html"
                _label = f"{instance_name} - Selected Projects"
                if _label not in completed_names:
                    metrics.project_name = projects_filter
                    dashboard_path = generate_html_dashboard(output_file, None, instance_name, metrics, cache, use_cache, args.days, has_aggregated_dashboard=aggregated_view_enabled)
                    generated_files.append((_label, dashboard_path))
                    if progress_tracker and session_id:
                        progress_tracker.update_progress(session_id, _label)
                else:
                    tqdm.write(f"  [SKIP] {_label}")
                    generated_files.append((_label, output_file))

                if not args.instance_only:
                    # Per-project dashboards
                    for proj in projects_filter:
                        proj_output = f"{instance_folder}/dashboard_{proj.replace(' ', '_')}.html"
                        _proj_label = f"{instance_name} - {proj}"
                        if _proj_label not in completed_names:
                            metrics_proj = CoverityMetrics(connection_params=connection_params, project_name=proj)
                            dashboard_path = generate_html_dashboard(proj_output, proj, instance_name, metrics_proj, cache, use_cache, args.days)
                            generated_files.append((_proj_label, dashboard_path))
                            if progress_tracker and session_id:
                                progress_tracker.update_progress(session_id, _proj_label)
                        else:
                            tqdm.write(f"  [SKIP] {_proj_label}")
                            generated_files.append((_proj_label, proj_output))

                if progress_tracker and session_id:
                    progress_tracker.complete_session(session_id)
            else:
                # Single project: existing behavior
                project = projects_filter[0]
                tqdm.write(f"\nGenerating dashboard for project: {project}")
                output_file = f"{instance_folder}/dashboard_{project.replace(' ', '_')}.html"
                _label = f"{instance_name} - {project}"
                if progress_tracker and not session_id:
                    session_id = progress_tracker.create_session(1)
                    tqdm.write(f"  [Progress] Session ID: {session_id}")
                if _label not in completed_names:
                    dashboard_path = generate_html_dashboard(output_file, project, instance_name, metrics, cache, use_cache, args.days, has_aggregated_dashboard=False, has_instance_dashboard=False)
                    generated_files.append((_label, dashboard_path))
                    if progress_tracker and session_id:
                        progress_tracker.update_progress(session_id, _label)
                else:
                    tqdm.write(f"  [SKIP] {_label}")
                    generated_files.append((_label, output_file))
                if progress_tracker and session_id:
                    progress_tracker.complete_session(session_id)
        else:
            # All projects (AUTO MODE) - same as multi-instance
            tqdm.write(f"\nGenerating all dashboards for instance: {instance_name}")
            projects = metrics.get_available_projects()

            # The aggregated cross-instance dashboard only makes sense when we
            # actually have a config file (so MultiInstanceMetrics has something
            # to load) and aggregated_view is opted in. Env-var mode always skips.
            generate_aggregated = bool(effective_config_path) and aggregated_view_enabled
            agg_count = 1 if generate_aggregated else 0

            # Calculate total work: [aggregated] + instance + projects
            project_count = 0 if args.instance_only else (len(projects) if not projects.empty else 0)
            total_dashboards = agg_count + 1 + project_count
            tqdm.write(f"  Total dashboards to generate: {total_dashboards} ({agg_count} aggregated + 1 instance + {project_count} projects)")

            if progress_tracker and not session_id:
                session_id = progress_tracker.create_session(total_dashboards)
                tqdm.write(f"  [Progress] Session ID: {session_id}  (use --resume {session_id} to resume if interrupted)")

            with tqdm(total=total_dashboards, desc=f"{instance_name}", unit="dashboard") as pbar:
                # Generate aggregated dashboard (only when opted in via config)
                if generate_aggregated:
                    pbar.set_description("Aggregated View")
                    multi_metrics = MultiInstanceMetrics(effective_config_path)
                    os.makedirs(args.output, exist_ok=True)
                    output_file = f"{args.output}/dashboard_aggregated.html"
                    _agg_label = "Aggregated View"
                    if _agg_label not in completed_names:
                        dashboard_path = generate_aggregated_dashboard(multi_metrics, output_file, args.days)
                        generated_files.append((_agg_label, dashboard_path))
                        if progress_tracker and session_id:
                            progress_tracker.update_progress(session_id, _agg_label)
                    else:
                        tqdm.write(f"  [SKIP] {_agg_label}")
                        generated_files.append((_agg_label, output_file))
                    pbar.update(1)
                
                # Generate instance-level dashboard (all projects)
                instance_folder = f"{args.output}/{instance_name.replace(' ', '_')}"
                os.makedirs(instance_folder, exist_ok=True)
                pbar.set_description(f"{instance_name} - Overview")
                output_file = f"{instance_folder}/dashboard.html"
                _inst_label = f"{instance_name} - All Projects"
                if _inst_label not in completed_names:
                    dashboard_path = generate_html_dashboard(output_file, None, instance_name, metrics, cache, use_cache, args.days, has_aggregated_dashboard=aggregated_view_enabled)
                    generated_files.append((_inst_label, dashboard_path))
                    if progress_tracker and session_id:
                        progress_tracker.update_progress(session_id, _inst_label)
                else:
                    tqdm.write(f"  [SKIP] {_inst_label}")
                    generated_files.append((_inst_label, output_file))
                pbar.update(1)
                
                # Generate project-level dashboards
                if not args.instance_only and not projects.empty:
                    for idx, project in enumerate(projects['project_name'], 1):
                        pbar.set_description(f"{instance_name} - {project}")
                        pbar.set_postfix_str(f"{idx}/{len(projects)}")
                        _proj_label = f"{instance_name} - {project}"
                        output_file = f"{instance_folder}/dashboard_{project.replace(' ', '_')}.html"
                        if _proj_label not in completed_names:
                            # Create a new metrics instance with project filter
                            metrics_proj = CoverityMetrics(connection_params=connection_params, project_name=project)
                            dashboard_path = generate_html_dashboard(output_file, project, instance_name, metrics_proj, cache, use_cache, args.days)
                            generated_files.append((_proj_label, dashboard_path))
                            if progress_tracker and session_id:
                                progress_tracker.update_progress(session_id, _proj_label)
                        else:
                            tqdm.write(f"  [SKIP] {_proj_label}")
                            generated_files.append((_proj_label, output_file))
                        pbar.update(1)
            if progress_tracker and session_id:
                progress_tracker.complete_session(session_id)
        
        # Summary and completion
        tqdm.write("\n" + "=" * 80)
        tqdm.write(f"[SUCCESS] Generated {len(generated_files)} dashboard(s)!")
        tqdm.write("=" * 80)
        
        if generated_files and not args.no_browser:
            tqdm.write("\nOpening dashboard in default browser...")
            webbrowser.open('file://' + os.path.abspath(generated_files[0][1]))
            tqdm.write("[OK] Dashboard opened")
        
        tqdm.write("\n" + "=" * 80)
        tqdm.write("Dashboard generation completed successfully!")
        tqdm.write("=" * 80 + "\n")

    except KeyboardInterrupt:
        tqdm.write("\n[INTERRUPTED] Aborted by user.")
        sys.exit(130)
    except Exception as e:
        tqdm.write(f"\n[ERROR] Failed to generate dashboard")
        tqdm.write(f"  {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

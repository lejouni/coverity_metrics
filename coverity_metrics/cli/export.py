"""
Coverity Metrics Export Utility
Export metrics to JSON format
Supports multi-instance export with ZIP packaging
"""
import os
import json
import sys
import time
import zipfile
from datetime import datetime, date
from decimal import Decimal
from coverity_metrics.metrics import CoverityMetrics
from coverity_metrics.anonymizer import Anonymizer, default_mapping_path
import pandas as pd
from tqdm import tqdm
import argparse


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


def json_serializer(obj):
    """Convert non-serializable objects to JSON-compatible formats
    
    Args:
        obj: Object to convert
        
    Returns:
        JSON-serializable value
        
    Raises:
        TypeError: If object type is not supported
    """
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, (datetime, pd.Timestamp)):
        return obj.isoformat()
    elif isinstance(obj, date):
        return obj.isoformat()
    elif pd.isna(obj):
        return None
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

# Metric names that make up the Leaderboards tab on the dashboard.
LEADERBOARD_METRICS = {
    'top_projects_by_fix_rate',
    'top_projects_by_triage_activity',
    'top_users_by_fixes',
    'top_triagers',
    'most_collaborative_users',
}

# Metric names that make up the Snapshots tab on the dashboard.
SNAPSHOT_METRICS = {
    'snapshot_commands',
}


def load_config(config_file='config.json'):
    """Load configuration with multi-instance support
    
    Returns:
        dict: Configuration data with instances
    """
    if not os.path.exists(config_file):
        print(f"ERROR: Configuration file not found: {config_file}")
        print("Please create config.json with at least one instance configured")
        sys.exit(1)
    
    try:
        with open(config_file, 'r') as f:
            config_data = json.load(f)
        
        instances = config_data.get('instances', [])
        enabled_instances = [inst for inst in instances if inst.get('enabled', True)]
        
        if not enabled_instances:
            print("ERROR: No enabled instances found in config.json")
            sys.exit(1)
        
        return config_data, enabled_instances
        
    except Exception as e:
        print(f"ERROR: Failed to load configuration: {str(e)}")
        sys.exit(1)


# Environment-variable names for single-instance config (see load_config_from_env()).
ENV_HOST = 'COVERITY_DB_HOST'
ENV_PORT = 'COVERITY_DB_PORT'
ENV_DATABASE = 'COVERITY_DB_NAME'
ENV_USER = 'COVERITY_DB_USER'
ENV_PASSWORD = 'COVERITY_DB_PASSWORD'
ENV_INSTANCE_NAME = 'COVERITY_INSTANCE_NAME'

_ENV_REQUIRED = (ENV_HOST, ENV_DATABASE, ENV_USER, ENV_PASSWORD)


def _env_vars_present():
    """Return True when every required Coverity DB env var is set to a non-empty value."""
    return all(os.environ.get(v) for v in _ENV_REQUIRED)


def load_config_from_env():
    """Build a single-instance config dict from environment variables.

    Required: ``COVERITY_DB_HOST``, ``COVERITY_DB_NAME``, ``COVERITY_DB_USER``,
    ``COVERITY_DB_PASSWORD``.
    Optional: ``COVERITY_DB_PORT`` (default ``5432``), ``COVERITY_INSTANCE_NAME``
    (default ``"Coverity"``).

    Returns:
        tuple: ``(config_data, enabled_instances)`` matching ``load_config()``.
    """
    missing = [v for v in _ENV_REQUIRED if not os.environ.get(v)]
    if missing:
        print("ERROR: Missing required environment variables: " + ", ".join(missing))
        print(f"Required: {', '.join(_ENV_REQUIRED)}")
        print(f"Optional: {ENV_PORT} (default 5432), {ENV_INSTANCE_NAME} (default 'Coverity')")
        sys.exit(1)

    port_raw = os.environ.get(ENV_PORT, '5432')
    try:
        port = int(port_raw)
    except ValueError:
        print(f"ERROR: {ENV_PORT} must be an integer, got: {port_raw!r}")
        sys.exit(1)

    instance = {
        'name': os.environ.get(ENV_INSTANCE_NAME) or 'Coverity',
        'enabled': True,
        'database': {
            'host': os.environ[ENV_HOST],
            'port': port,
            'database': os.environ[ENV_DATABASE],
            'user': os.environ[ENV_USER],
            'password': os.environ[ENV_PASSWORD],
        },
    }
    config_data = {'instances': [instance]}
    return config_data, [instance]


def resolve_config(config_file=None):
    """Resolve export configuration from a JSON file or environment variables.

    Precedence:
      1. Explicit ``config_file`` (from ``--config``) -> load from JSON, fail if missing.
      2. All required env vars set -> single-instance env-var mode with an [INFO] message.
      3. Default ``config.json`` exists in the current directory -> load from JSON.
      4. Otherwise -> error out listing both configuration options.
    """
    if config_file:
        return load_config(config_file)
    if _env_vars_present():
        print(f"[INFO] Using {ENV_HOST}/... environment variables for single-instance configuration.")
        return load_config_from_env()
    if os.path.exists('config.json'):
        return load_config('config.json')
    print("ERROR: No configuration provided.")
    print("Pass --config <file> pointing at a config.json (see config.json.example),")
    print("or set the following environment variables for single-instance mode:")
    print(f"  Required: {', '.join(_ENV_REQUIRED)}")
    print(f"  Optional: {ENV_PORT} (default 5432), {ENV_INSTANCE_NAME} (default 'Coverity')")
    sys.exit(1)

def export_instance_to_json(instance_name, connection_params, instance_dir, days=365, projects_filter=None, anonymizer=None, include_leaderboards=True, include_snapshots=True, verbose=False):
    """Export all metrics for a single instance to JSON files
    
    Args:
        instance_name: Name of the instance
        connection_params: Database connection parameters
        instance_dir: Instance-specific directory to save JSON files
        days: Number of days for trend analysis
        projects_filter: Optional list of project names to filter metrics
        anonymizer: Optional :class:`Anonymizer` used to swap real project/stream
            names for anonymized ids just before serialization.
        verbose: When True, log a per-metric ``[SKIP] ... No data`` line for
            every empty metric. When False (default), those lines are
            suppressed and the count is returned via the second tuple element.

    Returns:
        tuple: ``(exported_files, skipped_count)`` where ``skipped_count`` is
        the number of metrics that produced no data (or unsupported types).
    """
    print(f"\n[{instance_name}] Exporting metrics...")
    if projects_filter:
        print(f"  Project filter: {', '.join(projects_filter)}")
    
    metrics = CoverityMetrics(connection_params=connection_params, project_name=projects_filter if projects_filter else None)

    # When exactly one project is active, several metrics (e.g. total_defects_by_project,
    # top_projects_by_classification) switch to stream-per-row mode and emit stream names
    # under a ``project_name`` / ``name`` alias. Treat that as project-scope for the
    # anonymizer so those stream values are mapped as streams instead of new projects.
    single_project_context = bool(projects_filter) and len(projects_filter) == 1

    # Dictionary to store export metadata
    exported_files = {}
    
    # Define all metrics to export with their configurations
    metrics_config = {
        # Basic Metrics
        'available_projects': {'method': 'get_available_projects'},
        'overall_summary': {'method': 'get_overall_summary', 'kwargs': {'days': days}},
        'defects_by_severity': {'method': 'get_defects_by_severity'},
        'total_defects_by_project': {'method': 'get_total_defects_by_project'},
        'defects_by_checker_category': {'method': 'get_defects_by_checker_category', 'kwargs': {'fetch_all': True}},
        'defects_by_checker_name': {'method': 'get_defects_by_checker_name', 'kwargs': {'fetch_all': True}},
        'defect_density_by_project': {'method': 'get_defect_density_by_project'},
        'file_hotspots': {'method': 'get_file_hotspots', 'kwargs': {'fetch_all': True}},
        'code_metrics_by_stream': {'method': 'get_code_metrics_by_stream'},
        'function_complexity_distribution': {'method': 'get_function_complexity_distribution'},
        
        # Performance & System Metrics
        'database_statistics': {'method': 'get_database_statistics'},
        'instance_info': {'method': 'get_instance_info'},
        'analysis_versions': {'method': 'get_analysis_versions', 'kwargs': {'limit': 100, 'days': days}},
        'largest_tables': {'method': 'get_largest_tables', 'kwargs': {'limit': 100}},
        'snapshot_performance': {'method': 'get_snapshot_performance', 'kwargs': {'limit': 100}},
        'commit_time_statistics': {'method': 'get_commit_time_statistics'},
        'commit_activity_patterns': {'method': 'get_commit_activity_patterns'},
        'defect_discovery_rate': {'method': 'get_defect_discovery_rate', 'kwargs': {'days': days}},
        
        # Trend Metrics
        'defect_trends': {'method': 'get_defect_trends', 'kwargs': {'days': days, 'granularity': 'auto'}},
        'triage_trends': {'method': 'get_triage_trends', 'kwargs': {'days': days, 'granularity': 'auto'}},
        'fix_rate_metrics': {'method': 'get_fix_rate_metrics', 'kwargs': {'days': days}},
        'defect_aging_distribution': {'method': 'get_defect_aging_distribution'},
        'triage_progress_summary': {'method': 'get_triage_progress_summary'},
        'defect_velocity_trend': {'method': 'get_defect_velocity_trend', 'kwargs': {'days': days}},
        'cumulative_defect_trend': {'method': 'get_cumulative_defect_trend', 'kwargs': {'days': days}},
        'scan_activity_trend': {'method': 'get_scan_activity_trend', 'kwargs': {'days': days, 'granularity': 'week'}},
        'defect_trend_summary': {'method': 'get_defect_trend_summary', 'kwargs': {'days': days}},
        'technical_debt_summary': {'method': 'get_technical_debt_summary'},
        
        # Leaderboard Metrics
        'top_projects_by_fix_rate': {'method': 'get_top_projects_by_fix_rate', 'kwargs': {'days': days, 'limit': 100}},

        'top_projects_by_triage_activity': {'method': 'get_top_projects_by_triage_activity', 'kwargs': {'days': days, 'limit': 100}},
        'top_users_by_fixes': {'method': 'get_top_users_by_fixes', 'kwargs': {'days': days, 'limit': 100}},
        'top_triagers': {'method': 'get_top_triagers', 'kwargs': {'days': days, 'limit': 100}},
        'most_collaborative_users': {'method': 'get_most_collaborative_users', 'kwargs': {'days': days, 'limit': 100}},
        
        # User Activity
        'user_license_statistics': {'method': 'get_user_license_statistics', 'kwargs': {'days': days}},

        # Classification Breakdown
        'checker_classification_breakdown': {'method': 'get_checker_classification_breakdown', 'kwargs': {'limit': 15}},
        'top_projects_by_classification': {'method': 'get_top_projects_by_classification', 'kwargs': {'limit': 10}},
    }

    if not include_leaderboards:
        for m in LEADERBOARD_METRICS:
            metrics_config.pop(m, None)
    if not include_snapshots:
        for m in SNAPSHOT_METRICS:
            metrics_config.pop(m, None)

    # Export each metric as JSON
    skipped = 0
    for metric_name, config in tqdm(metrics_config.items(), desc=f"  {instance_name}", unit="metric"):
        try:
            method_name = config['method']
            kwargs = config.get('kwargs', {})
            
            # Get the method from metrics object
            method = getattr(metrics, method_name)
            
            # Call the method with kwargs
            result = method(**kwargs)
            
            # Convert result to JSON-serializable format
            if isinstance(result, pd.DataFrame):
                if anonymizer is not None:
                    result = anonymizer.apply_to_dataframe(result, metric_name=metric_name, is_project_scope=single_project_context)
                # Convert DataFrame to list of dictionaries
                data = result.to_dict(orient='records')
            elif isinstance(result, dict):
                data = result
            elif isinstance(result, list):
                data = result
            else:
                skipped += 1
                if verbose:
                    tqdm.write(f"    [SKIP] {metric_name}: Unsupported type {type(result)}")
                continue
            
            # Export as JSON
            if data:
                filename = f"{metric_name}.json"
                filepath = os.path.join(instance_dir, filename)
                with open(filepath, 'w') as f:
                    json.dump(data, f, indent=2, default=json_serializer)
                
                exported_files[metric_name] = {
                    'filename': filename,
                    'format': 'json',
                    'record_count': len(data) if isinstance(data, list) else 1
                }
            else:
                skipped += 1
                if verbose:
                    tqdm.write(f"    [SKIP] {metric_name}: No data")
        
        except Exception as e:
            tqdm.write(f"    [ERROR] {metric_name}: {str(e)}")
    
    return exported_files, skipped


def export_project_specific_metrics(metrics, instance_name, project_dir, project_name, days=365, anonymizer=None, include_leaderboards=True, include_snapshots=True, verbose=False):
    """Export project-specific metrics (OWASP, CWE) for a single project

    Args:
        metrics: Shared CoverityMetrics instance. Its ``project_name`` is
            reassigned in-place so that all downstream queries are scoped to
            the given project. This avoids reconnecting to Postgres for
            every project in a large export.
        instance_name: Name of the instance (used only for messages)
        project_dir: Project-specific directory to save JSON files
        project_name: Name of the project
        days: Number of days for trend analysis
        anonymizer: Optional :class:`Anonymizer` used to swap real project/stream
            names for anonymized ids just before serialization.
        verbose: When True, log a per-metric ``[SKIP] ... No data`` line for
            every empty metric. When False (default), those lines are
            suppressed and the count is returned via the second tuple element.

    Returns:
        tuple: ``(exported_files, skipped_count)``.
    """
    # Reuse the shared connection — just re-scope the metrics object.
    metrics.project_name = project_name

    exported_files = {}
    
    # Export core project-specific metrics needed for dashboards
    project_metrics_config = {
        'overall_summary': {'method': 'get_overall_summary', 'kwargs': {'days': days}},
        'defects_by_severity': {'method': 'get_defects_by_severity'},
        'total_defects_by_project': {'method': 'get_total_defects_by_project'},
        'defects_by_checker_category': {'method': 'get_defects_by_checker_category', 'kwargs': {'fetch_all': True}},
        'defects_by_checker_name': {'method': 'get_defects_by_checker_name', 'kwargs': {'fetch_all': True}},
        'file_hotspots': {'method': 'get_file_hotspots', 'kwargs': {'fetch_all': True}},
        'code_metrics_by_stream': {'method': 'get_code_metrics_by_stream'},
        'function_complexity_distribution': {'method': 'get_function_complexity_distribution'},
        'defect_density_by_project': {'method': 'get_defect_density_by_project'},
        'defect_trends': {'method': 'get_defect_trends', 'kwargs': {'days': days, 'granularity': 'auto'}},
        'triage_trends': {'method': 'get_triage_trends', 'kwargs': {'days': days, 'granularity': 'auto'}},
        'triage_progress_summary': {'method': 'get_triage_progress_summary'},
        'defect_trend_summary': {'method': 'get_defect_trend_summary', 'kwargs': {'days': days}},
        'fix_rate_metrics': {'method': 'get_fix_rate_metrics', 'kwargs': {'days': days}},
        'defect_aging_distribution': {'method': 'get_defect_aging_distribution'},
        'technical_debt_summary': {'method': 'get_technical_debt_summary'},
        'checker_classification_breakdown': {'method': 'get_checker_classification_breakdown', 'kwargs': {'limit': 15}},
        'top_projects_by_classification': {'method': 'get_top_projects_by_classification', 'kwargs': {'limit': 10}},
        
        # Snapshot and performance metrics (project-specific)
        'analysis_versions': {'method': 'get_analysis_versions', 'kwargs': {'limit': 100, 'days': days}},
        'snapshot_performance': {'method': 'get_snapshot_performance', 'kwargs': {'limit': 100}},
        'snapshot_commands': {'method': 'get_snapshot_commands', 'kwargs': {'limit': 20}},
        'commit_time_statistics': {'method': 'get_commit_time_statistics'},
        'commit_activity_patterns': {'method': 'get_commit_activity_patterns'},
        'defect_discovery_rate': {'method': 'get_defect_discovery_rate', 'kwargs': {'days': days}},
        'defect_velocity_trend': {'method': 'get_defect_velocity_trend', 'kwargs': {'days': days}},
        'cumulative_defect_trend': {'method': 'get_cumulative_defect_trend', 'kwargs': {'days': days}},
        'scan_activity_trend': {'method': 'get_scan_activity_trend', 'kwargs': {'days': days, 'granularity': 'day'}},

        # Per-project user leaderboards (scoped by metrics.project_name)
        'top_users_by_fixes': {'method': 'get_top_users_by_fixes', 'kwargs': {'days': days, 'limit': 100}},
        'top_triagers': {'method': 'get_top_triagers', 'kwargs': {'days': days, 'limit': 100}},
        'most_collaborative_users': {'method': 'get_most_collaborative_users', 'kwargs': {'days': days, 'limit': 100}},
    }

    if not include_leaderboards:
        for m in LEADERBOARD_METRICS:
            project_metrics_config.pop(m, None)
    if not include_snapshots:
        for m in SNAPSHOT_METRICS:
            project_metrics_config.pop(m, None)

    # Export each project metric
    skipped = 0
    for metric_name, config in project_metrics_config.items():
        try:
            method_name = config['method']
            kwargs = config.get('kwargs', {})
            
            # Get the method from metrics object
            method = getattr(metrics, method_name)
            
            # Call the method with kwargs
            result = method(**kwargs)
            
            # Convert result to JSON-serializable format
            if isinstance(result, pd.DataFrame):
                if anonymizer is not None:
                    result = anonymizer.apply_to_dataframe(result, metric_name=metric_name, is_project_scope=True)
                data = result.to_dict(orient='records')
            elif isinstance(result, dict):
                data = result
            elif isinstance(result, list):
                data = result
            else:
                skipped += 1
                if verbose:
                    tqdm.write(f"    [SKIP] {project_name}/{metric_name}: unsupported type {type(result).__name__}")
                continue
            
            # Export as JSON if data exists
            if data:
                filename = f"{metric_name}.json"
                filepath = os.path.join(project_dir, filename)
                with open(filepath, 'w') as f:
                    json.dump(data, f, indent=2, default=json_serializer)
                
                exported_files[metric_name] = {
                    'filename': filename,
                    'format': 'json',
                    'record_count': len(data) if isinstance(data, list) else 1
                }
            else:
                skipped += 1
                if verbose:
                    tqdm.write(f"    [SKIP] {project_name}/{metric_name}: No data")
        except Exception as e:
            tqdm.write(f"    [ERROR] {project_name}/{metric_name}: {e}")
    
    # OWASP Top 10 Metrics
    try:
        owasp_metrics = metrics.get_owasp_top10_metrics()
        if not owasp_metrics.empty:
            if anonymizer is not None:
                owasp_metrics = anonymizer.apply_to_dataframe(owasp_metrics, metric_name='owasp_top10_metrics', is_project_scope=True)
            filename = "owasp_top10_metrics.json"
            filepath = os.path.join(project_dir, filename)
            data = owasp_metrics.to_dict(orient='records')
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2, default=json_serializer)
            exported_files['owasp_top10_metrics'] = {
                'filename': filename,
                'format': 'json',
                'record_count': len(data)
            }
            
            # Export OWASP details for each category
            for _, row in owasp_metrics.iterrows():
                if row.get('total_defects', 0) > 0:
                    category_id = row['category']
                    details = metrics.get_owasp_category_details(category_id)
                    if details:
                        safe_category_id = category_id.replace(':', '_')
                        detail_filename = f"owasp_{safe_category_id}_details.json"
                        detail_filepath = os.path.join(project_dir, detail_filename)
                        with open(detail_filepath, 'w', encoding='utf-8') as f:
                            json.dump(details, f, indent=2, default=json_serializer)
    except Exception as e:
        tqdm.write(f"    [WARNING] OWASP metrics failed for {project_name}: {str(e)}")
    
    # CWE Top 25 Metrics
    try:
        cwe_metrics = metrics.get_cwe_top25_metrics()
        if not cwe_metrics.empty:
            if anonymizer is not None:
                cwe_metrics = anonymizer.apply_to_dataframe(cwe_metrics, metric_name='cwe_top25_metrics', is_project_scope=True)
            filename = "cwe_top25_metrics.json"
            filepath = os.path.join(project_dir, filename)
            data = cwe_metrics.to_dict(orient='records')
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2, default=json_serializer)
            exported_files['cwe_top25_metrics'] = {
                'filename': filename,
                'format': 'json',
                'record_count': len(data)
            }
            
            # Export CWE details for each weakness
            for _, row in cwe_metrics.iterrows():
                if row.get('total_defects', 0) > 0:
                    cwe_id = row['cwe_id']
                    details = metrics.get_cwe_top25_details(cwe_id)
                    if details:
                        detail_filename = f"cwe_{cwe_id}_details.json"
                        detail_filepath = os.path.join(project_dir, detail_filename)
                        with open(detail_filepath, 'w') as f:
                            json.dump(details, f, indent=2, default=json_serializer)
    except Exception as e:
        tqdm.write(f"    [WARNING] CWE metrics failed for {project_name}: {str(e)}")
    
    return exported_files, skipped


def export_to_json(output_dir="exports", days=365, config_file=None, projects_filter=None, workers=1,
                   anonymize=False, mapping_file=None, include_leaderboards=True, include_snapshots=True,
                   verbose=False):
    """Export all metrics to JSON files with multi-instance support

    Creates a separate ZIP file for each configured instance

    Args:
        output_dir: Directory for exports
        days: Number of days for trend analysis
        config_file: Path to configuration file
        projects_filter: Optional list of project names to restrict export
        workers: Number of parallel workers per instance for per-project export
            (each worker uses its own Postgres connection).
        anonymize: When True, replace real project and stream names in the ZIP
            with sequential ``project_NNN`` / ``stream_NNN`` ids and write the
            reverse mapping to a sibling ``.mapping.json`` file (or to
            ``mapping_file`` if supplied). The mapping file is intended to stay
            private; the ZIP itself becomes safely shareable.
        mapping_file: Optional path to a mapping JSON. If it exists it is
            loaded so ids stay stable across re-exports; regardless of whether
            it existed, the (extended) mapping is written back to this path.
            Only used when ``anonymize`` is True.

    Returns:
        list: List of paths to created ZIP files (one per instance)
    """
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    print(f"\nCoverity Metrics Export Utility")
    print("=" * 80)
    print(f"Output directory: {output_dir}/")
    print(f"Trend analysis period: {days} days")
    
    # Load configuration (config file, environment variables, or default config.json)
    config_data, enabled_instances = resolve_config(config_file)
    
    print(f"Instances to export: {len(enabled_instances)}")
    for inst in enabled_instances:
        print(f"  - {inst['name']}")
    if projects_filter:
        print(f"Project filter: {', '.join(projects_filter)}") 
    
    zip_files = []

    # Aggregate skip counts across every instance/project for the end-of-run summary.
    total_skipped_metrics = 0
    projects_with_skipped = 0
    
    # Export metrics for each instance separately
    for instance in enabled_instances:
        instance_name = instance['name']
        sanitized_name = instance_name.replace(' ', '_').replace('/', '_').replace('\\', '_')
        instance_t0 = time.perf_counter()

        print(f"\n{'=' * 80}")
        print(f"Processing instance: {instance_name}")
        print(f"{'=' * 80}")
        
        # Create temporary directory for this instance
        temp_dir = os.path.join(output_dir, f"temp_{sanitized_name}_{timestamp}")
        os.makedirs(temp_dir, exist_ok=True)
        
        # Create instance directory within temp
        instance_dir = os.path.join(temp_dir, instance_name)
        os.makedirs(instance_dir, exist_ok=True)
        
        connection_params = {
            'host': instance['database']['host'],
            'port': instance['database']['port'],
            'database': instance['database']['database'],
            'user': instance['database']['user'],
            'password': instance['database']['password']
        }
        
        # Metadata for this instance's ZIP file
        metadata = {
            'export_timestamp': timestamp,
            'export_date': datetime.now().isoformat(),
            'days': days,
            'format': 'json',
            'instances': {},
            'config_snapshot': {
                'instance_count': 1,
                'instance_names': [instance_name]
            }
        }
        
        # Set up per-instance anonymizer (one mapping file per ZIP).
        anonymizer = None
        instance_mapping_path = None
        if anonymize:
            anonymizer = Anonymizer.load_or_new(mapping_file)
            anonymizer.set_instance(instance_name)

        # Export instance-level metrics
        exported_files, instance_skipped = export_instance_to_json(
            instance_name, 
            connection_params, 
            instance_dir,
            days,
            projects_filter=projects_filter,
            anonymizer=anonymizer,
            include_leaderboards=include_leaderboards,
            include_snapshots=include_snapshots,
            verbose=verbose,
        )
        total_skipped_metrics += instance_skipped
        
        metadata['instances'][instance_name] = {
            'exported_files': exported_files,
            'host': instance['database']['host'],
            'database': instance['database']['database']
        }
        
        # Get available projects and export project-specific metrics.
        # Reuse a single CoverityMetrics (and therefore a single Postgres
        # connection) across all projects in this instance to avoid ~645
        # redundant connect/auth round-trips on large deployments. When
        # ``workers > 1`` we open one such instance per worker.
        shared_metrics = None
        worker_pool = None
        try:
            shared_metrics = CoverityMetrics(connection_params=connection_params)
            if projects_filter:
                projects = projects_filter
            else:
                projects_df = shared_metrics.get_available_projects()
                projects = projects_df['project_name'].tolist() if not projects_df.empty else []

            # Map real project names to anonymized ids up front so directory names,
            # metadata keys and downstream logging stay consistent.
            if anonymizer is not None:
                anon_project_map = anonymizer.preload_projects(projects)
            else:
                anon_project_map = {p: p for p in projects}

            metadata['instances'][instance_name]['projects'] = [anon_project_map[p] for p in projects]

            # Pre-create the project directories on the main thread so worker
            # threads don't race on os.makedirs.
            project_dirs = {}
            for project_name in projects:
                pdir = os.path.join(instance_dir, anon_project_map[project_name])
                os.makedirs(pdir, exist_ok=True)
                project_dirs[project_name] = pdir

            effective_workers = 1 if not projects else max(1, min(workers, len(projects), 8))
            print(f"\n[{instance_name}] Exporting project-specific metrics for {len(projects)} projects (workers={effective_workers})...")

            project_specific = metadata['instances'][instance_name].setdefault('project_specific_exports', {})

            if effective_workers == 1:
                # Sequential path — one shared metrics instance for all projects.
                for project_name in tqdm(projects, desc=f"  {instance_name} Projects", unit="project"):
                    try:
                        project_files, proj_skipped = export_project_specific_metrics(
                            shared_metrics,
                            instance_name,
                            project_dirs[project_name],
                            project_name,
                            days,
                            anonymizer=anonymizer,
                            include_leaderboards=include_leaderboards,
                            include_snapshots=include_snapshots,
                            verbose=verbose,
                        )
                        if project_files:
                            project_specific[anon_project_map[project_name]] = project_files
                        total_skipped_metrics += proj_skipped
                        if proj_skipped > 0:
                            projects_with_skipped += 1
                    except Exception as exc:
                        tqdm.write(f"  [ERROR] {project_name}: {exc}")
            else:
                # Parallel path — each worker owns its own CoverityMetrics
                # instance (psycopg2 connections aren't thread-safe).
                from concurrent.futures import ThreadPoolExecutor, as_completed
                from queue import Queue

                worker_pool = Queue()
                # Reuse the shared_metrics as one of the workers.
                worker_pool.put(shared_metrics)
                for _ in range(effective_workers - 1):
                    worker_pool.put(CoverityMetrics(connection_params=connection_params))

                def _process(project_name):
                    m = worker_pool.get()
                    try:
                        pf, ps = export_project_specific_metrics(
                            m,
                            instance_name,
                            project_dirs[project_name],
                            project_name,
                            days,
                            anonymizer=anonymizer,
                            include_leaderboards=include_leaderboards,
                            include_snapshots=include_snapshots,
                            verbose=verbose,
                        )
                        return project_name, pf, ps
                    finally:
                        worker_pool.put(m)

                executor = ThreadPoolExecutor(max_workers=effective_workers)
                try:
                    futures = [executor.submit(_process, p) for p in projects]
                    try:
                        for future in tqdm(as_completed(futures), total=len(futures),
                                            desc=f"  {instance_name} Projects", unit="project"):
                            try:
                                project_name, project_files, proj_skipped = future.result()
                                if project_files:
                                    project_specific[anon_project_map[project_name]] = project_files
                                total_skipped_metrics += proj_skipped
                                if proj_skipped > 0:
                                    projects_with_skipped += 1
                            except Exception as exc:
                                tqdm.write(f"  [ERROR] {exc}")
                    except KeyboardInterrupt:
                        tqdm.write("\n[INTERRUPTED] Cancelling pending exports (in-flight ones will still finish)...")
                        for f in futures:
                            f.cancel()
                        executor.shutdown(wait=False, cancel_futures=True)
                        raise
                finally:
                    executor.shutdown(wait=True)

        except Exception as e:
            tqdm.write(f"[WARNING] Failed to export project-specific metrics for {instance_name}: {str(e)}")
        finally:
            if shared_metrics is not None:
                try:
                    shared_metrics.db.close()
                except Exception:
                    pass
            # Close any extra worker connections created for parallel mode.
            if worker_pool is not None:
                while not worker_pool.empty():
                    try:
                        m = worker_pool.get_nowait()
                        if m is not shared_metrics:
                            try:
                                m.db.close()
                            except Exception:
                                pass
                    except Exception:
                        break
        
        # Save metadata
        metadata_file = os.path.join(temp_dir, 'metadata.json')
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        print(f"\n[OK] Metadata saved for {instance_name}")
        
        # Create ZIP file for this instance
        zip_filename = f"coverity_export_{sanitized_name}_{timestamp}.zip"
        zip_path = os.path.join(output_dir, zip_filename)
        
        print(f"\nCreating ZIP archive: {zip_filename}")
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Add all JSON files and metadata
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, temp_dir)
                    zipf.write(file_path, arcname)
        
        # Clean up temporary directory for this instance
        import shutil
        shutil.rmtree(temp_dir)

        # Write (or refresh) the sibling anonymization mapping.
        if anonymizer is not None:
            instance_mapping_path = mapping_file or default_mapping_path(zip_path)
            anonymizer.save(instance_mapping_path)
            print(f"[OK] Anonymization mapping written: {os.path.basename(instance_mapping_path)}")
            print(f"     Keep this file private \u2014 it maps anonymized ids back to real names.")

        zip_size_mb = os.path.getsize(zip_path) / 1024 / 1024
        instance_elapsed = time.perf_counter() - instance_t0
        project_count = len(metadata['instances'][instance_name].get('projects', []) or [])
        per_project = (instance_elapsed / project_count) if project_count > 0 else None
        print(f"[OK] {instance_name} export completed")
        print(f"     ZIP file: {zip_filename}")
        print(f"     Size: {zip_size_mb:.2f} MB")
        if per_project is not None:
            print(f"     Time: {_format_duration(instance_elapsed)} for {project_count} projects (~{per_project:.2f}s/project)")
        else:
            print(f"     Time: {_format_duration(instance_elapsed)}")

        zip_files.append(zip_path)
    
    print(f"\n{'=' * 80}")
    print(f"[SUCCESS] All exports completed!")
    print(f"Total ZIP files created: {len(zip_files)}")
    for zip_path in zip_files:
        print(f"  - {os.path.basename(zip_path)}")
    if total_skipped_metrics > 0 and not verbose:
        print(f"[INFO] Skipped {total_skipped_metrics} metrics with no data across {projects_with_skipped} project(s). Pass --verbose to see per-metric details.")
    elif total_skipped_metrics > 0 and verbose:
        print(f"[INFO] Total metrics skipped with no data: {total_skipped_metrics} across {projects_with_skipped} project(s).")
    print(f"{'=' * 80}")
    
    return zip_files

def main():
    """Main function"""

    parser = argparse.ArgumentParser(description='Export Coverity metrics to JSON and ZIP (separate file per instance)')
    parser.add_argument('--output', '-o', default='exports', help='Output directory (default: exports)')
    parser.add_argument('--days', '-d', type=int, default=365, help='Number of days for trend analysis (default: 365)')
    parser.add_argument('--config', '-c', default=None,
                        help=(
                            'Path to configuration file. If omitted, the following are tried in order: '
                            'the environment variables COVERITY_DB_HOST / COVERITY_DB_NAME / COVERITY_DB_USER / COVERITY_DB_PASSWORD '
                            '(optional: COVERITY_DB_PORT, COVERITY_INSTANCE_NAME), then a config.json in the current directory.'
                        ))
    parser.add_argument('--project', '-p', type=str, default=None, help='Comma-separated list of project names to export (default: all projects)')
    parser.add_argument('--workers', '-w', type=int, default=1,
                        help='Number of parallel workers for per-project export (default: 1, capped at 8). Each worker uses its own Postgres connection.')
    parser.add_argument('--anonymize', action='store_true',
                        help='Replace real project and stream names in the ZIP with sequential project_NNN/stream_NNN ids and write a sibling <zip>.mapping.json file.')
    parser.add_argument('--mapping-file', type=str, default=None,
                        help='Path to an anonymization mapping JSON. If it exists it is loaded (so ids stay stable across re-exports); the (extended) mapping is written back to this path. Only used with --anonymize.')
    parser.add_argument('--no-leaderboards', action='store_true',
                        help='Skip the Leaderboards metrics (top projects by fix rate / triage, top users by fixes, top triagers, most collaborative users). Dashboards generated from the resulting ZIP will hide the Leaderboards tab.')
    parser.add_argument('--no-snapshots', action='store_true',
                        help='Skip the Snapshots metric (recorded cov-build/cov-analyze command lines, invoker, host). Dashboards generated from the resulting ZIP will hide the Snapshots tab.')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Show per-metric "[SKIP] project/metric: No data" lines. Off by default; a summary count is printed at the end of the run.')
    parser.add_argument('--version', action='store_true', help='Print version and exit')

    args = parser.parse_args()

    if args.project:
        args.project = [p.strip() for p in args.project.split(',') if p.strip()]

    if args.version:
        try:
            from coverity_metrics.__version__ import __version__
            print(f"coverity-metrics export version: {__version__}")
        except Exception:
            print("coverity-metrics export version: unknown")
        return 0

    t0 = time.perf_counter()
    try:
        workers = max(1, min(args.workers, 8))
        if workers != args.workers:
            print(f"[INFO] --workers clamped to {workers} (allowed range: 1..8)")
        if args.mapping_file and not args.anonymize:
            print("[INFO] --mapping-file ignored because --anonymize was not specified.")
        zip_files = export_to_json(
            output_dir=args.output,
            days=args.days,
            config_file=args.config,
            projects_filter=args.project if args.project else None,
            workers=workers,
            anonymize=args.anonymize,
            mapping_file=args.mapping_file,
            include_leaderboards=not args.no_leaderboards,
            include_snapshots=not args.no_snapshots,
            verbose=args.verbose,
        )
        # Note: export_to_json now returns a list of ZIP files (one per instance)
        return 0
    except KeyboardInterrupt:
        print("\n[INTERRUPTED] Aborted by user.")
        return 130
    except Exception as e:
        print(f"\n[ERROR] Export failed - {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        total_elapsed = time.perf_counter() - t0
        print(f"\nTotal execution time: {_format_duration(total_elapsed)}")

if __name__ == "__main__":
    main()

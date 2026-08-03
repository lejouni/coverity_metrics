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

def export_instance_to_json(instance_name, connection_params, instance_dir, days=365, projects_filter=None):
    """Export all metrics for a single instance to JSON files
    
    Args:
        instance_name: Name of the instance
        connection_params: Database connection parameters
        instance_dir: Instance-specific directory to save JSON files
        days: Number of days for trend analysis
        projects_filter: Optional list of project names to filter metrics
        
    Returns:
        dict: Metadata about exported files
    """
    print(f"\n[{instance_name}] Exporting metrics...")
    if projects_filter:
        print(f"  Project filter: {', '.join(projects_filter)}")
    
    metrics = CoverityMetrics(connection_params=connection_params, project_name=projects_filter if projects_filter else None)
    
    # Dictionary to store export metadata
    exported_files = {}
    
    # Define all metrics to export with their configurations
    metrics_config = {
        # Basic Metrics
        'available_projects': {'method': 'get_available_projects'},
        'overall_summary': {'method': 'get_overall_summary'},
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
        'top_projects_by_fix_rate': {'method': 'get_top_projects_by_fix_rate', 'kwargs': {'days': 30, 'limit': 100}},

        'top_projects_by_triage_activity': {'method': 'get_top_projects_by_triage_activity', 'kwargs': {'days': 30, 'limit': 100}},
        'top_users_by_fixes': {'method': 'get_top_users_by_fixes', 'kwargs': {'days': days, 'limit': 100}},
        'top_triagers': {'method': 'get_top_triagers', 'kwargs': {'days': 30, 'limit': 100}},
        'most_collaborative_users': {'method': 'get_most_collaborative_users', 'kwargs': {'days': 30, 'limit': 100}},
        
        # User Activity
        'user_license_statistics': {'method': 'get_user_license_statistics', 'kwargs': {'days': days}},

        # Classification Breakdown
        'checker_classification_breakdown': {'method': 'get_checker_classification_breakdown', 'kwargs': {'limit': 15}},
        'top_projects_by_classification': {'method': 'get_top_projects_by_classification', 'kwargs': {'limit': 10}},
    }
    
    # Export each metric as JSON
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
                # Convert DataFrame to list of dictionaries
                data = result.to_dict(orient='records')
            elif isinstance(result, dict):
                data = result
            elif isinstance(result, list):
                data = result
            else:
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
                tqdm.write(f"    [SKIP] {metric_name}: No data")
        
        except Exception as e:
            tqdm.write(f"    [ERROR] {metric_name}: {str(e)}")
    
    return exported_files


def export_project_specific_metrics(metrics, instance_name, project_dir, project_name, days=365):
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

    Returns:
        dict: Metadata about exported files
    """
    # Reuse the shared connection — just re-scope the metrics object.
    metrics.project_name = project_name

    exported_files = {}
    
    # Export core project-specific metrics needed for dashboards
    project_metrics_config = {
        'overall_summary': {'method': 'get_overall_summary'},
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
        'commit_time_statistics': {'method': 'get_commit_time_statistics'},
        'commit_activity_patterns': {'method': 'get_commit_activity_patterns'},
        'defect_discovery_rate': {'method': 'get_defect_discovery_rate', 'kwargs': {'days': days}},
        'defect_velocity_trend': {'method': 'get_defect_velocity_trend', 'kwargs': {'days': days}},
        'cumulative_defect_trend': {'method': 'get_cumulative_defect_trend', 'kwargs': {'days': days}},
        'scan_activity_trend': {'method': 'get_scan_activity_trend', 'kwargs': {'days': days, 'granularity': 'day'}},
    }
    
    # Export each project metric
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
                data = result.to_dict(orient='records')
            elif isinstance(result, dict):
                data = result
            elif isinstance(result, list):
                data = result
            else:
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
        except Exception as e:
            # Silently skip metrics that fail - they may not be applicable for all projects
            pass
    
    # OWASP Top 10 Metrics
    try:
        owasp_metrics = metrics.get_owasp_top10_metrics()
        if not owasp_metrics.empty:
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
    
    return exported_files


def export_to_json(output_dir="exports", days=365, config_file='config.json', projects_filter=None, workers=1):
    """Export all metrics to JSON files with multi-instance support

    Creates a separate ZIP file for each configured instance

    Args:
        output_dir: Directory for exports
        days: Number of days for trend analysis
        config_file: Path to configuration file
        projects_filter: Optional list of project names to restrict export
        workers: Number of parallel workers per instance for per-project export
            (each worker uses its own Postgres connection).

    Returns:
        list: List of paths to created ZIP files (one per instance)
    """
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    print(f"\nCoverity Metrics Export Utility")
    print("=" * 80)
    print(f"Output directory: {output_dir}/")
    print(f"Trend analysis period: {days} days")
    
    # Load configuration
    config_data, enabled_instances = load_config(config_file)
    
    print(f"Instances to export: {len(enabled_instances)}")
    for inst in enabled_instances:
        print(f"  - {inst['name']}")
    if projects_filter:
        print(f"Project filter: {', '.join(projects_filter)}") 
    
    zip_files = []
    
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
        
        # Export instance-level metrics
        exported_files = export_instance_to_json(
            instance_name, 
            connection_params, 
            instance_dir,
            days,
            projects_filter=projects_filter
        )
        
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

            metadata['instances'][instance_name]['projects'] = projects

            # Pre-create the project directories on the main thread so worker
            # threads don't race on os.makedirs.
            project_dirs = {}
            for project_name in projects:
                pdir = os.path.join(instance_dir, project_name)
                os.makedirs(pdir, exist_ok=True)
                project_dirs[project_name] = pdir

            effective_workers = 1 if not projects else max(1, min(workers, len(projects), 8))
            print(f"\n[{instance_name}] Exporting project-specific metrics for {len(projects)} projects (workers={effective_workers})...")

            project_specific = metadata['instances'][instance_name].setdefault('project_specific_exports', {})

            if effective_workers == 1:
                # Sequential path — one shared metrics instance for all projects.
                for project_name in tqdm(projects, desc=f"  {instance_name} Projects", unit="project"):
                    try:
                        project_files = export_project_specific_metrics(
                            shared_metrics,
                            instance_name,
                            project_dirs[project_name],
                            project_name,
                            days,
                        )
                        if project_files:
                            project_specific[project_name] = project_files
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
                        return project_name, export_project_specific_metrics(
                            m,
                            instance_name,
                            project_dirs[project_name],
                            project_name,
                            days,
                        )
                    finally:
                        worker_pool.put(m)

                executor = ThreadPoolExecutor(max_workers=effective_workers)
                try:
                    futures = [executor.submit(_process, p) for p in projects]
                    try:
                        for future in tqdm(as_completed(futures), total=len(futures),
                                            desc=f"  {instance_name} Projects", unit="project"):
                            try:
                                project_name, project_files = future.result()
                                if project_files:
                                    project_specific[project_name] = project_files
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
    print(f"{'=' * 80}")
    
    return zip_files

def main():
    """Main function"""

    parser = argparse.ArgumentParser(description='Export Coverity metrics to JSON and ZIP (separate file per instance)')
    parser.add_argument('--output', '-o', default='exports', help='Output directory (default: exports)')
    parser.add_argument('--days', '-d', type=int, default=365, help='Number of days for trend analysis (default: 365)')
    parser.add_argument('--config', '-c', default='config.json', help='Path to configuration file (default: config.json)')
    parser.add_argument('--project', '-p', type=str, default=None, help='Comma-separated list of project names to export (default: all projects)')
    parser.add_argument('--workers', '-w', type=int, default=1,
                        help='Number of parallel workers for per-project export (default: 1, capped at 8). Each worker uses its own Postgres connection.')
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
        zip_files = export_to_json(
            output_dir=args.output,
            days=args.days,
            config_file=args.config,
            projects_filter=args.project if args.project else None,
            workers=workers,
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

"""
Coverity Metrics - Main Application
Generates comprehensive metrics reports from Coverity database
"""
import sys
import json
import os
from datetime import datetime
from coverity_metrics.metrics import CoverityMetrics
from coverity_metrics.zip_data_loader import ZipDataLoader

def load_all_instances(config_file='config.json'):
    """Load all enabled instances from config.json
    
    Returns:
        list: List of dicts with 'name' and 'connection_params' keys
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
        
        result = []
        for inst in enabled_instances:
            result.append({
                'name': inst['name'],
                'connection_params': {
                    'host': inst['database']['host'],
                    'port': inst['database']['port'],
                    'database': inst['database']['database'],
                    'user': inst['database']['user'],
                    'password': inst['database']['password']
                }
            })
        return result
        
    except Exception as e:
        print(f"ERROR: Failed to load configuration: {str(e)}")
        sys.exit(1)

def print_section(title):
    """Print a formatted section header"""
    print(f"\n{'=' * 80}")
    print(f"  {title}")
    print(f"{'=' * 80}\n")

def print_dataframe(df, title=None, max_rows=20):
    """Print a pandas DataFrame with formatting"""
    if title:
        print(f"\n{title}:")
        print("-" * 80)
    
    if df.empty:
        print("  No data available")
    else:
        print(df.to_string(index=False, max_rows=max_rows))
    print()

def generate_instance_report(instance_name, metrics_instance=None, connection_params=None):
    """Generate a metrics report for a single instance"""
    if metrics_instance is not None:
        metrics = metrics_instance
    else:
        metrics = CoverityMetrics(connection_params=connection_params)

    # ========== SUMMARY ==========
    print_section("OVERALL SUMMARY")
    summary = metrics.get_overall_summary()
    for key, value in summary.items():
        print(f"  {key.replace('_', ' ').title()}: {value:,}")

    # ========== DEFECT METRICS ==========
    print_section("DEFECT METRICS")

    df = metrics.get_total_defects_by_project()
    print_dataframe(df, "Defects by Project")

    df = metrics.get_defects_by_severity()
    print_dataframe(df, "Defects by Severity")

    df = metrics.get_defects_by_checker_category(limit=15)
    print_dataframe(df, "Top 15 Defect Categories")

    df = metrics.get_defects_by_checker_name(limit=15)
    print_dataframe(df, "Top 15 Defect Checkers")

    df = metrics.get_defect_density_by_project()
    print_dataframe(df, "Defect Density by Project/Stream")

    df = metrics.get_file_hotspots(limit=15)
    print_dataframe(df, "Top 15 File Hotspots (Most Defects)")

    # ========== TRIAGE METRICS ==========
    print_section("TRIAGE METRICS")

    df = metrics.get_defects_by_triage_status()
    print_dataframe(df, "Defects by Triage Action")

    df = metrics.get_defects_by_classification()
    print_dataframe(df, "Defects by Classification")

    df = metrics.get_defects_by_owner(limit=15)
    print_dataframe(df, "Defects by Owner (Top 15)")

    # ========== CODE QUALITY METRICS ==========
    print_section("CODE QUALITY METRICS")

    df = metrics.get_code_metrics_by_stream()
    print_dataframe(df, "Code Metrics by Stream")

    df = metrics.get_function_complexity_distribution()
    print_dataframe(df, "Function Complexity Distribution")

    df = metrics.get_most_complex_functions(limit=15)
    print_dataframe(df, "Top 15 Most Complex Functions")

    # ========== SNAPSHOT HISTORY ==========
    print_section("SNAPSHOT HISTORY")

    df = metrics.get_snapshot_history(limit=10)
    print_dataframe(df, "Recent Snapshots (Last 10)")

    # ========== TREND METRICS ==========
    print_section("TREND METRICS")

    df = metrics.get_defect_trend_weekly(weeks=12)
    print_dataframe(df, "Weekly Defect Trend (Last 12 Weeks)")

    df = metrics.get_file_count_trend_weekly(weeks=12)
    print_dataframe(df, "Weekly File Count Trend (Last 12 Weeks)")

    # ========== USER ACTIVITY ==========
    print_section("USER ACTIVITY METRICS")

    df = metrics.get_user_login_statistics(days=30)
    print_dataframe(df, "User Login Statistics (Last 30 Days)")

    df = metrics.get_most_active_triagers(days=30, limit=10)
    print_dataframe(df, "Most Active Triagers (Last 30 Days)")


def generate_full_report():
    """Generate a comprehensive metrics report for all enabled instances"""
    print("\n" + "=" * 80)
    print("  COVERITY METRICS REPORT")
    print(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    instances = load_all_instances()
    print(f"  Instances: {len(instances)}")

    for inst in instances:
        instance_name = inst['name']
        connection_params = inst['connection_params']

        print("\n" + "#" * 80)
        print(f"#  INSTANCE: {instance_name}")
        print("#" * 80)

        try:
            generate_instance_report(instance_name, connection_params=connection_params)
        except Exception as e:
            print(f"\nERROR: Failed to generate report for instance '{instance_name}'")
            print(f"  {str(e)}")
            import traceback
            traceback.print_exc()
            continue

    print("\n" + "=" * 80)
    print("  Report generation completed successfully")
    print("=" * 80 + "\n")

def generate_full_report_from_zips(zip_files):
    """Generate a comprehensive metrics report from one or more ZIP export files"""
    print("\n" + "=" * 80)
    print("  COVERITY METRICS REPORT (ZIP)")
    print(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    for zip_file in zip_files:
        if not os.path.exists(zip_file):
            print(f"ERROR: ZIP file not found: {zip_file}")
            continue

        print(f"\nLoading: {zip_file}")
        loader = ZipDataLoader(zip_file)
        metadata = loader.get_metadata()
        print(f"  Export date: {metadata.get('export_date', 'Unknown')}")
        print(f"  Trend period: {metadata.get('days', 'Unknown')} days")

        available_instances = loader.list_available_instances()
        if not available_instances:
            print("  [WARNING] No instances found in ZIP file, skipping")
            continue

        print(f"  Instances: {', '.join(available_instances)}")

        for instance_name in available_instances:
            loader.instance_name = instance_name
            loader.project_name = None

            print("\n" + "#" * 80)
            print(f"#  INSTANCE: {instance_name}  [{os.path.basename(zip_file)}]")
            print("#" * 80)

            try:
                generate_instance_report(instance_name, metrics_instance=loader)
            except Exception as e:
                print(f"\nERROR: Failed to generate report for instance '{instance_name}'")
                print(f"  {str(e)}")
                import traceback
                traceback.print_exc()
                continue

    print("\n" + "=" * 80)
    print("  Report generation completed successfully")
    print("=" * 80 + "\n")


def main():
    """Main entry point"""
    import argparse
    parser = argparse.ArgumentParser(description="Coverity Metrics Tool")
    parser.add_argument('--version', action='store_true', help='Print version and exit')
    parser.add_argument('--zip-file', '-z', type=str, nargs='+',
                        help='Read metrics from exported ZIP file(s) instead of database')
    parser.add_argument('--config', '-c', type=str, default='config.json',
                        help='Path to configuration file (default: config.json)')
    args, unknown = parser.parse_known_args()

    if args.version:
        try:
            from coverity_metrics.__version__ import __version__
            print(f"coverity-metrics version: {__version__}")
        except Exception:
            print("coverity-metrics version: unknown")
        return

    print("\nCoverity Metrics Tool")
    print("=" * 80)

    if args.zip_file:
        generate_full_report_from_zips(args.zip_file)
    else:
        generate_full_report()

if __name__ == "__main__":
    main()

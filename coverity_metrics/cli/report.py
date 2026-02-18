"""
Coverity Metrics - Main Application
Generates comprehensive metrics reports from Coverity database
"""
import sys
import json
import os
from datetime import datetime
from coverity_metrics.metrics import CoverityMetrics
from coverity_metrics.db_connection import CoverityDatabase

def load_connection_params(config_file='config.json'):
    """Load database connection parameters from config.json
    
    Returns:
        dict: Connection parameters for first enabled instance
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
        
        first_instance = enabled_instances[0]
        connection_params = {
            'host': first_instance['database']['host'],
            'port': first_instance['database']['port'],
            'database': first_instance['database']['database'],
            'user': first_instance['database']['user'],
            'password': first_instance['database']['password']
        }
        
        print(f"Using instance: {first_instance['name']}")
        return connection_params
        
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

def generate_full_report():
    """Generate a comprehensive metrics report"""
    print("\n" + "=" * 80)
    print("  COVERITY METRICS REPORT")
    print(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    try:
        # Load connection parameters from config.json
        connection_params = load_connection_params()
        
        # Initialize metrics calculator
        metrics = CoverityMetrics(connection_params=connection_params)
        
        # ========== SUMMARY ==========
        print_section("OVERALL SUMMARY")
        summary = metrics.get_overall_summary()
        for key, value in summary.items():
            print(f"  {key.replace('_', ' ').title()}: {value:,}")
        
        # ========== DEFECT METRICS ==========
        print_section("DEFECT METRICS")
        
        # Defects by project
        df = metrics.get_total_defects_by_project()
        print_dataframe(df, "Defects by Project")
        
        # Defects by severity
        df = metrics.get_defects_by_severity()
        print_dataframe(df, "Defects by Severity")
        
        # Defects by category
        df = metrics.get_defects_by_checker_category(limit=15)
        print_dataframe(df, "Top 15 Defect Categories")
        
        # Defects by checker
        df = metrics.get_defects_by_checker_name(limit=15)
        print_dataframe(df, "Top 15 Defect Checkers")
        
        # Defect density
        df = metrics.get_defect_density_by_project()
        print_dataframe(df, "Defect Density by Project/Stream")
        
        # File hotspots
        df = metrics.get_file_hotspots(limit=15)
        print_dataframe(df, "Top 15 File Hotspots (Most Defects)")
        
        # ========== TRIAGE METRICS ==========
        print_section("TRIAGE METRICS")
        
        # Triage status
        df = metrics.get_defects_by_triage_status()
        print_dataframe(df, "Defects by Triage Action")
        
        # Classification
        df = metrics.get_defects_by_classification()
        print_dataframe(df, "Defects by Classification")
        
        # Owners
        df = metrics.get_defects_by_owner(limit=15)
        print_dataframe(df, "Defects by Owner (Top 15)")
        
        # ========== CODE QUALITY METRICS ==========
        print_section("CODE QUALITY METRICS")
        
        # Code metrics by stream
        df = metrics.get_code_metrics_by_stream()
        print_dataframe(df, "Code Metrics by Stream")
        
        # Function complexity
        df = metrics.get_function_complexity_distribution()
        print_dataframe(df, "Function Complexity Distribution")
        
        # Most complex functions
        df = metrics.get_most_complex_functions(limit=15)
        print_dataframe(df, "Top 15 Most Complex Functions")
        
        # ========== SNAPSHOT HISTORY ==========
        print_section("SNAPSHOT HISTORY")
        
        df = metrics.get_snapshot_history(limit=10)
        print_dataframe(df, "Recent Snapshots (Last 10)")
        
        # ========== TREND METRICS ==========
        print_section("TREND METRICS")
        
        # Weekly defect trend
        df = metrics.get_defect_trend_weekly(weeks=12)
        print_dataframe(df, "Weekly Defect Trend (Last 12 Weeks)")
        
        # Weekly file count trend
        df = metrics.get_file_count_trend_weekly(weeks=12)
        print_dataframe(df, "Weekly File Count Trend (Last 12 Weeks)")
        
        # ========== USER ACTIVITY ==========
        print_section("USER ACTIVITY METRICS")
        
        # Login statistics
        df = metrics.get_user_login_statistics(days=30)
        print_dataframe(df, "User Login Statistics (Last 30 Days)")
        
        # Active triagers
        df = metrics.get_most_active_triagers(days=30, limit=10)
        print_dataframe(df, "Most Active Triagers (Last 30 Days)")
        
        print("\n" + "=" * 80)
        print("  Report generation completed successfully")
        print("=" * 80 + "\n")
        
    except Exception as e:
        print(f"\nERROR: Failed to generate report")
        print(f"  {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

def main():
    """Main entry point"""
    print("\nCoverity Metrics Tool")
    print("=" * 80)
    
    # Test database connection
    print("\nTesting database connection...")
    try:
        db = CoverityDatabase()
        db.connect()
        print("[OK] Database connection successful")
        db.close()
    except Exception as e:
        print(f"[ERROR] Database connection failed: {e}")
        sys.exit(1)
    
    # Generate full report
    generate_full_report()

if __name__ == "__main__":
    main()

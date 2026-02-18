"""
Coverity Metrics Export Utility
Export metrics to CSV, Excel, or JSON formats
"""
import os
import json
import sys
from datetime import datetime
from metrics import CoverityMetrics
import pandas as pd

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

def export_to_csv(output_dir="exports"):
    """Export all metrics to CSV files"""
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    print(f"\nExporting metrics to CSV files in '{output_dir}/'...")
    
    # Load connection parameters from config.json
    connection_params = load_connection_params()
    metrics = CoverityMetrics(connection_params=connection_params)
    
    exports = {
        'defects_by_project': metrics.get_total_defects_by_project(),
        'defects_by_severity': metrics.get_defects_by_severity(),
        'defects_by_category': metrics.get_defects_by_checker_category(limit=50),
        'defect_density': metrics.get_defect_density_by_project(),
        'file_hotspots': metrics.get_file_hotspots(limit=50),
        'triage_status': metrics.get_defects_by_triage_status(),
        'classification': metrics.get_defects_by_classification(),
        'code_metrics': metrics.get_code_metrics_by_stream(),
        'snapshot_history': metrics.get_snapshot_history(limit=50),
    }
    
    for name, df in exports.items():
        if not df.empty:
            filename = f"{output_dir}/{name}_{timestamp}.csv"
            df.to_csv(filename, index=False)
            print(f"  [OK] Exported {name}: {len(df)} rows -> {filename}")
        else:
            print(f"  [SKIP] {name}: No data")
    
    # Export summary
    summary = metrics.get_overall_summary()
    summary_df = pd.DataFrame([summary])
    summary_file = f"{output_dir}/summary_{timestamp}.csv"
    summary_df.to_csv(summary_file, index=False)
    print(f"  [OK] Exported summary -> {summary_file}")
    
    print(f"\nExport completed!\n")

def main():
    """Main function"""
    print("\nCoverity Metrics Export Utility")
    print("=" * 80)
    
    try:
        export_to_csv()
        print("Export completed successfully!")
    except Exception as e:
        print(f"\nERROR: Export failed - {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

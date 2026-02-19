"""
Coverity Metrics HTML Dashboard Generator
Creates a beautiful HTML dashboard using Jinja2 templates
Supports single-instance and multi-instance deployments
"""
import os
import sys
import argparse
import logging
import json
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from coverity_metrics.metrics import CoverityMetrics
import webbrowser
from tqdm import tqdm
from coverity_metrics.metrics_cache import MetricsCache, ProgressTracker, collect_metrics_with_cache

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def load_inline_css():
    """
    Load CSS content from static directory to embed inline in HTML
    
    Returns:
        str: CSS content to embed in HTML style tags
    """
    # Get the package directory (where this file is located)
    package_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    css_path = os.path.join(package_dir, 'static', 'css', 'dashboard.css')
    
    # Load CSS file content
    if os.path.exists(css_path):
        with open(css_path, 'r', encoding='utf-8') as f:
            return f.read()
    else:
        tqdm.write(f"  [WARNING] CSS file not found at {css_path}")
        return "/* CSS file not found */"


def detect_multi_instance_config(config_file='config.json'):
    """
    Detect if multi-instance configuration exists and has multiple instances
    
    Returns:
        tuple: (is_multi_instance, instance_count, config_data)
    """
    if not os.path.exists(config_file):
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

def generate_html_dashboard(output_file="output/dashboard.html", project_name=None, 
                           instance_name=None, metrics_instance=None, cache=None, use_cache=True, days=90):
    """Generate HTML dashboard with all metrics
    
    Args:
        output_file: Path to output HTML file
        project_name: Optional project name to filter metrics
        instance_name: Optional instance name for multi-instance mode
        metrics_instance: Optional CoverityMetrics instance (for multi-instance)
        cache: Optional MetricsCache instance for caching support
        use_cache: Whether to use cached data if available
        days: Number of days for trend analysis (default: 90)
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
            commit_stats = metrics_data.get('commit_stats', {})
            defect_discovery = metrics_data.get('defect_discovery', [])
            projects_list = metrics_data.get('all_projects', [])
            defect_trends = metrics_data.get('defect_trends', [])
            triage_trends = metrics_data.get('triage_trends', [])
            fix_rate_metrics = metrics_data.get('fix_rate_metrics', {})
            defect_aging = metrics_data.get('defect_aging', [])
            triage_summary = metrics_data.get('triage_summary', {})
            defect_velocity = metrics_data.get('defect_velocity', [])
            cumulative_trends = metrics_data.get('cumulative_trends', [])
            trend_summary = metrics_data.get('trend_summary', {})
            trend_period_text = metrics_data.get('trend_period_text', f'Last {days} Days')
            user_activity_stats = metrics_data.get('user_activity_stats', {})
            top_projects_by_fix_rate = metrics_data.get('top_projects_by_fix_rate', [])
            most_improved_projects = metrics_data.get('most_improved_projects', [])
            top_projects_by_triage = metrics_data.get('top_projects_by_triage', [])
            top_users_by_fixes = metrics_data.get('top_users_by_fixes', [])
            top_triagers = metrics_data.get('top_triagers', [])
            most_collaborative_users = metrics_data.get('most_collaborative_users', [])
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
            commit_stats = metrics_data['commit_stats']
            defect_discovery = metrics_data['defect_discovery']
            projects_list = metrics_data['all_projects']
            defect_trends = metrics_data.get('defect_trends', [])
            triage_trends = metrics_data.get('triage_trends', [])
            fix_rate_metrics = metrics_data.get('fix_rate_metrics', {})
            defect_aging = metrics_data.get('defect_aging', [])
            triage_summary = metrics_data.get('triage_summary', {})
            defect_velocity = metrics_data.get('defect_velocity', [])
            cumulative_trends = metrics_data.get('cumulative_trends', [])
            trend_summary = metrics_data.get('trend_summary', {})
            trend_period_text = metrics_data.get('trend_period_text', f'Last {days} Days')
            user_activity_stats = metrics_data.get('user_activity_stats', {})
            top_projects_by_fix_rate = metrics_data.get('top_projects_by_fix_rate', [])
            most_improved_projects = metrics_data.get('most_improved_projects', [])
            top_projects_by_triage = metrics_data.get('top_projects_by_triage', [])
            top_users_by_fixes = metrics_data.get('top_users_by_fixes', [])
            top_triagers = metrics_data.get('top_triagers', [])
            most_collaborative_users = metrics_data.get('most_collaborative_users', [])
    else:
        # Collect without caching
        all_projects = metrics.get_available_projects()
        projects_list = all_projects['project_name'].tolist() if not all_projects.empty else []
        
        # Collect all metrics data
        tqdm.write("Collecting metrics data...")
        
        summary = metrics.get_overall_summary()
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
        commit_stats = metrics.get_commit_time_statistics()
        defect_discovery = metrics.get_defect_discovery_rate(days=days).to_dict('records')
        
        # Collect user activity statistics
        user_activity_stats = metrics.get_user_license_statistics(days=days)
        
        # Collect trend analysis data
        defect_trends = metrics.get_defect_trends(days=days, granularity='week').to_dict('records')
        triage_trends = metrics.get_triage_trends(days=days).to_dict('records')
        fix_rate_metrics = metrics.get_fix_rate_metrics(days=days)
        defect_aging = metrics.get_defect_aging_distribution().to_dict('records')
        triage_summary = metrics.get_triage_progress_summary()
        
        # Collect enhanced velocity and cumulative trends
        defect_velocity = metrics.get_defect_velocity_trend(days=days).to_dict('records')
        cumulative_trends = metrics.get_cumulative_defect_trend(days=days).to_dict('records')
        trend_summary = metrics.get_defect_trend_summary(days=days)
        
        # Collect technical debt summary
        tech_debt_summary = metrics.get_technical_debt_summary()
        
        # Collect leaderboard data (now using triage_state table for user metrics)
        top_projects_by_fix_rate = metrics.get_top_projects_by_fix_rate(days=30, limit=10).to_dict('records')
        most_improved_projects = metrics.get_most_improved_projects(days=90, limit=10).to_dict('records')
        top_projects_by_triage = metrics.get_top_projects_by_triage_activity(days=30, limit=10).to_dict('records')
        top_users_by_fixes = metrics.get_top_users_by_fixes(days=30, limit=10).to_dict('records')
        top_triagers = metrics.get_top_triagers(days=30, limit=10).to_dict('records')
        most_collaborative_users = metrics.get_most_collaborative_users(days=30, limit=10).to_dict('records')
        
        # Collect OWASP Top 10 2025 metrics (project-level only)
        owasp_metrics = metrics.get_owasp_top10_metrics().to_dict('records') if project_name else []
        
        # Collect CWE Top 25 2024 metrics (project-level only)
        cwe_top25_metrics = metrics.get_cwe_top25_metrics().to_dict('records') if project_name else []
        
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
        tqdm.write(f"  [OK] User activity: {user_activity_stats['active_users']} active users")
    
    # Check for high severity alert
    high_severity_alert = summary.get('high_severity_defects', 0) > 0
    
    # Load CSS content for inline embedding
    inline_css = load_inline_css()
    
    # Set up Jinja2 environment (templates are in parent package directory)
    template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates')
    env = Environment(loader=FileSystemLoader(template_dir))
    
    # Load template
    template = env.get_template('dashboard.html')
    
    # Render template with data
    html_content = template.render(
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
        commit_stats=commit_stats,
        defect_discovery=defect_discovery,
        # Trend analysis
        defect_trends=defect_trends,
        triage_trends=triage_trends,
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
        most_improved_projects=most_improved_projects,
        top_projects_by_triage=top_projects_by_triage,
        top_users_by_fixes=top_users_by_fixes,
        top_triagers=top_triagers,
        most_collaborative_users=most_collaborative_users,
        # OWASP Top 10 2025 (project-level only)
        owasp_metrics=owasp_metrics,
        # CWE Top 25 2024 (project-level only)
        cwe_top25_metrics=cwe_top25_metrics
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
    
    summary = metrics.get_overall_summary()
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
    commit_stats = metrics.get_commit_time_statistics()
    defect_discovery = metrics.get_defect_discovery_rate(days=days).to_dict('records')
    
    # Collect user activity statistics
    user_activity_stats = metrics.get_user_license_statistics(days=days)
    
    # Collect trend analysis data
    defect_trends = metrics.get_defect_trends(days=days, granularity='week').to_dict('records')
    triage_trends = metrics.get_triage_trends(days=days).to_dict('records')
    fix_rate_metrics = metrics.get_fix_rate_metrics(days=days)
    defect_aging = metrics.get_defect_aging_distribution().to_dict('records')
    triage_summary = metrics.get_triage_progress_summary()
    
    # Collect enhanced velocity and cumulative trends
    defect_velocity = metrics.get_defect_velocity_trend(days=days).to_dict('records')
    cumulative_trends = metrics.get_cumulative_defect_trend(days=days).to_dict('records')
    trend_summary = metrics.get_defect_trend_summary(days=days)
    
    # Collect leaderboard data (project-level only - database doesn't have history tables for user tracking)
    top_projects_by_fix_rate = metrics.get_top_projects_by_fix_rate(days=30, limit=10).to_dict('records')
    most_improved_projects = metrics.get_most_improved_projects(days=90, limit=10).to_dict('records')
    top_projects_by_triage = metrics.get_top_projects_by_triage_activity(days=30, limit=10).to_dict('records')
    top_users_by_fixes = []  # Not available without defect_triage_history table
    top_triagers = []  # Not available without defect_triage_history table
    most_collaborative_users = []  # Not available without defect_history table
    
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
    tqdm.write(f"  [OK] User activity: {user_activity_stats['active_users']} active users")
    
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
        'commit_stats': commit_stats,
        'defect_discovery': defect_discovery,
        'all_projects': projects_list,
        'defect_trends': defect_trends,
        'triage_trends': triage_trends,
        'fix_rate_metrics': fix_rate_metrics,
        'defect_aging': defect_aging,
        'triage_summary': triage_summary,
        'defect_velocity': defect_velocity,
        'cumulative_trends': cumulative_trends,
        'trend_summary': trend_summary,
        'trend_period_text': trend_period_text,
        'user_activity_stats': user_activity_stats,
        'top_projects_by_fix_rate': top_projects_by_fix_rate,
        'most_improved_projects': most_improved_projects,
        'top_projects_by_triage': top_projects_by_triage,
        'top_users_by_fixes': top_users_by_fixes,
        'top_triagers': top_triagers,
        'most_collaborative_users': most_collaborative_users
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
    aggregated_trends = multi_metrics.get_aggregated_trends(days=days)
    
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
    
    # Set up Jinja2 environment (templates are in parent package directory)
    template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates')
    env = Environment(loader=FileSystemLoader(template_dir))
    
    # Load aggregated template
    template = env.get_template('dashboard_aggregated.html')
    
    # Render template with data
    html_content = template.render(
        inline_css=inline_css,
        timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        summary=summary,
        defects_by_instance=defects_by_instance,
        defects_by_severity=defects_by_severity,
        analysis_versions=analysis_versions,
        instance_configs=instance_configs,
        user_statistics=user_statistics,
        database_statistics=database_statistics,
        triage_summary=aggregated_trends['triage_summary'],
        trend_summary=aggregated_trends['trend_summary'],
        fix_rate_metrics=aggregated_trends['fix_rate_metrics'],
        trends_by_instance=aggregated_trends['by_instance'],
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


def main():
    """Main entry point with automatic multi-instance detection"""
    parser = argparse.ArgumentParser(
        description='Generate Coverity Metrics HTML Dashboard (auto-detects multi-instance from config.json)',
        epilog='Examples:\n'
               '  coverity-dashboard                    # Auto-detect and generate all\n'
               '  coverity-dashboard --project MyApp    # Filter by project\n'
               '  coverity-dashboard --instance Prod    # Specific instance only\n'
               '  coverity-dashboard --days 365         # Change trend period\n',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--project', '-p', type=str, 
                       help='Filter metrics by specific project name')
    parser.add_argument('--output', '-o', type=str, default='output', 
                       help='Output folder path (default: output)')
    parser.add_argument('--no-browser', action='store_true',
                       help='Do not open dashboard in browser')
    
    # Multi-instance arguments (mostly for backward compatibility and override)
    parser.add_argument('--config', '-c', type=str, default='config.json',
                       help='Path to configuration file (default: config.json)')
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
    
    args = parser.parse_args()
    
    tqdm.write("\nCoverity Metrics HTML Dashboard Generator")
    tqdm.write("=" * 80)
    
    # Auto-detect multi-instance configuration
    is_multi_instance, instance_count, config_data = detect_multi_instance_config(args.config)
    
    # Override detection if single-instance mode forced
    if args.single_instance_mode:
        is_multi_instance = False
        tqdm.write("\n[Single-Instance Mode] Forced by --single-instance-mode flag")
    elif is_multi_instance:
        tqdm.write(f"\n[Multi-Instance Mode] Auto-detected {instance_count} instances in {args.config}")
    else:
        tqdm.write("\n[Single-Instance Mode] Using first instance from {args.config}")
    
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
            tqdm.write(f"  Completed: {progress_data['completed_tasks']}/{progress_data['total_tasks']}")
            tqdm.write(f"  Failed: {progress_data['failed_tasks']}")
    
    try:
        # ========================================================================
        # MULTI-INSTANCE MODE (automatic)
        # ========================================================================
        if is_multi_instance and not args.single_instance_mode:
            from coverity_metrics.multi_instance_metrics import MultiInstanceMetrics
            
            multi_metrics = MultiInstanceMetrics(args.config)
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
                    # Specific instance + specific project
                    tqdm.write(f"  Project filter: {args.project}")
                    metrics = multi_metrics.get_metrics_for_instance(args.instance, args.project)
                    instance_folder = f"{args.output}/{args.instance.replace(' ', '_')}"
                    os.makedirs(instance_folder, exist_ok=True)
                    output_file = f"{instance_folder}/dashboard_{args.project.replace(' ', '_')}.html"
                    dashboard_path = generate_html_dashboard(output_file, args.project, args.instance, metrics, cache, use_cache, args.days)
                    generated_files.append((f"{args.instance} - {args.project}", dashboard_path))
                else:
                    # Specific instance + all projects (AUTO)
                    tqdm.write(f"  Generating all projects (auto-mode)")
                    metrics = multi_metrics.get_metrics_for_instance(args.instance)
                    projects = metrics.get_available_projects()
                    
                    # Generate instance-level dashboard (all projects)
                    instance_folder = f"{args.output}/{args.instance.replace(' ', '_')}"
                    os.makedirs(instance_folder, exist_ok=True)
                    output_file = f"{instance_folder}/dashboard.html"
                    dashboard_path = generate_html_dashboard(output_file, None, args.instance, metrics, cache, use_cache, args.days)
                    generated_files.append((f"{args.instance} - All Projects", dashboard_path))
                    
                    # Generate project-level dashboards
                    if not projects.empty:
                        for project in tqdm(projects['project_name'], desc=f"  {args.instance} projects", unit="project"):
                            metrics_proj = multi_metrics.get_metrics_for_instance(args.instance, project)
                            output_file = f"{instance_folder}/dashboard_{project.replace(' ', '_')}.html"
                            dashboard_path = generate_html_dashboard(output_file, project, args.instance, metrics_proj, cache, use_cache, args.days)
                            generated_files.append((f"{args.instance} - {project}", dashboard_path))
                    
            else:
                # ALL INSTANCES MODE (AUTO-AGGREGATED)
                if args.project:
                    # All instances filtered by specific project
                    tqdm.write(f"\nGenerating dashboards for all instances, project: {args.project}")
                    for instance_name in tqdm(instance_names, desc="Instances", unit="instance"):
                        metrics = multi_metrics.get_metrics_for_instance(instance_name, args.project)
                        instance_folder = f"{args.output}/{instance_name.replace(' ', '_')}"
                        os.makedirs(instance_folder, exist_ok=True)
                        output_file = f"{instance_folder}/dashboard_{args.project.replace(' ', '_')}.html"
                        dashboard_path = generate_html_dashboard(output_file, args.project, instance_name, metrics, cache, use_cache, args.days)
                        generated_files.append((f"{instance_name} - {args.project}", dashboard_path))
                else:
                    # All instances + all projects (FULL AUTO MODE)
                    # Generate aggregated dashboard
                    tqdm.write("\nGenerating aggregated dashboard across all instances...")
                    # Ensure output folder exists
                    os.makedirs(args.output, exist_ok=True)
                    output_file = f"{args.output}/dashboard_aggregated.html"
                    dashboard_path = generate_aggregated_dashboard(multi_metrics, output_file, args.days)
                    generated_files.append(("Aggregated View", dashboard_path))
                    
                    # Also generate instance-level dashboards for navigation
                    tqdm.write("\nGenerating instance-level dashboards for navigation...")
                    for instance_name in tqdm(instance_names, desc="Instance dashboards", unit="instance"):
                        metrics = multi_metrics.get_metrics_for_instance(instance_name)
                        instance_folder = f"{args.output}/{instance_name.replace(' ', '_')}"
                        os.makedirs(instance_folder, exist_ok=True)
                        output_file = f"{instance_folder}/dashboard.html"
                        dashboard_path = generate_html_dashboard(output_file, None, instance_name, metrics, cache, use_cache, args.days)
                        generated_files.append((instance_name, dashboard_path))
                    
                    tqdm.write(f"\n[OK] Generated aggregated view + {len(instance_names)} instance dashboards")
                    
                    # Auto-generate project-level dashboards for each instance
                    tqdm.write("\nGenerating project-level dashboards for all instances...")
                    total_projects = 0
                    for instance_name in instance_names:
                        metrics = multi_metrics.get_metrics_for_instance(instance_name)
                        projects = metrics.get_available_projects()
                        
                        if not projects.empty:
                            for project in tqdm(projects['project_name'], desc=f"{instance_name}", unit="project", leave=False):
                                metrics_proj = multi_metrics.get_metrics_for_instance(instance_name, project)
                                instance_folder = f"{args.output}/{instance_name.replace(' ', '_')}"
                                os.makedirs(instance_folder, exist_ok=True)
                                output_file = f"{instance_folder}/dashboard_{project.replace(' ', '_')}.html"
                                dashboard_path = generate_html_dashboard(output_file, project, instance_name, metrics_proj, cache, use_cache, args.days)
                                generated_files.append((f"{instance_name} - {project}", dashboard_path))
                                total_projects += 1
                    
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
        # For single-instance mode, read first enabled instance from config.json
        connection_params = None
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
                tqdm.write(f"  Using instance: {first_instance['name']}")
        
        if not connection_params:
            tqdm.write("\n[ERROR] No database configuration found in config.json")
            tqdm.write("Please configure at least one instance in config.json")
            sys.exit(1)
        
        # Generate single dashboard
        os.makedirs(args.output, exist_ok=True)
        if args.project:
            # Project-specific dashboard
            output_file = f"{args.output}/dashboard_{args.project.replace(' ', '_')}.html"
        else:
            # All projects dashboard
            output_file = f"{args.output}/dashboard.html"
        
        # Create metrics instance with connection params from config.json
        metrics = CoverityMetrics(connection_params=connection_params)
        dashboard_path = generate_html_dashboard(output_file, args.project, None, metrics, cache, use_cache, args.days)
        
        if not args.no_browser:
            tqdm.write("\nOpening dashboard in default browser...")
            webbrowser.open('file://' + dashboard_path)
            tqdm.write("[OK] Dashboard opened")
        
        tqdm.write("\n" + "=" * 80)
        tqdm.write("Dashboard generation completed successfully!")
        tqdm.write("=" * 80 + "\n")
        
    except Exception as e:
        tqdm.write(f"\n[ERROR] Failed to generate dashboard")
        tqdm.write(f"  {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

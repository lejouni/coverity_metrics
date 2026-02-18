"""
Metrics caching system for Coverity dashboards

Provides caching of database query results to speed up dashboard generation
and enable resumable processing for large deployments.
"""

import os
import json
import pickle
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class MetricsCache:
    """Cache manager for Coverity metrics data"""
    
    def __init__(self, cache_dir="cache", cache_ttl_hours=24):
        """
        Initialize metrics cache
        
        Args:
            cache_dir: Directory to store cache files
            cache_ttl_hours: Time-to-live for cache entries in hours
        """
        self.cache_dir = Path(cache_dir)
        self.cache_ttl = timedelta(hours=cache_ttl_hours)
        self.cache_dir.mkdir(exist_ok=True)
        
        # Separate directories for different cache types
        self.metrics_cache_dir = self.cache_dir / "metrics"
        self.progress_cache_dir = self.cache_dir / "progress"
        self.metrics_cache_dir.mkdir(exist_ok=True)
        self.progress_cache_dir.mkdir(exist_ok=True)
        
        logger.info(f"Metrics cache initialized: {self.cache_dir}")
        logger.info(f"Cache TTL: {cache_ttl_hours} hours")
    
    def _get_cache_key(self, instance_name, project_name=None, days=90):
        """Generate unique cache key for instance/project combination"""
        if project_name:
            key = f"{instance_name}_{project_name}_days{days}"
        else:
            key = f"{instance_name}_days{days}"
        
        # Hash the key to avoid filesystem issues with special characters
        return hashlib.md5(key.encode()).hexdigest() + "_" + key.replace(' ', '_').replace('/', '_')
    
    def _get_cache_file_path(self, cache_key):
        """Get full path to cache file"""
        return self.metrics_cache_dir / f"{cache_key}.pkl"
    
    def _is_cache_valid(self, cache_file):
        """Check if cache file exists and is not expired"""
        if not cache_file.exists():
            return False
        
        # Check file modification time
        mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
        age = datetime.now() - mtime
        
        if age > self.cache_ttl:
            logger.debug(f"Cache expired: {cache_file.name} (age: {age})")
            return False
        
        return True
    
    def get_cached_metrics(self, instance_name, project_name=None, days=90):
        """
        Retrieve cached metrics data
        
        Args:
            instance_name: Coverity instance name
            project_name: Optional project name
            days: Number of days for trend analysis
            
        Returns:
            Cached metrics dict or None if not available/expired
        """
        cache_key = self._get_cache_key(instance_name, project_name, days)
        cache_file = self._get_cache_file_path(cache_key)
        
        if not self._is_cache_valid(cache_file):
            return None
        
        try:
            with open(cache_file, 'rb') as f:
                cached_data = pickle.load(f)
            
            logger.info(f"Cache hit: {instance_name}" + (f" - {project_name}" if project_name else ""))
            return cached_data
        
        except Exception as e:
            logger.warning(f"Failed to load cache {cache_key}: {e}")
            return None
    
    def save_metrics_to_cache(self, instance_name, metrics_data, project_name=None, days=90):
        """
        Save metrics data to cache
        
        Args:
            instance_name: Coverity instance name
            metrics_data: Dictionary containing all metrics for this instance/project
            project_name: Optional project name
            days: Number of days for trend analysis
        """
        cache_key = self._get_cache_key(instance_name, project_name, days)
        cache_file = self._get_cache_file_path(cache_key)
        
        try:
            # Add metadata to cached data
            cache_entry = {
                'timestamp': datetime.now().isoformat(),
                'instance_name': instance_name,
                'project_name': project_name,
                'data': metrics_data
            }
            
            with open(cache_file, 'wb') as f:
                pickle.dump(cache_entry, f)
            
            logger.info(f"Cached metrics: {instance_name}" + (f" - {project_name}" if project_name else ""))
        
        except Exception as e:
            logger.warning(f"Failed to save cache {cache_key}: {e}")
    
    def clear_cache(self, instance_name=None, project_name=None, days=None):
        """
        Clear cache entries
        
        Args:
            instance_name: If provided, clear only this instance (and optionally project)
            project_name: If provided with instance_name, clear only this project
            days: If provided with instance_name, clear only this specific days cache
        """
        if instance_name and days is not None:
            cache_key = self._get_cache_key(instance_name, project_name, days)
            cache_file = self._get_cache_file_path(cache_key)
            
            if cache_file.exists():
                cache_file.unlink()
                logger.info(f"Cleared cache: {cache_key}")
        elif instance_name:
            cache_key = self._get_cache_key(instance_name, project_name, 90)
            cache_file = self._get_cache_file_path(cache_key)
            
            if cache_file.exists():
                cache_file.unlink()
                logger.info(f"Cleared cache: {cache_key}")
        else:
            # Clear all metrics cache
            for cache_file in self.metrics_cache_dir.glob("*.pkl"):
                cache_file.unlink()
            logger.info("Cleared all metrics cache")
    
    def get_cache_stats(self):
        """Get cache statistics"""
        cache_files = list(self.metrics_cache_dir.glob("*.pkl"))
        total_size = sum(f.stat().st_size for f in cache_files)
        valid_count = sum(1 for f in cache_files if self._is_cache_valid(f))
        expired_count = len(cache_files) - valid_count
        
        return {
            'total_entries': len(cache_files),
            'valid_entries': valid_count,
            'expired_entries': expired_count,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'cache_dir': str(self.cache_dir)
        }
    
    def cleanup_expired_cache(self):
        """Remove expired cache entries"""
        removed_count = 0
        for cache_file in self.metrics_cache_dir.glob("*.pkl"):
            if not self._is_cache_valid(cache_file):
                cache_file.unlink()
                removed_count += 1
        
        logger.info(f"Cleaned up {removed_count} expired cache entries")
        return removed_count


class ProgressTracker:
    """Track dashboard generation progress for resumable operations"""
    
    def __init__(self, cache_dir="cache"):
        """Initialize progress tracker"""
        self.cache_dir = Path(cache_dir)
        self.progress_dir = self.cache_dir / "progress"
        self.progress_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_progress_file(self, session_id):
        """Get progress file path for session"""
        return self.progress_dir / f"progress_{session_id}.json"
    
    def create_session(self, total_tasks, session_id=None):
        """
        Create a new progress tracking session
        
        Args:
            total_tasks: Total number of tasks to complete
            session_id: Optional session identifier (defaults to timestamp)
            
        Returns:
            Session ID
        """
        if session_id is None:
            session_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        progress_data = {
            'session_id': session_id,
            'created_at': datetime.now().isoformat(),
            'total_tasks': total_tasks,
            'completed_tasks': 0,
            'failed_tasks': 0,
            'completed_items': [],
            'failed_items': [],
            'in_progress': True
        }
        
        progress_file = self._get_progress_file(session_id)
        with open(progress_file, 'w') as f:
            json.dump(progress_data, f, indent=2)
        
        logger.info(f"Created progress session: {session_id} ({total_tasks} tasks)")
        return session_id
    
    def update_progress(self, session_id, item_name, success=True, error=None):
        """
        Update progress for a completed task
        
        Args:
            session_id: Session identifier
            item_name: Name of completed item
            success: Whether task completed successfully
            error: Optional error message if failed
        """
        progress_file = self._get_progress_file(session_id)
        
        if not progress_file.exists():
            logger.warning(f"Progress file not found: {session_id}")
            return
        
        with open(progress_file, 'r') as f:
            progress_data = json.load(f)
        
        if success:
            progress_data['completed_tasks'] += 1
            progress_data['completed_items'].append({
                'name': item_name,
                'timestamp': datetime.now().isoformat()
            })
        else:
            progress_data['failed_tasks'] += 1
            progress_data['failed_items'].append({
                'name': item_name,
                'error': str(error) if error else 'Unknown error',
                'timestamp': datetime.now().isoformat()
            })
        
        with open(progress_file, 'w') as f:
            json.dump(progress_data, f, indent=2)
        
        # Log progress
        total = progress_data['total_tasks']
        completed = progress_data['completed_tasks']
        failed = progress_data['failed_tasks']
        percent = (completed + failed) / total * 100 if total > 0 else 0
        
        logger.info(f"Progress: {completed}/{total} completed, {failed} failed ({percent:.1f}%)")
    
    def complete_session(self, session_id):
        """Mark session as completed"""
        progress_file = self._get_progress_file(session_id)
        
        if not progress_file.exists():
            return
        
        with open(progress_file, 'r') as f:
            progress_data = json.load(f)
        
        progress_data['in_progress'] = False
        progress_data['completed_at'] = datetime.now().isoformat()
        
        with open(progress_file, 'w') as f:
            json.dump(progress_data, f, indent=2)
        
        logger.info(f"Session completed: {session_id}")
    
    def get_progress(self, session_id):
        """Get current progress for session"""
        progress_file = self._get_progress_file(session_id)
        
        if not progress_file.exists():
            return None
        
        with open(progress_file, 'r') as f:
            return json.load(f)
    
    def get_incomplete_sessions(self):
        """Get list of incomplete progress sessions"""
        incomplete = []
        
        for progress_file in self.progress_dir.glob("progress_*.json"):
            with open(progress_file, 'r') as f:
                data = json.load(f)
                if data.get('in_progress', False):
                    incomplete.append(data)
        
        return incomplete
    
    def get_resumable_tasks(self, session_id):
        """
        Get list of tasks that can be resumed (not yet completed)
        
        Args:
            session_id: Session identifier
            
        Returns:
            List of completed item names (to skip during resume)
        """
        progress_data = self.get_progress(session_id)
        
        if not progress_data:
            return []
        
        completed_names = [item['name'] for item in progress_data.get('completed_items', [])]
        return completed_names


def collect_metrics_with_cache(metrics, instance_name, project_name, cache, use_cache=True):
    """
    Collect metrics data with caching support
    
    Args:
        metrics: CoverityMetrics instance
        instance_name: Instance name
        project_name: Optional project name
        cache: MetricsCache instance
        use_cache: Whether to use cached data if available
        
    Returns:
        Dictionary containing all collected metrics
    """
    # Try to get from cache first
    if use_cache:
        cached_data = cache.get_cached_metrics(instance_name, project_name)
        if cached_data:
            return cached_data['data']
    
    # Collect fresh metrics from database
    logger.info(f"Collecting metrics from database: {instance_name}" + 
                (f" - {project_name}" if project_name else ""))
    
    try:
        metrics_data = {
            'summary': metrics.get_overall_summary(),
            'defects_by_severity': metrics.get_defects_by_severity().to_dict('records'),
            'defects_by_project': metrics.get_total_defects_by_project().to_dict('records'),
            'defects_by_category': metrics.get_defects_by_checker_category(limit=20).to_dict('records'),
            'top_checkers': metrics.get_defects_by_checker_name(limit=20).to_dict('records'),
            'defect_density': metrics.get_defect_density_by_project().to_dict('records'),
            'file_hotspots': metrics.get_file_hotspots(limit=20).to_dict('records'),
            'code_metrics': metrics.get_code_metrics_by_stream().to_dict('records'),
            'complexity_distribution': metrics.get_function_complexity_distribution().to_dict('records'),
            'db_stats': metrics.get_database_statistics(),
            'largest_tables': metrics.get_largest_tables(limit=10).to_dict('records'),
            'snapshot_performance': metrics.get_snapshot_performance(limit=15).to_dict('records'),
            'commit_stats': metrics.get_commit_time_statistics(),
            'defect_discovery': metrics.get_defect_discovery_rate(days=90).to_dict('records'),
            'all_projects': metrics.get_available_projects()['project_name'].tolist() if not metrics.get_available_projects().empty else []
        }
        
        # Save to cache
        cache.save_metrics_to_cache(instance_name, metrics_data, project_name)
        
        return metrics_data
    
    except Exception as e:
        logger.error(f"Failed to collect metrics: {e}")
        raise

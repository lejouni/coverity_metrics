"""
ZIP Data Loader for Coverity Metrics
Provides the same interface as CoverityMetrics but reads from exported ZIP files
All metrics are stored in JSON format for better handling of complex data structures
"""
import os
import json
import zipfile
import pandas as pd


class ZipDataLoader:
    """
    Data loader that reads Coverity metrics from a ZIP file export
    Provides the same interface as CoverityMetrics for seamless integration
    """
    
    def __init__(self, zip_file_path, instance_name=None, project_name=None):
        """Initialize ZIP data loader
        
        Args:
            zip_file_path: Path to exported ZIP file
            instance_name: Optional instance name to filter data
            project_name: Optional project name to filter data
        """
        self.zip_file_path = zip_file_path
        self.instance_name = instance_name
        self.project_name = project_name
        self.metadata = None
        self._cache = {}
        
        # Validate ZIP file exists
        if not os.path.exists(zip_file_path):
            raise FileNotFoundError(f"ZIP file not found: {zip_file_path}")
        
        # Load metadata
        self._load_metadata()
        
        # Auto-select instance if not specified
        if not self.instance_name and self.metadata:
            instances = list(self.metadata.get('instances', {}).keys())
            if instances:
                self.instance_name = instances[0]
                print(f"Auto-selected instance: {self.instance_name}")
    
    def _load_metadata(self):
        """Load metadata from ZIP file"""
        try:
            with zipfile.ZipFile(self.zip_file_path, 'r') as zf:
                metadata_content = zf.read('metadata.json').decode('utf-8')
                self.metadata = json.loads(metadata_content)
        except Exception as e:
            print(f"WARNING: Failed to load metadata from ZIP: {e}")
            self.metadata = {}
    
    def _read_json_from_zip(self, filename, as_dataframe=False):
        """Read a JSON file from the ZIP archive
        
        Args:
            filename: Name of JSON file in ZIP
            as_dataframe: If True, convert list data to DataFrame
            
        Returns:
            dict, list, or DataFrame depending on content and as_dataframe flag
        """
        # Check cache first
        cache_key = f"{self.instance_name}_{filename}_json"
        if cache_key in self._cache:
            data = self._cache[cache_key]
            if as_dataframe and isinstance(data, list):
                return pd.DataFrame(data)
            return data
        
        try:
            with zipfile.ZipFile(self.zip_file_path, 'r') as zf:
                # Try to read the file
                json_content = zf.read(filename).decode('utf-8')
                data = json.loads(json_content)
                
                # Cache the result
                self._cache[cache_key] = data
                
                # Convert to DataFrame if requested and data is a list
                if as_dataframe and isinstance(data, list):
                    return pd.DataFrame(data)
                
                return data
        except KeyError:
            # File not found in ZIP
            return pd.DataFrame() if as_dataframe else {}
        except Exception as e:
            print(f"WARNING: Error reading {filename}: {e}")
            return pd.DataFrame() if as_dataframe else {}
    
    def _get_metric_file(self, metric_name):
        """Get JSON filename for a metric
        
        Args:
            metric_name: Name of the metric
            
        Returns:
            str: Filepath in format {instance}/{metric}.json
        """
        return f"{self.instance_name}/{metric_name}.json"
    
    def _get_project_metric_file(self, metric_name):
        """Get JSON filename for a project-specific metric
        
        Args:
            metric_name: Name of the metric
            
        Returns:
            str: Filepath in format {instance}/{project}/{metric}.json
        """
        if not self.project_name:
            return None
        return f"{self.instance_name}/{self.project_name}/{metric_name}.json"
    
    def _read_metric_json(self, metric_name, as_dataframe=False):
        """Read a metric JSON file, checking project-specific path first if project_name is set
        
        Args:
            metric_name: Name of the metric
            as_dataframe: If True, convert list data to DataFrame
            
        Returns:
            dict, list, or DataFrame depending on content and as_dataframe flag
        """
        # If project_name is set, use project-specific file only
        if self.project_name:
            project_file = self._get_project_metric_file(metric_name)
            if project_file:
                try:
                    # Check if project-specific file exists in ZIP
                    with zipfile.ZipFile(self.zip_file_path, 'r') as zf:
                        if project_file in zf.namelist():
                            # Project-specific file exists, use it
                            return self._read_json_from_zip(project_file, as_dataframe=as_dataframe)
                except Exception:
                    pass
            # Project-specific file not found (stream has no snapshots / no data exported).
            # Return empty data instead of falling back to instance-level metrics.
            return pd.DataFrame() if as_dataframe else {}
        
        # No project filter - use instance-level file
        instance_file = self._get_metric_file(metric_name)
        return self._read_json_from_zip(instance_file, as_dataframe=as_dataframe)
    
    # ========== METRIC METHODS (mirroring CoverityMetrics) ==========
    
    def get_available_projects(self):
        """Get list of available projects"""
        return self._read_json_from_zip(self._get_metric_file('available_projects'), as_dataframe=True)
    
    def get_overall_summary(self):
        """Get overall summary metrics"""
        return self._read_metric_json('overall_summary')
    
    def get_defects_by_severity(self):
        """Get defects grouped by severity"""
        return self._read_metric_json('defects_by_severity', as_dataframe=True)
    
    def get_total_defects_by_project(self):
        """Get total defects by project"""
        return self._read_json_from_zip(self._get_metric_file('total_defects_by_project'), as_dataframe=True)
    
    def get_defects_by_checker_category(self, limit=20, fetch_all=False):
        """Get defects by checker category"""
        df = self._read_metric_json('defects_by_checker_category', as_dataframe=True)
        if not fetch_all and not df.empty:
            return df.head(limit)
        return df
    
    def get_defects_by_checker_name(self, limit=20, fetch_all=False):
        """Get defects by checker name"""
        df = self._read_metric_json('defects_by_checker_name', as_dataframe=True)
        if not fetch_all and not df.empty:
            return df.head(limit)
        return df
    
    def get_defect_density_by_project(self):
        """Get defect density by project"""
        return self._read_metric_json('defect_density_by_project', as_dataframe=True)
    
    def get_file_hotspots(self, limit=20, fetch_all=False):
        """Get file hotspots"""
        df = self._read_metric_json('file_hotspots', as_dataframe=True)
        if not fetch_all and not df.empty:
            return df.head(limit)
        return df
    
    def get_code_metrics_by_stream(self):
        """Get code metrics by stream"""
        return self._read_metric_json('code_metrics_by_stream', as_dataframe=True)
    
    def get_function_complexity_distribution(self):
        """Get function complexity distribution"""
        return self._read_json_from_zip(self._get_metric_file('function_complexity_distribution'), as_dataframe=True)
    
    def get_database_statistics(self):
        """Get database statistics"""
        return self._read_json_from_zip(self._get_metric_file('database_statistics'))
    
    def get_instance_info(self):
        """Get instance information"""
        return self._read_json_from_zip(self._get_metric_file('instance_info'))
    
    def get_analysis_versions(self, limit=10, days=365):
        """Get analysis versions"""
        data = self._read_json_from_zip(self._get_metric_file('analysis_versions'))
        if isinstance(data, list) and len(data) > limit:
            return data[:limit]
        return data
    
    def get_largest_tables(self, limit=10):
        """Get largest database tables"""
        df = self._read_json_from_zip(self._get_metric_file('largest_tables'), as_dataframe=True)
        if not df.empty:
            return df.head(limit)
        return df
    
    def get_snapshot_performance(self, limit=15):
        """Get snapshot performance metrics"""
        df = self._read_json_from_zip(self._get_metric_file('snapshot_performance'), as_dataframe=True)
        if not df.empty:
            return df.head(limit)
        return df
    
    def get_commit_time_statistics(self):
        """Get commit time statistics"""
        return self._read_json_from_zip(self._get_metric_file('commit_time_statistics'))
    
    def get_commit_activity_patterns(self):
        """Get commit activity patterns"""
        return self._read_json_from_zip(self._get_metric_file('commit_activity_patterns'))
    
    def get_defect_discovery_rate(self, days=30):
        """Get defect discovery rate"""
        return self._read_json_from_zip(self._get_metric_file('defect_discovery_rate'), as_dataframe=True)
    
    def get_user_license_statistics(self, days=30):
        """Get user license statistics"""
        return self._read_json_from_zip(self._get_metric_file('user_license_statistics'))
    
    def get_defect_trends(self, days=90, granularity='auto'):
        """Get defect trends"""
        return self._read_metric_json('defect_trends', as_dataframe=True)
    
    def get_triage_trends(self, days=90, granularity='auto'):
        """Get triage trends"""
        return self._read_metric_json('triage_trends', as_dataframe=True)

    def get_checker_classification_breakdown(self, limit=15):
        """Get checker classification breakdown"""
        return self._read_metric_json('checker_classification_breakdown', as_dataframe=True)

    def get_top_projects_by_classification(self, limit=10):
        """Get top projects/streams by intentional classification count"""
        return self._read_metric_json('top_projects_by_classification', as_dataframe=True)

    def get_fix_rate_metrics(self, days=90):
        """Get fix rate metrics"""
        return self._read_metric_json('fix_rate_metrics')
    
    def get_defect_aging_distribution(self):
        """Get defect aging distribution"""
        return self._read_metric_json('defect_aging_distribution', as_dataframe=True)
    
    def get_triage_progress_summary(self):
        """Get triage progress summary"""
        return self._read_metric_json('triage_progress_summary')
    
    def get_defect_velocity_trend(self, days=90):
        """Get defect velocity trend"""
        return self._read_json_from_zip(self._get_metric_file('defect_velocity_trend'), as_dataframe=True)
    
    def get_cumulative_defect_trend(self, days=90):
        """Get cumulative defect trend"""
        return self._read_json_from_zip(self._get_metric_file('cumulative_defect_trend'), as_dataframe=True)
    
    def get_defect_trend_summary(self, days=90):
        """Get defect trend summary"""
        return self._read_metric_json('defect_trend_summary')
    
    def get_technical_debt_summary(self):
        """Get technical debt summary"""
        return self._read_metric_json('technical_debt_summary')
    
    def get_top_projects_by_fix_rate(self, days=30, limit=10):
        """Get top projects by fix rate"""
        df = self._read_json_from_zip(self._get_metric_file('top_projects_by_fix_rate'), as_dataframe=True)
        if not df.empty:
            return df.head(limit)
        return df
    
    def get_most_improved_projects(self, days=90, limit=10):
        """Get most improved projects"""
        df = self._read_json_from_zip(self._get_metric_file('most_improved_projects'), as_dataframe=True)
        if not df.empty:
            return df.head(limit)
        return df
    
    def get_top_projects_by_triage_activity(self, days=30, limit=10):
        """Get top projects by triage activity"""
        df = self._read_json_from_zip(self._get_metric_file('top_projects_by_triage_activity'), as_dataframe=True)
        if not df.empty:
            return df.head(limit)
        return df
    
    def get_top_users_by_fixes(self, days=30, limit=10):
        """Get top users by fixes"""
        df = self._read_json_from_zip(self._get_metric_file('top_users_by_fixes'), as_dataframe=True)
        if not df.empty:
            return df.head(limit)
        return df
    
    def get_top_triagers(self, days=30, limit=10):
        """Get top triagers"""
        df = self._read_json_from_zip(self._get_metric_file('top_triagers'), as_dataframe=True)
        if not df.empty:
            return df.head(limit)
        return df
    
    def get_most_collaborative_users(self, days=30, limit=10):
        """Get most collaborative users"""
        df = self._read_json_from_zip(self._get_metric_file('most_collaborative_users'), as_dataframe=True)
        if not df.empty:
            return df.head(limit)
        return df
    
    def get_owasp_top10_metrics(self):
        """Get OWASP Top 10 metrics (project-specific)"""
        filename = self._get_project_metric_file('owasp_top10_metrics')
        if filename:
            return self._read_json_from_zip(filename, as_dataframe=True)
        return pd.DataFrame()
    
    def get_owasp_category_details(self, category_id):
        """Get OWASP category details"""
        if not self.project_name:
            return []
        filename = f"{self.instance_name}_{self.project_name}_owasp_{category_id}_details.json"
        data = self._read_json_from_zip(filename)
        if isinstance(data, list):
            return data
        return []
    
    def get_cwe_top25_metrics(self):
        """Get CWE Top 25 metrics (project-specific)"""
        filename = self._get_project_metric_file('cwe_top25_metrics')
        if filename:
            return self._read_json_from_zip(filename, as_dataframe=True)
        return pd.DataFrame()
    
    def get_cwe_top25_details(self, cwe_id):
        """Get CWE Top 25 details"""
        if not self.project_name:
            return []
        filename = f"{self.instance_name}_{self.project_name}_cwe_{cwe_id}_details.json"
        data = self._read_json_from_zip(filename)
        if isinstance(data, list):
            return data
        return []
    
    def get_metadata(self):
        """Get export metadata
        
        Returns:
            dict: Metadata about the export
        """
        return self.metadata
    
    def list_available_instances(self):
        """List all instances available in the ZIP file
        
        Returns:
            list: Instance names
        """
        if self.metadata:
            return list(self.metadata.get('instances', {}).keys())
        return []
    
    def list_available_projects(self, instance_name=None):
        """List all projects for an instance
        
        Args:
            instance_name: Instance name (uses current if not specified)
            
        Returns:
            list: Project names
        """
        inst_name = instance_name or self.instance_name
        if self.metadata and inst_name in self.metadata.get('instances', {}):
            return self.metadata['instances'][inst_name].get('projects', [])
        return []

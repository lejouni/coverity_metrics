"""
Multi-Instance Coverity Metrics Manager
Handles multiple Coverity instances and provides aggregated views
"""
import json
import os
from typing import List, Dict, Optional
import pandas as pd
from tqdm import tqdm
from metrics import CoverityMetrics


class InstanceConfig:
    """Configuration for a single Coverity instance"""
    
    def __init__(self, config_dict: dict):
        self.name = config_dict['name']
        self.description = config_dict.get('description', '')
        self.enabled = config_dict.get('enabled', True)
        self.db_config = config_dict['database']
        self.color = config_dict.get('color', '#2c3e50')
    
    def get_connection_params(self) -> dict:
        """Get database connection parameters"""
        return {
            'host': self.db_config['host'],
            'port': self.db_config['port'],
            'database': self.db_config['database'],
            'user': self.db_config['user'],
            'password': self.db_config['password']
        }


class MultiInstanceMetrics:
    """Manager for multiple Coverity instance metrics"""
    
    def __init__(self, config_file: str = 'config.json'):
        self.config_file = config_file
        self.instances: List[InstanceConfig] = []
        self.metrics_managers: Dict[str, CoverityMetrics] = {}
        
        self._load_config()
        self._initialize_connections()
    
    def _load_config(self):
        """Load configuration from JSON file"""
        try:
            # Check if config file exists, fall back to example if not
            if not os.path.exists(self.config_file):
                example_file = 'config.example.json'
                tqdm.write(f"Warning: {self.config_file} not found, using {example_file}")
                self.config_file = example_file
            
            with open(self.config_file, 'r') as f:
                config = json.load(f)
                
            for inst_config in config.get('instances', []):
                instance = InstanceConfig(inst_config)
                if instance.enabled:
                    self.instances.append(instance)
                    
        except Exception as e:
            raise Exception(f"Failed to load configuration: {str(e)}")
    
    def _initialize_connections(self):
        """Initialize metrics managers for all instances"""
        for instance in self.instances:
            try:
                # Create metrics manager for this instance
                metrics = CoverityMetrics(
                    connection_params=instance.get_connection_params()
                )
                self.metrics_managers[instance.name] = metrics
                tqdm.write(f"[OK] Connected to instance: {instance.name}")
            except Exception as e:
                tqdm.write(f"[ERROR] Failed to connect to {instance.name}: {str(e)}")
    
    def get_instance_names(self) -> List[str]:
        """Get list of all instance names"""
        return [inst.name for inst in self.instances]
    
    def get_instance_config(self, instance_name: str) -> Optional[InstanceConfig]:
        """Get configuration for a specific instance"""
        for instance in self.instances:
            if instance.name == instance_name:
                return instance
        return None
    
    def get_metrics_manager(self, instance_name: str) -> Optional[CoverityMetrics]:
        """Get metrics manager for a specific instance"""
        return self.metrics_managers.get(instance_name)
    
    def get_metrics_for_instance(self, instance_name: str, project_name: Optional[str] = None) -> Optional[CoverityMetrics]:
        """
        Get metrics manager for a specific instance, optionally filtered by project
        
        Args:
            instance_name: Name of the instance
            project_name: Optional project name to filter by
            
        Returns:
            CoverityMetrics object or None if instance not found
        """
        metrics = self.metrics_managers.get(instance_name)
        if metrics is None:
            return None
            
        if project_name:
            # Create a new metrics object scoped to the specific project
            instance_config = self.get_instance_config(instance_name)
            if instance_config:
                project_metrics = CoverityMetrics(
                    project_name=project_name,
                    connection_params=instance_config.get_connection_params()
                )
                return project_metrics
        
        return metrics
    
    def get_aggregated_summary(self) -> dict:
        """Get aggregated summary across all instances"""
        total_defects = 0
        total_outstanding = 0
        total_projects = 0
        high_severity_defects = 0
        
        for instance_name, metrics in self.metrics_managers.items():
            try:
                summary = metrics.get_overall_summary()
                total_defects += summary.get('total_defects', 0)
                total_outstanding += summary.get('outstanding_defects', 0)
                total_projects += summary.get('total_projects', 0)
                high_severity_defects += summary.get('high_severity_defects', 0)
            except Exception as e:
                tqdm.write(f"Warning: Failed to get summary from {instance_name}: {str(e)}")
                continue
        
        return {
            'total_instances': len(self.metrics_managers),
            'total_defects': total_defects,
            'outstanding_defects': total_outstanding,
            'total_projects': total_projects,
            'high_severity_defects': high_severity_defects
        }
    
    def get_defects_by_instance(self) -> pd.DataFrame:
        """Get defect counts by instance with detailed metrics"""
        data = []
        
        for instance_name, metrics in self.metrics_managers.items():
            try:
                # Get instance config for description and color
                instance_config = self.get_instance_config(instance_name)
                
                # Get summary metrics
                summary = metrics.get_overall_summary()
                
                # Get severity breakdown
                severity_data = metrics.get_defects_by_severity()
                high_severity = 0
                medium_severity = 0
                low_severity = 0
                
                if not severity_data.empty:
                    for _, row in severity_data.iterrows():
                        # Check for 'impact' or 'severity' column
                        severity = row.get('impact', row.get('severity', '')).lower()
                        # Check for 'defect_count' or 'count' column
                        count = row.get('defect_count', row.get('count', 0))
                        
                        if 'high' in severity:
                            high_severity += count
                        elif 'medium' in severity:
                            medium_severity += count
                        elif 'low' in severity:
                            low_severity += count
                
                data.append({
                    'instance_name': instance_name,
                    'instance': instance_name,  # Keep for backwards compatibility
                    'description': instance_config.description if instance_config else '',
                    'color': instance_config.color if instance_config else '#2c3e50',
                    'total_defects': summary.get('total_defects', 0),
                    'outstanding': summary.get('outstanding_defects', 0),
                    'fixed': summary.get('total_defects', 0) - summary.get('outstanding_defects', 0),
                    'high_severity': high_severity,
                    'medium_severity': medium_severity,
                    'low_severity': low_severity,
                    'total_projects': summary.get('total_projects', 0),
                    'total_streams': summary.get('total_streams', 0)
                })
            except Exception as e:
                tqdm.write(f"Warning: Failed to get defects from {instance_name}: {str(e)}")
                continue
        
        return pd.DataFrame(data)
    
    def get_all_projects(self) -> pd.DataFrame:
        """Get all projects across all instances"""
        all_projects = []
        
        for instance_name, metrics in self.metrics_managers.items():
            try:
                # Get instance config for color
                instance_config = self.get_instance_config(instance_name)
                instance_color = instance_config.color if instance_config else '#2c3e50'
                
                projects_df = metrics.get_available_projects()
                if not projects_df.empty and 'project_name' in projects_df.columns:
                    for _, row in projects_df.iterrows():
                        all_projects.append({
                            'instance_name': instance_name,
                            'project_name': row['project_name'],
                            'instance_color': instance_color
                        })
            except Exception as e:
                tqdm.write(f"Warning: Failed to get projects from {instance_name}: {str(e)}")
                continue
        
        return pd.DataFrame(all_projects)
    
    def get_all_projects_across_instances(self) -> pd.DataFrame:
        """Alias for get_all_projects() - Get all projects across all instances"""
        return self.get_all_projects()
    
    def get_aggregated_defects_by_severity(self) -> pd.DataFrame:
        """
        Get aggregated defect counts by severity across all instances
        Returns a DataFrame with severity levels and their total counts
        """
        all_data = []
        
        for instance_name, metrics in self.metrics_managers.items():
            try:
                severity_data = metrics.get_defects_by_severity()
                if not severity_data.empty:
                    # Normalize column names
                    severity_data = severity_data.copy()
                    if 'impact' in severity_data.columns:
                        severity_data.rename(columns={'impact': 'severity'}, inplace=True)
                    if 'defect_count' in severity_data.columns:
                        severity_data.rename(columns={'defect_count': 'count'}, inplace=True)
                    
                    severity_data['instance'] = instance_name
                    all_data.append(severity_data)
            except Exception as e:
                tqdm.write(f"Warning: Failed to get severity data from {instance_name}: {str(e)}")
                continue
        
        if not all_data:
            return pd.DataFrame(columns=['severity', 'count'])
        
        # Concatenate all instance data
        combined = pd.concat(all_data, ignore_index=True)
        
        # Aggregate by severity
        if 'severity' in combined.columns and 'count' in combined.columns:
            aggregated = combined.groupby('severity', as_index=False)['count'].sum()
            return aggregated
        else:
            return pd.DataFrame(columns=['severity', 'count'])
    
    def get_defects_by_severity_all_instances(self) -> pd.DataFrame:
        """Get defects by severity across all instances"""
        all_data = []
        
        for instance_name, metrics in self.metrics_managers.items():
            try:
                severity_data = metrics.get_defects_by_severity()
                severity_data['instance'] = instance_name
                all_data.append(severity_data)
            except Exception as e:
                tqdm.write(f"Warning: Failed to get severity data from {instance_name}: {str(e)}")
                continue
        
        if all_data:
            return pd.concat(all_data, ignore_index=True)
        else:
            return pd.DataFrame()
    
    def get_aggregated_analysis_versions(self, limit: int = 10) -> list:
        """
        Get aggregated analysis versions across all instances
        
        Args:
            limit: Number of top versions to return (default: 10)
            
        Returns:
            list: List of dicts containing version info aggregated across instances
        """
        # Collect all version data from all instances
        all_versions = {}
        
        for instance_name, metrics in self.metrics_managers.items():
            try:
                version_data = metrics.get_analysis_versions(limit=100)  # Get more from each instance
                
                for ver in version_data:
                    version_str = ver.get('version')
                    if version_str:
                        if version_str not in all_versions:
                            all_versions[version_str] = {
                                'version': version_str,
                                'snapshot_count': 0,
                                'first_used': None,
                                'last_used': None,
                                'instances': []
                            }
                        
                        # Aggregate counts
                        all_versions[version_str]['snapshot_count'] += ver.get('snapshot_count', 0)
                        all_versions[version_str]['instances'].append(instance_name)
                        
                        # Track earliest first_used
                        first_used = ver.get('first_used')
                        if first_used:
                            if all_versions[version_str]['first_used'] is None:
                                all_versions[version_str]['first_used'] = first_used
                            elif first_used < all_versions[version_str]['first_used']:
                                all_versions[version_str]['first_used'] = first_used
                        
                        # Track latest last_used
                        last_used = ver.get('last_used')
                        if last_used:
                            if all_versions[version_str]['last_used'] is None:
                                all_versions[version_str]['last_used'] = last_used
                            elif last_used > all_versions[version_str]['last_used']:
                                all_versions[version_str]['last_used'] = last_used
                        
            except Exception as e:
                tqdm.write(f"Warning: Failed to get analysis versions from {instance_name}: {str(e)}")
                continue
        
        # Convert to list and sort by snapshot count
        result = list(all_versions.values())
        result.sort(key=lambda x: x['snapshot_count'], reverse=True)
        
        # Return top N
        return result[:limit]


if __name__ == "__main__":
    # Example usage
    multi_metrics = MultiInstanceMetrics('config.json')
    
    tqdm.write("\n" + "="*80)
    tqdm.write("Multi-Instance Coverity Metrics")
    tqdm.write("="*80)
    
    # Print configured instances
    tqdm.write(f"\nConfigured Instances: {', '.join(multi_metrics.get_instance_names())}")
    
    # Print aggregated summary
    tqdm.write("\nAggregated Summary:")
    summary = multi_metrics.get_aggregated_summary()
    for key, value in summary.items():
        tqdm.write(f"  {key}: {value}")
    
    # Print defects by instance
    tqdm.write("\nDefects by Instance:")
    by_instance = multi_metrics.get_defects_by_instance()
    tqdm.write(by_instance.to_string(index=False))
    
    # Print all projects
    tqdm.write("\nAll Projects Across Instances:")
    all_projects = multi_metrics.get_all_projects()
    if not all_projects.empty:
        tqdm.write(f"  Total projects: {len(all_projects)}")
        tqdm.write(all_projects[['project_name', 'instance_name']].to_string(index=False))

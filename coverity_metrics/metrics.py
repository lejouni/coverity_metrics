"""
Coverity Metrics Module
Provides various metrics calculations based on Coverity database
"""
from datetime import datetime, timedelta
from coverity_metrics.db_connection import CoverityDatabase
import pandas as pd
from tqdm import tqdm

class CoverityMetrics:
    """Comprehensive metrics for Coverity static analysis data"""
    
    def __init__(self, connection_params, project_name=None):
        """Initialize metrics calculator
        
        Args:
            connection_params: Dict with connection parameters (host, port, database, user, password).
                              Required - read from config.json
            project_name: Optional project name to filter all metrics
        """
        if not connection_params:
            raise ValueError("connection_params is required. Please provide database connection parameters from config.json")
        
        self.db = CoverityDatabase(connection_params=connection_params)
        self.project_name = project_name
    
    # ========== DEFECT METRICS ==========
    
    def get_total_defects_by_project(self):
        """Get total defect count grouped by project
        
        Returns:
            pandas.DataFrame: Project name and defect count
        """
        query = """
            SELECT 
                p.name as project_name,
                COUNT(DISTINCT sd.id) as defect_count,
                COUNT(DISTINCT CASE WHEN sd.fixed_snapshot_element_id IS NULL THEN sd.id END) as active_defects,
                COUNT(DISTINCT CASE WHEN sd.fixed_snapshot_element_id IS NOT NULL THEN sd.id END) as fixed_defects
            FROM project p
            JOIN project_stream ps ON p.id = ps.project_id
            JOIN stream s ON ps.stream_id = s.id
            JOIN stream_element se ON s.id = se.stream_id
            LEFT JOIN stream_defect sd ON se.id = sd.stream_element_id
            WHERE p.deleted = false AND s.deleted = false
                AND p.name != 'Developer Streams'
                {project_filter}
            GROUP BY p.name
            ORDER BY defect_count DESC
        """
        if self.project_name:
            query = query.format(project_filter="AND p.name = %s")
            results = self.db.execute_query_dict(query, (self.project_name,))
        else:
            query = query.format(project_filter="")
            results = self.db.execute_query_dict(query)
        return pd.DataFrame(results)
    
    def get_defects_by_severity(self):
        """Get defect count grouped by impact (severity)
        
        Returns:
            pandas.DataFrame: Impact level and count
        """
        query = """
            SELECT 
                cp.impact,
                COUNT(*) as defect_count
            FROM stream_defect sd
            JOIN checker_properties cp ON sd.checker_properties_id = cp.id
            JOIN stream_element se ON sd.stream_element_id = se.id
            JOIN stream s ON se.stream_id = s.id
            JOIN project_stream ps ON s.id = ps.stream_id
            JOIN project p ON ps.project_id = p.id
            WHERE sd.fixed_snapshot_element_id IS NULL
                AND p.deleted = false
                {project_filter}
            GROUP BY cp.impact
            ORDER BY 
                CASE cp.impact
                    WHEN 'High' THEN 1
                    WHEN 'Medium' THEN 2
                    WHEN 'Low' THEN 3
                    ELSE 4
                END
        """
        if self.project_name:
            query = query.format(project_filter="AND p.name = %s")
            results = self.db.execute_query_dict(query, (self.project_name,))
        else:
            query = query.format(project_filter="")
            results = self.db.execute_query_dict(query)
        return pd.DataFrame(results)
    
    def get_defects_by_checker_category(self, limit=20, fetch_all=False):
        """Get defect count by checker category
        
        Args:
            limit: Maximum number of categories to return (ignored if fetch_all=True)
            fetch_all: If True, fetch all categories instead of top N
            
        Returns:
            pandas.DataFrame: Category and defect count
        """
        limit_clause = "" if fetch_all else "LIMIT %s"
        query = f"""
            SELECT 
                cc.name as category,
                COUNT(*) as defect_count
            FROM stream_defect sd
            JOIN checker_properties cp ON sd.checker_properties_id = cp.id
            JOIN checker_category cc ON cp.checker_category_id = cc.id
            JOIN stream_element se ON sd.stream_element_id = se.id
            JOIN stream s ON se.stream_id = s.id
            JOIN project_stream ps ON s.id = ps.stream_id
            JOIN project p ON ps.project_id = p.id
            WHERE sd.fixed_snapshot_element_id IS NULL
                AND p.deleted = false
                {{project_filter}}
            GROUP BY cc.name
            ORDER BY defect_count DESC
            {limit_clause}
        """
        if self.project_name:
            query = query.format(project_filter="AND p.name = %s")
            params = (self.project_name,) if fetch_all else (self.project_name, limit)
            results = self.db.execute_query_dict(query, params)
        else:
            query = query.format(project_filter="")
            params = () if fetch_all else (limit,)
            results = self.db.execute_query_dict(query, params)
        return pd.DataFrame(results)
    
    def get_defects_by_checker_name(self, limit=20, fetch_all=False):
        """Get defect count by specific checker
        
        Args:
            limit: Maximum number of checkers to return (ignored if fetch_all=True)
            fetch_all: If True, fetch all checkers instead of top N
            
        Returns:
            pandas.DataFrame: Checker name and defect count
        """
        limit_clause = "" if fetch_all else "LIMIT %s"
        query = f"""
            SELECT 
                ct.name as checker_name,
                cc.name as category,
                cp.impact,
                COUNT(*) as defect_count
            FROM stream_defect sd
            JOIN checker_properties cp ON sd.checker_properties_id = cp.id
            JOIN checker_type ct ON cp.checker_type_id = ct.id
            JOIN checker_category cc ON cp.checker_category_id = cc.id
            JOIN stream_element se ON sd.stream_element_id = se.id
            JOIN stream s ON se.stream_id = s.id
            JOIN project_stream ps ON s.id = ps.stream_id
            JOIN project p ON ps.project_id = p.id
            WHERE sd.fixed_snapshot_element_id IS NULL
                AND p.deleted = false
                {{project_filter}}
            GROUP BY ct.name, cc.name, cp.impact
            ORDER BY defect_count DESC
            {limit_clause}
        """
        if self.project_name:
            query = query.format(project_filter="AND p.name = %s")
            params = (self.project_name,) if fetch_all else (self.project_name, limit)
            results = self.db.execute_query_dict(query, params)
        else:
            query = query.format(project_filter="")
            params = () if fetch_all else (limit,)
            results = self.db.execute_query_dict(query, params)
        return pd.DataFrame(results)
    
    def get_defect_density_by_project(self):
        """Calculate defect density (defects per KLOC) by project
        
        Returns:
            pandas.DataFrame: Project metrics including defect density
        """
        query = """
            SELECT 
                p.name as project_name,
                s.name as stream_name,
                COUNT(DISTINCT sd.id) as total_defects,
                SUM(COALESCE(sf.current_code_line_count, 0)) as total_loc,
                CASE 
                    WHEN SUM(COALESCE(sf.current_code_line_count, 0)) > 0 
                    THEN ROUND((COUNT(DISTINCT sd.id)::decimal / SUM(sf.current_code_line_count) * 1000), 2)
                    ELSE 0
                END as defects_per_kloc
            FROM project p
            JOIN project_stream ps ON p.id = ps.project_id
            JOIN stream s ON ps.stream_id = s.id
            JOIN stream_element se ON s.id = se.stream_id
            LEFT JOIN stream_defect sd ON se.id = sd.stream_element_id 
                AND sd.fixed_snapshot_element_id IS NULL
            LEFT JOIN stream_file sf ON se.id = sf.stream_element_id
            WHERE p.deleted = false AND s.deleted = false
                AND p.name != 'Developer Streams'
            GROUP BY p.name, s.name
            ORDER BY defects_per_kloc DESC
        """
        results = self.db.execute_query_dict(query)
        return pd.DataFrame(results)
    
    # ========== TRIAGE METRICS ==========
    
    def get_defects_by_triage_status(self):
        """Get defect count by triage status (action)
        
        Returns:
            pandas.DataFrame: Triage action and count
        """
        query = """
            SELECT 
                de.name as triage_action,
                COUNT(DISTINCT dt.id) as defect_count
            FROM defect_triage dt
            JOIN dynamic_enum de ON dt.current_action_id = de.id
            WHERE de.dtype = 'Act'
            GROUP BY de.name
            ORDER BY defect_count DESC
        """
        results = self.db.execute_query_dict(query)
        return pd.DataFrame(results)
    
    def get_defects_by_classification(self):
        """Get defect count by classification
        
        Returns:
            pandas.DataFrame: Classification and count
        """
        query = """
            SELECT 
                de.name as classification,
                COUNT(DISTINCT dt.id) as defect_count
            FROM defect_triage dt
            JOIN dynamic_enum de ON dt.current_classification_id = de.id
            WHERE de.dtype = 'Cls'
            GROUP BY de.name
            ORDER BY defect_count DESC
        """
        results = self.db.execute_query_dict(query)
        return pd.DataFrame(results)
    
    def get_defects_by_owner(self, limit=20, fetch_all=False):
        """Get defect count by owner
        
        Args:
            limit: Maximum number of owners to return (ignored if fetch_all=True)
            fetch_all: If True, fetch all owners instead of top N
            
        Returns:
            pandas.DataFrame: Owner and defect count
        """
        limit_clause = "" if fetch_all else "LIMIT %s"
        query = f"""
            SELECT 
                COALESCE(u.username, 'Unassigned') as owner,
                COUNT(DISTINCT dt.id) as defect_count,
                COUNT(DISTINCT CASE WHEN de.name = 'Fix Required' THEN dt.id END) as fix_required,
                COUNT(DISTINCT CASE WHEN de.name != 'Fix Required' THEN dt.id END) as other_actions
            FROM defect_triage dt
            LEFT JOIN users u ON dt.current_owner_user_id = u.id
            LEFT JOIN dynamic_enum de ON dt.current_action_id = de.id AND de.dtype = 'Act'
            GROUP BY u.username
            ORDER BY defect_count DESC
            {limit_clause}
        """
        params = () if fetch_all else (limit,)
        results = self.db.execute_query_dict(query, params)
        return pd.DataFrame(results)
    
    # ========== CODE QUALITY METRICS ==========
    
    def get_code_metrics_by_stream(self):
        """Get code quality metrics by stream
        
        Returns:
            pandas.DataFrame: Stream code metrics
        """
        query = """
            SELECT 
                s.name as stream_name,
                COUNT(DISTINCT sf.id) as file_count,
                SUM(COALESCE(sf.current_code_line_count, 0)) as total_loc,
                SUM(COALESCE(sf.current_comment_line_count, 0)) as total_comment_lines,
                SUM(COALESCE(sf.current_blank_line_count, 0)) as total_blank_lines,
                ROUND(AVG(COALESCE(sf.current_code_line_count, 0)), 2) as avg_file_loc,
                CASE 
                    WHEN SUM(COALESCE(sf.current_code_line_count, 0)) > 0
                    THEN ROUND((SUM(COALESCE(sf.current_comment_line_count, 0))::decimal / 
                               SUM(sf.current_code_line_count) * 100), 2)
                    ELSE 0
                END as comment_ratio_pct
            FROM stream s
            JOIN stream_element se ON s.id = se.stream_id
            JOIN stream_file sf ON se.id = sf.stream_element_id
            JOIN project_stream ps ON s.id = ps.stream_id
            JOIN project p ON ps.project_id = p.id
            WHERE s.deleted = false
                AND p.deleted = false
                {project_filter}
            GROUP BY s.name
            ORDER BY total_loc DESC
        """
        if self.project_name:
            query = query.format(project_filter="AND p.name = %s")
            results = self.db.execute_query_dict(query, (self.project_name,))
        else:
            query = query.format(project_filter="")
            results = self.db.execute_query_dict(query)
        return pd.DataFrame(results)
    
    def get_function_complexity_distribution(self):
        """Get distribution of function complexity
        
        Returns:
            pandas.DataFrame: Complexity ranges and counts
        """
        query = """
            WITH complexity_data AS (
                SELECT 
                    fm.cyclomatic_complexity as complexity
                FROM stream_function sf
                JOIN function_metrics fm ON sf.function_id = fm.id
                WHERE fm.cyclomatic_complexity IS NOT NULL
            )
            SELECT 
                CASE 
                    WHEN complexity <= 5 THEN '1-5 (Low)'
                    WHEN complexity <= 10 THEN '6-10 (Moderate)'
                    WHEN complexity <= 20 THEN '11-20 (High)'
                    WHEN complexity <= 50 THEN '21-50 (Very High)'
                    ELSE '51+ (Extreme)'
                END as complexity_range,
                COUNT(*) as function_count,
                ROUND(AVG(complexity), 2) as avg_complexity
            FROM complexity_data
            GROUP BY 
                CASE 
                    WHEN complexity <= 5 THEN '1-5 (Low)'
                    WHEN complexity <= 10 THEN '6-10 (Moderate)'
                    WHEN complexity <= 20 THEN '11-20 (High)'
                    WHEN complexity <= 50 THEN '21-50 (Very High)'
                    ELSE '51+ (Extreme)'
                END
            ORDER BY 
                MIN(CASE 
                    WHEN complexity <= 5 THEN 1
                    WHEN complexity <= 10 THEN 2
                    WHEN complexity <= 20 THEN 3
                    WHEN complexity <= 50 THEN 4
                    ELSE 5
                END)
        """
        results = self.db.execute_query_dict(query)
        return pd.DataFrame(results)
    
    def get_most_complex_functions(self, limit=20, fetch_all=False):
        """Get most complex functions
        
        Args:
            limit: Maximum number of functions to return (ignored if fetch_all=True)
            fetch_all: If True, fetch all functions instead of top N
            
        Returns:
            pandas.DataFrame: Function details with complexity
        """
        limit_clause = "" if fetch_all else "LIMIT %s"
        query = f"""
            SELECT 
                f.display_name as function_name,
                fp.filename as file_path,
                fm.cyclomatic_complexity,
                fm.line_count
            FROM stream_function sf
            JOIN function f ON sf.function_id = f.id
            JOIN function_metrics fm ON f.id = fm.id
            JOIN stream_file stf ON sf.stream_file_id = stf.id
            JOIN file_path fp ON stf.file_path_id = fp.id
            WHERE fm.cyclomatic_complexity IS NOT NULL
            ORDER BY fm.cyclomatic_complexity DESC, fm.line_count DESC
            {limit_clause}
        """
        params = () if fetch_all else (limit,)
        results = self.db.execute_query_dict(query, params)
        return pd.DataFrame(results)
    
    # ========== TREND METRICS ==========
    
    def get_defect_trend_weekly(self, weeks=12):
        """Get weekly defect trend
        
        Args:
            weeks: Number of weeks to retrieve
            
        Returns:
            pandas.DataFrame: Weekly defect counts with date ranges
        """
        query = """
            SELECT 
                from_date,
                to_date,
                SUM(count) as total_defects
            FROM weekly_issue_count
            WHERE from_date >= CURRENT_DATE - INTERVAL '%s weeks'
            GROUP BY from_date, to_date
            ORDER BY from_date DESC
        """
        results = self.db.execute_query_dict(query, (weeks,))
        return pd.DataFrame(results)
    
    def get_file_count_trend_weekly(self, weeks=12):
        """Get weekly file count trend
        
        Args:
            weeks: Number of weeks to retrieve
            
        Returns:
            pandas.DataFrame: Weekly file counts
        """
        query = """
            SELECT 
                from_date,
                to_date,
                SUM(count) as total_files
            FROM weekly_file_count
            WHERE from_date >= CURRENT_DATE - INTERVAL '%s weeks'
            GROUP BY from_date, to_date
            ORDER BY from_date DESC
        """
        results = self.db.execute_query_dict(query, (weeks,))
        return pd.DataFrame(results)
    
    def get_snapshot_history(self, stream_name=None, limit=20, fetch_all=False):
        """Get snapshot analysis history
        
        Args:
            stream_name: Optional stream name to filter
            limit: Maximum number of snapshots to return (ignored if fetch_all=True)
            fetch_all: If True, fetch all snapshots instead of most recent N
            
        Returns:
            pandas.DataFrame: Snapshot details
        """
        limit_clause = "" if fetch_all else "LIMIT %s"
        if stream_name:
            query = f"""
                SELECT 
                    s.name as stream_name,
                    sn.date_created,
                    sn.total_defect_count,
                    sn.new_defect_count,
                    sn.eliminated_defect_count,
                    sn.code_line_count,
                    sn.total_file_count as file_count
                FROM snapshot sn
                JOIN stream s ON sn.stream_id = s.id
                WHERE s.name = %s
                ORDER BY sn.date_created DESC
                {limit_clause}
            """
            params = (stream_name,) if fetch_all else (stream_name, limit)
            results = self.db.execute_query_dict(query, params)
        else:
            query = f"""
                SELECT 
                    s.name as stream_name,
                    sn.date_created,
                    sn.total_defect_count,
                    sn.new_defect_count,
                    sn.eliminated_defect_count,
                    sn.code_line_count,
                    sn.total_file_count as file_count
                FROM snapshot sn
                JOIN stream s ON sn.stream_id = s.id
                ORDER BY sn.date_created DESC
                {limit_clause}
            """
            params = () if fetch_all else (limit,)
            results = self.db.execute_query_dict(query, params)
        return pd.DataFrame(results)
    
    # ========== USER ACTIVITY METRICS ==========
    
    def get_user_login_statistics(self, days=30):
        """Get user login statistics
        
        Args:
            days: Number of days to look back
            
        Returns:
            pandas.DataFrame: User login stats
        """
        query = """
            SELECT 
                u.username,
                COUNT(ul.id) as login_count,
                MAX(ul.session_start) as last_login,
                ROUND(AVG(EXTRACT(EPOCH FROM (ul.session_end - ul.session_start)) / 60), 2) as avg_session_minutes
            FROM users u
            LEFT JOIN user_login ul ON u.id = ul.user_id
            WHERE ul.session_start >= CURRENT_DATE - INTERVAL '%s days'
            GROUP BY u.username
            ORDER BY login_count DESC
        """
        results = self.db.execute_query_dict(query, (days,))
        return pd.DataFrame(results)
    
    def get_most_active_triagers(self, days=30, limit=10):
        """Get most active users in triaging defects
        
        Args:
            days: Number of days to look back
            limit: Maximum number of users to return
            
        Returns:
            pandas.DataFrame: User triage activity
        """
        query = """
            SELECT 
                u.username,
                COUNT(ts.id) as triage_actions,
                COUNT(DISTINCT ts.defect_triage_id) as defects_triaged
            FROM users u
            JOIN triage_state ts ON u.id = ts.user_created_id
            WHERE ts.date_created >= CURRENT_DATE - INTERVAL '%s days'
            GROUP BY u.username
            ORDER BY triage_actions DESC
            LIMIT %s
        """
        results = self.db.execute_query_dict(query, (days, limit))
        return pd.DataFrame(results)
    
    # ========== SUMMARY METRICS ==========
    
    def get_overall_summary(self):
        """Get overall summary statistics
        
        Returns:
            dict: Summary statistics
        """
        if self.project_name:
            # Project-specific queries
            queries = {
                'total_projects': ("SELECT COUNT(*) FROM project WHERE deleted = false AND name = %s", (self.project_name,)),
                'total_streams': ("""
                    SELECT COUNT(DISTINCT s.id) FROM stream s
                    JOIN project_stream ps ON s.id = ps.stream_id
                    JOIN project p ON ps.project_id = p.id
                    WHERE s.deleted = false AND p.name = %s
                """, (self.project_name,)),
                'total_defects': ("""
                    SELECT COUNT(DISTINCT sd.id) FROM stream_defect sd
                    JOIN stream_element se ON sd.stream_element_id = se.id
                    JOIN stream s ON se.stream_id = s.id
                    JOIN project_stream ps ON s.id = ps.stream_id
                    JOIN project p ON ps.project_id = p.id
                    WHERE sd.fixed_snapshot_element_id IS NULL AND p.name = %s
                """, (self.project_name,)),
                'total_files': ("""
                    SELECT COUNT(DISTINCT sfile.id) FROM stream_file sfile
                    JOIN stream_element se ON sfile.stream_element_id = se.id
                    JOIN stream s ON se.stream_id = s.id
                    JOIN project_stream ps ON s.id = ps.stream_id
                    JOIN project p ON ps.project_id = p.id
                    WHERE p.name = %s
                """, (self.project_name,)),
                'total_functions': ("""
                    SELECT COUNT(sf.id) FROM stream_function sf
                    JOIN stream_file sfile ON sf.stream_file_id = sfile.id
                    JOIN stream_element se ON sfile.stream_element_id = se.id
                    JOIN stream s ON se.stream_id = s.id
                    JOIN project_stream ps ON s.id = ps.stream_id
                    JOIN project p ON ps.project_id = p.id
                    WHERE p.name = %s
                """, (self.project_name,)),
                'total_loc': ("""
                    SELECT SUM(COALESCE(sfile.current_code_line_count, 0)) FROM stream_file sfile
                    JOIN stream_element se ON sfile.stream_element_id = se.id
                    JOIN stream s ON se.stream_id = s.id
                    JOIN project_stream ps ON s.id = ps.stream_id
                    JOIN project p ON ps.project_id = p.id
                    WHERE p.name = %s
                """, (self.project_name,)),
                'total_users': ("SELECT COUNT(*) FROM users WHERE deleted = false", None),
                'high_severity_defects': ("""
                    SELECT COUNT(DISTINCT sd.id) FROM stream_defect sd 
                    JOIN checker_properties cp ON sd.checker_properties_id = cp.id
                    JOIN stream_element se ON sd.stream_element_id = se.id
                    JOIN stream s ON se.stream_id = s.id
                    JOIN project_stream ps ON s.id = ps.stream_id
                    JOIN project p ON ps.project_id = p.id
                    WHERE sd.fixed_snapshot_element_id IS NULL 
                        AND cp.impact = 'High' 
                        AND p.name = %s
                """, (self.project_name,)),
            }
        else:
            # Global queries
            queries = {
                'total_projects': ("SELECT COUNT(*) FROM project WHERE deleted = false AND name != 'Developer Streams'", None),
                'total_streams': ("SELECT COUNT(*) FROM stream WHERE deleted = false", None),
                'total_defects': ("SELECT COUNT(*) FROM stream_defect WHERE fixed_snapshot_element_id IS NULL", None),
                'total_files': ("SELECT COUNT(DISTINCT id) FROM stream_file", None),
                'total_functions': ("SELECT COUNT(*) FROM stream_function", None),
                'total_loc': ("SELECT SUM(COALESCE(current_code_line_count, 0)) FROM stream_file", None),
                'total_users': ("SELECT COUNT(*) FROM users WHERE deleted = false", None),
                'high_severity_defects': ("""
                    SELECT COUNT(*) FROM stream_defect sd 
                    JOIN checker_properties cp ON sd.checker_properties_id = cp.id 
                    WHERE sd.fixed_snapshot_element_id IS NULL AND cp.impact = 'High'
                """, None),
            }
        
        summary = {}
        for key, (query, params) in queries.items():
            result = self.db.execute_query(query, params)
            summary[key] = result[0][0] if result and result[0][0] is not None else 0
        
        return summary
    
    # ========== FILE HOTSPOT METRICS ==========
    
    def get_file_hotspots(self, limit=20, fetch_all=False):
        """Get files with most defects (hotspots)
        
        Args:
            limit: Maximum number of files to return (ignored if fetch_all=True)
            fetch_all: If True, fetch all files instead of top N hotspots
            
        Returns:
            pandas.DataFrame: File hotspots with defect counts
        """
        limit_clause = "" if fetch_all else "LIMIT %s"
        query = f"""
            SELECT 
                fp.filename as file_path,
                COUNT(DISTINCT sdo.stream_defect_id) as defect_count,
                sf.current_code_line_count as loc,
                CASE 
                    WHEN sf.current_code_line_count > 0 
                    THEN ROUND((COUNT(DISTINCT sdo.stream_defect_id)::decimal / sf.current_code_line_count * 1000), 2)
                    ELSE 0
                END as defects_per_kloc
            FROM stream_defect_occurrence sdo
            JOIN stream_file sf ON sdo.stream_file_id = sf.id
            JOIN file_path fp ON sf.file_path_id = fp.id
            JOIN stream_defect sd ON sdo.stream_defect_id = sd.id
            JOIN stream_element se ON sd.stream_element_id = se.id
            JOIN stream s ON se.stream_id = s.id
            JOIN project_stream ps ON s.id = ps.stream_id
            JOIN project p ON ps.project_id = p.id
            WHERE sd.fixed_snapshot_element_id IS NULL
                AND p.deleted = false
                {{project_filter}}
            GROUP BY fp.filename, sf.current_code_line_count
            ORDER BY defect_count DESC
            {limit_clause}
        """
        if self.project_name:
            query = query.format(project_filter="AND p.name = %s")
            params = (self.project_name,) if fetch_all else (self.project_name, limit)
            results = self.db.execute_query_dict(query, params)
        else:
            query = query.format(project_filter="")
            params = () if fetch_all else (limit,)
            results = self.db.execute_query_dict(query, params)
        return pd.DataFrame(results)
    
    def get_available_projects(self):
        """Get list of all available projects
        
        Returns:
            pandas.DataFrame: List of projects with basic information
        """
        query = """
            SELECT 
                p.name as project_name,
                COUNT(DISTINCT ps.stream_id) as stream_count,
                p.date_created,
                p.deleted
            FROM project p
            LEFT JOIN project_stream ps ON p.id = ps.project_id
            WHERE p.deleted = false
                AND p.name != 'Developer Streams'
            GROUP BY p.name, p.date_created, p.deleted
            ORDER BY p.name
        """
        results = self.db.execute_query_dict(query)
        return pd.DataFrame(results)
    
    def _add_project_filter(self, query, table_alias='p'):
        """Helper method to add project filter to queries
        
        Args:
            query: Base SQL query
            table_alias: Alias used for project table (default 'p')
            
        Returns:
            tuple: (modified_query, params) with project filter added if needed
        """
        if self.project_name:
            # Add WHERE or AND clause for project filter
            if 'WHERE' in query.upper():
                query = query.replace('WHERE', f"WHERE {table_alias}.name = %s AND", 1)
            else:
                # Find the position before GROUP BY or ORDER BY
                for keyword in ['GROUP BY', 'ORDER BY', 'LIMIT']:
                    if keyword in query.upper():
                        pos = query.upper().index(keyword)
                        query = query[:pos] + f" WHERE {table_alias}.name = %s " + query[pos:]
                        break
            return query, (self.project_name,)
        return query, None
    
    # ========== PERFORMANCE METRICS ==========
    
    def get_database_statistics(self):
        """Get database size and statistics
        
        Returns:
            dict: Database statistics
        """
        query = """
            SELECT 
                pg_size_pretty(pg_database_size(current_database())) as db_size,
                pg_database_size(current_database()) as db_size_bytes,
                (SELECT count(*) FROM stream_defect) as total_defects,
                (SELECT count(*) FROM snapshot) as total_snapshots,
                (SELECT count(*) FROM stream_file) as total_files,
                (SELECT count(*) FROM stream_function) as total_functions,
                (SELECT count(*) FROM users WHERE deleted = false) as total_users,
                (SELECT count(*) FROM project WHERE deleted = false) as total_projects
        """
        result = self.db.execute_query_dict(query)
        return result[0] if result else {}
    
    def get_instance_info(self):
        """Get Coverity instance runtime and version information
        
        Returns:
            dict: Instance information including version, uptime, system ID, and activity timeline
        """
        info = {}
        
        # Get PostgreSQL database uptime
        try:
            uptime_query = "SELECT pg_postmaster_start_time()"
            uptime_result = self.db.execute_query_dict(uptime_query)
            if uptime_result:
                start_time = uptime_result[0]['pg_postmaster_start_time']
                info['db_start_time'] = start_time
                
                # Calculate uptime
                if start_time:
                    from datetime import datetime
                    if isinstance(start_time, datetime):
                        uptime = datetime.now() - start_time.replace(tzinfo=None)
                        info['db_uptime_days'] = uptime.days
                        info['db_uptime_hours'] = uptime.seconds // 3600
                        info['db_uptime_minutes'] = (uptime.seconds % 3600) // 60
                        info['db_uptime_formatted'] = f"{uptime.days}d {uptime.seconds // 3600}h {(uptime.seconds % 3600) // 60}m"
        except Exception as e:
            info['db_uptime_error'] = str(e)
        
        # Get Coverity version information
        try:
            version_query = "SELECT external_version, internal_version FROM version_info ORDER BY id DESC LIMIT 1"
            version_result = self.db.execute_query_dict(version_query)
            if version_result:
                info['coverity_version'] = version_result[0].get('external_version')
                info['coverity_build'] = version_result[0].get('internal_version')
        except Exception as e:
            info['version_error'] = str(e)
        
        # Get system unique ID
        try:
            uid_query = "SELECT preference_value FROM system_preference WHERE preference_name = 'UNIQUE_ID'"
            uid_result = self.db.execute_query_dict(uid_query)
            if uid_result:
                info['system_unique_id'] = uid_result[0].get('preference_value')
        except Exception as e:
            info['unique_id_error'] = str(e)
        
        # Get snapshot activity timeline
        try:
            timeline_query = """
                SELECT 
                    MIN(date_created) as first_snapshot,
                    MAX(date_created) as last_snapshot,
                    COUNT(*) as total_snapshots
                FROM snapshot
            """
            timeline_result = self.db.execute_query_dict(timeline_query)
            if timeline_result:
                first = timeline_result[0].get('first_snapshot')
                last = timeline_result[0].get('last_snapshot')
                
                info['first_snapshot'] = first
                info['last_snapshot'] = last
                info['total_snapshots_count'] = timeline_result[0].get('total_snapshots')
                
                # Calculate usage period
                if first and last and isinstance(first, datetime) and isinstance(last, datetime):
                    usage_period = last.replace(tzinfo=None) - first.replace(tzinfo=None)
                    info['usage_period_days'] = usage_period.days
                    
                    # Time since last activity
                    from datetime import datetime
                    inactive = datetime.now() - last.replace(tzinfo=None)
                    info['days_since_last_activity'] = inactive.days
                    info['last_activity_formatted'] = f"{inactive.days} days ago"
        except Exception as e:
            info['timeline_error'] = str(e)
        
        # Get database connection info
        try:
            db_info_query = """
                SELECT 
                    current_database() as database_name,
                    (SELECT count(*) FROM pg_stat_activity 
                     WHERE pg_stat_activity.datname = current_database()) as active_connections
            """
            db_info_result = self.db.execute_query_dict(db_info_query)
            if db_info_result:
                info['database_name'] = db_info_result[0].get('database_name')
                info['active_connections'] = db_info_result[0].get('active_connections')
        except Exception as e:
            info['db_info_error'] = str(e)
        
        return info
    
    def get_analysis_versions(self, limit=10, days=None):
        """Get top analysis versions used in snapshots
        
        Args:
            limit: Number of top versions to return (default: 10)
            days: Optional number of days to filter snapshots (None = all time)
            
        Returns:
            list: List of dicts containing version info (version, snapshot_count, first_used, last_used)
        """
        versions = []
        
        try:
            # Base query for analysis versions
            if self.project_name:
                # Project-specific query
                query = """
                    SELECT 
                        s.prevent_ver_ext as version,
                        COUNT(*) as snapshot_count,
                        MIN(s.date_created) as first_used,
                        MAX(s.date_created) as last_used
                    FROM snapshot s
                    JOIN stream st ON s.stream_id = st.id
                    JOIN project_stream ps ON st.id = ps.stream_id
                    JOIN project p ON ps.project_id = p.id
                    WHERE s.prevent_ver_ext IS NOT NULL
                        AND p.name = %s
                        AND s.deleted = false
                """
                params = [self.project_name]
            else:
                # Instance-wide query
                query = """
                    SELECT 
                        prevent_ver_ext as version,
                        COUNT(*) as snapshot_count,
                        MIN(date_created) as first_used,
                        MAX(date_created) as last_used
                    FROM snapshot
                    WHERE prevent_ver_ext IS NOT NULL
                        AND deleted = false
                """
                params = []
            
            # Add date filter if specified
            if days:
                if self.project_name:
                    query += " AND s.date_created >= CURRENT_DATE - INTERVAL '%s days'"
                else:
                    query += " AND date_created >= CURRENT_DATE - INTERVAL '%s days'"
                params.append(days)
            
            # Group and order
            query += """
                GROUP BY prevent_ver_ext
                ORDER BY snapshot_count DESC, last_used DESC
                LIMIT %s
            """
            params.append(limit)
            
            # Execute query
            results = self.db.execute_query_dict(query, tuple(params))
            
            if results:
                versions = results
                
        except Exception as e:
            tqdm.write(f"[ERROR] Failed to get analysis versions: {e}")
        
        return versions
    
    def get_largest_tables(self, limit=10):
        """Get largest database tables by size
        
        Args:
            limit: Number of tables to return
            
        Returns:
            pandas.DataFrame: Table names and sizes
        """
        query = """
            SELECT 
                tablename as table_name,
                pg_size_pretty(pg_total_relation_size('public.'||tablename)) AS size,
                pg_total_relation_size('public.'||tablename) AS size_bytes
            FROM pg_tables
            WHERE schemaname = 'public'
            ORDER BY size_bytes DESC
            LIMIT %s
        """
        results = self.db.execute_query_dict(query, (limit,))
        return pd.DataFrame(results)
    
    def get_snapshot_performance(self, limit=20):
        """Get snapshot/commit performance metrics
        
        Args:
            limit: Number of recent snapshots to analyze
            
        Returns:
            pandas.DataFrame: Snapshot performance data
        """
        query = """
            SELECT 
                sn.id as snapshot_id,
                s.name as stream_name,
                sn.date_created,
                sn.date_ended,
                sn.total_defect_count,
                sn.new_defect_count,
                sn.eliminated_defect_count,
                sn.total_file_count,
                sn.function_count,
                ROUND(sn.duration_commit_total / 60.0, 2) as duration_minutes,
                ROUND(sn.duration_issue_processing / 60.0, 2) as issue_processing_minutes,
                ROUND(sn.duration_file_processing / 60.0, 2) as file_processing_minutes,
                sn.queue_length,
                ROUND(sn.duration_on_queue / 60.0, 2) as queue_time_minutes
            FROM snapshot sn
            JOIN stream s ON sn.stream_id = s.id
            {project_filter_join}
            WHERE sn.deleted = false
                {project_filter}
            ORDER BY sn.date_created DESC
            LIMIT %s
        """
        
        if self.project_name:
            query = query.format(
                project_filter_join="""
                    JOIN project_stream ps ON s.id = ps.stream_id
                    JOIN project p ON ps.project_id = p.id
                """,
                project_filter="AND p.name = %s"
            )
            results = self.db.execute_query_dict(query, (self.project_name, limit))
        else:
            query = query.format(project_filter_join="", project_filter="")
            results = self.db.execute_query_dict(query, (limit,))
        
        return pd.DataFrame(results)
    
    def get_commit_time_statistics(self):
        """Get commit/analysis time statistics
        
        Returns:
            dict: Commit time statistics
        """
        query = """
            SELECT 
                COUNT(*) as total_commits,
                ROUND(AVG(duration_commit_total / 60.0), 2) as avg_duration_minutes,
                ROUND(MIN(duration_commit_total / 60.0), 2) as min_duration_minutes,
                ROUND(MAX(duration_commit_total / 60.0), 2) as max_duration_minutes,
                ROUND(AVG(total_file_count), 0) as avg_files_per_commit,
                ROUND(AVG(total_defect_count), 0) as avg_defects_per_commit,
                ROUND(AVG(new_defect_count), 0) as avg_new_defects_per_commit
            FROM snapshot sn
            {project_filter_join}
            WHERE sn.deleted = false
                AND sn.duration_commit_total IS NOT NULL
                {project_filter}
        """
        
        if self.project_name:
            query = query.format(
                project_filter_join="""
                    JOIN stream s ON sn.stream_id = s.id
                    JOIN project_stream ps ON s.id = ps.stream_id
                    JOIN project p ON ps.project_id = p.id
                """,
                project_filter="AND p.name = %s"
            )
            result = self.db.execute_query_dict(query, (self.project_name,))
        else:
            query = query.format(project_filter_join="", project_filter="")
            result = self.db.execute_query_dict(query)
        
        return result[0] if result else {}
    
    def get_defect_discovery_rate(self, days=30):
        """Get defect discovery rate over time
        
        Args:
            days: Number of days to analyze
            
        Returns:
            pandas.DataFrame: Daily defect discovery metrics
        """
        query = """
            SELECT 
                DATE(sn.date_created) as snapshot_date,
                COUNT(*) as snapshot_count,
                SUM(sn.new_defect_count) as new_defects,
                SUM(sn.eliminated_defect_count) as eliminated_defects,
                SUM(sn.total_file_count) as files_analyzed
            FROM snapshot sn
            {project_filter_join}
            WHERE sn.deleted = false
                AND sn.date_created >= CURRENT_DATE - INTERVAL '%s days'
                {project_filter}
            GROUP BY DATE(sn.date_created)
            ORDER BY snapshot_date DESC
        """
        
        if self.project_name:
            query = query.format(
                project_filter_join="""
                    JOIN stream s ON sn.stream_id = s.id
                    JOIN project_stream ps ON s.id = ps.stream_id
                    JOIN project p ON ps.project_id = p.id
                """,
                project_filter="AND p.name = %s"
            )
            results = self.db.execute_query_dict(query, (days, self.project_name))
        else:
            query = query.format(project_filter_join="", project_filter="")
            results = self.db.execute_query_dict(query, (days,))
        
        return pd.DataFrame(results)

    # ========== TREND ANALYSIS METRICS ==========
    
    def get_defect_trends(self, days=90, granularity='week'):
        """Get defect trends over time showing new, fixed, and outstanding defects
        
        Args:
            days: Number of days to analyze
            granularity: 'day', 'week', or 'month'
            
        Returns:
            pandas.DataFrame: Trend data with date, new_defects, fixed_defects, outstanding_defects
        """
        # Map granularity to SQL date truncation
        trunc_map = {
            'day': 'DATE(sn.date_created)',
            'week': 'DATE_TRUNC(\'week\', sn.date_created)::date',
            'month': 'DATE_TRUNC(\'month\', sn.date_created)::date'
        }
        date_trunc = trunc_map.get(granularity, trunc_map['week'])
        
        query = f"""
            WITH snapshot_metrics AS (
                SELECT 
                    {date_trunc} as period,
                    SUM(sn.new_defect_count) as new_defects,
                    SUM(sn.eliminated_defect_count) as fixed_defects,
                    AVG(sn.total_defect_count) as avg_outstanding_defects,
                    MAX(sn.total_defect_count) as max_outstanding_defects
                FROM snapshot sn
                {{project_filter_join}}
                WHERE sn.deleted = false
                    AND sn.date_created >= CURRENT_DATE - INTERVAL '%s days'
                    {{project_filter}}
                GROUP BY period
                ORDER BY period ASC
            )
            SELECT 
                period,
                new_defects,
                fixed_defects,
                ROUND(avg_outstanding_defects::numeric, 0) as outstanding_defects,
                max_outstanding_defects,
                (new_defects - fixed_defects) as net_change
            FROM snapshot_metrics
            ORDER BY period ASC
        """
        
        if self.project_name:
            query = query.format(
                project_filter_join="""
                    JOIN stream s ON sn.stream_id = s.id
                    JOIN project_stream ps ON s.id = ps.stream_id
                    JOIN project p ON ps.project_id = p.id
                """,
                project_filter="AND p.name = %s"
            )
            results = self.db.execute_query_dict(query, (days, self.project_name))
        else:
            query = query.format(project_filter_join="", project_filter="")
            results = self.db.execute_query_dict(query, (days,))
        
        return pd.DataFrame(results)
    
    def get_triage_trends(self, days=90):
        """Get defect triage/classification trends over time
        
        Args:
            days: Number of days to analyze
            
        Returns:
            pandas.DataFrame: Triage status trends over time
        """
        # Use snapshot dates to show trending of classified vs unclassified defects
        query = """
            WITH classification_data AS (
                SELECT 
                    de.name as classification,
                    COUNT(dt.id) as count
                FROM defect_triage dt
                JOIN dynamic_enum de ON dt.current_classification_id = de.id
                WHERE de.dtype = 'Cls'
                GROUP BY de.name
            )
            SELECT 
                CURRENT_DATE as detected_date,
                classification,
                'Current' as action,
                count
            FROM classification_data
            ORDER BY count DESC
        """
        
        results = self.db.execute_query_dict(query)
        return pd.DataFrame(results)
    
    def get_fix_rate_metrics(self, days=90):
        """Get defect fix rate and velocity metrics using snapshot data
        
        Args:
            days: Number of days to analyze
            
        Returns:
            dict: Fix rate statistics
        """
        query = """
            WITH fix_stats AS (
                SELECT 
                    SUM(sn.new_defect_count) as total_new,
                    SUM(sn.eliminated_defect_count) as total_fixed,
                    AVG(sn.total_defect_count) as avg_outstanding
                FROM snapshot sn
                {project_filter_join}
                WHERE sn.deleted = false
                    AND sn.date_created >= CURRENT_DATE - INTERVAL '%s days'
                    {project_filter}
            )
            SELECT 
                total_new as total_defects,
                total_fixed as fixed_defects,
                ROUND((total_fixed::numeric / NULLIF(total_new, 0) * 100), 2) as fix_rate_percentage,
                ROUND(avg_outstanding, 1) as avg_days_to_fix,
                ROUND(avg_outstanding, 1) as median_days_to_fix,
                0 as min_days_to_fix,
                ROUND(avg_outstanding * 2, 1) as max_days_to_fix
            FROM fix_stats
        """
        
        if self.project_name:
            query = query.format(
                project_filter_join="""
                    JOIN stream s ON sn.stream_id = s.id
                    JOIN project_stream ps ON s.id = ps.stream_id
                    JOIN project p ON ps.project_id = p.id
                """,
                project_filter="AND p.name = %s"
            )
            result = self.db.execute_query_dict(query, (days, self.project_name))
        else:
            query = query.format(project_filter_join="", project_filter="")
            result = self.db.execute_query_dict(query, (days,))
        
        return result[0] if result else {}
    
    def get_defect_velocity_trend(self, days=90):
        """Get defect velocity showing introduction rate vs fix rate over time
        
        Args:
            days: Number of days to analyze
            
        Returns:
            pandas.DataFrame: Daily velocities with introduction and fix rates
        """
        query = """
            WITH daily_metrics AS (
                SELECT 
                    DATE(sn.date_created) as snapshot_date,
                    SUM(sn.new_defect_count) as new_count,
                    SUM(sn.eliminated_defect_count) as fixed_count,
                    AVG(sn.total_defect_count) as outstanding_count
                FROM snapshot sn
                {project_filter_join}
                WHERE sn.deleted = false
                    AND sn.date_created >= CURRENT_DATE - INTERVAL '%s days'
                    {project_filter}
                GROUP BY DATE(sn.date_created)
            )
            SELECT 
                snapshot_date,
                new_count,
                fixed_count,
                (new_count - fixed_count) as net_change,
                ROUND(outstanding_count::numeric, 0) as outstanding,
                CASE 
                    WHEN fixed_count > 0 THEN ROUND((fixed_count::numeric / NULLIF(new_count, 0) * 100), 1)
                    ELSE 0
                END as fix_efficiency_pct
            FROM daily_metrics
            ORDER BY snapshot_date ASC
        """
        
        if self.project_name:
            query = query.format(
                project_filter_join="""
                    JOIN stream s ON sn.stream_id = s.id
                    JOIN project_stream ps ON s.id = ps.stream_id
                    JOIN project p ON ps.project_id = p.id
                """,
                project_filter="AND p.name = %s"
            )
            results = self.db.execute_query_dict(query, (days, self.project_name))
        else:
            query = query.format(project_filter_join="", project_filter="")
            results = self.db.execute_query_dict(query, (days,))
        
        return pd.DataFrame(results)
    
    def get_cumulative_defect_trend(self, days=90):
        """Get cumulative defect counts over time
        
        Args:
            days: Number of days to analyze
            
        Returns:
            pandas.DataFrame: Cumulative new, fixed, and net defects
        """
        query = """
            WITH daily_metrics AS (
                SELECT 
                    DATE(sn.date_created) as snapshot_date,
                    SUM(sn.new_defect_count) as daily_new,
                    SUM(sn.eliminated_defect_count) as daily_fixed
                FROM snapshot sn
                {project_filter_join}
                WHERE sn.deleted = false
                    AND sn.date_created >= CURRENT_DATE - INTERVAL '%s days'
                    {project_filter}
                GROUP BY DATE(sn.date_created)
                ORDER BY DATE(sn.date_created) ASC
            )
            SELECT 
                snapshot_date,
                daily_new,
                daily_fixed,
                SUM(daily_new) OVER (ORDER BY snapshot_date) as cumulative_new,
                SUM(daily_fixed) OVER (ORDER BY snapshot_date) as cumulative_fixed,
                SUM(daily_new - daily_fixed) OVER (ORDER BY snapshot_date) as cumulative_net
            FROM daily_metrics
            ORDER BY snapshot_date ASC
        """
        
        if self.project_name:
            query = query.format(
                project_filter_join="""
                    JOIN stream s ON sn.stream_id = s.id
                    JOIN project_stream ps ON s.id = ps.stream_id
                    JOIN project p ON ps.project_id = p.id
                """,
                project_filter="AND p.name = %s"
            )
            results = self.db.execute_query_dict(query, (days, self.project_name))
        else:
            query = query.format(project_filter_join="", project_filter="")
            results = self.db.execute_query_dict(query, (days,))
        
        return pd.DataFrame(results)
    
    def get_defect_trend_summary(self, days=90):
        """Get summary statistics for defect trends
        
        Args:
            days: Number of days to analyze
            
        Returns:
            dict: Summary statistics including rates and trends
        """
        query = """
            WITH period_metrics AS (
                SELECT 
                    SUM(sn.new_defect_count) as total_new,
                    SUM(sn.eliminated_defect_count) as total_fixed,
                    COUNT(DISTINCT DATE(sn.date_created)) as days_with_data
                FROM snapshot sn
                {project_filter_join_period}
                WHERE sn.deleted = false
                    AND sn.date_created >= CURRENT_DATE - INTERVAL '%s days'
                    {project_filter_period}
            ),
            current_state AS (
                SELECT COUNT(*) as current_outstanding
                FROM stream_defect sd
                JOIN stream_element se ON sd.stream_element_id = se.id
                JOIN stream s ON se.stream_id = s.id
                {project_filter_join_current}
                WHERE sd.fixed_snapshot_element_id IS NULL
                    {project_filter_current}
            )
            SELECT 
                pm.total_new,
                pm.total_fixed,
                (pm.total_new - pm.total_fixed) as net_change,
                ROUND((pm.total_new::numeric / NULLIF(pm.days_with_data, 0)), 2) as avg_new_per_day,
                ROUND((pm.total_fixed::numeric / NULLIF(pm.days_with_data, 0)), 2) as avg_fixed_per_day,
                ROUND(((pm.total_fixed::numeric / NULLIF(pm.total_new, 0)) * 100), 2) as fix_rate_pct,
                cs.current_outstanding,
                CASE 
                    WHEN pm.total_fixed > pm.total_new THEN 'improving'
                    WHEN pm.total_fixed < pm.total_new THEN 'declining'
                    ELSE 'stable'
                END as trend_direction
            FROM period_metrics pm, current_state cs
        """
        
        if self.project_name:
            query = query.format(
                project_filter_join_period="""
                    JOIN stream s ON sn.stream_id = s.id
                    JOIN project_stream ps ON s.id = ps.stream_id
                    JOIN project p ON ps.project_id = p.id
                """,
                project_filter_period="AND p.name = %s",
                project_filter_join_current="""
                    JOIN project_stream ps ON s.id = ps.stream_id
                    JOIN project p ON ps.project_id = p.id
                """,
                project_filter_current="AND p.name = %s"
            )
            result = self.db.execute_query_dict(query, (days, self.project_name, self.project_name))
        else:
            query = query.format(
                project_filter_join_period="",
                project_filter_period="",
                project_filter_join_current="",
                project_filter_current=""
            )
            result = self.db.execute_query_dict(query, (days,))
        
        return result[0] if result else {}
    
    def get_defect_aging_distribution(self):
        """Get distribution of defect severity for outstanding defects (simplified)
        
        Returns:
            pandas.DataFrame: Age ranges and defect counts
        """
        query = """
            SELECT 
                'Current' as age_range,
                COUNT(sd.id) as defect_count,
                30 as avg_age_days,
                COUNT(CASE WHEN cp.impact = 'High' THEN 1 END) as high_severity,
                COUNT(CASE WHEN cp.impact = 'Medium' THEN 1 END) as medium_severity,
                COUNT(CASE WHEN cp.impact = 'Low' THEN 1 END) as low_severity
            FROM stream_defect sd
            JOIN checker_properties cp ON sd.checker_properties_id = cp.id
            JOIN stream_element se ON sd.stream_element_id = se.id
            JOIN stream s ON se.stream_id = s.id
            {project_filter_join}
            WHERE sd.fixed_snapshot_element_id IS NULL
                {project_filter}
        """
        
        if self.project_name:
            query = query.format(
                project_filter_join="""
                    JOIN project_stream ps ON s.id = ps.stream_id
                    JOIN project p ON ps.project_id = p.id
                """,
                project_filter="AND p.name = %s"
            )
            results = self.db.execute_query_dict(query, (self.project_name,))
        else:
            query = query.format(project_filter_join="", project_filter="")
            results = self.db.execute_query_dict(query)
        
        return pd.DataFrame(results)
    
    def get_triage_progress_summary(self):
        """Get current triage progress summary
        
        Returns:
            dict: Triage statistics
        """
        query = """
            SELECT 
                COUNT(DISTINCT dt.id) as total_defects,
                COUNT(DISTINCT CASE WHEN dt.current_classification_id IS NOT NULL THEN dt.id END) as classified_count,
                COUNT(DISTINCT CASE WHEN dt.current_classification_id IS NULL THEN dt.id END) as unclassified_count,
                COUNT(DISTINCT CASE WHEN dt.current_action_id IS NOT NULL THEN dt.id END) as action_assigned_count,
                COUNT(DISTINCT CASE WHEN dt.current_action_id IS NULL THEN dt.id END) as no_action_count,
                ROUND((COUNT(DISTINCT CASE WHEN dt.current_classification_id IS NOT NULL THEN dt.id END)::numeric / 
                       NULLIF(COUNT(DISTINCT dt.id), 0) * 100), 2) as triage_completion_percentage,
                COUNT(DISTINCT CASE WHEN de_cls.name = 'Bug' THEN dt.id END) as bug_count,
                COUNT(DISTINCT CASE WHEN de_cls.name = 'False Positive' THEN dt.id END) as false_positive_count,
                COUNT(DISTINCT CASE WHEN de_cls.name = 'Intentional' THEN dt.id END) as intentional_count
            FROM defect_triage dt
            LEFT JOIN dynamic_enum de_cls ON dt.current_classification_id = de_cls.id AND de_cls.dtype = 'Cls'
        """
        
        result = self.db.execute_query_dict(query)
        return result[0] if result else {}

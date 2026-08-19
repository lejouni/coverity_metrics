"""
Coverity Metrics Module
Provides various metrics calculations based on Coverity database
"""
import logging
from datetime import datetime, timedelta
from coverity_metrics.db_connection import CoverityDatabase
import pandas as pd
from tqdm import tqdm

logger = logging.getLogger(__name__)

class CoverityMetrics:
    """Comprehensive metrics for Coverity static analysis data"""

    # Active / Fixed anchoring, with per-row fallback for defects that lack a
    # ``last_detected_snapshot`` (LDS) entry.
    #
    # Preferred rule: a stream_defect is Active iff its ``last_detected_snapshot`` (lds) row
    # points at the latest non-deleted snapshot of its stream (``sn_latest.latest_snap_id``);
    # Fixed iff lds points at an earlier snapshot. This matches Coverity Connect's UI exactly
    # and correctly handles defects that were fixed and later reappeared.
    #
    # Fallback rule (per row): when the defect has no lds entry â€” either because the stream's
    # LDS is stale (upgrade / migration / purge on the Coverity side hasn't been followed by
    # the population job) or because a healthy stream has the usual ~2.5% tail of missing
    # rows â€” the CASE falls back to two ``stream_defect`` columns Coverity Connect updates
    # itself:
    #
    #   Active iff  fixed_snapshot_element_id IS NULL
    #           OR  introduced_snapshot_element_id > fixed_snapshot_element_id
    #
    # The second disjunct catches defects that were fixed and later reappeared. Coverity does
    # NOT clear ``fixed_snapshot_element_id`` on reappearance, but it DOES update
    # ``introduced_snapshot_element_id`` to point at the new introduction â€” so
    # ``introduced > fixed`` (both are ``snapshot_element.id`` values, which are monotonic on
    # Coverity's DB) means "the defect was re-detected after the last known fix" and is
    # authoritative. Without this second disjunct the fallback under-counted Active by ~5% on
    # DBs where LDS is stale but re-detections have happened. ``_check_lds_freshness`` still
    # logs a one-time WARNING when entire streams are stale so users can diagnose the
    # situation and (optionally) get Coverity Connect to rebuild the table.
    #
    # Queries embed these constants via f-strings; use ``{{name}}`` for later ``.format()``
    # placeholders such as ``{project_filter}``.
    _ACTIVE_JOIN_SQL = """
        LEFT JOIN last_detected_snapshot lds ON lds.stream_defect_id = sd.id
        LEFT JOIN (
            SELECT sn2.stream_id, MAX(sn2.id) AS latest_snap_id
            FROM snapshot sn2
            WHERE NOT COALESCE(sn2.deleted, FALSE)
            GROUP BY sn2.stream_id
        ) sn_latest ON sn_latest.stream_id = se.stream_id
    """
    _ACTIVE_COND_SQL = (
        "(CASE "
        "WHEN lds.detected_snapshot_id IS NOT NULL "
        "  THEN (lds.detected_snapshot_id = sn_latest.latest_snap_id) "
        "WHEN sd.id IS NOT NULL "
        "  THEN (sd.fixed_snapshot_element_id IS NULL "
        "        OR sd.introduced_snapshot_element_id > sd.fixed_snapshot_element_id) "
        "ELSE NULL "
        "END)"
    )
    _FIXED_COND_SQL = (
        "(CASE "
        "WHEN lds.detected_snapshot_id IS NOT NULL "
        "  THEN (lds.detected_snapshot_id != sn_latest.latest_snap_id) "
        "WHEN sd.id IS NOT NULL "
        "  THEN (sd.fixed_snapshot_element_id IS NOT NULL "
        "        AND (sd.introduced_snapshot_element_id IS NULL "
        "             OR sd.introduced_snapshot_element_id <= sd.fixed_snapshot_element_id)) "
        "ELSE NULL "
        "END)"
    )

    # Per-DB caches shared across all instances in this process. Keyed by
    # (host, port, database, user) so multiple CoverityMetrics workers against
    # the same server pay for the freshness probe exactly once and don't spam
    # duplicate warnings.
    _LDS_FRESHNESS_CACHE: dict = {}
    _LDS_WARNING_EMITTED: set = set()

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
        # Use the property setter so _project_names is always normalised
        self.project_name = project_name
        self._lds_stale_streams: list = []
        self._check_lds_freshness()

    # ------------------------------------------------------------------
    # project_name property â€“ accepts str, list[str], or None.
    # Internally stored as self._project_names (list or None).
    # ------------------------------------------------------------------
    @property
    def project_name(self):
        """Return a display-friendly project name string (or None)."""
        if not self._project_names:
            return None
        return self._project_names[0] if len(self._project_names) == 1 else ', '.join(self._project_names)

    @project_name.setter
    def project_name(self, value):
        if value is None:
            self._project_names = None
        elif isinstance(value, list):
            self._project_names = value if value else None
        else:
            self._project_names = [value]

    # ------------------------------------------------------------------
    # last_detected_snapshot (LDS) freshness probe.
    #
    # A stream is "stale" when its max ``lds.detected_snapshot_id`` is
    # missing or below its latest non-deleted snapshot. The Active/Fixed
    # CASE predicates fall back to ``stream_defect.fixed_snapshot_element_id``
    # for those streams; this method surfaces the situation to the caller
    # via a one-time WARNING so silent under-counting can be diagnosed.
    # ------------------------------------------------------------------
    def _db_signature(self):
        p = getattr(self.db, 'connection_params', None) or {}
        return (p.get('host'), p.get('port'), p.get('database'), p.get('user'))

    def _check_lds_freshness(self):
        """Populate ``self._lds_stale_streams`` and warn once per DB if stale."""
        sig = self._db_signature()
        cache = type(self)._LDS_FRESHNESS_CACHE
        if sig in cache:
            self._lds_stale_streams = cache[sig]
            return
        query = """
            SELECT s.name AS stream_name,
                   s_lat.latest_snap AS latest_snap,
                   l_max.max_lds_snap AS max_lds_snap
            FROM stream s
            JOIN (
                SELECT stream_id, MAX(id) AS latest_snap
                FROM snapshot
                WHERE NOT COALESCE(deleted, FALSE)
                GROUP BY stream_id
            ) s_lat ON s_lat.stream_id = s.id
            LEFT JOIN (
                SELECT se.stream_id, MAX(lds.detected_snapshot_id) AS max_lds_snap
                FROM last_detected_snapshot lds
                JOIN stream_defect sd ON sd.id = lds.stream_defect_id
                JOIN stream_element se ON se.id = sd.stream_element_id
                GROUP BY se.stream_id
            ) l_max ON l_max.stream_id = s.id
            WHERE NOT COALESCE(s.deleted, FALSE)
              AND (l_max.max_lds_snap IS NULL
                   OR l_max.max_lds_snap < s_lat.latest_snap)
            ORDER BY s.name
        """
        try:
            rows = self.db.execute_query_dict(query) or []
        except Exception as exc:
            # Probe is best-effort; if it fails we assume LDS is healthy.
            logger.debug("LDS freshness probe failed: %s", exc)
            cache[sig] = []
            return
        stale = [r['stream_name'] for r in rows]
        cache[sig] = stale
        self._lds_stale_streams = stale
        warned = type(self)._LDS_WARNING_EMITTED
        if stale and sig not in warned:
            warned.add(sig)
            preview = ', '.join(stale[:5])
            more = '' if len(stale) <= 5 else f' (+{len(stale) - 5} more)'
            logger.warning(
                "last_detected_snapshot is stale for %d stream(s): %s%s. "
                "Active/Fixed for these streams fall back to "
                "stream_defect.fixed_snapshot_element_id, which can be ~5%% off "
                "when defects have been re-detected after a fix. Ask a Coverity "
                "admin to rebuild the table to restore strict LDS-based counts.",
                len(stale), preview, more,
            )

    # ========== DEFECT METRICS ==========

    def get_total_defects_by_project(self):
        """Get total defect count grouped by project, or by stream when filtered to a single project
        Includes both code-based fixes and triaged defects (False Positive/Intentional)
        
        Returns:
            pandas.DataFrame: Project/stream name and defect count
        """
        multi_project = self._project_names and len(self._project_names) > 1
        single_project = self._project_names and len(self._project_names) == 1

        if multi_project:
            # Multiple projects: group by project name, filter to selected projects only
            # active / fixed / dismissed are mutually exclusive and sum to defect_count.
            # Counts are per stream_defect row, so a defect present in multiple streams
            # contributes once per stream (matching Coverity Connect's per-stream totals).
            query = f"""
                SELECT 
                    p.name as project_name,
                    COUNT(DISTINCT sd.id) as defect_count,
                    COUNT(DISTINCT CASE 
                        WHEN {self._ACTIVE_COND_SQL}
                            AND (de_cls.name NOT IN ('False Positive', 'Intentional') OR de_cls.name IS NULL)
                        THEN sd.id 
                    END) as active_defects,
                    COUNT(DISTINCT CASE 
                        WHEN {self._FIXED_COND_SQL}
                            AND (de_cls.name NOT IN ('False Positive', 'Intentional') OR de_cls.name IS NULL)
                        THEN sd.id 
                    END) as fixed_defects,
                    COUNT(DISTINCT CASE 
                        WHEN de_cls.name IN ('False Positive', 'Intentional')
                        THEN sd.id 
                    END) as dismissed_defects
                FROM project p
                JOIN project_stream ps ON p.id = ps.project_id
                JOIN stream s ON ps.stream_id = s.id
                JOIN stream_element se ON s.id = se.stream_id
                LEFT JOIN stream_defect sd ON se.id = sd.stream_element_id
                LEFT JOIN defect_triage dt ON sd.defect_triage_id = dt.id
                LEFT JOIN dynamic_enum de_cls ON dt.current_classification_id = de_cls.id AND de_cls.dtype = 'Cls'
                {self._ACTIVE_JOIN_SQL}
                WHERE p.deleted = false AND s.deleted = false
                    AND p.name = ANY(%s)
                GROUP BY p.name
                ORDER BY defect_count DESC
            """
            results = self.db.execute_query_dict(query, (self._project_names,))
            results
        elif single_project:
            # Single project: group by stream for drill-down view.
            # active / fixed / dismissed are mutually exclusive and sum to defect_count.
            query = f"""
                SELECT 
                    s.name as project_name,
                    COUNT(DISTINCT sd.id) as defect_count,
                    COUNT(DISTINCT CASE 
                        WHEN {self._ACTIVE_COND_SQL}
                            AND (de_cls.name NOT IN ('False Positive', 'Intentional') OR de_cls.name IS NULL)
                        THEN sd.id 
                    END) as active_defects,
                    COUNT(DISTINCT CASE 
                        WHEN {self._FIXED_COND_SQL}
                            AND (de_cls.name NOT IN ('False Positive', 'Intentional') OR de_cls.name IS NULL)
                        THEN sd.id 
                    END) as fixed_defects,
                    COUNT(DISTINCT CASE 
                        WHEN de_cls.name IN ('False Positive', 'Intentional')
                        THEN sd.id 
                    END) as dismissed_defects
                FROM project p
                JOIN project_stream ps ON p.id = ps.project_id
                JOIN stream s ON ps.stream_id = s.id
                JOIN stream_element se ON s.id = se.stream_id
                LEFT JOIN stream_defect sd ON se.id = sd.stream_element_id
                LEFT JOIN defect_triage dt ON sd.defect_triage_id = dt.id
                LEFT JOIN dynamic_enum de_cls ON dt.current_classification_id = de_cls.id AND de_cls.dtype = 'Cls'
                {self._ACTIVE_JOIN_SQL}
                WHERE p.deleted = false AND s.deleted = false
                    AND p.name = ANY(%s)
                GROUP BY s.name
                ORDER BY defect_count DESC
            """
            results = self.db.execute_query_dict(query, (self._project_names,))
            results
        else:
            # All projects: active / fixed / dismissed are mutually exclusive and sum to defect_count.
            # Counts are per stream_defect row, so a defect present in multiple streams
            # contributes once per stream.
            query = f"""
                SELECT 
                    p.name as project_name,
                    COUNT(DISTINCT sd.id) as defect_count,
                    COUNT(DISTINCT CASE 
                        WHEN {self._ACTIVE_COND_SQL}
                            AND (de_cls.name NOT IN ('False Positive', 'Intentional') OR de_cls.name IS NULL)
                        THEN sd.id 
                    END) as active_defects,
                    COUNT(DISTINCT CASE 
                        WHEN {self._FIXED_COND_SQL}
                            AND (de_cls.name NOT IN ('False Positive', 'Intentional') OR de_cls.name IS NULL)
                        THEN sd.id 
                    END) as fixed_defects,
                    COUNT(DISTINCT CASE 
                        WHEN de_cls.name IN ('False Positive', 'Intentional')
                        THEN sd.id 
                    END) as dismissed_defects
                FROM project p
                JOIN project_stream ps ON p.id = ps.project_id
                JOIN stream s ON ps.stream_id = s.id
                JOIN stream_element se ON s.id = se.stream_id
                LEFT JOIN stream_defect sd ON se.id = sd.stream_element_id
                LEFT JOIN defect_triage dt ON sd.defect_triage_id = dt.id
                LEFT JOIN dynamic_enum de_cls ON dt.current_classification_id = de_cls.id AND de_cls.dtype = 'Cls'
                {self._ACTIVE_JOIN_SQL}
                WHERE p.deleted = false AND s.deleted = false
                    AND p.name != 'Developer Streams'
                GROUP BY p.name
                ORDER BY defect_count DESC
            """
            results = self.db.execute_query_dict(query)
            results
        return pd.DataFrame(results)
    
    def get_defects_by_severity(self):
        """Get defect count grouped by checker Impact (High / Medium / Low / Unspecified).

        Coverity Connect labels the ``checker_properties.impact`` column as "Severity" in most
        UI surfaces, and that's what we bucket by here. Only counts defects that are currently
        active â€” present in the latest non-deleted snapshot of their stream â€” and excludes
        defects classified as False Positive or Intentional. Counts are per stream_defect row,
        so a defect present in multiple streams of the same project contributes once per
        stream. The sum of the buckets therefore matches the Overview "Active Defects" card.

        Returns:
            pandas.DataFrame: Impact level and count.
        """
        query = f"""
            SELECT 
                cp.impact,
                COUNT(DISTINCT sd.id) as defect_count
            FROM stream_defect sd
            JOIN checker_properties cp ON sd.checker_properties_id = cp.id
            JOIN stream_element se ON sd.stream_element_id = se.id
            JOIN stream s ON se.stream_id = s.id
            JOIN project_stream ps ON s.id = ps.stream_id
            JOIN project p ON ps.project_id = p.id
            LEFT JOIN defect_triage dt ON sd.defect_triage_id = dt.id
            LEFT JOIN dynamic_enum de_cls ON dt.current_classification_id = de_cls.id
                AND de_cls.dtype = 'Cls'
            {self._ACTIVE_JOIN_SQL}
            WHERE {self._ACTIVE_COND_SQL}
                AND p.deleted = false
                AND (de_cls.name NOT IN ('False Positive', 'Intentional') OR de_cls.name IS NULL)
                {{project_filter}}
            GROUP BY cp.impact
            ORDER BY 
                CASE cp.impact
                    WHEN 'High' THEN 1
                    WHEN 'Medium' THEN 2
                    WHEN 'Low' THEN 3
                    ELSE 4
                END
        """
        if self._project_names:
            query = query.format(project_filter="AND p.name = ANY(%s)")
            results = self.db.execute_query_dict(query, (self._project_names,))
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
            {self._ACTIVE_JOIN_SQL}
            WHERE {self._ACTIVE_COND_SQL}
                AND p.deleted = false
                {{project_filter}}
            GROUP BY cc.name
            ORDER BY defect_count DESC
            {limit_clause}
        """
        if self._project_names:
            query = query.format(project_filter="AND p.name = ANY(%s)")
            params = (self._project_names,) if fetch_all else (self._project_names, limit)
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
            {self._ACTIVE_JOIN_SQL}
            WHERE {self._ACTIVE_COND_SQL}
                AND p.deleted = false
                {{project_filter}}
            GROUP BY ct.name, cc.name, cp.impact
            ORDER BY defect_count DESC
            {limit_clause}
        """
        if self._project_names:
            query = query.format(project_filter="AND p.name = ANY(%s)")
            params = (self._project_names,) if fetch_all else (self._project_names, limit)
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
        query = f"""
            SELECT 
                p.name as project_name,
                s.name as stream_name,
                COUNT(DISTINCT sd.id) as total_defects,
                SUM(GREATEST(COALESCE(sf.current_code_line_count, 0), 0)) as total_loc,
                CASE 
                    WHEN SUM(GREATEST(COALESCE(sf.current_code_line_count, 0), 0)) > 0 
                    THEN ROUND((COUNT(DISTINCT sd.id)::decimal / SUM(GREATEST(COALESCE(sf.current_code_line_count, 0), 0)) * 1000), 2)
                    ELSE 0
                END as defects_per_kloc
            FROM project p
            JOIN project_stream ps ON p.id = ps.project_id
            JOIN stream s ON ps.stream_id = s.id
            JOIN stream_element se ON s.id = se.stream_id
            LEFT JOIN stream_defect sd ON se.id = sd.stream_element_id
            {self._ACTIVE_JOIN_SQL}
            LEFT JOIN stream_file sf ON se.id = sf.stream_element_id
            WHERE p.deleted = false AND s.deleted = false
                AND p.name != 'Developer Streams'
                AND (sd.id IS NULL OR {self._ACTIVE_COND_SQL})
                {{project_filter}}
            GROUP BY p.name, s.name
            ORDER BY defects_per_kloc DESC
        """
        if self._project_names:
            query = query.format(project_filter="AND p.name = ANY(%s)")
            results = self.db.execute_query_dict(query, (self._project_names,))
        else:
            query = query.format(project_filter="")
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
        """Get code quality metrics by stream.

        In Coverity's schema each stream has one long-lived ``stream_element`` whose
        ``stream_file`` children accumulate over the stream's entire history: files
        that no longer exist in the current codebase stay as rows but with all their
        ``current_*_line_count`` columns zeroed. That means the SUMs of LOC / comments /
        blanks already reflect the current codebase, but ``COUNT(sf.id)`` and any AVG
        over those files are inflated by the zero rows. We filter to rows where at
        least one of the current line-count columns is > 0 so ``file_count`` matches
        Coverity Connect's per-stream "Files" number and ``avg_file_loc`` is meaningful.

        Returns:
            pandas.DataFrame: Stream code metrics
        """
        query = """
            SELECT 
                s.name as stream_name,
                COUNT(DISTINCT sf.id) as file_count,
                SUM(GREATEST(COALESCE(sf.current_code_line_count, 0), 0)) as total_loc,
                SUM(GREATEST(COALESCE(sf.current_comment_line_count, 0), 0)) as total_comment_lines,
                SUM(GREATEST(COALESCE(sf.current_blank_line_count, 0), 0)) as total_blank_lines,
                ROUND(AVG(GREATEST(COALESCE(sf.current_code_line_count, 0), 0)), 2) as avg_file_loc,
                CASE 
                    WHEN SUM(GREATEST(COALESCE(sf.current_code_line_count, 0), 0)) > 0
                    THEN ROUND((SUM(GREATEST(COALESCE(sf.current_comment_line_count, 0), 0))::decimal / 
                               SUM(GREATEST(COALESCE(sf.current_code_line_count, 0), 0)) * 100), 2)
                    ELSE 0
                END as comment_ratio_pct
            FROM stream s
            JOIN stream_element se ON s.id = se.stream_id
            JOIN stream_file sf ON se.id = sf.stream_element_id
            JOIN project_stream ps ON s.id = ps.stream_id
            JOIN project p ON ps.project_id = p.id
            WHERE s.deleted = false
                AND p.deleted = false
                AND (
                    GREATEST(COALESCE(sf.current_code_line_count, 0), 0)
                  + GREATEST(COALESCE(sf.current_comment_line_count, 0), 0)
                  + GREATEST(COALESCE(sf.current_blank_line_count, 0), 0)
                ) > 0
                {project_filter}
            GROUP BY s.name
            ORDER BY total_loc DESC
        """
        if self._project_names:
            query = query.format(project_filter="AND p.name = ANY(%s)")
            results = self.db.execute_query_dict(query, (self._project_names,))
        else:
            query = query.format(project_filter="")
            results = self.db.execute_query_dict(query)
        return pd.DataFrame(results)
    
    def get_function_complexity_distribution(self):
        """Get distribution of function complexity for the current (latest) code.

        Correct linkage in Coverity Connect:

            stream_function            <-- listing of current functions in the code
                |
                | fi.stream_function_id
                v
            function_instance          <-- per-snapshot-range instance with metrics
                |
                | fi.function_metrics_id
                v
            function_metrics           <-- actual metric values (cyclomatic_complexity, ...)

        ``function_metrics.id`` is *not* a foreign key from ``stream_function.function_id`` â€”
        the old ``JOIN function_metrics fm ON sf.function_id = fm.id`` matched only rows where
        the two id spaces coincidentally overlapped, drastically under-counting.

        ``function_instance.snapshot_end_id IS NULL`` restricts to instances that are still
        current (present in the latest snapshot). ``COUNT(DISTINCT sf.id)`` de-duplicates the
        rare case where a stream_function has multiple current instances.

        Returns:
            pandas.DataFrame: Complexity ranges with function counts and average complexity.
        """
        project_filter_join = ""
        project_filter_where = ""
        params = None
        if self._project_names:
            project_filter_join = """
                JOIN stream_element se ON stf.stream_element_id = se.id
                JOIN stream s ON se.stream_id = s.id
                JOIN project_stream ps ON s.id = ps.stream_id
                JOIN project p ON ps.project_id = p.id
            """
            project_filter_where = "AND p.name = ANY(%s)"
            params = (self._project_names,)

        query = f"""
            WITH complexity_data AS (
                SELECT
                    sf.id AS sf_id,
                    MAX(fm.cyclomatic_complexity) AS complexity
                FROM stream_function sf
                JOIN stream_file stf ON sf.stream_file_id = stf.id
                JOIN function_instance fi ON fi.stream_function_id = sf.id
                JOIN function_metrics fm ON fm.id = fi.function_metrics_id
                {project_filter_join}
                WHERE fm.cyclomatic_complexity IS NOT NULL
                    AND fi.snapshot_end_id IS NULL
                    {project_filter_where}
                GROUP BY sf.id
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
        results = self.db.execute_query_dict(query, params)
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

        project_filter_join = ""
        project_filter_where = ""
        project_params = ()
        if self._project_names:
            project_filter_join = """
                JOIN stream_element se ON stf.stream_element_id = se.id
                JOIN stream s ON se.stream_id = s.id
                JOIN project_stream ps ON s.id = ps.stream_id
                JOIN project p ON ps.project_id = p.id
            """
            project_filter_where = "AND p.name = ANY(%s)"
            project_params = (self._project_names,)

        query = f"""
            SELECT 
                f.display_name as function_name,
                fp.filename as file_path,
                fm.cyclomatic_complexity,
                fm.line_count
            FROM stream_function sf
            JOIN function f ON sf.function_id = f.id
            JOIN function_instance fi ON fi.stream_function_id = sf.id
            JOIN function_metrics fm ON fm.id = fi.function_metrics_id
            JOIN stream_file stf ON sf.stream_file_id = stf.id
            JOIN file_path fp ON stf.file_path_id = fp.id
            {project_filter_join}
            WHERE fm.cyclomatic_complexity IS NOT NULL
                AND fi.snapshot_end_id IS NULL
                {project_filter_where}
            ORDER BY fm.cyclomatic_complexity DESC, fm.line_count DESC
            {limit_clause}
        """
        params = project_params if fetch_all else project_params + (limit,)
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
            WHERE from_date >= CURRENT_DATE - INTERVAL '1 week' * %s
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
            WHERE from_date >= CURRENT_DATE - INTERVAL '1 week' * %s
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
                    GREATEST(COALESCE(sn.code_line_count, 0), 0) as code_line_count,
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
                    GREATEST(COALESCE(sn.code_line_count, 0), 0) as code_line_count,
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
    
    def get_user_license_statistics(self, days=90):
        """Get user license and activity statistics
        
        Args:
            days: Number of days to look back for active users
            
        Returns:
            dict: User license statistics including:
                - total_licensed_users: Total users in system
                - users_with_login: Users who have logged in at least once
                - active_users: Users with commits or triage activity in given period
        """
        # Total licensed users (all users in the system, excluding system and internal users)
        total_users_query = "SELECT COUNT(*) FROM users WHERE deleted = false AND username NOT IN ('system', 'reporter')"
        total_users_result = self.db.execute_query(total_users_query)
        total_licensed_users = total_users_result[0][0] if total_users_result else 0
        
        # Users with at least one login ever
        users_with_login_query = """
            SELECT COUNT(DISTINCT u.id)
            FROM users u
            INNER JOIN user_login ul ON u.id = ul.user_id
            WHERE u.deleted = false
                AND u.username NOT IN ('system', 'reporter')
        """
        users_with_login_result = self.db.execute_query(users_with_login_query)
        users_with_login = users_with_login_result[0][0] if users_with_login_result else 0
        
        # Active users: those who have done triage, added comments, or committed snapshots
        # For project-level: only count users with activity on that specific project
        # Note: Excluding 'system' and 'reporter' users from counts
        if self.project_name:
            # Project-specific active users: triage, comment, or snapshot commit activity for this project
            active_users_query = f"""
                SELECT COUNT(DISTINCT user_id) as active_users
                FROM (
                    -- Users who performed triage actions on defects in this project
                    SELECT DISTINCT ts.user_created_id as user_id
                    FROM triage_state ts
                    JOIN users u ON ts.user_created_id = u.id
                    JOIN defect_triage dt ON ts.defect_triage_id = dt.id
                    JOIN stream_defect sd ON dt.id = sd.defect_triage_id
                    JOIN stream_element se ON sd.stream_element_id = se.id
                    JOIN stream s ON se.stream_id = s.id
                    JOIN project_stream ps ON s.id = ps.stream_id
                    JOIN project p ON ps.project_id = p.id
                    WHERE ts.date_created >= CURRENT_DATE - INTERVAL '{days} days'
                        AND ts.user_created_id IS NOT NULL
                        AND u.username NOT IN ('system', 'reporter')
                        AND p.name = ANY(%s)
                    
                    UNION
                    
                    -- Users who added comments on defects in this project
                    SELECT DISTINCT ts.user_created_id as user_id
                    FROM triage_state ts
                    JOIN users u ON ts.user_created_id = u.id
                    JOIN defect_triage dt ON ts.defect_triage_id = dt.id
                    JOIN stream_defect sd ON dt.id = sd.defect_triage_id
                    JOIN stream_element se ON sd.stream_element_id = se.id
                    JOIN stream s ON se.stream_id = s.id
                    JOIN project_stream ps ON s.id = ps.stream_id
                    JOIN project p ON ps.project_id = p.id
                    WHERE ts.date_created >= CURRENT_DATE - INTERVAL '{days} days'
                        AND ts.user_created_id IS NOT NULL
                        AND u.username NOT IN ('system', 'reporter')
                        AND ts.cmnt IS NOT NULL
                        AND ts.cmnt != ''
                        AND p.name = ANY(%s)
                    
                    UNION
                    
                    -- Users who committed snapshots for streams in this project
                    SELECT DISTINCT sn.committer_user_id as user_id
                    FROM snapshot sn
                    JOIN users u ON sn.committer_user_id = u.id
                    JOIN stream s ON sn.stream_id = s.id
                    JOIN project_stream ps ON s.id = ps.stream_id
                    JOIN project p ON ps.project_id = p.id
                    WHERE sn.date_created >= CURRENT_DATE - INTERVAL '{days} days'
                        AND sn.committer_user_id IS NOT NULL
                        AND u.username NOT IN ('system', 'reporter')
                        AND sn.deleted = false
                        AND p.name = ANY(%s)
                ) active_user_list
            """
        else:
            # Instance-level active users: triage, login, or snapshot commit activity across all projects
            active_users_query = f"""
                SELECT COUNT(DISTINCT user_id) as active_users
                FROM (
                    -- Users who performed triage actions
                    SELECT DISTINCT ts.user_created_id as user_id
                    FROM triage_state ts
                    JOIN users u ON ts.user_created_id = u.id
                    WHERE ts.date_created >= CURRENT_DATE - INTERVAL '{days} days'
                        AND ts.user_created_id IS NOT NULL
                        AND u.username NOT IN ('system', 'reporter')
                    
                    UNION
                    
                    -- Users who had login activity (showing engagement)
                    SELECT DISTINCT ul.user_id
                    FROM user_login ul
                    JOIN users u ON ul.user_id = u.id
                    WHERE ul.session_start >= CURRENT_DATE - INTERVAL '{days} days'
                        AND ul.user_id IS NOT NULL
                        AND u.username NOT IN ('system', 'reporter')
                    
                    UNION
                    
                    -- Users who committed snapshots
                    SELECT DISTINCT sn.committer_user_id as user_id
                    FROM snapshot sn
                    JOIN users u ON sn.committer_user_id = u.id
                    WHERE sn.date_created >= CURRENT_DATE - INTERVAL '{days} days'
                        AND sn.committer_user_id IS NOT NULL
                        AND u.username NOT IN ('system', 'reporter')
                        AND sn.deleted = false
                ) active_user_list
            """
        
        active_users_result = self.db.execute_query(active_users_query,
            (self._project_names, self._project_names, self._project_names) if self._project_names else None)
        active_users = active_users_result[0][0] if active_users_result else 0
        
        return {
            'total_licensed_users': total_licensed_users,
            'users_with_login': users_with_login,
            'active_users': active_users,
            'active_user_percentage': round((active_users / total_licensed_users * 100), 1) if total_licensed_users > 0 else 0,
            'login_user_percentage': round((users_with_login / total_licensed_users * 100), 1) if total_licensed_users > 0 else 0
        }
    
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
            WHERE ul.session_start >= CURRENT_DATE - INTERVAL '1 day' * %s
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
            WHERE ts.date_created >= CURRENT_DATE - INTERVAL '1 day' * %s
            GROUP BY u.username
            ORDER BY triage_actions DESC
            LIMIT %s
        """
        results = self.db.execute_query_dict(query, (days, limit))
        return pd.DataFrame(results)
    
    # ========== SUMMARY METRICS ==========

    def get_overall_summary(self, days=None):
        """Get overall summary statistics

        Args:
            days: Optional trend window (days). When set, ``total_files``,
                ``total_functions``, and ``total_loc`` are computed from the
                latest non-deleted snapshot per stream whose ``date_created``
                falls within the window. Streams with no snapshot in the
                window contribute 0. When ``None``, uses the latest
                non-deleted snapshot per stream regardless of age.

        Returns:
            dict: Summary statistics
        """
        # Files, functions, and LOC: use per-snapshot aggregates on the latest
        # non-deleted snapshot per stream (optionally restricted to a date
        # window) â€” mirrors Coverity Connect's per-stream numbers, not the
        # cumulative stream_file / stream_function history.
        if days is not None:
            files_date_filter = "AND sn.date_created >= CURRENT_DATE - INTERVAL '1 day' * %s"
        else:
            files_date_filter = ""

        if self.project_name:
            # Project-specific queries
            queries = {
                'total_projects': ("SELECT COUNT(*) FROM project WHERE deleted = false AND name = ANY(%s)", (self._project_names,)),
                'total_streams': ("""
                    SELECT COUNT(DISTINCT s.id) FROM stream s
                    JOIN project_stream ps ON s.id = ps.stream_id
                    JOIN project p ON ps.project_id = p.id
                    WHERE s.deleted = false AND p.name = ANY(%s)
                """, (self._project_names,)),
                'total_defects': (f"""
                    SELECT COUNT(DISTINCT sd.id) FROM stream_defect sd
                    JOIN stream_element se ON sd.stream_element_id = se.id
                    JOIN stream s ON se.stream_id = s.id
                    JOIN project_stream ps ON s.id = ps.stream_id
                    JOIN project p ON ps.project_id = p.id
                    LEFT JOIN defect_triage dt ON sd.defect_triage_id = dt.id
                    LEFT JOIN dynamic_enum de_cls ON dt.current_classification_id = de_cls.id
                        AND de_cls.dtype = 'Cls'
                    {self._ACTIVE_JOIN_SQL}
                    WHERE {self._ACTIVE_COND_SQL}
                        AND p.name = ANY(%s)
                        AND (de_cls.name NOT IN ('False Positive', 'Intentional') OR de_cls.name IS NULL)
                """, (self._project_names,)),
                'total_files': (f"""
                    SELECT COALESCE(SUM(win.total_file_count), 0)
                    FROM (
                        SELECT DISTINCT ON (sn.stream_id) sn.total_file_count
                        FROM snapshot sn
                        JOIN stream s ON sn.stream_id = s.id
                        JOIN project_stream ps ON s.id = ps.stream_id
                        JOIN project p ON ps.project_id = p.id
                        WHERE sn.deleted = false
                            AND p.name = ANY(%s)
                            {files_date_filter}
                        ORDER BY sn.stream_id, sn.id DESC
                    ) win
                """, (self._project_names,) if days is None else (self._project_names, days)),
                'total_functions': (f"""
                    SELECT COALESCE(SUM(win.function_count), 0)
                    FROM (
                        SELECT DISTINCT ON (sn.stream_id) sn.function_count
                        FROM snapshot sn
                        JOIN stream s ON sn.stream_id = s.id
                        JOIN project_stream ps ON s.id = ps.stream_id
                        JOIN project p ON ps.project_id = p.id
                        WHERE sn.deleted = false
                            AND p.name = ANY(%s)
                            {files_date_filter}
                        ORDER BY sn.stream_id, sn.id DESC
                    ) win
                """, (self._project_names,) if days is None else (self._project_names, days)),
                'total_loc': (f"""
                    SELECT COALESCE(SUM(GREATEST(win.code_line_count, 0)), 0)
                    FROM (
                        SELECT DISTINCT ON (sn.stream_id) sn.code_line_count
                        FROM snapshot sn
                        JOIN stream s ON sn.stream_id = s.id
                        JOIN project_stream ps ON s.id = ps.stream_id
                        JOIN project p ON ps.project_id = p.id
                        WHERE sn.deleted = false
                            AND p.name = ANY(%s)
                            {files_date_filter}
                        ORDER BY sn.stream_id, sn.id DESC
                    ) win
                """, (self._project_names,) if days is None else (self._project_names, days)),
                'total_users': ("""
                    SELECT COUNT(DISTINCT user_id) FROM (
                        -- Users with triage activity on this project's defects
                        SELECT DISTINCT ts.user_created_id as user_id
                        FROM triage_state ts
                        JOIN users u ON ts.user_created_id = u.id
                        JOIN defect_triage dt ON ts.defect_triage_id = dt.id
                        JOIN stream_defect sd ON dt.id = sd.defect_triage_id
                        JOIN stream_element se ON sd.stream_element_id = se.id
                        JOIN stream s ON se.stream_id = s.id
                        JOIN project_stream ps ON s.id = ps.stream_id
                        JOIN project p ON ps.project_id = p.id
                        WHERE ts.user_created_id IS NOT NULL
                            AND u.username NOT IN ('system', 'reporter')
                            AND p.name = ANY(%s)
                        
                        UNION
                        
                        -- Users with comment activity on this project's defects
                        SELECT DISTINCT ts.user_created_id as user_id
                        FROM triage_state ts
                        JOIN users u ON ts.user_created_id = u.id
                        JOIN defect_triage dt ON ts.defect_triage_id = dt.id
                        JOIN stream_defect sd ON dt.id = sd.defect_triage_id
                        JOIN stream_element se ON sd.stream_element_id = se.id
                        JOIN stream s ON se.stream_id = s.id
                        JOIN project_stream ps ON s.id = ps.stream_id
                        JOIN project p ON ps.project_id = p.id
                        WHERE ts.user_created_id IS NOT NULL
                            AND u.username NOT IN ('system', 'reporter')
                            AND ts.cmnt IS NOT NULL
                            AND ts.cmnt != ''
                            AND p.name = ANY(%s)
                        
                        UNION
                        
                        -- Users who committed snapshots for streams in this project
                        SELECT DISTINCT sn.committer_user_id as user_id
                        FROM snapshot sn
                        JOIN users u ON sn.committer_user_id = u.id
                        JOIN stream s ON sn.stream_id = s.id
                        JOIN project_stream ps ON s.id = ps.stream_id
                        JOIN project p ON ps.project_id = p.id
                        WHERE sn.committer_user_id IS NOT NULL
                            AND u.username NOT IN ('system', 'reporter')
                            AND sn.deleted = false
                            AND p.name = ANY(%s)
                    ) active_users
                """, (self._project_names, self._project_names, self._project_names)),
                'high_severity_defects': (f"""
                    SELECT COUNT(DISTINCT sd.id) FROM stream_defect sd 
                    JOIN checker_properties cp ON sd.checker_properties_id = cp.id
                    JOIN stream_element se ON sd.stream_element_id = se.id
                    JOIN stream s ON se.stream_id = s.id
                    JOIN project_stream ps ON s.id = ps.stream_id
                    JOIN project p ON ps.project_id = p.id
                    LEFT JOIN defect_triage dt ON sd.defect_triage_id = dt.id
                    LEFT JOIN dynamic_enum de_cls ON dt.current_classification_id = de_cls.id
                        AND de_cls.dtype = 'Cls'
                    {self._ACTIVE_JOIN_SQL}
                    WHERE {self._ACTIVE_COND_SQL}
                        AND cp.impact = 'High' 
                        AND p.name = ANY(%s)
                        AND (de_cls.name NOT IN ('False Positive', 'Intentional') OR de_cls.name IS NULL)
                """, (self._project_names,)),
            }
        else:
            # Global queries
            queries = {
                'total_projects': ("SELECT COUNT(*) FROM project WHERE deleted = false AND name != 'Developer Streams'", None),
                'total_streams': ("SELECT COUNT(*) FROM stream WHERE deleted = false", None),
                'total_defects': (f"""
                    SELECT COUNT(DISTINCT sd.id) FROM stream_defect sd
                    JOIN stream_element se ON sd.stream_element_id = se.id
                    LEFT JOIN defect_triage dt ON sd.defect_triage_id = dt.id
                    LEFT JOIN dynamic_enum de_cls ON dt.current_classification_id = de_cls.id
                        AND de_cls.dtype = 'Cls'
                    {self._ACTIVE_JOIN_SQL}
                    WHERE {self._ACTIVE_COND_SQL}
                        AND (de_cls.name NOT IN ('False Positive', 'Intentional') OR de_cls.name IS NULL)
                """, None),
                'total_files': (f"""
                    SELECT COALESCE(SUM(win.total_file_count), 0)
                    FROM (
                        SELECT DISTINCT ON (sn.stream_id) sn.total_file_count
                        FROM snapshot sn
                        JOIN stream s ON sn.stream_id = s.id
                        WHERE sn.deleted = false
                            AND s.deleted = false
                            {files_date_filter}
                        ORDER BY sn.stream_id, sn.id DESC
                    ) win
                """, None if days is None else (days,)),
                'total_functions': (f"""
                    SELECT COALESCE(SUM(win.function_count), 0)
                    FROM (
                        SELECT DISTINCT ON (sn.stream_id) sn.function_count
                        FROM snapshot sn
                        JOIN stream s ON sn.stream_id = s.id
                        WHERE sn.deleted = false
                            AND s.deleted = false
                            {files_date_filter}
                        ORDER BY sn.stream_id, sn.id DESC
                    ) win
                """, None if days is None else (days,)),
                'total_loc': (f"""
                    SELECT COALESCE(SUM(GREATEST(win.code_line_count, 0)), 0)
                    FROM (
                        SELECT DISTINCT ON (sn.stream_id) sn.code_line_count
                        FROM snapshot sn
                        JOIN stream s ON sn.stream_id = s.id
                        WHERE sn.deleted = false
                            AND s.deleted = false
                            {files_date_filter}
                        ORDER BY sn.stream_id, sn.id DESC
                    ) win
                """, None if days is None else (days,)),
                # Deduplicated active users (triage, login, or commit activity, excluding system/reporter)
                'total_users': ("""
                    SELECT COUNT(DISTINCT user_id) FROM (
                        -- Users who performed triage actions
                        SELECT DISTINCT ts.user_created_id as user_id
                        FROM triage_state ts
                        JOIN users u ON ts.user_created_id = u.id
                        WHERE ts.date_created >= CURRENT_DATE - INTERVAL '90 days'
                            AND ts.user_created_id IS NOT NULL
                            AND u.username NOT IN ('system', 'reporter')
                        UNION
                        -- Users who had login activity
                        SELECT DISTINCT ul.user_id
                        FROM user_login ul
                        JOIN users u ON ul.user_id = u.id
                        WHERE ul.session_start >= CURRENT_DATE - INTERVAL '90 days'
                            AND ul.user_id IS NOT NULL
                            AND u.username NOT IN ('system', 'reporter')
                        UNION
                        -- Users who committed snapshots
                        SELECT DISTINCT sn.committer_user_id as user_id
                        FROM snapshot sn
                        JOIN users u ON sn.committer_user_id = u.id
                        WHERE sn.date_created >= CURRENT_DATE - INTERVAL '90 days'
                            AND sn.committer_user_id IS NOT NULL
                            AND u.username NOT IN ('system', 'reporter')
                            AND sn.deleted = false
                    ) active_user_list
                """, None),
                'high_severity_defects': (f"""
                    SELECT COUNT(DISTINCT sd.id) FROM stream_defect sd 
                    JOIN checker_properties cp ON sd.checker_properties_id = cp.id 
                    JOIN stream_element se ON sd.stream_element_id = se.id
                    LEFT JOIN defect_triage dt ON sd.defect_triage_id = dt.id
                    LEFT JOIN dynamic_enum de_cls ON dt.current_classification_id = de_cls.id
                        AND de_cls.dtype = 'Cls'
                    {self._ACTIVE_JOIN_SQL}
                    WHERE {self._ACTIVE_COND_SQL} AND cp.impact = 'High'
                        AND (de_cls.name NOT IN ('False Positive', 'Intentional') OR de_cls.name IS NULL)
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
        
        At instance scope, each row is aggregated by (file, project) and
        includes a ``project_name`` column so the caller can attribute the
        hotspot to its owning project. At project scope, each row is
        aggregated by (file, stream) and includes a ``stream_name`` column
        instead â€” a finer split that's more useful when the project is
        already fixed.
        
        Args:
            limit: Maximum number of files to return (ignored if fetch_all=True)
            fetch_all: If True, fetch all files instead of top N hotspots
            
        Returns:
            pandas.DataFrame: File hotspots with defect counts
        """
        if self.project_name:
            name_select = "s.name as stream_name"
            name_group = "s.name"
        else:
            name_select = "p.name as project_name"
            name_group = "p.name"
        limit_clause = "" if fetch_all else "LIMIT %s"
        query = f"""
            SELECT 
                fp.filename as file_path,
                {name_select},
                COUNT(DISTINCT sdo.stream_defect_id) as defect_count,
                GREATEST(COALESCE(sf.current_code_line_count, 0), 0) as loc,
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
            LEFT JOIN defect_triage dt ON sd.defect_triage_id = dt.id
            LEFT JOIN dynamic_enum de_cls ON dt.current_classification_id = de_cls.id
                AND de_cls.dtype = 'Cls'
            {self._ACTIVE_JOIN_SQL}
            WHERE {self._ACTIVE_COND_SQL}
                AND (de_cls.name NOT IN ('False Positive', 'Intentional') OR de_cls.name IS NULL)
                AND p.deleted = false
                {{project_filter}}
            GROUP BY fp.filename, {name_group}, sf.current_code_line_count
            ORDER BY defect_count DESC
            {limit_clause}
        """
        if self.project_name:
            query = query.format(project_filter="AND p.name = ANY(%s)")
            params = (self._project_names,) if fetch_all else (self._project_names, limit)
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
        if self._project_names:
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
                    AND p.name = ANY(%s)
                GROUP BY p.name, p.date_created, p.deleted
                ORDER BY p.name
            """
            results = self.db.execute_query_dict(query, (self._project_names,))
        else:
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
                query = query.replace('WHERE', f"WHERE {table_alias}.name = ANY(%s) AND", 1)
            else:
                # Find the position before GROUP BY or ORDER BY
                for keyword in ['GROUP BY', 'ORDER BY', 'LIMIT']:
                    if keyword in query.upper():
                        pos = query.upper().index(keyword)
                        query = query[:pos] + f" WHERE {table_alias}.name = ANY(%s) " + query[pos:]
                        break
            return query, (self._project_names,)
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
                    from datetime import datetime, timezone
                    if isinstance(start_time, datetime):
                        # Get current time in UTC
                        now_utc = datetime.now(timezone.utc)
                        
                        # Convert start_time to UTC if it's timezone-aware, otherwise assume it's UTC
                        if start_time.tzinfo is not None:
                            start_time_utc = start_time.astimezone(timezone.utc)
                        else:
                            # If naive, assume it's already UTC
                            start_time_utc = start_time.replace(tzinfo=timezone.utc)
                        
                        # Calculate uptime
                        uptime = now_utc - start_time_utc
                        
                        # Handle negative uptime (should not happen, but guard against it)
                        if uptime.days < 0:
                            info['db_uptime_formatted'] = "Invalid (negative)"
                            info['db_uptime_days'] = 0
                            info['db_uptime_hours'] = 0
                            info['db_uptime_minutes'] = 0
                        else:
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
                        AND p.name = ANY(%s)
                        AND s.deleted = false
                """
                params = [self._project_names]
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
                    query += " AND s.date_created >= CURRENT_DATE - INTERVAL '1 day' * %s"
                else:
                    query += " AND date_created >= CURRENT_DATE - INTERVAL '1 day' * %s"
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
                ROUND(sn.duration_commit_total / 1000.0, 2) as duration_seconds,
                ROUND(sn.duration_issue_processing / 1000.0, 2) as issue_processing_seconds,
                ROUND(sn.duration_file_processing / 1000.0, 2) as file_processing_seconds,
                sn.queue_length,
                ROUND(sn.duration_on_queue / 1000.0, 2) as queue_time_seconds
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
                project_filter="AND p.name = ANY(%s)"
            )
            results = self.db.execute_query_dict(query, (self._project_names, limit))
        else:
            query = query.format(project_filter_join="", project_filter="")
            results = self.db.execute_query_dict(query, (limit,))
        
        return pd.DataFrame(results)
    
    def get_snapshot_commands(self, limit=20):
        """Get analysis and build command lines for recent snapshots.

        Reads `snapshot_element` rows attached to the N most recent snapshots
        (filtered by project when `project_name` is set). Each snapshot has one
        or more elements â€” typically one `SrcSE` (cov-build) and one `StcSE`
        (cov-analyze). Mirrors the "Command Line" data shown per snapshot in
        the Coverity Connect UI.

        Args:
            limit: Maximum number of recent snapshots to include.

        Returns:
            pandas.DataFrame: Columns snapshot_id, stream_name, date_created,
            dtype, command_type, command, invoker, host, platform,
            run_time_seconds, success_count, failure_count.
        """
        query = """
            WITH recent_snapshots AS (
                SELECT sn.id, sn.date_created, s.name AS stream_name
                FROM snapshot sn
                JOIN stream s ON sn.stream_id = s.id
                {project_filter_join}
                WHERE sn.deleted = false
                    {project_filter}
                ORDER BY sn.date_created DESC
                LIMIT %s
            )
            SELECT
                rs.id AS snapshot_id,
                rs.stream_name,
                rs.date_created,
                se.dtype,
                CASE se.dtype
                    WHEN 'SrcSE' THEN 'Build / Capture'
                    WHEN 'StcSE' THEN 'Static Analysis'
                    ELSE se.dtype
                END AS command_type,
                se.command,
                se.invoker,
                se.host,
                se.platform,
                ROUND(se.run_time / 1000.0, 1) AS run_time_seconds,
                se.success_count,
                se.failure_count
            FROM recent_snapshots rs
            JOIN snapshot_element se ON se.snapshot_id = rs.id
            WHERE se.command IS NOT NULL AND se.command <> ''
            ORDER BY rs.date_created DESC, rs.id DESC,
                     CASE se.dtype WHEN 'SrcSE' THEN 0 WHEN 'StcSE' THEN 1 ELSE 2 END,
                     se.id
        """

        if self.project_name:
            query = query.format(
                project_filter_join="""
                    JOIN project_stream ps ON s.id = ps.stream_id
                    JOIN project p ON ps.project_id = p.id
                """,
                project_filter="AND p.name = ANY(%s)"
            )
            results = self.db.execute_query_dict(query, (self._project_names, limit))
        else:
            query = query.format(project_filter_join="", project_filter="")
            results = self.db.execute_query_dict(query, (limit,))

        df = pd.DataFrame(results)
        if not df.empty:
            # Convert pandas NaN (from SQL NULLs on numeric cols) to None so Jinja
            # `is not none` and json.dumps produce clean, safe output
            df = df.astype(object).where(df.notna(), None)
        return df
    
    def get_commit_time_statistics(self):
        """Get commit/analysis time statistics
        
        Returns:
            dict: Commit time statistics
        """
        query = """
            SELECT 
                COUNT(*) as total_commits,
                ROUND(AVG(duration_commit_total / 1000.0), 2) as avg_duration_seconds,
                ROUND(MIN(duration_commit_total / 1000.0), 2) as min_duration_seconds,
                ROUND(MAX(duration_commit_total / 1000.0), 2) as max_duration_seconds,
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
                project_filter="AND p.name = ANY(%s)"
            )
            result = self.db.execute_query_dict(query, (self._project_names,))
        else:
            query = query.format(project_filter_join="", project_filter="")
            result = self.db.execute_query_dict(query)
        
        return result[0] if result else {}
    
    def get_commit_activity_patterns(self):
        """Get commit activity patterns - busiest and quietest times
        
        Analyzes when commits/snapshots occur by hour of day and day of week
        to identify busiest and quietest commit times.
        
        Returns:
            dict: Activity patterns with busiest/quietest times
                {
                    'by_hour': [{'hour': 14, 'commit_count': 150, ...}, ...],
                    'by_day_of_week': [{'day_name': 'Tuesday', 'day_num': 2, 'commit_count': 500, ...}, ...],
                    'busiest_hour': {'hour': 14, 'hour_display': '14:00 (2 PM)', 'commit_count': 150, ...},
                    'quietest_hour': {'hour': 3, 'hour_display': '03:00 (3 AM)', 'commit_count': 2, ...},
                    'busiest_day': {'day_name': 'Tuesday', 'commit_count': 500, ...},
                    'quietest_day': {'day_name': 'Saturday', 'commit_count': 15, ...},
                    'total_commits': 2500
                }
        """
        # Query for commits by hour of day
        query_by_hour = """
            SELECT 
                EXTRACT(HOUR FROM sn.date_created) as hour,
                COUNT(*) as commit_count,
                ROUND(AVG(sn.duration_commit_total / 1000.0), 2) as avg_duration_seconds,
                ROUND(AVG(sn.total_file_count), 0) as avg_files,
                ROUND(AVG(sn.new_defect_count), 0) as avg_new_defects
            FROM snapshot sn
            {project_filter_join}
            WHERE sn.deleted = false
                AND sn.date_created IS NOT NULL
                {project_filter}
            GROUP BY EXTRACT(HOUR FROM sn.date_created)
            ORDER BY hour
        """
        
        # Query for commits by day of week (0=Sunday, 6=Saturday in PostgreSQL)
        query_by_dow = """
            SELECT 
                EXTRACT(DOW FROM sn.date_created) as day_num,
                CASE 
                    WHEN EXTRACT(DOW FROM sn.date_created) = 0 THEN 'Sunday'
                    WHEN EXTRACT(DOW FROM sn.date_created) = 1 THEN 'Monday'
                    WHEN EXTRACT(DOW FROM sn.date_created) = 2 THEN 'Tuesday'
                    WHEN EXTRACT(DOW FROM sn.date_created) = 3 THEN 'Wednesday'
                    WHEN EXTRACT(DOW FROM sn.date_created) = 4 THEN 'Thursday'
                    WHEN EXTRACT(DOW FROM sn.date_created) = 5 THEN 'Friday'
                    WHEN EXTRACT(DOW FROM sn.date_created) = 6 THEN 'Saturday'
                END as day_name,
                COUNT(*) as commit_count,
                ROUND(AVG(sn.duration_commit_total / 1000.0), 2) as avg_duration_seconds,
                ROUND(AVG(sn.total_file_count), 0) as avg_files,
                ROUND(AVG(sn.new_defect_count), 0) as avg_new_defects
            FROM snapshot sn
            {project_filter_join}
            WHERE sn.deleted = false
                AND sn.date_created IS NOT NULL
                {project_filter}
            GROUP BY EXTRACT(DOW FROM sn.date_created), day_name
            ORDER BY day_num
        """
        
        if self.project_name:
            query_by_hour = query_by_hour.format(
                project_filter_join="""
                    JOIN stream s ON sn.stream_id = s.id
                    JOIN project_stream ps ON s.id = ps.stream_id
                    JOIN project p ON ps.project_id = p.id
                """,
                project_filter="AND p.name = ANY(%s)"
            )
            query_by_dow = query_by_dow.format(
                project_filter_join="""
                    JOIN stream s ON sn.stream_id = s.id
                    JOIN project_stream ps ON s.id = ps.stream_id
                    JOIN project p ON ps.project_id = p.id
                """,
                project_filter="AND p.name = ANY(%s)"
            )
            by_hour = self.db.execute_query_dict(query_by_hour, (self._project_names,))
            by_dow = self.db.execute_query_dict(query_by_dow, (self._project_names,))
        else:
            query_by_hour = query_by_hour.format(project_filter_join="", project_filter="")
            query_by_dow = query_by_dow.format(project_filter_join="", project_filter="")
            by_hour = self.db.execute_query_dict(query_by_hour)
            by_dow = self.db.execute_query_dict(query_by_dow)
        
        result = {
            'by_hour': by_hour,
            'by_day_of_week': by_dow,
            'total_commits': sum(row['commit_count'] for row in by_hour) if by_hour else 0
        }
        
        # Group hours into 3-hour blocks and find busiest/quietest
        if by_hour:
            # Create 3-hour blocks: 0-2, 3-5, 6-8, 9-11, 12-14, 15-17, 18-20, 21-23
            blocks = {}
            for hour_row in by_hour:
                hour = int(hour_row['hour'])
                block_start = (hour // 3) * 3
                block_key = block_start
                
                if block_key not in blocks:
                    blocks[block_key] = {
                        'block_start': block_start,
                        'commit_count': 0,
                        'total_duration': 0,
                        'total_files': 0,
                        'total_new_defects': 0,
                        'hour_count': 0
                    }
                
                blocks[block_key]['commit_count'] += hour_row['commit_count']
                blocks[block_key]['total_duration'] += (hour_row.get('avg_duration_seconds', 0) or 0) * hour_row['commit_count']
                blocks[block_key]['total_files'] += (hour_row.get('avg_files', 0) or 0) * hour_row['commit_count']
                blocks[block_key]['total_new_defects'] += (hour_row.get('avg_new_defects', 0) or 0) * hour_row['commit_count']
                blocks[block_key]['hour_count'] += 1
            
            # Calculate averages for each block
            for block in blocks.values():
                count = block['commit_count']
                if count > 0:
                    block['avg_duration_seconds'] = round(block['total_duration'] / count, 2)
                    block['avg_files'] = round(block['total_files'] / count, 0)
                    block['avg_new_defects'] = round(block['total_new_defects'] / count, 0)
                else:
                    block['avg_duration_seconds'] = 0
                    block['avg_files'] = 0
                    block['avg_new_defects'] = 0
            
            # Find busiest and quietest 3-hour blocks
            if blocks:
                busiest_block = max(blocks.values(), key=lambda x: x['commit_count'])
                quietest_block = min(blocks.values(), key=lambda x: x['commit_count'])
                
                # Format block display
                def format_block(block_start):
                    start = int(block_start)
                    end = start + 2
                    
                    # Format start hour
                    start_12 = start if start <= 12 else start - 12
                    start_12 = 12 if start_12 == 0 else start_12
                    start_ampm = 'AM' if start < 12 else 'PM'
                    
                    # Format end hour
                    end_12 = end if end <= 12 else end - 12
                    end_12 = 12 if end_12 == 0 else end_12
                    end_ampm = 'AM' if end < 12 else 'PM'
                    
                    return f"{start:02d}:00-{end:02d}:00 ({start_12} {start_ampm} - {end_12} {end_ampm})"
                
                result['busiest_hours'] = {
                    'block_start': busiest_block['block_start'],
                    'block_end': busiest_block['block_start'] + 2,
                    'hours_display': format_block(busiest_block['block_start']),
                    'commit_count': busiest_block['commit_count'],
                    'avg_duration_seconds': busiest_block['avg_duration_seconds'],
                    'avg_files': busiest_block['avg_files'],
                    'avg_new_defects': busiest_block['avg_new_defects']
                }
                result['quietest_hours'] = {
                    'block_start': quietest_block['block_start'],
                    'block_end': quietest_block['block_start'] + 2,
                    'hours_display': format_block(quietest_block['block_start']),
                    'commit_count': quietest_block['commit_count'],
                    'avg_duration_seconds': quietest_block['avg_duration_seconds'],
                    'avg_files': quietest_block['avg_files'],
                    'avg_new_defects': quietest_block['avg_new_defects']
                }
        
        # Find busiest and quietest days
        if by_dow:
            busiest_day = max(by_dow, key=lambda x: x['commit_count'])
            quietest_day = min(by_dow, key=lambda x: x['commit_count'])
            
            result['busiest_day'] = busiest_day
            result['quietest_day'] = quietest_day
        
        return result
    
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
                AND sn.date_created >= CURRENT_DATE - INTERVAL '1 day' * %s
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
                project_filter="AND p.name = ANY(%s)"
            )
            results = self.db.execute_query_dict(query, (days, self._project_names))
        else:
            query = query.format(project_filter_join="", project_filter="")
            results = self.db.execute_query_dict(query, (days,))
        
        return pd.DataFrame(results)

    # ========== TREND ANALYSIS METRICS ==========
    
    def get_defect_trends(self, days=90, granularity='week'):
        """Get defect trends over time showing new, fixed, and outstanding defects
        Includes both code-based fixes and triaged defects (False Positive/Intentional)
        
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
                    SUM(sn.eliminated_defect_count) as code_fixed_defects,
                    AVG(sn.total_defect_count) as avg_outstanding_defects,
                    MAX(sn.total_defect_count) as max_outstanding_defects
                FROM snapshot sn
                {{project_filter_join}}
                WHERE sn.deleted = false
                    AND sn.date_created >= CURRENT_DATE - INTERVAL '1 day' * %s
                    {{project_filter}}
                GROUP BY period
            ),
            triaged_metrics AS (
                -- Count defects triaged as False Positive or Intentional in each period
                SELECT 
                    {date_trunc.replace('sn.date_created', 'ts.date_created')} as period,
                    COUNT(DISTINCT sd.id) as triaged_defects
                FROM stream_defect sd
                JOIN defect_triage dt ON sd.defect_triage_id = dt.id
                JOIN triage_state ts ON dt.current_triage_state_id = ts.id
                JOIN dynamic_enum de ON dt.current_classification_id = de.id
                JOIN stream_element se ON sd.stream_element_id = se.id
                JOIN stream s ON se.stream_id = s.id
                {self._ACTIVE_JOIN_SQL}
                {{project_filter_join_triage}}
                WHERE de.dtype = 'Cls'
                    AND de.name IN ('False Positive', 'Intentional')
                    AND {self._ACTIVE_COND_SQL}
                    AND ts.date_created >= CURRENT_DATE - INTERVAL '1 day' * %s
                    {{project_filter_triage}}
                GROUP BY period
            )
            SELECT 
                COALESCE(sm.period, tm.period) as period,
                COALESCE(sm.new_defects, 0) as new_defects,
                COALESCE(sm.code_fixed_defects, 0) + COALESCE(tm.triaged_defects, 0) as fixed_defects,
                ROUND(COALESCE(sm.avg_outstanding_defects, 0)::numeric, 0) as outstanding_defects,
                COALESCE(sm.max_outstanding_defects, 0) as max_outstanding_defects,
                (COALESCE(sm.new_defects, 0) - (COALESCE(sm.code_fixed_defects, 0) + COALESCE(tm.triaged_defects, 0))) as net_change
            FROM snapshot_metrics sm
            FULL OUTER JOIN triaged_metrics tm ON sm.period = tm.period
            ORDER BY COALESCE(sm.period, tm.period) ASC
        """
        
        if self.project_name:
            query = query.format(
                project_filter_join="""
                    JOIN stream s ON sn.stream_id = s.id
                    JOIN project_stream ps ON s.id = ps.stream_id
                    JOIN project p ON ps.project_id = p.id
                """,
                project_filter="AND p.name = ANY(%s)",
                project_filter_join_triage="""
                    JOIN project_stream ps ON s.id = ps.stream_id
                    JOIN project p ON ps.project_id = p.id
                """,
                project_filter_triage="AND p.name = ANY(%s)"
            )
            results = self.db.execute_query_dict(query, (days, self._project_names, days, self._project_names))
        else:
            query = query.format(
                project_filter_join="", 
                project_filter="",
                project_filter_join_triage="",
                project_filter_triage=""
            )
            results = self.db.execute_query_dict(query, (days, days))
        
        return pd.DataFrame(results)
    
    def get_triage_trends(self, days=90, granularity='week'):
        """Get triage classification distribution of active defects, grouped by stream.

        Shows ALL currently active defects, broken down by stream and their CURRENT
        classification, so every triage bucket that Coverity Connect displays is
        represented â€” ``Bug``, ``False Positive``, ``Intentional``, ``Pending``,
        ``Untriaged``, etc. â€” plus an ``Unclassified`` bucket for defects that have no
        triage record yet (``defect_triage_id IS NULL`` or classification not set).
        Streams are ordered so those with the most unclassified defects appear first,
        highlighting where triage attention is most needed.

        Args:
            days: Not used (kept for API compatibility).
            granularity: Not used (kept for API compatibility).
            
        Returns:
            pandas.DataFrame: Active defect counts per stream and classification
        """
        query = f"""
            SELECT 
                s.name as stream,
                COALESCE(de.name, 'Unclassified') as classification,
                COUNT(DISTINCT sd.id) as count
            FROM stream_defect sd
            JOIN stream_element se ON sd.stream_element_id = se.id
            JOIN stream s ON se.stream_id = s.id
            LEFT JOIN defect_triage dt ON sd.defect_triage_id = dt.id
            LEFT JOIN dynamic_enum de ON dt.current_classification_id = de.id AND de.dtype = 'Cls'
            {self._ACTIVE_JOIN_SQL}
            {{project_filter_join}}
            WHERE {self._ACTIVE_COND_SQL}
                {{project_filter}}
            GROUP BY s.name, COALESCE(de.name, 'Unclassified')
            ORDER BY
                COUNT(DISTINCT CASE WHEN de.name IS NULL OR de.name = 'Unclassified' THEN sd.id END) DESC,
                s.name,
                COALESCE(de.name, 'Unclassified')
        """
        
        if self.project_name:
            query = query.format(
                project_filter_join="""
                    JOIN project_stream ps ON s.id = ps.stream_id
                    JOIN project p ON ps.project_id = p.id
                """,
                project_filter="AND p.name = ANY(%s)"
            )
            results = self.db.execute_query_dict(query, (self._project_names,))
        else:
            query = query.format(project_filter_join="", project_filter="")
            results = self.db.execute_query_dict(query)
        
        return pd.DataFrame(results)

    def get_checker_classification_breakdown(self, limit=15):
        """Get triage classification breakdown for the top checkers with classified defects.

        Identifies which checker rules accumulate the most explicit triage classifications
        (False Positive, Intentional, Bug).  Only defects that have been explicitly
        classified are included â€” Unclassified defects are intentionally excluded so the
        result focuses on deliberate decisions.  Checkers are ranked by the sum of
        False Positive + Intentional counts (noise / accepted-debt signal), helping teams
        spot overly noisy rules or rules whose findings are routinely dismissed.

        Args:
            limit: Maximum number of distinct checkers to include (top N by FP + Intentional).

        Returns:
            pandas.DataFrame: Rows with checker_name, classification, count columns.
        """
        query = f"""
            WITH classified AS (
                SELECT
                    ct.name AS checker_name,
                    de.name AS classification,
                    COUNT(DISTINCT sd.id) AS count
                FROM stream_defect sd
                JOIN checker_properties cp ON sd.checker_properties_id = cp.id
                JOIN checker_type ct ON cp.checker_type_id = ct.id
                JOIN stream_element se ON sd.stream_element_id = se.id
                JOIN stream s ON se.stream_id = s.id
                JOIN defect_triage dt ON sd.defect_triage_id = dt.id
                JOIN dynamic_enum de ON dt.current_classification_id = de.id AND de.dtype = 'Cls'
                {self._ACTIVE_JOIN_SQL}
                {{project_filter_join}}
                WHERE {self._ACTIVE_COND_SQL}
                    AND de.name != 'Unclassified'
                    {{project_filter}}
                GROUP BY ct.name, de.name
            ),
            top_checkers AS (
                SELECT checker_name,
                       SUM(CASE WHEN classification IN ('False Positive', 'Intentional') THEN count ELSE 0 END) AS fp_int_count
                FROM classified
                GROUP BY checker_name
                ORDER BY fp_int_count DESC
                LIMIT {limit}
            )
            SELECT c.checker_name, c.classification, c.count
            FROM classified c
            JOIN top_checkers tc ON c.checker_name = tc.checker_name
            ORDER BY tc.fp_int_count DESC, c.checker_name, c.classification
        """

        if self.project_name:
            query = query.format(
                project_filter_join="""
                    JOIN project_stream ps ON s.id = ps.stream_id
                    JOIN project p ON ps.project_id = p.id
                """,
                project_filter="AND p.name = ANY(%s)"
            )
            results = self.db.execute_query_dict(query, (self._project_names,))
        else:
            query = query.format(project_filter_join="", project_filter="")
            results = self.db.execute_query_dict(query)

        return pd.DataFrame(results)

    def get_top_projects_by_classification(self, limit=10):
        """Get the top projects (or streams at project level) ranked by Intentional count.

        At the instance level shows top *projects*; at the project level shows top
        *streams* within that project.  All classification buckets are returned
        (including Unclassified) so the bar chart can show the full triage picture
        alongside the Intentional highlight.

        The primary sort key is Intentional count descending â€” highlighting teams
        that may be marking defects Intentional to pass a security quality gate
        without addressing the underlying findings.

        Args:
            limit: Maximum number of projects/streams to return.

        Returns:
            pandas.DataFrame: Rows with name (project or stream), classification, count.
        """
        if self.project_name:
            name_col = "s.name"
            extra_join = """
                JOIN project_stream ps ON s.id = ps.stream_id
                JOIN project p ON ps.project_id = p.id
            """
            where_filter = "AND p.name = ANY(%s)"
        else:
            name_col = "p.name"
            extra_join = """
                JOIN project_stream ps ON s.id = ps.stream_id
                JOIN project p ON ps.project_id = p.id
            """
            where_filter = "AND p.deleted = false"

        query = f"""
            WITH classified AS (
                SELECT
                    {name_col} AS name,
                    COALESCE(de.name, 'Unclassified') AS classification,
                    COUNT(DISTINCT sd.id) AS count
                FROM stream_defect sd
                JOIN stream_element se ON sd.stream_element_id = se.id
                JOIN stream s ON se.stream_id = s.id
                {extra_join}
                LEFT JOIN defect_triage dt ON sd.defect_triage_id = dt.id
                LEFT JOIN dynamic_enum de ON dt.current_classification_id = de.id AND de.dtype = 'Cls'
                {self._ACTIVE_JOIN_SQL}
                WHERE {self._ACTIVE_COND_SQL}
                    {where_filter}
                GROUP BY {name_col}, COALESCE(de.name, 'Unclassified')
            ),
            top_names AS (
                SELECT name,
                       SUM(CASE WHEN classification = 'Intentional' THEN count ELSE 0 END) AS intentional_count
                FROM classified
                GROUP BY name
                ORDER BY intentional_count DESC
                LIMIT {limit}
            )
            SELECT c.name, c.classification, c.count
            FROM classified c
            JOIN top_names tn ON c.name = tn.name
            ORDER BY tn.intentional_count DESC, c.name, c.classification
        """

        if self.project_name:
            results = self.db.execute_query_dict(query, (self._project_names,))
        else:
            results = self.db.execute_query_dict(query)

        return pd.DataFrame(results)

    def get_fix_rate_metrics(self, days=90):
        """Get defect fix rate and velocity metrics using snapshot data
        
        Args:
            days: Number of days to analyze
            
        Returns:
            dict: Fix rate statistics
        """
        query = f"""
            WITH fix_stats AS (
                SELECT 
                    SUM(sn.new_defect_count) as total_new,
                    SUM(sn.eliminated_defect_count) as code_fixed,
                    AVG(sn.total_defect_count) as avg_outstanding
                FROM snapshot sn
                {{project_filter_join}}
                WHERE sn.deleted = false
                    AND sn.date_created >= CURRENT_DATE - INTERVAL '1 day' * %s
                    {{project_filter}}
            ),
            triaged_stats AS (
                -- Count defects triaged as False Positive or Intentional
                SELECT 
                    COUNT(DISTINCT sd.id) as triaged_fixed
                FROM stream_defect sd
                JOIN defect_triage dt ON sd.defect_triage_id = dt.id
                JOIN triage_state ts ON dt.current_triage_state_id = ts.id
                JOIN dynamic_enum de ON dt.current_classification_id = de.id
                JOIN stream_element se ON sd.stream_element_id = se.id
                JOIN stream s ON se.stream_id = s.id
                {self._ACTIVE_JOIN_SQL}
                {{project_filter_join_triaged_stats}}
                WHERE de.dtype = 'Cls'
                    AND de.name IN ('False Positive', 'Intentional')
                    AND {self._ACTIVE_COND_SQL}
                    AND ts.date_created >= CURRENT_DATE - INTERVAL '1 day' * %s
                    {{project_filter_triaged_stats}}
            ),
            fix_times AS (
                -- Calculate actual fix times using snapshot_element and snapshot
                -- Includes both: defects removed from code + defects triaged as FP/Intentional
                SELECT 
                    EXTRACT(EPOCH FROM (sn_fix.date_created - sn_detect.date_created)) / 86400.0 as days_to_fix
                FROM stream_defect sd
                -- Join to get detection snapshot date
                JOIN snapshot_element se_detect ON sd.first_snapshot_element_id = se_detect.id
                JOIN snapshot sn_detect ON se_detect.snapshot_id = sn_detect.id
                -- Join to get fix snapshot date
                JOIN snapshot_element se_fix ON sd.fixed_snapshot_element_id = se_fix.id
                JOIN snapshot sn_fix ON se_fix.snapshot_id = sn_fix.id
                -- Join to stream for project filtering
                JOIN stream_element se ON sd.stream_element_id = se.id
                JOIN stream s ON se.stream_id = s.id
                {self._ACTIVE_JOIN_SQL}
                {{project_filter_join_fix}}
                WHERE sd.fixed_snapshot_element_id IS NOT NULL
                    AND {self._FIXED_COND_SQL}
                    AND sd.first_snapshot_element_id IS NOT NULL
                    AND sn_fix.date_created >= CURRENT_DATE - INTERVAL '1 day' * %s
                    AND sn_fix.date_created > sn_detect.date_created
                    {{project_filter_fix}}
                
                UNION ALL
                
                -- Include defects triaged as False Positive or Intentional
                SELECT 
                    EXTRACT(EPOCH FROM (ts.date_created - sn_detect.date_created)) / 86400.0 as days_to_fix
                FROM stream_defect sd
                -- Join to get detection snapshot date
                JOIN snapshot_element se_detect ON sd.first_snapshot_element_id = se_detect.id
                JOIN snapshot sn_detect ON se_detect.snapshot_id = sn_detect.id
                -- Join to get triage classification
                JOIN defect_triage dt ON sd.defect_triage_id = dt.id
                JOIN triage_state ts ON dt.current_triage_state_id = ts.id
                JOIN dynamic_enum de ON dt.current_classification_id = de.id
                -- Join to stream for project filtering
                JOIN stream_element se ON sd.stream_element_id = se.id
                JOIN stream s ON se.stream_id = s.id
                {self._ACTIVE_JOIN_SQL}
                {{project_filter_join_triage}}
                WHERE de.dtype = 'Cls'
                    AND de.name IN ('False Positive', 'Intentional')
                    AND {self._ACTIVE_COND_SQL}  -- Not already counted in code-based fixes
                    AND sd.first_snapshot_element_id IS NOT NULL
                    AND ts.date_created >= CURRENT_DATE - INTERVAL '1 day' * %s
                    AND ts.date_created > sn_detect.date_created
                    {{project_filter_triage}}
            )
            SELECT 
                fs.total_new as total_defects,
                COALESCE(fs.code_fixed, 0) + COALESCE(ts.triaged_fixed, 0) as fixed_defects,
                ROUND(((COALESCE(fs.code_fixed, 0) + COALESCE(ts.triaged_fixed, 0))::numeric / NULLIF(fs.total_new, 0) * 100), 2) as fix_rate_percentage,
                ROUND((SELECT AVG(days_to_fix)::numeric FROM fix_times), 1) as avg_days_to_fix,
                ROUND((SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY days_to_fix)::numeric FROM fix_times), 1) as median_days_to_fix,
                ROUND((SELECT MIN(days_to_fix)::numeric FROM fix_times WHERE days_to_fix >= 0), 1) as min_days_to_fix,
                ROUND((SELECT MAX(days_to_fix)::numeric FROM fix_times), 1) as max_days_to_fix
            FROM fix_stats fs, triaged_stats ts
        """
        
        if self.project_name:
            query = query.format(
                project_filter_join="""
                    JOIN stream s ON sn.stream_id = s.id
                    JOIN project_stream ps ON s.id = ps.stream_id
                    JOIN project p ON ps.project_id = p.id
                """,
                project_filter="AND p.name = ANY(%s)",
                project_filter_join_triaged_stats="""
                    JOIN project_stream ps ON s.id = ps.stream_id
                    JOIN project p ON ps.project_id = p.id
                """,
                project_filter_triaged_stats="AND p.name = ANY(%s)",
                project_filter_join_fix="""
                    JOIN project_stream ps ON s.id = ps.stream_id
                    JOIN project p ON ps.project_id = p.id
                """,
                project_filter_fix="AND p.name = ANY(%s)",
                project_filter_join_triage="""
                    JOIN project_stream ps ON s.id = ps.stream_id
                    JOIN project p ON ps.project_id = p.id
                """,
                project_filter_triage="AND p.name = ANY(%s)"
            )
            result = self.db.execute_query_dict(query, (days, self._project_names, days, self._project_names, days, self._project_names, days, self._project_names))
        else:
            query = query.format(
                project_filter_join="", 
                project_filter="",
                project_filter_join_triaged_stats="",
                project_filter_triaged_stats="",
                project_filter_join_fix="",
                project_filter_fix="",
                project_filter_join_triage="",
                project_filter_triage=""
            )
            result = self.db.execute_query_dict(query, (days, days, days, days))
        
        return result[0] if result else {}
    
    def get_defect_velocity_trend(self, days=90):
        """Get defect velocity showing introduction rate vs fix rate over time
        Includes both code-based fixes and triaged defects (False Positive/Intentional)
        
        Args:
            days: Number of days to analyze
            
        Returns:
            pandas.DataFrame: Daily velocities with introduction and fix rates
        """
        query = f"""
            WITH daily_snapshot_metrics AS (
                SELECT 
                    DATE(sn.date_created) as snapshot_date,
                    SUM(sn.new_defect_count) as new_count,
                    SUM(sn.eliminated_defect_count) as code_fixed_count,
                    AVG(sn.total_defect_count) as outstanding_count
                FROM snapshot sn
                {{project_filter_join}}
                WHERE sn.deleted = false
                    AND sn.date_created >= CURRENT_DATE - INTERVAL '1 day' * %s
                    {{project_filter}}
                GROUP BY DATE(sn.date_created)
            ),
            daily_triaged_metrics AS (
                -- Count defects triaged as False Positive or Intentional per day
                SELECT 
                    DATE(ts.date_created) as snapshot_date,
                    COUNT(DISTINCT sd.id) as triaged_count
                FROM stream_defect sd
                JOIN defect_triage dt ON sd.defect_triage_id = dt.id
                JOIN triage_state ts ON dt.current_triage_state_id = ts.id
                JOIN dynamic_enum de ON dt.current_classification_id = de.id
                JOIN stream_element se ON sd.stream_element_id = se.id
                JOIN stream s ON se.stream_id = s.id
                {self._ACTIVE_JOIN_SQL}
                {{project_filter_join_triage}}
                WHERE de.dtype = 'Cls'
                    AND de.name IN ('False Positive', 'Intentional')
                    AND {self._ACTIVE_COND_SQL}
                    AND ts.date_created >= CURRENT_DATE - INTERVAL '1 day' * %s
                    {{project_filter_triage}}
                GROUP BY DATE(ts.date_created)
            )
            SELECT 
                COALESCE(sm.snapshot_date, tm.snapshot_date) as snapshot_date,
                COALESCE(sm.new_count, 0) as new_count,
                COALESCE(sm.code_fixed_count, 0) + COALESCE(tm.triaged_count, 0) as fixed_count,
                (COALESCE(sm.new_count, 0) - (COALESCE(sm.code_fixed_count, 0) + COALESCE(tm.triaged_count, 0))) as net_change,
                ROUND(COALESCE(sm.outstanding_count, 0)::numeric, 0) as outstanding,
                CASE 
                    WHEN (COALESCE(sm.new_count, 0) + COALESCE(sm.code_fixed_count, 0) + COALESCE(tm.triaged_count, 0)) = 0 THEN 0
                    ELSE ROUND(
                        ((COALESCE(sm.code_fixed_count, 0) + COALESCE(tm.triaged_count, 0))::numeric
                         / (COALESCE(sm.new_count, 0) + COALESCE(sm.code_fixed_count, 0) + COALESCE(tm.triaged_count, 0))) * 100,
                        1)
                END as fix_efficiency_pct
            FROM daily_snapshot_metrics sm
            FULL OUTER JOIN daily_triaged_metrics tm ON sm.snapshot_date = tm.snapshot_date
            ORDER BY COALESCE(sm.snapshot_date, tm.snapshot_date) ASC
        """
        
        if self.project_name:
            query = query.format(
                project_filter_join="""
                    JOIN stream s ON sn.stream_id = s.id
                    JOIN project_stream ps ON s.id = ps.stream_id
                    JOIN project p ON ps.project_id = p.id
                """,
                project_filter="AND p.name = ANY(%s)",
                project_filter_join_triage="""
                    JOIN project_stream ps ON s.id = ps.stream_id
                    JOIN project p ON ps.project_id = p.id
                """,
                project_filter_triage="AND p.name = ANY(%s)"
            )
            results = self.db.execute_query_dict(query, (days, self._project_names, days, self._project_names))
        else:
            query = query.format(
                project_filter_join="", 
                project_filter="",
                project_filter_join_triage="",
                project_filter_triage=""
            )
            results = self.db.execute_query_dict(query, (days, days))
        
        return pd.DataFrame(results)
    
    def get_scan_activity_trend(self, days=90, granularity='day'):
        """Get snapshot (scan/commit) activity bucketed over time.

        Args:
            days: Number of days to analyze.
            granularity: Bucket size â€” one of 'day', 'week', 'month'.
                Defaults to 'day'. Anything else falls back to 'day'.

        Returns:
            pandas.DataFrame with columns:
                period (date of bucket start),
                scan_count,
                unique_committers,
                total_files_analyzed,
                total_new_defects,
                total_eliminated_defects.
        """
        # Whitelist granularity â€” value is injected directly into SQL, not bound.
        allowed = {'day', 'week', 'month'}
        bucket = granularity if granularity in allowed else 'day'

        query = f"""
            SELECT
                DATE_TRUNC('{bucket}', sn.date_created)::date as period,
                COUNT(*) as scan_count,
                COUNT(DISTINCT sn.committer_user_id) as unique_committers,
                COALESCE(SUM(sn.total_file_count), 0) as total_files_analyzed,
                COALESCE(SUM(sn.new_defect_count), 0) as total_new_defects,
                COALESCE(SUM(sn.eliminated_defect_count), 0) as total_eliminated_defects
            FROM snapshot sn
            {{project_filter_join}}
            WHERE sn.deleted = false
                AND sn.date_created >= CURRENT_DATE - INTERVAL '1 day' * %s
                {{project_filter}}
            GROUP BY DATE_TRUNC('{bucket}', sn.date_created)
            ORDER BY period ASC
        """

        if self.project_name:
            query = query.format(
                project_filter_join="""
                    JOIN stream s ON sn.stream_id = s.id
                    JOIN project_stream ps ON s.id = ps.stream_id
                    JOIN project p ON ps.project_id = p.id
                """,
                project_filter="AND p.name = ANY(%s)"
            )
            results = self.db.execute_query_dict(query, (days, self._project_names))
        else:
            query = query.format(project_filter_join="", project_filter="")
            results = self.db.execute_query_dict(query, (days,))

        return pd.DataFrame(results)

    def get_cumulative_defect_trend(self, days=90):
        """Get cumulative defect counts over time
        Includes both code-based fixes and triaged defects (False Positive/Intentional)
        
        Args:
            days: Number of days to analyze
            
        Returns:
            pandas.DataFrame: Cumulative new, fixed, and net defects
        """
        query = f"""
            WITH daily_snapshot_metrics AS (
                SELECT 
                    DATE(sn.date_created) as snapshot_date,
                    SUM(sn.new_defect_count) as daily_new,
                    SUM(sn.eliminated_defect_count) as daily_code_fixed
                FROM snapshot sn
                {{project_filter_join}}
                WHERE sn.deleted = false
                    AND sn.date_created >= CURRENT_DATE - INTERVAL '1 day' * %s
                    {{project_filter}}
                GROUP BY DATE(sn.date_created)
            ),
            daily_triaged_metrics AS (
                -- Count defects triaged as False Positive or Intentional per day
                SELECT 
                    DATE(ts.date_created) as snapshot_date,
                    COUNT(DISTINCT sd.id) as daily_triaged
                FROM stream_defect sd
                JOIN defect_triage dt ON sd.defect_triage_id = dt.id
                JOIN triage_state ts ON dt.current_triage_state_id = ts.id
                JOIN dynamic_enum de ON dt.current_classification_id = de.id
                JOIN stream_element se ON sd.stream_element_id = se.id
                JOIN stream s ON se.stream_id = s.id
                {self._ACTIVE_JOIN_SQL}
                {{project_filter_join_triage}}
                WHERE de.dtype = 'Cls'
                    AND de.name IN ('False Positive', 'Intentional')
                    AND {self._ACTIVE_COND_SQL}
                    AND ts.date_created >= CURRENT_DATE - INTERVAL '1 day' * %s
                    {{project_filter_triage}}
                GROUP BY DATE(ts.date_created)
            ),
            daily_combined AS (
                SELECT 
                    COALESCE(sm.snapshot_date, tm.snapshot_date) as snapshot_date,
                    COALESCE(sm.daily_new, 0) as daily_new,
                    COALESCE(sm.daily_code_fixed, 0) + COALESCE(tm.daily_triaged, 0) as daily_fixed
                FROM daily_snapshot_metrics sm
                FULL OUTER JOIN daily_triaged_metrics tm ON sm.snapshot_date = tm.snapshot_date
                ORDER BY snapshot_date ASC
            )
            SELECT 
                snapshot_date,
                daily_new,
                daily_fixed,
                SUM(daily_new) OVER (ORDER BY snapshot_date) as cumulative_new,
                SUM(daily_fixed) OVER (ORDER BY snapshot_date) as cumulative_fixed,
                SUM(daily_new - daily_fixed) OVER (ORDER BY snapshot_date) as cumulative_net
            FROM daily_combined
            ORDER BY snapshot_date ASC
        """
        
        if self.project_name:
            query = query.format(
                project_filter_join="""
                    JOIN stream s ON sn.stream_id = s.id
                    JOIN project_stream ps ON s.id = ps.stream_id
                    JOIN project p ON ps.project_id = p.id
                """,
                project_filter="AND p.name = ANY(%s)",
                project_filter_join_triage="""
                    JOIN project_stream ps ON s.id = ps.stream_id
                    JOIN project p ON ps.project_id = p.id
                """,
                project_filter_triage="AND p.name = ANY(%s)"
            )
            results = self.db.execute_query_dict(query, (days, self._project_names, days, self._project_names))
        else:
            query = query.format(
                project_filter_join="", 
                project_filter="",
                project_filter_join_triage="",
                project_filter_triage=""
            )
            results = self.db.execute_query_dict(query, (days, days))
        
        return pd.DataFrame(results)
    
    def get_defect_trend_summary(self, days=90):
        """Get summary statistics for defect trends
        Includes both code-based fixes and triaged defects (False Positive/Intentional)
        
        Args:
            days: Number of days to analyze
            
        Returns:
            dict: Summary statistics including rates and trends
        """
        query = f"""
            WITH period_snapshot_metrics AS (
                SELECT 
                    SUM(sn.new_defect_count) as total_new,
                    SUM(sn.eliminated_defect_count) as total_code_fixed,
                    COUNT(DISTINCT DATE(sn.date_created)) as days_with_data
                FROM snapshot sn
                {{project_filter_join_period}}
                WHERE sn.deleted = false
                    AND sn.date_created >= CURRENT_DATE - INTERVAL '1 day' * %s
                    {{project_filter_period}}
            ),
            period_triaged_metrics AS (
                -- Count defects triaged as False Positive or Intentional in period
                SELECT 
                    COUNT(DISTINCT sd.id) as total_triaged
                FROM stream_defect sd
                JOIN defect_triage dt ON sd.defect_triage_id = dt.id
                JOIN triage_state ts ON dt.current_triage_state_id = ts.id
                JOIN dynamic_enum de ON dt.current_classification_id = de.id
                JOIN stream_element se ON sd.stream_element_id = se.id
                JOIN stream s ON se.stream_id = s.id
                {self._ACTIVE_JOIN_SQL}
                {{project_filter_join_triaged}}
                WHERE de.dtype = 'Cls'
                    AND de.name IN ('False Positive', 'Intentional')
                    AND {self._ACTIVE_COND_SQL}
                    AND ts.date_created >= CURRENT_DATE - INTERVAL '1 day' * %s
                    {{project_filter_triaged}}
            ),
            current_state AS (
                SELECT COUNT(*) as current_outstanding
                FROM stream_defect sd
                JOIN stream_element se ON sd.stream_element_id = se.id
                JOIN stream s ON se.stream_id = s.id
                LEFT JOIN defect_triage dt_cs ON sd.defect_triage_id = dt_cs.id
                LEFT JOIN dynamic_enum de_cs ON dt_cs.current_classification_id = de_cs.id
                    AND de_cs.dtype = 'Cls'
                {self._ACTIVE_JOIN_SQL}
                {{project_filter_join_current}}
                WHERE {self._ACTIVE_COND_SQL}
                    AND (de_cs.name NOT IN ('False Positive', 'Intentional') OR de_cs.name IS NULL)
                    {{project_filter_current}}
            )
            SELECT 
                pm.total_new,
                (pm.total_code_fixed + COALESCE(tm.total_triaged, 0)) as total_fixed,
                (pm.total_new - (pm.total_code_fixed + COALESCE(tm.total_triaged, 0))) as net_change,
                ROUND((pm.total_new::numeric / NULLIF(pm.days_with_data, 0)), 2) as avg_new_per_day,
                ROUND(((pm.total_code_fixed + COALESCE(tm.total_triaged, 0))::numeric / NULLIF(pm.days_with_data, 0)), 2) as avg_fixed_per_day,
                ROUND((((pm.total_code_fixed + COALESCE(tm.total_triaged, 0))::numeric / NULLIF(pm.total_new, 0)) * 100), 2) as fix_rate_pct,
                cs.current_outstanding,
                CASE 
                    WHEN (pm.total_code_fixed + COALESCE(tm.total_triaged, 0)) > pm.total_new THEN 'improving'
                    WHEN (pm.total_code_fixed + COALESCE(tm.total_triaged, 0)) < pm.total_new THEN 'declining'
                    ELSE 'stable'
                END as trend_direction
            FROM period_snapshot_metrics pm, period_triaged_metrics tm, current_state cs
        """
        
        if self.project_name:
            query = query.format(
                project_filter_join_period="""
                    JOIN stream s ON sn.stream_id = s.id
                    JOIN project_stream ps ON s.id = ps.stream_id
                    JOIN project p ON ps.project_id = p.id
                """,
                project_filter_period="AND p.name = ANY(%s)",
                project_filter_join_triaged="""
                    JOIN project_stream ps ON s.id = ps.stream_id
                    JOIN project p ON ps.project_id = p.id
                """,
                project_filter_triaged="AND p.name = ANY(%s)",
                project_filter_join_current="""
                    JOIN project_stream ps ON s.id = ps.stream_id
                    JOIN project p ON ps.project_id = p.id
                """,
                project_filter_current="AND p.name = ANY(%s)"
            )
            result = self.db.execute_query_dict(query, (days, self._project_names, days, self._project_names, self._project_names))
        else:
            query = query.format(
                project_filter_join_period="",
                project_filter_period="",
                project_filter_join_triaged="",
                project_filter_triaged="",
                project_filter_join_current="",
                project_filter_current=""
            )
            result = self.db.execute_query_dict(query, (days, days))
        
        return result[0] if result else {}
    
    def get_defect_aging_distribution(self):
        """Get distribution of outstanding defects by age ranges
        
        Calculates how long outstanding defects have been open based on their first detection date.
        Groups defects into age ranges and calculates average age and severity breakdown.
        
        Returns:
            pandas.DataFrame: Age ranges with defect counts, average age, and severity breakdown
        """
        query = f"""
            WITH defect_ages AS (
                SELECT 
                    sd.id,
                    cp.impact,
                    CURRENT_DATE - DATE(sn.date_created) as age_days
                FROM stream_defect sd
                JOIN checker_properties cp ON sd.checker_properties_id = cp.id
                JOIN snapshot_element se_first ON sd.first_snapshot_element_id = se_first.id
                JOIN snapshot sn ON se_first.snapshot_id = sn.id
                JOIN stream_element se ON sd.stream_element_id = se.id
                JOIN stream s ON se.stream_id = s.id
                LEFT JOIN defect_triage dt ON sd.defect_triage_id = dt.id
                LEFT JOIN dynamic_enum de_cls ON dt.current_classification_id = de_cls.id
                    AND de_cls.dtype = 'Cls'
                {self._ACTIVE_JOIN_SQL}
                {{project_filter_join}}
                WHERE {self._ACTIVE_COND_SQL}
                    AND (de_cls.name NOT IN ('False Positive', 'Intentional') OR de_cls.name IS NULL)
                    {{project_filter}}
            )
            SELECT 
                CASE 
                    WHEN age_days <= 30 THEN '0-30 days'
                    WHEN age_days <= 90 THEN '31-90 days'
                    WHEN age_days <= 180 THEN '91-180 days'
                    WHEN age_days <= 365 THEN '181-365 days'
                    ELSE 'Over 1 year'
                END as age_range,
                COUNT(*) as defect_count,
                ROUND(AVG(age_days)::numeric, 0) as avg_age_days,
                COUNT(CASE WHEN impact = 'High' THEN 1 END) as high_severity,
                COUNT(CASE WHEN impact = 'Medium' THEN 1 END) as medium_severity,
                COUNT(CASE WHEN impact = 'Low' THEN 1 END) as low_severity
            FROM defect_ages
            GROUP BY 
                CASE 
                    WHEN age_days <= 30 THEN '0-30 days'
                    WHEN age_days <= 90 THEN '31-90 days'
                    WHEN age_days <= 180 THEN '91-180 days'
                    WHEN age_days <= 365 THEN '181-365 days'
                    ELSE 'Over 1 year'
                END,
                CASE 
                    WHEN age_days <= 30 THEN 1
                    WHEN age_days <= 90 THEN 2
                    WHEN age_days <= 180 THEN 3
                    WHEN age_days <= 365 THEN 4
                    ELSE 5
                END
            ORDER BY 
                CASE 
                    WHEN age_days <= 30 THEN 1
                    WHEN age_days <= 90 THEN 2
                    WHEN age_days <= 180 THEN 3
                    WHEN age_days <= 365 THEN 4
                    ELSE 5
                END
        """
        
        if self.project_name:
            query = query.format(
                project_filter_join="""
                    JOIN project_stream ps ON s.id = ps.stream_id
                    JOIN project p ON ps.project_id = p.id
                """,
                project_filter="AND p.name = ANY(%s)"
            )
            results = self.db.execute_query_dict(query, (self._project_names,))
        else:
            query = query.format(project_filter_join="", project_filter="")
            results = self.db.execute_query_dict(query)
        
        return pd.DataFrame(results)
    
    def get_triage_progress_summary(self):
        """Get current triage progress summary
        
        Returns:
            dict: Triage statistics
        """
        query = f"""
            SELECT 
                COUNT(DISTINCT sd.id) as total_defects,
                COUNT(DISTINCT CASE WHEN de_cls.name IS NOT NULL AND de_cls.name != 'Unclassified' THEN sd.id END) as classified_count,
                COUNT(DISTINCT CASE WHEN de_cls.name IS NULL OR de_cls.name = 'Unclassified' THEN sd.id END) as unclassified_count,
                COUNT(DISTINCT CASE WHEN de_act.name IS NOT NULL AND de_act.name NOT IN ('Undecided', 'No Action') THEN sd.id END) as action_assigned_count,
                COUNT(DISTINCT CASE WHEN de_act.name IS NULL OR de_act.name IN ('Undecided', 'No Action') THEN sd.id END) as no_action_count,
                ROUND((COUNT(DISTINCT CASE WHEN de_cls.name IS NOT NULL AND de_cls.name != 'Unclassified' THEN sd.id END)::numeric / 
                       NULLIF(COUNT(DISTINCT sd.id), 0) * 100), 2) as triage_completion_percentage,
                COUNT(DISTINCT CASE WHEN de_cls.name = 'Bug' THEN sd.id END) as bug_count,
                COUNT(DISTINCT CASE WHEN de_cls.name = 'False Positive' THEN sd.id END) as false_positive_count,
                COUNT(DISTINCT CASE WHEN de_cls.name = 'Intentional' THEN sd.id END) as intentional_count
            FROM stream_defect sd
            JOIN stream_element se ON sd.stream_element_id = se.id
            JOIN stream s ON se.stream_id = s.id
            LEFT JOIN defect_triage dt ON sd.defect_triage_id = dt.id
            LEFT JOIN dynamic_enum de_cls ON dt.current_classification_id = de_cls.id AND de_cls.dtype = 'Cls'
            LEFT JOIN dynamic_enum de_act ON dt.current_action_id = de_act.id AND de_act.dtype = 'Act'
            LEFT JOIN project_stream ps ON s.id = ps.stream_id
            LEFT JOIN project p ON ps.project_id = p.id
            {self._ACTIVE_JOIN_SQL}
            WHERE {self._ACTIVE_COND_SQL}
                {{project_filter}}
        """
        
        if self.project_name:
            query = query.format(project_filter="AND p.name = ANY(%s)")
            result = self.db.execute_query_dict(query, (self._project_names,))
        else:
            query = query.format(project_filter="")
            result = self.db.execute_query_dict(query)
        return result[0] if result else {}
    
    def get_technical_debt_summary(self):
        """Calculate estimated technical debt based on defect impact levels
        
        Excludes defects triaged as False Positive or Intentional (already resolved).
        Only counts defects that require actual remediation work.
        
        Estimation formula:
        - High impact: 4 hours per defect
        - Medium impact: 2 hours per defect  
        - Low impact: 1 hour per defect
        - Unspecified: 0.5 hours per defect
        
        Returns:
            dict: Technical debt statistics including total hours, days, and breakdown by impact
        """
        query = f"""
            SELECT 
                cp.impact,
                COUNT(DISTINCT sd.id) as defect_count,
                CASE cp.impact
                    WHEN 'High' THEN COUNT(DISTINCT sd.id) * 4    
                    WHEN 'Medium' THEN COUNT(DISTINCT sd.id) * 2  
                    WHEN 'Low' THEN COUNT(DISTINCT sd.id) * 1     
                    ELSE COUNT(DISTINCT sd.id) * 0.5
                END as estimated_hours
            FROM stream_defect sd
            JOIN checker_properties cp ON sd.checker_properties_id = cp.id
            JOIN stream_element se ON sd.stream_element_id = se.id
            JOIN stream s ON se.stream_id = s.id
            -- Join to exclude False Positive and Intentional classifications
            LEFT JOIN defect_triage dt ON sd.defect_triage_id = dt.id
            LEFT JOIN dynamic_enum de ON dt.current_classification_id = de.id AND de.dtype = 'Cls'
            {self._ACTIVE_JOIN_SQL}
            {{project_filter_join}}
            WHERE {self._ACTIVE_COND_SQL}
                AND (de.name IS NULL OR de.name NOT IN ('False Positive', 'Intentional'))
                {{project_filter}}
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
            query = query.format(
                project_filter_join="""
                    JOIN project_stream ps ON s.id = ps.stream_id
                    JOIN project p ON ps.project_id = p.id
                """,
                project_filter="AND p.name = ANY(%s)"
            )
            results = self.db.execute_query_dict(query, (self._project_names,))
        else:
            query = query.format(
                project_filter_join="",
                project_filter=""
            )
            results = self.db.execute_query_dict(query)
        
        # Calculate totals
        total_hours = float(sum(row['estimated_hours'] for row in results))
        total_days = total_hours / 8.0  # 8-hour work days
        total_weeks = total_days / 5.0  # 5-day work weeks
        total_defects = sum(row['defect_count'] for row in results)
        
        # Build breakdown by impact
        breakdown = {
            'High': {'defects': 0, 'hours': 0},
            'Medium': {'defects': 0, 'hours': 0},
            'Low': {'defects': 0, 'hours': 0},
            'Unspecified': {'defects': 0, 'hours': 0}
        }
        
        for row in results:
            impact = row['impact'] if row['impact'] in breakdown else 'Unspecified'
            breakdown[impact]['defects'] = row['defect_count']
            breakdown[impact]['hours'] = float(row['estimated_hours'])
        
        return {
            'total_hours': round(total_hours, 1),
            'total_days': round(total_days, 1),
            'total_weeks': round(total_weeks, 1),
            'total_defects': total_defects,
            'breakdown': breakdown,
            'avg_hours_per_defect': round(total_hours / total_defects, 2) if total_defects > 0 else 0
        }
    
    # ========== COMPETITIVE LEADERBOARDS ==========
    
    def get_top_projects_by_fix_rate(self, days=30, limit=10):
        """Get top projects ranked by defect fix velocity
        
        Args:
            days: Number of days to analyze
            limit: Number of projects to return
            
        Returns:
            pandas.DataFrame: Projects ranked by fixes
        """
        project_filter = "AND p.name = ANY(%s)" if self._project_names else ""
        query = f"""
            WITH project_fixes AS (
                SELECT 
                    p.name as project_name,
                    COUNT(DISTINCT sd.id) FILTER (WHERE sn.eliminated_defect_count > 0) as defects_fixed,
                    COUNT(DISTINCT sn.id) as snapshot_count,
                    ROUND(COUNT(DISTINCT sd.id) FILTER (WHERE sn.eliminated_defect_count > 0)::numeric / 
                          NULLIF(COUNT(DISTINCT sn.id), 0), 2) as avg_fixes_per_snapshot,
                    MIN(sn.date_created) as first_snapshot,
                    MAX(sn.date_created) as last_snapshot
                FROM project p
                JOIN project_stream ps ON p.id = ps.project_id
                JOIN stream s ON ps.stream_id = s.id
                JOIN snapshot sn ON s.id = sn.stream_id
                LEFT JOIN stream_element se ON s.id = se.stream_id
                LEFT JOIN stream_defect sd ON se.id = sd.stream_element_id 
                    AND sd.fixed_snapshot_element_id IS NOT NULL
                {self._ACTIVE_JOIN_SQL}
                WHERE p.deleted = false
                    AND sn.deleted = false
                    AND (sd.id IS NULL OR {self._FIXED_COND_SQL})
                    AND sn.date_created >= CURRENT_DATE - INTERVAL '1 day' * %s
                    {project_filter}
                GROUP BY p.name
                HAVING COUNT(DISTINCT sd.id) FILTER (WHERE sn.eliminated_defect_count > 0) > 0
            )
            SELECT 
                project_name,
                defects_fixed as eliminated_defects,
                snapshot_count,
                avg_fixes_per_snapshot,
                ROUND(defects_fixed::numeric / NULLIF(EXTRACT(EPOCH FROM (last_snapshot - first_snapshot))::numeric, 0) * 86400, 2) as avg_fixes_per_day
            FROM project_fixes
            ORDER BY defects_fixed DESC, avg_fixes_per_snapshot DESC
            LIMIT %s
        """
        
        if self._project_names:
            results = self.db.execute_query_dict(query, (days, self._project_names, limit))
        else:
            results = self.db.execute_query_dict(query, (days, limit))
        return pd.DataFrame(results)
    
    def get_most_improved_projects(self, days=90, limit=10):
        """Get projects ranked by improvement within the analysis period."""
        project_filter_snap = "AND p.name = ANY(%s)" if self._project_names else ""
        project_filter_triage = "AND p.name = ANY(%s)" if self._project_names else ""
        query = f"""
            WITH snapshot_data AS (
                SELECT
                    p.name                                                                AS project_name,
                    sn.total_defect_count,
                    ROW_NUMBER() OVER (PARTITION BY p.name ORDER BY sn.date_created ASC)  AS rn_first,
                    ROW_NUMBER() OVER (PARTITION BY p.name ORDER BY sn.date_created DESC) AS rn_last,
                    COUNT(sn.id)           OVER (PARTITION BY p.name)                    AS total_snapshots
                FROM project p
                JOIN project_stream ps ON p.id  = ps.project_id
                JOIN stream s          ON ps.stream_id = s.id
                JOIN snapshot sn       ON s.id  = sn.stream_id
                WHERE p.deleted  = false
                  AND sn.deleted = false
                  AND sn.date_created >= CURRENT_DATE - INTERVAL '1 day' * %s
                  {project_filter_snap}
            ),
            snapshot_comparison AS (
                SELECT
                    project_name,
                    MAX(CASE WHEN rn_first = 1 THEN total_defect_count END) AS first_defects,
                    MAX(CASE WHEN rn_last  = 1 THEN total_defect_count END) AS last_defects,
                    MAX(total_snapshots)                                     AS snapshot_count
                FROM snapshot_data
                GROUP BY project_name
            ),
            triage_counts AS (
                SELECT
                    p.name AS project_name,
                    COUNT(DISTINCT sd.id) AS total_defects,
                    COUNT(DISTINCT CASE
                        WHEN de.name IN ('False Positive', 'Intentional') THEN sd.id
                    END) AS dismissed_defects
                FROM project p
                JOIN project_stream ps ON p.id  = ps.project_id
                JOIN stream s          ON ps.stream_id = s.id
                JOIN stream_element se ON s.id  = se.stream_id
                JOIN stream_defect sd  ON se.id = sd.stream_element_id
                LEFT JOIN defect_triage dt ON sd.defect_triage_id = dt.id
                LEFT JOIN dynamic_enum de  ON dt.current_classification_id = de.id
                                          AND de.dtype = 'Cls'
                WHERE p.deleted = false AND s.deleted = false
                  {project_filter_triage}
                GROUP BY p.name
            ),
            combined AS (
                SELECT
                    sc.project_name,
                    sc.first_defects,
                    sc.last_defects,
                    sc.snapshot_count,
                    COALESCE(tc.dismissed_defects, 0) AS dismissed_defects,
                    COALESCE(tc.total_defects,    0) AS total_defects,
                    CASE
                        WHEN sc.snapshot_count >= 2 AND COALESCE(sc.first_defects, 0) > 0
                        THEN GREATEST(0.0,
                             ROUND(((sc.first_defects - sc.last_defects)::numeric
                                    / sc.first_defects * 100), 1))
                        ELSE NULL
                    END AS snap_pct,
                    CASE
                        WHEN COALESCE(tc.total_defects, 0) > 0
                        THEN ROUND((COALESCE(tc.dismissed_defects, 0)::numeric
                                    / tc.total_defects * 100), 1)
                        ELSE 0.0
                    END AS triage_pct
                FROM snapshot_comparison sc
                LEFT JOIN triage_counts tc ON sc.project_name = tc.project_name
            )
            SELECT
                project_name,
                COALESCE(last_defects,  total_defects) AS current_defects,
                COALESCE(first_defects, total_defects) AS previous_avg_defects,
                snapshot_count,
                CASE
                    WHEN snap_pct IS NOT NULL AND snap_pct > 0 THEN snap_pct
                    ELSE COALESCE(triage_pct, 0)
                END AS improvement_percentage,
                CASE
                    WHEN snap_pct IS NOT NULL AND snap_pct > 0
                        THEN GREATEST(0, first_defects - last_defects)
                    ELSE dismissed_defects
                END AS defects_reduced,
                CASE
                    WHEN snap_pct IS NOT NULL AND snap_pct > 0 THEN 'snapshot'
                    ELSE 'triage'
                END AS improvement_source
            FROM combined
            ORDER BY improvement_percentage DESC, defects_reduced DESC
            LIMIT %s
        """
        if self._project_names:
            results = self.db.execute_query_dict(query, (days, self._project_names, self._project_names, limit))
        else:
            results = self.db.execute_query_dict(query, (days, limit))
        return pd.DataFrame(results)
    
    def get_top_projects_by_triage_activity(self, days=30, limit=10):
        """Get top projects by triage completeness (current state)
        
        Note: Database does not have defect_triage_history table, so we rank by current triage state
        
        Args:
            days: Not used (kept for API compatibility)
            limit: Number of projects to return
            
        Returns:
            pandas.DataFrame: Projects ranked by triage completeness
        """
        project_filter = "AND p.name = ANY(%s)" if self._project_names else ""
        query = f"""
            WITH project_triage AS (
                SELECT 
                    p.name as project_name,
                    COUNT(DISTINCT sd.id) as total_defects,
                    COUNT(DISTINCT CASE 
                        WHEN de_cls.name IS NOT NULL AND de_cls.name != 'Unclassified' 
                        THEN sd.id 
                    END) as classified_defects,
                    COUNT(DISTINCT CASE 
                        WHEN de_act.name IS NOT NULL AND de_act.name NOT IN ('Undecided', 'No Action')
                        THEN sd.id 
                    END) as action_assigned_defects,
                    COUNT(DISTINCT dt.current_owner_user_id) as users_with_assignments
                FROM project p
                JOIN project_stream ps ON p.id = ps.project_id
                JOIN stream s ON ps.stream_id = s.id
                JOIN stream_element se ON s.id = se.stream_id
                JOIN stream_defect sd ON se.id = sd.stream_element_id
                LEFT JOIN defect_triage dt ON sd.defect_triage_id = dt.id
                LEFT JOIN dynamic_enum de_cls ON dt.current_classification_id = de_cls.id AND de_cls.dtype = 'Cls'
                LEFT JOIN dynamic_enum de_act ON dt.current_action_id = de_act.id AND de_act.dtype = 'Act'
                {self._ACTIVE_JOIN_SQL}
                WHERE p.deleted = false
                    AND {self._ACTIVE_COND_SQL}
                    AND (de_cls.name NOT IN ('False Positive', 'Intentional') OR de_cls.name IS NULL)
                    {project_filter}
                GROUP BY p.name
                HAVING COUNT(DISTINCT sd.id) > 0
            )
            SELECT 
                project_name,
                total_defects as triage_actions,
                classified_defects as classifications,
                action_assigned_defects as actions_assigned,
                users_with_assignments as active_users,
                ROUND((classified_defects::numeric / NULLIF(total_defects, 0)) * 100, 1) as triage_percentage
            FROM project_triage
            WHERE classified_defects > 0
            ORDER BY triage_percentage DESC, classified_defects DESC
            LIMIT %s
        """
        if self._project_names:
            results = self.db.execute_query_dict(query, (self._project_names, limit))
        else:
            results = self.db.execute_query_dict(query, (limit,))
        return pd.DataFrame(results)
    
    def get_top_users_by_fixes(self, days=30, limit=10):
        """Get top users ranked by defects actually eliminated from code
        
        Counts defects that disappeared in subsequent snapshots (fixed_snapshot_element_id IS NOT NULL),
        attributing the fix to the last human user who triaged it (excluding System User).
        
        Args:
            days: Number of days to analyze
            limit: Number of users to return
            
        Returns:
            pandas.DataFrame: Users ranked by actual fixes (eliminated defects)
        """
        if self.project_name:
            query = f"""
                WITH fixed_defects AS (
                    -- Get all defects that were actually eliminated from code (not found in next snapshot)
                    SELECT 
                        sd.defect_triage_id,
                        sd.id as stream_defect_id
                    FROM stream_defect sd
                    JOIN stream_element se ON sd.stream_element_id = se.id
                    JOIN stream s ON se.stream_id = s.id
                    JOIN project_stream ps ON s.id = ps.stream_id
                    JOIN project p ON ps.project_id = p.id
                    {self._ACTIVE_JOIN_SQL}
                    WHERE sd.fixed_snapshot_element_id IS NOT NULL
                        AND {self._FIXED_COND_SQL}
                        AND p.name = ANY(%s)
                ),
                last_triagers AS (
                    -- For each fixed defect, find the last HUMAN user who triaged it
                    SELECT DISTINCT ON (fd.defect_triage_id)
                        fd.defect_triage_id,
                        ts.user_created_id,
                        ts.date_created
                    FROM fixed_defects fd
                    JOIN triage_state ts ON fd.defect_triage_id = ts.defect_triage_id
                    JOIN users u ON ts.user_created_id = u.id
                    WHERE u.username NOT IN ('system', 'System User')  -- Exclude system-generated actions
                        AND ts.date_created >= '1971-01-01'::timestamp  -- Exclude sentinel/default timestamps
                        AND ts.date_created >= CURRENT_DATE - INTERVAL '1 day' * %s
                    ORDER BY fd.defect_triage_id, ts.date_created DESC
                ),
                user_fixes AS (
                    SELECT 
                        u.username,
                        COALESCE(u.given_name || ' ' || u.family_name, u.username) as user_name,
                        COUNT(DISTINCT lt.defect_triage_id) as defects_fixed,
                        MIN(lt.date_created) as first_activity,
                        MAX(lt.date_created) as last_activity,
                        COUNT(DISTINCT lt.date_created::date) as active_days
                    FROM users u
                    JOIN last_triagers lt ON u.id = lt.user_created_id
                    GROUP BY u.id, u.username, u.given_name, u.family_name
                    HAVING COUNT(DISTINCT lt.defect_triage_id) > 0
                )
                SELECT 
                    user_name,
                    username,
                    defects_fixed as total_fixes,
                    active_days,
                    ROUND(defects_fixed::numeric / NULLIF(active_days, 0), 1) as avg_fixes_per_day
                FROM user_fixes
                ORDER BY defects_fixed DESC, active_days DESC
                LIMIT %s
            """
            results = self.db.execute_query_dict(query, (self._project_names, days, limit))
        else:
            query = f"""
                WITH fixed_defects AS (
                    -- Get all defects that were actually eliminated from code (not found in next snapshot)
                    SELECT 
                        sd.defect_triage_id,
                        sd.id as stream_defect_id
                    FROM stream_defect sd
                    JOIN stream_element se ON sd.stream_element_id = se.id
                    {self._ACTIVE_JOIN_SQL}
                    WHERE sd.fixed_snapshot_element_id IS NOT NULL
                        AND {self._FIXED_COND_SQL}
                ),
                last_triagers AS (
                    -- For each fixed defect, find the last HUMAN user who triaged it
                    SELECT DISTINCT ON (fd.defect_triage_id)
                        fd.defect_triage_id,
                        ts.user_created_id,
                        ts.date_created
                    FROM fixed_defects fd
                    JOIN triage_state ts ON fd.defect_triage_id = ts.defect_triage_id
                    JOIN users u ON ts.user_created_id = u.id
                    WHERE u.username NOT IN ('system', 'System User')  -- Exclude system-generated actions
                        AND ts.date_created >= '1971-01-01'::timestamp  -- Exclude sentinel/default timestamps
                        AND ts.date_created >= CURRENT_DATE - INTERVAL '1 day' * %s
                    ORDER BY fd.defect_triage_id, ts.date_created DESC
                ),
                user_fixes AS (
                    SELECT 
                        u.username,
                        COALESCE(u.given_name || ' ' || u.family_name, u.username) as user_name,
                        COUNT(DISTINCT lt.defect_triage_id) as defects_fixed,
                        MIN(lt.date_created) as first_activity,
                        MAX(lt.date_created) as last_activity,
                        COUNT(DISTINCT lt.date_created::date) as active_days
                    FROM users u
                    JOIN last_triagers lt ON u.id = lt.user_created_id
                    GROUP BY u.id, u.username, u.given_name, u.family_name
                    HAVING COUNT(DISTINCT lt.defect_triage_id) > 0
                )
                SELECT 
                    user_name,
                    username,
                    defects_fixed as total_fixes,
                    active_days,
                    ROUND(defects_fixed::numeric / NULLIF(active_days, 0), 1) as avg_fixes_per_day
                FROM user_fixes
                ORDER BY defects_fixed DESC, active_days DESC
                LIMIT %s
            """
            results = self.db.execute_query_dict(query, (days, limit))
        return pd.DataFrame(results)
    
    def get_top_triagers(self, days=30, limit=10):
        """Get top users by triage activity (classifications and actions)
        
        Args:
            days: Number of days to analyze
            limit: Number of users to return
            
        Returns:
            pandas.DataFrame: Users ranked by triage activity
        """
        if self.project_name:
            query = """
                WITH user_triage_stats AS (
                    SELECT 
                        u.username,
                        COALESCE(u.given_name || ' ' || u.family_name, u.username) as user_name,
                        COUNT(DISTINCT ts.id) as triage_actions,
                        COUNT(DISTINCT ts.classification_id) as unique_classifications,
                        COUNT(DISTINCT ts.action_id) as unique_actions,
                        COUNT(DISTINCT ts.defect_triage_id) as defects_triaged,
                        COUNT(DISTINCT ts.date_created::date) as active_days,
                        MAX(ts.date_created) as last_activity
                    FROM users u
                    JOIN triage_state ts ON u.id = ts.user_created_id
                    JOIN defect_triage dt ON ts.defect_triage_id = dt.id
                    JOIN stream_defect sd ON dt.id = sd.defect_triage_id
                    JOIN stream_element se ON sd.stream_element_id = se.id
                    JOIN stream s ON se.stream_id = s.id
                    JOIN project_stream ps ON s.id = ps.stream_id
                    JOIN project p ON ps.project_id = p.id
                    WHERE ts.date_created >= CURRENT_DATE - INTERVAL '1 day' * %s
                        AND p.name = ANY(%s)
                    GROUP BY u.id, u.username, u.given_name, u.family_name
                    HAVING COUNT(DISTINCT ts.id) > 0
                )
                SELECT 
                    user_name,
                    username,
                    defects_triaged as total_triage_actions,
                    unique_classifications,
                    unique_actions,
                    triage_actions as state_changes,
                    active_days,
                    ROUND(defects_triaged::numeric / NULLIF(active_days, 0), 1) as avg_triage_per_day
                FROM user_triage_stats
                ORDER BY defects_triaged DESC, triage_actions DESC
                LIMIT %s
            """
            results = self.db.execute_query_dict(query, (days, self._project_names, limit))
        else:
            query = """
                WITH user_triage_stats AS (
                    SELECT 
                        u.username,
                        COALESCE(u.given_name || ' ' || u.family_name, u.username) as user_name,
                        COUNT(DISTINCT ts.id) as triage_actions,
                        COUNT(DISTINCT ts.classification_id) as unique_classifications,
                        COUNT(DISTINCT ts.action_id) as unique_actions,
                        COUNT(DISTINCT ts.defect_triage_id) as defects_triaged,
                        COUNT(DISTINCT ts.date_created::date) as active_days,
                        MAX(ts.date_created) as last_activity
                    FROM users u
                    JOIN triage_state ts ON u.id = ts.user_created_id
                    WHERE ts.date_created >= CURRENT_DATE - INTERVAL '1 day' * %s
                    GROUP BY u.id, u.username, u.given_name, u.family_name
                    HAVING COUNT(DISTINCT ts.id) > 0
                )
                SELECT 
                    user_name,
                    username,
                    defects_triaged as total_triage_actions,
                    unique_classifications,
                    unique_actions,
                    triage_actions as state_changes,
                    active_days,
                    ROUND(defects_triaged::numeric / NULLIF(active_days, 0), 1) as avg_triage_per_day
                FROM user_triage_stats
                ORDER BY defects_triaged DESC, triage_actions DESC
                LIMIT %s
            """
            results = self.db.execute_query_dict(query, (days, limit))
        return pd.DataFrame(results)
    
    def get_most_collaborative_users(self, days=30, limit=10):
        """Get users with most collaboration activity (comments, etc.)
        
        Args:
            days: Number of days to analyze
            limit: Number of users to return
            
        Returns:
            pandas.DataFrame: Users ranked by collaboration
        """
        if self.project_name:
            query = """
                WITH user_collaboration AS (
                    SELECT 
                        u.username,
                        COALESCE(u.given_name || ' ' || u.family_name, u.username) as user_name,
                        COUNT(DISTINCT ts.id) FILTER (WHERE ts.cmnt IS NOT NULL AND ts.cmnt != '') as comments_added,
                        COUNT(DISTINCT ts.defect_triage_id) as defects_involved,
                        COUNT(DISTINCT ts.date_created::date) as active_days,
                        MAX(ts.date_created) as last_activity
                    FROM users u
                    JOIN triage_state ts ON u.id = ts.user_created_id
                    JOIN defect_triage dt ON ts.defect_triage_id = dt.id
                    JOIN stream_defect sd ON dt.id = sd.defect_triage_id
                    JOIN stream_element se ON sd.stream_element_id = se.id
                    JOIN stream s ON se.stream_id = s.id
                    JOIN project_stream ps ON s.id = ps.stream_id
                    JOIN project p ON ps.project_id = p.id
                    WHERE ts.date_created >= CURRENT_DATE - INTERVAL '1 day' * %s
                        AND ts.cmnt IS NOT NULL 
                        AND ts.cmnt != ''
                        AND p.name = ANY(%s)
                    GROUP BY u.id, u.username, u.given_name, u.family_name
                    HAVING COUNT(DISTINCT ts.id) FILTER (WHERE ts.cmnt IS NOT NULL AND ts.cmnt != '') > 0
                )
                SELECT 
                    user_name,
                    username,
                    comments_added as total_comments,
                    defects_involved,
                    active_days,
                    ROUND(comments_added::numeric / NULLIF(active_days, 0), 1) as avg_comments_per_day
                FROM user_collaboration
                ORDER BY comments_added DESC, active_days DESC
                LIMIT %s
            """
            results = self.db.execute_query_dict(query, (days, self._project_names, limit))
        else:
            query = """
                WITH user_collaboration AS (
                    SELECT 
                        u.username,
                        COALESCE(u.given_name || ' ' || u.family_name, u.username) as user_name,
                        COUNT(DISTINCT ts.id) FILTER (WHERE ts.cmnt IS NOT NULL AND ts.cmnt != '') as comments_added,
                        COUNT(DISTINCT ts.defect_triage_id) as defects_involved,
                        COUNT(DISTINCT ts.date_created::date) as active_days,
                        MAX(ts.date_created) as last_activity
                    FROM users u
                    JOIN triage_state ts ON u.id = ts.user_created_id
                    WHERE ts.date_created >= CURRENT_DATE - INTERVAL '1 day' * %s
                        AND ts.cmnt IS NOT NULL 
                        AND ts.cmnt != ''
                    GROUP BY u.id, u.username, u.given_name, u.family_name
                    HAVING COUNT(DISTINCT ts.id) FILTER (WHERE ts.cmnt IS NOT NULL AND ts.cmnt != '') > 0
                )
                SELECT 
                    user_name,
                    username,
                    comments_added as total_comments,
                    defects_involved,
                    active_days,
                    ROUND(comments_added::numeric / NULLIF(active_days, 0), 1) as avg_comments_per_day
                FROM user_collaboration
                ORDER BY comments_added DESC, active_days DESC
                LIMIT %s
            """
            results = self.db.execute_query_dict(query, (days, limit))
        return pd.DataFrame(results)
    
    def get_owasp_top10_metrics(self):
        """Get defect counts mapped to OWASP Top 10 2025 categories
        
        Only available for project-level dashboards.
        Maps defects via CWE codes using checker_properties table.
        Returns ALL 10 OWASP categories (even those with 0 defects).
        
        Returns:
            pandas.DataFrame: OWASP categories with defect counts and severity breakdown
        """
        if not self.project_name:
            # OWASP tab only for project-level dashboards
            return pd.DataFrame()
        
        from .owasp_mapping import OWASP_TOP_10_2025
        
        # Initialize all OWASP categories with 0 defects
        owasp_data = {}
        for category_id, data in OWASP_TOP_10_2025.items():
            owasp_data[category_id] = {
                'category': category_id,
                'description': data['description'],
                'total_defects': 0,
                'high': 0,
                'medium': 0,
                'low': 0,
                'unspecified': 0,
                'cwe_codes': set(),
                'status': 'PASS'  # Default to PASS
            }
        
        # Build CWE to OWASP category mapping (multi-value: a CWE can appear in multiple categories)
        # Using a list per CWE avoids the "last writer wins" bug where a CWE shared across
        # categories (e.g. CWE-918 in A09 and A10, CWE-117 in A03 and A09) would only be
        # attributed to the last category encountered during dict construction.
        cwe_to_owasp = {}
        for category_id, data in OWASP_TOP_10_2025.items():
            for cwe_id in data['cwe_ids']:
                if cwe_id not in cwe_to_owasp:
                    cwe_to_owasp[cwe_id] = []
                cwe_to_owasp[cwe_id].append(category_id)
        
        query = f"""
            SELECT 
                cp.cwe,
                de.name as severity,
                COUNT(DISTINCT sd.merged_defect_id) as defect_count,
                dt.current_action_id,
                act.name as action
            FROM stream_defect sd
            JOIN stream_element se ON sd.stream_element_id = se.id
            JOIN stream s ON se.stream_id = s.id
            JOIN project_stream ps ON s.id = ps.stream_id
            JOIN project p ON ps.project_id = p.id
            JOIN defect_triage dt ON sd.defect_triage_id = dt.id
            LEFT JOIN checker_properties cp ON sd.checker_properties_id = cp.id
            LEFT JOIN dynamic_enum de ON dt.current_severity_id = de.id
            LEFT JOIN dynamic_enum act ON dt.current_action_id = act.id
            LEFT JOIN dynamic_enum de_cls ON dt.current_classification_id = de_cls.id AND de_cls.dtype = 'Cls'
            {self._ACTIVE_JOIN_SQL}
            WHERE p.name = ANY(%s)
                AND cp.cwe IS NOT NULL
                AND {self._ACTIVE_COND_SQL}
                AND (de_cls.name NOT IN ('False Positive', 'Intentional') OR de_cls.name IS NULL)
                AND sd.merged_defect_id IS NOT NULL
            GROUP BY cp.cwe, de.name, dt.current_action_id, act.name
            ORDER BY cp.cwe, de.name
        """
        
        results = self.db.execute_query_dict(query, (self._project_names,))
        
        # Aggregate by OWASP category.
        # A CWE in multiple categories contributes to each of them, so that
        # "Total Defects" in the summary always matches the defect table below it.
        for row in results:
            cwe_id = row['cwe']
            if cwe_id not in cwe_to_owasp:
                continue  # CWE not mapped to any OWASP Top 10 2025 category
            
            severity = row.get('severity', 'Unspecified') or 'Unspecified'
            count = row['defect_count']
            
            for category_id in cwe_to_owasp[cwe_id]:
                owasp_data[category_id]['total_defects'] += count
                owasp_data[category_id]['cwe_codes'].add(cwe_id)
                owasp_data[category_id]['status'] = 'FAILED'  # Mark as FAILED if defects found
                
                # Coverity severity mapping: Major=High, Moderate=Medium, Minor=Low
                if severity == 'Major':
                    owasp_data[category_id]['high'] += count
                elif severity == 'Moderate':
                    owasp_data[category_id]['medium'] += count
                elif severity == 'Minor':
                    owasp_data[category_id]['low'] += count
                else:
                    owasp_data[category_id]['unspecified'] += count
        
        # Convert to DataFrame - include all categories
        df_data = []
        for category_id, data in owasp_data.items():
            # Convert CWE codes set to comma-separated string for display
            cwe_codes_str = ', '.join(sorted([f"CWE-{cwe}" for cwe in data['cwe_codes']])) if data['cwe_codes'] else ''

            # Empirical risk scores from owasp.org/Top10/2025/ Score tables.
            # Priority formula: defects * exploit * impact / 100
            #   -> "severity-adjusted defect equivalents", so a category with
            #      few but very exploitable/high-impact defects can outrank
            #      a category with many low-risk ones.
            score = OWASP_TOP_10_2025[category_id].get('score_data', {})
            exploit_score = score.get('exploit_score', 0.0)
            impact_score = score.get('impact_score', 0.0)
            priority_score = round(
                data['total_defects'] * exploit_score * impact_score / 100.0,
                1,
            )

            df_data.append({
                'category': data['category'],
                'description': data['description'],
                'total_defects': data['total_defects'],
                'high': data['high'],
                'medium': data['medium'],
                'low': data['low'],
                'unspecified': data['unspecified'],
                'cwe_count': len(data['cwe_codes']),
                'cwe_codes_str': cwe_codes_str,
                'status': data['status'],
                'exploit_score': exploit_score,
                'impact_score': impact_score,
                'priority_score': priority_score,
            })
        
        df = pd.DataFrame(df_data)
        # Sort by OWASP rank (by category ID: A01, A02, ..., A10)
        df = df.sort_values('category')
        return df
    
    def get_owasp_category_details(self, category_id):
        """Get detailed defect breakdown for a specific OWASP Top 10 category
        
        Args:
            category_id: OWASP category (e.g., "A01:2025-Broken Access Control")
            
        Returns:
            dict: Detailed breakdown with checkers and all defects
        """
        if not self.project_name:
            return {}
        
        from .owasp_mapping import OWASP_TOP_10_2025
        
        # Get CWE IDs for this category
        if category_id not in OWASP_TOP_10_2025:
            return {}
        
        cwe_ids = OWASP_TOP_10_2025[category_id]['cwe_ids']
        cwe_placeholders = ','.join(['%s'] * len(cwe_ids))
        
        # Get all defects with CID, file, and function for this OWASP category
        defects_query = f"""
            SELECT DISTINCT ON (sd.merged_defect_id)
                sd.merged_defect_id as cid,
                cp.cwe,
                ct.name as checker_name,
                de.name as severity,
                fp.filename as file_path,
                func.display_name as function_name
            FROM stream_defect sd
            JOIN stream_element se ON sd.stream_element_id = se.id
            JOIN stream s ON se.stream_id = s.id
            JOIN project_stream ps ON s.id = ps.stream_id
            JOIN project p ON ps.project_id = p.id
            JOIN defect_triage dt ON sd.defect_triage_id = dt.id
            LEFT JOIN checker_properties cp ON sd.checker_properties_id = cp.id
            LEFT JOIN checker_type ct ON cp.checker_type_id = ct.id
            LEFT JOIN dynamic_enum de ON dt.current_severity_id = de.id
            LEFT JOIN dynamic_enum de_cls ON dt.current_classification_id = de_cls.id AND de_cls.dtype = 'Cls'
            LEFT JOIN stream_defect_occurrence sdo ON sd.id = sdo.stream_defect_id
            LEFT JOIN stream_file sf ON sdo.stream_file_id = sf.id
            LEFT JOIN file_path fp ON sf.file_path_id = fp.id
            LEFT JOIN function func ON sdo.function_id = func.id
            {self._ACTIVE_JOIN_SQL}
            WHERE p.name = ANY(%s)
                AND cp.cwe IN ({cwe_placeholders})
                AND {self._ACTIVE_COND_SQL}
                AND (de_cls.name NOT IN ('False Positive', 'Intentional') OR de_cls.name IS NULL)
                AND sd.merged_defect_id IS NOT NULL
            ORDER BY sd.merged_defect_id, cp.cwe, de.name DESC
        """
        
        defect_results = self.db.execute_query_dict(defects_query, (self._project_names, *cwe_ids))
        
        # Process all defects and collect checker stats
        checker_breakdown = {}
        all_defects = []
        
        for row in defect_results:
            cwe_id = row['cwe']
            if not cwe_id:
                continue
            
            checker_name = row['checker_name'] or 'Unknown'
            
            # Collect all defects
            all_defects.append({
                'cid': row['cid'],
                'cwe': cwe_id,
                'checker': checker_name,
                'severity': row['severity'] or 'Unspecified',
                'file': row['file_path'] or 'Unknown',
                'function': row['function_name'] or 'N/A'
            })
            
            # Checker breakdown for top checkers display
            if checker_name not in checker_breakdown:
                checker_breakdown[checker_name] = {
                    'checker': checker_name,
                    'defect_count': 0
                }
            checker_breakdown[checker_name]['defect_count'] += 1
        
        # Sort checker breakdown by count
        checker_list = sorted(checker_breakdown.values(), key=lambda x: x['defect_count'], reverse=True)[:10]
        
        return {
            'checker_breakdown': checker_list,  # Top 10 checkers
            'all_defects': all_defects,  # All defects for this category
            'total_checkers': len(checker_breakdown)
        }
    
    def get_cwe_top25_metrics(self):
        """Get defect counts for CWE Top 25 Most Dangerous Software Weaknesses (2025)
        
        Only available for project-level dashboards.
        Shows ALL 25 CWE entries with PASS/FAILED status.
        
        Returns:
            pandas.DataFrame: All 25 CWE entries with defect counts, severity breakdown, and status
        """
        if not self.project_name:
            # CWE Top 25 tab only for project-level dashboards
            return pd.DataFrame()
        
        from .cwe_top25_mapping import CWE_TOP_25_2025
        
        # Initialize all 25 CWE entries with PASS status
        cwe_data = {}
        for rank, data in CWE_TOP_25_2025.items():
            cwe_id = data['cwe_id']
            cwe_data[cwe_id] = {
                'rank': data['rank'],
                'cwe_id': cwe_id,
                'name': data['name'],
                'score': data['score'],
                'total_defects': 0,
                'high': 0,
                'medium': 0,
                'low': 0,
                'unspecified': 0,
                'status': 'PASS'  # Default to PASS
            }
        
        # Build set of Top 25 CWE IDs for filtering
        top25_cwe_ids = {data['cwe_id'] for data in CWE_TOP_25_2025.values()}
        
        query = f"""
            SELECT 
                cp.cwe,
                de.name as severity,
                COUNT(DISTINCT sd.id) as defect_count
            FROM stream_defect sd
            JOIN stream_element se ON sd.stream_element_id = se.id
            JOIN stream s ON se.stream_id = s.id
            JOIN project_stream ps ON s.id = ps.stream_id
            JOIN project p ON ps.project_id = p.id
            JOIN defect_triage dt ON sd.defect_triage_id = dt.id
            LEFT JOIN checker_properties cp ON sd.checker_properties_id = cp.id
            LEFT JOIN dynamic_enum de ON dt.current_severity_id = de.id
            LEFT JOIN dynamic_enum de_cls ON dt.current_classification_id = de_cls.id AND de_cls.dtype = 'Cls'
            {self._ACTIVE_JOIN_SQL}
            WHERE p.name = ANY(%s)
                AND cp.cwe IS NOT NULL
                AND {self._ACTIVE_COND_SQL}
                AND (de_cls.name NOT IN ('False Positive', 'Intentional') OR de_cls.name IS NULL)
            GROUP BY cp.cwe, de.name
            ORDER BY cp.cwe, de.name
        """
        
        results = self.db.execute_query_dict(query, (self._project_names,))
        
        # Update CWE data with actual defect counts
        for row in results:
            cwe_id = row['cwe']
            if cwe_id not in top25_cwe_ids:
                continue  # CWE not in Top 25
            
            if cwe_id in cwe_data:
                severity = row.get('severity', 'Unspecified') or 'Unspecified'
                count = row['defect_count']
                
                cwe_data[cwe_id]['total_defects'] += count
                cwe_data[cwe_id]['status'] = 'FAILED'  # Mark as FAILED if defects exist
                
                # Coverity severity mapping: Major=High, Moderate=Medium, Minor=Low
                if severity == 'Major':
                    cwe_data[cwe_id]['high'] += count
                elif severity == 'Moderate':
                    cwe_data[cwe_id]['medium'] += count
                elif severity == 'Minor':
                    cwe_data[cwe_id]['low'] += count
                else:
                    cwe_data[cwe_id]['unspecified'] += count
        
        # Convert to DataFrame with all 25 entries
        df_data = []
        for cwe_id, data in cwe_data.items():
            df_data.append({
                'rank': data['rank'],
                'cwe_id': data['cwe_id'],
                'name': data['name'],
                'score': data['score'],
                'total_defects': data['total_defects'],
                'high': data['high'],
                'medium': data['medium'],
                'low': data['low'],
                'unspecified': data['unspecified'],
                'status': data['status']
            })
        
        df = pd.DataFrame(df_data)
        # Sort by rank (ascending - most dangerous first)
        df = df.sort_values('rank', ascending=True)
        return df
    
    def get_cwe_top25_details(self, cwe_id):
        """Get detailed defect breakdown for a specific CWE Top 25 weakness
        
        Args:
            cwe_id: CWE ID (e.g., 79 for CWE-79)
            
        Returns:
            dict: Detailed breakdown with all defects
        """
        if not self.project_name:
            return {}
        
        # Get all defects with CID, file, and function for this CWE
        defects_query = f"""
            SELECT DISTINCT ON (sd.merged_defect_id)
                sd.merged_defect_id as cid,
                cp.cwe,
                ct.name as checker_name,
                de.name as severity,
                fp.filename as file_path,
                func.display_name as function_name
            FROM stream_defect sd
            JOIN stream_element se ON sd.stream_element_id = se.id
            JOIN stream s ON se.stream_id = s.id
            JOIN project_stream ps ON s.id = ps.stream_id
            JOIN project p ON ps.project_id = p.id
            JOIN defect_triage dt ON sd.defect_triage_id = dt.id
            LEFT JOIN checker_properties cp ON sd.checker_properties_id = cp.id
            LEFT JOIN checker_type ct ON cp.checker_type_id = ct.id
            LEFT JOIN dynamic_enum de ON dt.current_severity_id = de.id
            LEFT JOIN dynamic_enum de_cls ON dt.current_classification_id = de_cls.id AND de_cls.dtype = 'Cls'
            LEFT JOIN stream_defect_occurrence sdo ON sd.id = sdo.stream_defect_id
            LEFT JOIN stream_file sf ON sdo.stream_file_id = sf.id
            LEFT JOIN file_path fp ON sf.file_path_id = fp.id
            LEFT JOIN function func ON sdo.function_id = func.id
            {self._ACTIVE_JOIN_SQL}
            WHERE p.name = ANY(%s)
                AND cp.cwe = %s
                AND {self._ACTIVE_COND_SQL}
                AND (de_cls.name NOT IN ('False Positive', 'Intentional') OR de_cls.name IS NULL)
                AND sd.merged_defect_id IS NOT NULL
            ORDER BY sd.merged_defect_id, de.name DESC
        """
        
        defect_results = self.db.execute_query_dict(defects_query, (self._project_names, cwe_id))
        
        # Process all defects and collect checker stats
        checker_breakdown = {}
        all_defects = []
        
        for row in defect_results:
            checker_name = row['checker_name'] or 'Unknown'
            
            # Collect all defects
            all_defects.append({
                'cid': row['cid'],
                'checker': checker_name,
                'severity': row['severity'] or 'Unspecified',
                'file': row['file_path'] or 'Unknown',
                'function': row['function_name'] or 'N/A'
            })
            
            # Checker breakdown for top checkers display
            if checker_name not in checker_breakdown:
                checker_breakdown[checker_name] = {
                    'checker': checker_name,
                    'defect_count': 0
                }
            checker_breakdown[checker_name]['defect_count'] += 1
        
        # Sort checker breakdown by count
        checker_list = sorted(checker_breakdown.values(), key=lambda x: x['defect_count'], reverse=True)[:10]
        
        return {
            'checker_breakdown': checker_list,  # Top 10 checkers
            'all_defects': all_defects,  # All defects for this CWE
            'total_checkers': len(checker_breakdown)
        }


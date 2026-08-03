"""
Database connection module for Coverity PostgreSQL database
"""
import logging

import psycopg2
from psycopg2 import pool

logger = logging.getLogger(__name__)


class CoverityDatabase:
    """Manages database connections to Coverity PostgreSQL database"""
    
    def __init__(self, connection_params):
        """Initialize database connection manager
        
        Args:
            connection_params: Dict with connection parameters (host, port, database, user, password).
                              Required - no default fallback.
        """
        if not connection_params:
            raise ValueError("connection_params is required. Please provide database connection parameters from config.json")
        
        self.connection_params = connection_params
        self.connection = None
    
    def connect(self):
        """Establish database connection"""
        if self.connection is None or self.connection.closed:
            self.connection = psycopg2.connect(**self.connection_params)
        return self.connection
    
    def close(self):
        """Close database connection"""
        if self.connection and not self.connection.closed:
            self.connection.close()
    
    def execute_query(self, query, params=None):
        """Execute a query and return results.

        Any database or connection error is logged and an empty list is
        returned so callers can safely continue (e.g. build empty
        DataFrames) instead of aborting the whole run.

        Args:
            query: SQL query string
            params: Query parameters (optional)

        Returns:
            list: Query results as list of tuples. Returns ``[]`` if the
            query fails or the driver returns no result set.
        """
        try:
            conn = self.connect()
        except Exception as exc:  # pragma: no cover - connection failure
            logger.warning("Database connection failed: %s", exc)
            return []

        cursor = conn.cursor()
        try:
            cursor.execute(query, params)
            results = cursor.fetchall()
            if results is None:
                return []
            return results
        except Exception as exc:
            logger.warning("execute_query failed: %s", exc)
            try:
                conn.rollback()
            except Exception:
                pass
            return []
        finally:
            cursor.close()

    def execute_query_dict(self, query, params=None):
        """Execute a query and return results as list of dictionaries.

        Any database or connection error is logged and an empty list is
        returned so callers can safely continue (e.g. build empty
        DataFrames) instead of aborting the whole run.

        Args:
            query: SQL query string
            params: Query parameters (optional)

        Returns:
            list: Query results as list of dictionaries. Returns ``[]`` if
            the query fails or produces no result set.
        """
        try:
            conn = self.connect()
        except Exception as exc:  # pragma: no cover - connection failure
            logger.warning("Database connection failed: %s", exc)
            return []

        cursor = conn.cursor()
        try:
            cursor.execute(query, params)
            if cursor.description is None:
                # Non-SELECT statement or no result set
                return []
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall() or []
            return [dict(zip(columns, row)) for row in rows]
        except Exception as exc:
            logger.warning("execute_query_dict failed: %s", exc)
            try:
                conn.rollback()
            except Exception:
                pass
            return []
        finally:
            cursor.close()
    
    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()

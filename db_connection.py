"""
Database connection module for Coverity PostgreSQL database
"""
import psycopg2
from psycopg2 import pool

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
        """Execute a query and return results
        
        Args:
            query: SQL query string
            params: Query parameters (optional)
            
        Returns:
            list: Query results as list of tuples
        """
        conn = self.connect()
        cursor = conn.cursor()
        try:
            cursor.execute(query, params)
            results = cursor.fetchall()
            return results
        finally:
            cursor.close()
    
    def execute_query_dict(self, query, params=None):
        """Execute a query and return results as list of dictionaries
        
        Args:
            query: SQL query string
            params: Query parameters (optional)
            
        Returns:
            list: Query results as list of dictionaries
        """
        conn = self.connect()
        cursor = conn.cursor()
        try:
            cursor.execute(query, params)
            columns = [desc[0] for desc in cursor.description]
            results = [dict(zip(columns, row)) for row in cursor.fetchall()]
            return results
        finally:
            cursor.close()
    
    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()

import os
import sqlite3
from typing import Any, Optional, Generator
from contextlib import contextmanager
import json

DATABASE_URL = os.environ.get("DATABASE_URL")
POSTGRES_POOL = None

if DATABASE_URL:
    import psycopg2
    from psycopg2 import pool
    from psycopg2.extras import RealDictCursor
    # Initialize a global connection pool
    POSTGRES_POOL = psycopg2.pool.SimpleConnectionPool(1, 10, DATABASE_URL)
    
DEFAULT_SQLITE_PATH = os.path.join(os.path.dirname(__file__), "..", "DATA", "monitoring.db")

class PostgresConnectionWrapper:
    """Wraps psycopg2 connection to mimic sqlite3 context manager and cursor execution"""
    def __init__(self, conn):
        self.conn = conn

    def execute(self, query: str, params: tuple = ()):
        # Convert SQLite ? placeholders to psycopg2 %s
        pg_query = query.replace('?', '%s')
        cursor = self.conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(pg_query, params)
        return cursor

    def commit(self):
        self.conn.commit()
        
    def rollback(self):
        self.conn.rollback()

    def close(self):
        # We don't physically close, we release back to pool
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        # Returning False propagates the exception
        return False

@contextmanager
def get_db(db_path: Optional[str] = None) -> Generator[Any, None, None]:
    """
    Context manager yielding a database connection.
    Uses Postgres pool if DATABASE_URL is set, otherwise SQLite.
    """
    if POSTGRES_POOL is not None:
        conn = POSTGRES_POOL.getconn()
        wrapper = PostgresConnectionWrapper(conn)
        try:
            yield wrapper
        finally:
            POSTGRES_POOL.putconn(conn)
    else:
        resolved = db_path if db_path is not None else DEFAULT_SQLITE_PATH
        norm_path = os.path.abspath(resolved)
        os.makedirs(os.path.dirname(norm_path), exist_ok=True)
        conn = sqlite3.connect(norm_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        try:
            yield conn
        finally:
            conn.close()

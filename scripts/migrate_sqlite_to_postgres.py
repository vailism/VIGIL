import os
import sqlite3
from sanket.db import get_db, POSTGRES_POOL, DEFAULT_SQLITE_PATH
from sanket.monitoring import init_db

if not POSTGRES_POOL:
    raise ValueError("DATABASE_URL must be set and valid to run migration to Postgres")

# Ensure Postgres schema exists
print("Initializing Postgres schema...")
init_db()

# Connect to local SQLite directly
sqlite_path = DEFAULT_SQLITE_PATH
if not os.path.exists(sqlite_path):
    print("No SQLite database found at", sqlite_path)
    exit(0)

print(f"Connecting to SQLite database {sqlite_path}...")
sqlite_conn = sqlite3.connect(sqlite_path)
sqlite_conn.row_factory = sqlite3.Row

tables = [
    "monitored_projects",
    "monthly_observations",
    "contractor_warnings",
    "contractor_responses",
    "authority_escalations",
    "audit_events"
]

with get_db() as pg_conn:
    for table in tables:
        rows = sqlite_conn.execute(f"SELECT * FROM {table}").fetchall()
        print(f"Migrating {len(rows)} records from {table}...")
        
        if not rows:
            continue
            
        # Get column names
        cols = rows[0].keys()
        col_str = ", ".join(cols)
        val_str = ", ".join(["%s"] * len(cols))
        
        query = f"INSERT INTO {table} ({col_str}) VALUES ({val_str}) ON CONFLICT DO NOTHING"
        
        with pg_conn: # transaction
            for row in rows:
                pg_conn.execute(query, tuple(row[col] for col in cols))
                
print("Migration completed successfully!")

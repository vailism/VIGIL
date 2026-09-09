import re

with open('sanket/monitoring.py', 'r') as f:
    content = f.read()

# 1. Imports
content = content.replace("import sqlite3", "import sqlite3\nfrom sanket.db import get_db, POSTGRES_POOL")

# 2. init_db replacement
init_db_new = """def init_db(db_path: Optional[str] = None) -> None:
    \"\"\"Initialize database tables for operational monitoring.\"\"\"
    with get_db(db_path) as conn:
        with conn:
            if POSTGRES_POOL is not None:
                # Postgres Schema
                conn.execute(\"\"\"
                    CREATE TABLE IF NOT EXISTS monitored_projects (
                        project_id TEXT PRIMARY KEY,
                        project_name TEXT NOT NULL,
                        sector TEXT NOT NULL,
                        ministry TEXT,
                        state TEXT,
                        approved_cost DOUBLE PRECISION NOT NULL,
                        revised_cost DOUBLE PRECISION,
                        planned_start_date TEXT,
                        planned_completion_date TEXT,
                        contractor TEXT,
                        initial_reporting_month TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'ACTIVE',
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                \"\"\")

                conn.execute(\"\"\"
                    CREATE TABLE IF NOT EXISTS monthly_observations (
                        id SERIAL PRIMARY KEY,
                        project_id TEXT NOT NULL,
                        reporting_month TEXT NOT NULL,
                        observation_number INTEGER NOT NULL,
                        financial_progress DOUBLE PRECISION,
                        physical_progress DOUBLE PRECISION,
                        expenditure DOUBLE PRECISION,
                        revised_cost DOUBLE PRECISION,
                        completion_date TEXT,
                        schedule_deviation_months DOUBLE PRECISION,
                        milestone_status TEXT,
                        milestone_slippage DOUBLE PRECISION,
                        notes TEXT,
                        supporting_documents TEXT,
                        raw_prob DOUBLE PRECISION,
                        calibrated_prob DOUBLE PRECISION,
                        risk_tier TEXT,
                        alert INTEGER,
                        trajectory_status TEXT,
                        history_confidence TEXT,
                        trajectory_history_months INTEGER,
                        top_explanations TEXT,
                        features_snapshot TEXT,
                        submitted_at TEXT NOT NULL,
                        FOREIGN KEY (project_id) REFERENCES monitored_projects(project_id) ON DELETE CASCADE,
                        UNIQUE (project_id, reporting_month)
                    )
                \"\"\")

                conn.execute(\"\"\"
                    CREATE TABLE IF NOT EXISTS contractor_warnings (
                        warning_id TEXT PRIMARY KEY,
                        project_id TEXT NOT NULL,
                        issued_at TEXT NOT NULL,
                        reporting_month TEXT NOT NULL,
                        risk_probability DOUBLE PRECISION NOT NULL,
                        risk_tier TEXT NOT NULL,
                        warning_reason TEXT NOT NULL,
                        deterministic_evidence TEXT,
                        observed_trajectory TEXT,
                        required_response TEXT NOT NULL,
                        response_deadline TEXT NOT NULL,
                        status TEXT NOT NULL,
                        FOREIGN KEY (project_id) REFERENCES monitored_projects(project_id) ON DELETE CASCADE
                    )
                \"\"\")

                conn.execute(\"\"\"
                    CREATE TABLE IF NOT EXISTS contractor_responses (
                        response_id TEXT PRIMARY KEY,
                        warning_id TEXT NOT NULL,
                        project_id TEXT NOT NULL,
                        acknowledged INTEGER NOT NULL,
                        response_text TEXT NOT NULL,
                        corrective_action TEXT NOT NULL,
                        expected_recovery_date TEXT,
                        responsible_person TEXT,
                        supporting_documents TEXT,
                        submitted_at TEXT NOT NULL,
                        FOREIGN KEY (warning_id) REFERENCES contractor_warnings(warning_id) ON DELETE CASCADE,
                        FOREIGN KEY (project_id) REFERENCES monitored_projects(project_id) ON DELETE CASCADE
                    )
                \"\"\")

                conn.execute(\"\"\"
                    CREATE TABLE IF NOT EXISTS authority_escalations (
                        escalation_id TEXT PRIMARY KEY,
                        project_id TEXT NOT NULL,
                        warning_id TEXT NOT NULL,
                        escalation_date TEXT NOT NULL,
                        risk_at_warning DOUBLE PRECISION NOT NULL,
                        current_risk DOUBLE PRECISION NOT NULL,
                        persistence_duration_months INTEGER NOT NULL,
                        evidence TEXT,
                        contractor_response TEXT,
                        response_status TEXT NOT NULL,
                        reason_for_escalation TEXT NOT NULL,
                        full_audit_trail TEXT,
                        FOREIGN KEY (project_id) REFERENCES monitored_projects(project_id) ON DELETE CASCADE,
                        FOREIGN KEY (warning_id) REFERENCES contractor_warnings(warning_id) ON DELETE CASCADE
                    )
                \"\"\")

                conn.execute(\"\"\"
                    CREATE TABLE IF NOT EXISTS audit_events (
                        event_id TEXT PRIMARY KEY,
                        project_id TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        reporting_month TEXT,
                        event_type TEXT NOT NULL,
                        actor TEXT NOT NULL,
                        risk_probability DOUBLE PRECISION,
                        evidence_snapshot TEXT,
                        metadata TEXT,
                        FOREIGN KEY (project_id) REFERENCES monitored_projects(project_id) ON DELETE CASCADE
                    )
                \"\"\")

                conn.execute("CREATE INDEX IF NOT EXISTS idx_obs_proj_month ON monthly_observations(project_id, reporting_month)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_warnings_proj ON contractor_warnings(project_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_proj ON audit_events(project_id, timestamp)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_escalations_proj ON authority_escalations(project_id)")
                
            else:
                # SQLite Schema
                conn.execute(\"\"\"
                    CREATE TABLE IF NOT EXISTS monitored_projects (
                        project_id TEXT PRIMARY KEY,
                        project_name TEXT NOT NULL,
                        sector TEXT NOT NULL,
                        ministry TEXT,
                        state TEXT,
                        approved_cost REAL NOT NULL,
                        revised_cost REAL,
                        planned_start_date TEXT,
                        planned_completion_date TEXT,
                        contractor TEXT,
                        initial_reporting_month TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'ACTIVE',
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                \"\"\")

                conn.execute(\"\"\"
                    CREATE TABLE IF NOT EXISTS monthly_observations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        project_id TEXT NOT NULL,
                        reporting_month TEXT NOT NULL,
                        observation_number INTEGER NOT NULL,
                        financial_progress REAL,
                        physical_progress REAL,
                        expenditure REAL,
                        revised_cost REAL,
                        completion_date TEXT,
                        schedule_deviation_months REAL,
                        milestone_status TEXT,
                        milestone_slippage REAL,
                        notes TEXT,
                        supporting_documents TEXT,
                        raw_prob REAL,
                        calibrated_prob REAL,
                        risk_tier TEXT,
                        alert INTEGER,
                        trajectory_status TEXT,
                        history_confidence TEXT,
                        trajectory_history_months INTEGER,
                        top_explanations TEXT,
                        features_snapshot TEXT,
                        submitted_at TEXT NOT NULL,
                        FOREIGN KEY (project_id) REFERENCES monitored_projects(project_id) ON DELETE CASCADE,
                        UNIQUE (project_id, reporting_month)
                    )
                \"\"\")

                conn.execute(\"\"\"
                    CREATE TABLE IF NOT EXISTS contractor_warnings (
                        warning_id TEXT PRIMARY KEY,
                        project_id TEXT NOT NULL,
                        issued_at TEXT NOT NULL,
                        reporting_month TEXT NOT NULL,
                        risk_probability REAL NOT NULL,
                        risk_tier TEXT NOT NULL,
                        warning_reason TEXT NOT NULL,
                        deterministic_evidence TEXT,
                        observed_trajectory TEXT,
                        required_response TEXT NOT NULL,
                        response_deadline TEXT NOT NULL,
                        status TEXT NOT NULL,
                        FOREIGN KEY (project_id) REFERENCES monitored_projects(project_id) ON DELETE CASCADE
                    )
                \"\"\")

                conn.execute(\"\"\"
                    CREATE TABLE IF NOT EXISTS contractor_responses (
                        response_id TEXT PRIMARY KEY,
                        warning_id TEXT NOT NULL,
                        project_id TEXT NOT NULL,
                        acknowledged INTEGER NOT NULL,
                        response_text TEXT NOT NULL,
                        corrective_action TEXT NOT NULL,
                        expected_recovery_date TEXT,
                        responsible_person TEXT,
                        supporting_documents TEXT,
                        submitted_at TEXT NOT NULL,
                        FOREIGN KEY (warning_id) REFERENCES contractor_warnings(warning_id) ON DELETE CASCADE,
                        FOREIGN KEY (project_id) REFERENCES monitored_projects(project_id) ON DELETE CASCADE
                    )
                \"\"\")

                conn.execute(\"\"\"
                    CREATE TABLE IF NOT EXISTS authority_escalations (
                        escalation_id TEXT PRIMARY KEY,
                        project_id TEXT NOT NULL,
                        warning_id TEXT NOT NULL,
                        escalation_date TEXT NOT NULL,
                        risk_at_warning REAL NOT NULL,
                        current_risk REAL NOT NULL,
                        persistence_duration_months INTEGER NOT NULL,
                        evidence TEXT,
                        contractor_response TEXT,
                        response_status TEXT NOT NULL,
                        reason_for_escalation TEXT NOT NULL,
                        full_audit_trail TEXT,
                        FOREIGN KEY (project_id) REFERENCES monitored_projects(project_id) ON DELETE CASCADE,
                        FOREIGN KEY (warning_id) REFERENCES contractor_warnings(warning_id) ON DELETE CASCADE
                    )
                \"\"\")

                conn.execute(\"\"\"
                    CREATE TABLE IF NOT EXISTS audit_events (
                        event_id TEXT PRIMARY KEY,
                        project_id TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        reporting_month TEXT,
                        event_type TEXT NOT NULL,
                        actor TEXT NOT NULL,
                        risk_probability REAL,
                        evidence_snapshot TEXT,
                        metadata TEXT,
                        FOREIGN KEY (project_id) REFERENCES monitored_projects(project_id) ON DELETE CASCADE
                    )
                \"\"\")

                conn.execute("CREATE INDEX IF NOT EXISTS idx_obs_proj_month ON monthly_observations(project_id, reporting_month)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_warnings_proj ON contractor_warnings(project_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_proj ON audit_events(project_id, timestamp)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_escalations_proj ON authority_escalations(project_id)")"""

# Replace init_db
content = re.sub(r'def init_db.*?finally:\n        conn\.close\(\)\n', init_db_new + "\n", content, flags=re.DOTALL)

# Remove get_db_connection and resolve_db_path functions as they are in sanket.db now, but let's just leave them or delete them.
# Let's replace `conn = get_db_connection(...)` and `try: with conn:` with `with get_db(...) as conn: with conn:`
content = re.sub(
    r'conn = get_db_connection\(db_path\)\n\s+try:\n\s+(.*?)\n\s+finally:\n\s+conn\.close\(\)',
    r'with get_db(db_path) as conn:\n        \1',
    content,
    flags=re.DOTALL
)

# Fix append_audit_event type hint
content = content.replace("conn: sqlite3.Connection", "conn")
content = content.replace("conn: sqlite3.Connection,", "conn,")
content = content.replace("evaluate_governance_workflow(\n    conn: sqlite3.Connection", "evaluate_governance_workflow(\n    conn")

with open('sanket/monitoring.py', 'w') as f:
    f.write(content)

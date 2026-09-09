# SQLite → PostgreSQL Compatibility & Migration Map

## 1. Type Mappings
To guarantee 100% semantic preservation and identical Python JSON-serialization, we use the following strict type mapping:

| SQLite Type | PostgreSQL Type | Notes |
|-------------|-----------------|-------|
| `TEXT`      | `TEXT`          | Preserved exactly. ISO8601 timestamps and serialized JSON remain `TEXT` to guarantee identical `json.loads()` and dictionary mapping behavior in Python without timezone offset drift. |
| `REAL`      | `DOUBLE PRECISION`| Maximum float precision retained for ML trajectory risk probabilities. |
| `INTEGER`   | `INTEGER`       | Standard integers. |
| `INTEGER PRIMARY KEY AUTOINCREMENT` | `SERIAL PRIMARY KEY` | Postgres native auto-increment. |

## 2. Table Migrations

### `monitored_projects`
*No structural changes.*
- Primary Key: `project_id (TEXT)`

### `monthly_observations`
- `id`: `INTEGER PRIMARY KEY AUTOINCREMENT` → `SERIAL PRIMARY KEY`
- All JSON-stored features (`features_snapshot`, `top_explanations`, `supporting_documents`) remain `TEXT`.

### `contractor_warnings`
*No structural changes.*

### `contractor_responses`
- `acknowledged`: `INTEGER` (0/1 for booleans in SQLite). Preserved as `INTEGER` in Postgres to avoid rewriting Python boolean/int cast logic.

### `authority_escalations`
*No structural changes.*

### `audit_events`
*No structural changes.*

## 3. Query Abstraction (Python Level)
1. **Placeholders**: All `?` parameterized queries in `monitoring.py` will be dynamically mapped to `%s` when executing against PostgreSQL, or remain `?` when running against the SQLite local/test fallback.
2. **Row Factory**: `sqlite3.Row` will be substituted with `psycopg2.extras.RealDictCursor` to guarantee that DB results return as dict-like objects.
3. **Transactions**: `with conn:` context managers in `sqlite3` handle transactions. In `psycopg2`, we must explicitly manage `conn.commit()` or use a context manager wrapper to replicate the `with conn:` auto-commit on success and rollback on exception.

## 4. Uniqueness & Indexes
All indexes and `UNIQUE (project_id, reporting_month)` constraints translate 1:1 to PostgreSQL without syntax changes.

## 5. NULL Handling
Both SQLite and PostgreSQL handle `NULL` identically for uniqueness and foreign keys in this schema. Python `None` maps to `NULL` seamlessly in both drivers.

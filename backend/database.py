"""
SQLite Persistence Layer for SHIM.
Handles projects, integrations, schemas, mappings, transformation logs, and anonymous download tracking.
"""
import sqlite3
import json
import time
import os
from typing import Dict, Any, List, Optional, Tuple

DB_PATH = os.getenv("SHIM_DB_PATH", os.path.join(os.path.dirname(__file__), "shim.db"))

def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db(db_path: str = DB_PATH) -> None:
    """Initialize database tables with indexes."""
    conn = get_connection(db_path)
    with conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'customer',
            created_at REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            owner_id TEXT NOT NULL,
            api_key TEXT UNIQUE NOT NULL,
            created_at REAL NOT NULL,
            FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS integrations (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            name TEXT NOT NULL,
            target_base_url TEXT NOT NULL,
            auth_token TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            created_at REAL NOT NULL,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS endpoint_schemas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL,
            endpoint_path TEXT NOT NULL,
            version INTEGER NOT NULL,
            version_tag TEXT NOT NULL,
            schema_hash TEXT NOT NULL,
            schema_json TEXT NOT NULL,
            is_baseline INTEGER NOT NULL DEFAULT 0,
            created_at REAL NOT NULL,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
            UNIQUE(project_id, endpoint_path, version)
        );

        CREATE TABLE IF NOT EXISTS schema_changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL,
            endpoint_path TEXT NOT NULL,
            from_version INTEGER NOT NULL,
            to_version INTEGER NOT NULL,
            diff_json TEXT NOT NULL,
            detected_at REAL NOT NULL,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS field_mappings (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            endpoint_path TEXT NOT NULL,
            source_field TEXT NOT NULL,
            target_field TEXT NOT NULL,
            source_type TEXT NOT NULL,
            target_type TEXT NOT NULL,
            similarity_score REAL NOT NULL,
            confidence REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDING',
            approved_by TEXT,
            approved_at REAL,
            explanation TEXT,
            created_at REAL NOT NULL,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
            UNIQUE(project_id, endpoint_path, source_field, target_field)
        );

        CREATE TABLE IF NOT EXISTS transformation_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL,
            endpoint_path TEXT NOT NULL,
            method TEXT NOT NULL,
            status_code INTEGER NOT NULL,
            original_payload TEXT,
            transformed_payload TEXT,
            mappings_applied_json TEXT,
            transformation_occurred INTEGER NOT NULL DEFAULT 0,
            latency_ms REAL NOT NULL,
            timestamp REAL NOT NULL,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS extension_downloads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version TEXT NOT NULL DEFAULT '1.0.0',
            user_agent TEXT,
            ip_hash TEXT,
            downloaded_at REAL NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_schemas_lookup ON endpoint_schemas(project_id, endpoint_path);
        CREATE INDEX IF NOT EXISTS idx_mappings_lookup ON field_mappings(project_id, endpoint_path, status);
        CREATE INDEX IF NOT EXISTS idx_logs_lookup ON transformation_logs(project_id, timestamp);
        CREATE INDEX IF NOT EXISTS idx_downloads_time ON extension_downloads(downloaded_at);
        """)

# Download tracking operations (No sign-in required)
def record_extension_download(user_agent: str = "", ip_hash: str = "", version: str = "1.0.0", db_path: str = DB_PATH) -> int:
    conn = get_connection(db_path)
    now = time.time()
    with conn:
        conn.execute(
            "INSERT INTO extension_downloads (version, user_agent, ip_hash, downloaded_at) VALUES (?, ?, ?, ?)",
            (version, user_agent, ip_hash, now)
        )
        total = conn.execute("SELECT COUNT(*) FROM extension_downloads").fetchone()[0]
        return total

def get_download_stats(db_path: str = DB_PATH) -> Dict[str, Any]:
    conn = get_connection(db_path)
    total = conn.execute("SELECT COUNT(*) FROM extension_downloads").fetchone()[0]
    unique_ips = conn.execute("SELECT COUNT(DISTINCT ip_hash) FROM extension_downloads WHERE ip_hash != ''").fetchone()[0]
    recent_rows = conn.execute("SELECT version, user_agent, downloaded_at FROM extension_downloads ORDER BY downloaded_at DESC LIMIT 20").fetchall()
    return {
        "total_downloads": total,
        "unique_downloaders": unique_ips,
        "recent_downloads": [dict(r) for r in recent_rows]
    }

# Project operations
def create_project(project_id: str, name: str, owner_id: str, api_key: str, db_path: str = DB_PATH) -> Dict[str, Any]:
    conn = get_connection(db_path)
    now = time.time()
    with conn:
        conn.execute(
            "INSERT INTO projects (id, name, owner_id, api_key, created_at) VALUES (?, ?, ?, ?, ?)",
            (project_id, name, owner_id, api_key, now)
        )
    return {"id": project_id, "name": name, "owner_id": owner_id, "api_key": api_key, "created_at": now}

def get_project(project_id: str, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    conn = get_connection(db_path)
    row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    return dict(row) if row else None

def get_project_by_api_key(api_key: str, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    conn = get_connection(db_path)
    row = conn.execute("SELECT * FROM projects WHERE api_key = ?", (api_key,)).fetchone()
    return dict(row) if row else None

# Schema operations
def save_endpoint_schema(
    project_id: str,
    endpoint_path: str,
    version: int,
    version_tag: str,
    schema_hash: str,
    schema_dict: Dict[str, Any],
    is_baseline: bool,
    db_path: str = DB_PATH
) -> int:
    conn = get_connection(db_path)
    now = time.time()
    with conn:
        cur = conn.execute(
            """INSERT INTO endpoint_schemas 
               (project_id, endpoint_path, version, version_tag, schema_hash, schema_json, is_baseline, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (project_id, endpoint_path, version, version_tag, schema_hash, json.dumps(schema_dict), 1 if is_baseline else 0, now)
        )
        return cur.lastrowid

def get_latest_schema(project_id: str, endpoint_path: str, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    conn = get_connection(db_path)
    row = conn.execute(
        """SELECT * FROM endpoint_schemas 
           WHERE project_id = ? AND endpoint_path = ? 
           ORDER BY version DESC LIMIT 1""",
        (project_id, endpoint_path)
    ).fetchone()
    if row:
        res = dict(row)
        res["schema"] = json.loads(res["schema_json"])
        return res
    return None

def get_baseline_schema(project_id: str, endpoint_path: str, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    conn = get_connection(db_path)
    row = conn.execute(
        """SELECT * FROM endpoint_schemas 
           WHERE project_id = ? AND endpoint_path = ? AND is_baseline = 1 
           LIMIT 1""",
        (project_id, endpoint_path)
    ).fetchone()
    if row:
        res = dict(row)
        res["schema"] = json.loads(res["schema_json"])
        return res
    return None

def save_schema_change(
    project_id: str,
    endpoint_path: str,
    from_version: int,
    to_version: int,
    diff_dict: Dict[str, Any],
    db_path: str = DB_PATH
) -> int:
    conn = get_connection(db_path)
    now = time.time()
    with conn:
        cur = conn.execute(
            """INSERT INTO schema_changes 
               (project_id, endpoint_path, from_version, to_version, diff_json, detected_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (project_id, endpoint_path, from_version, to_version, json.dumps(diff_dict), now)
        )
        return cur.lastrowid

# Mapping operations
def upsert_mapping(
    mapping_id: str,
    project_id: str,
    endpoint_path: str,
    source_field: str,
    target_field: str,
    source_type: str,
    target_type: str,
    similarity_score: float,
    confidence: float,
    status: str = "PENDING",
    explanation: str = "",
    db_path: str = DB_PATH
) -> None:
    conn = get_connection(db_path)
    now = time.time()
    with conn:
        conn.execute(
            """INSERT INTO field_mappings 
               (id, project_id, endpoint_path, source_field, target_field, source_type, target_type, 
                similarity_score, confidence, status, explanation, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(project_id, endpoint_path, source_field, target_field) DO UPDATE SET
               similarity_score=excluded.similarity_score,
               confidence=excluded.confidence,
               explanation=excluded.explanation""",
            (mapping_id, project_id, endpoint_path, source_field, target_field, source_type, target_type,
             similarity_score, confidence, status, explanation, now)
        )

def update_mapping_status(
    mapping_id: str,
    status: str,
    approved_by: Optional[str] = None,
    db_path: str = DB_PATH
) -> bool:
    conn = get_connection(db_path)
    now = time.time()
    with conn:
        cur = conn.execute(
            """UPDATE field_mappings 
               SET status = ?, approved_by = ?, approved_at = ? 
               WHERE id = ?""",
            (status, approved_by, now if status == "APPROVED" else None, mapping_id)
        )
        return cur.rowcount > 0

def get_approved_mappings(project_id: str, endpoint_path: str, db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    conn = get_connection(db_path)
    rows = conn.execute(
        """SELECT * FROM field_mappings 
           WHERE project_id = ? AND endpoint_path = ? AND status = 'APPROVED'""",
        (project_id, endpoint_path)
    ).fetchall()
    return [dict(r) for r in rows]

def get_mappings_for_project(project_id: str, db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT * FROM field_mappings WHERE project_id = ? ORDER BY created_at DESC",
        (project_id,)
    ).fetchall()
    return [dict(r) for r in rows]

# Log operations
def log_transformation(
    project_id: str,
    endpoint_path: str,
    method: str,
    status_code: int,
    original_payload: Optional[Dict[str, Any]],
    transformed_payload: Optional[Dict[str, Any]],
    mappings_applied: List[Dict[str, Any]],
    transformation_occurred: bool,
    latency_ms: float,
    db_path: str = DB_PATH
) -> int:
    conn = get_connection(db_path)
    now = time.time()
    with conn:
        cur = conn.execute(
            """INSERT INTO transformation_logs 
               (project_id, endpoint_path, method, status_code, original_payload, transformed_payload, 
                mappings_applied_json, transformation_occurred, latency_ms, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (project_id, endpoint_path, method, status_code,
             json.dumps(original_payload) if original_payload else None,
             json.dumps(transformed_payload) if transformed_payload else None,
             json.dumps(mappings_applied),
             1 if transformation_occurred else 0,
             latency_ms, now)
        )
        return cur.lastrowid

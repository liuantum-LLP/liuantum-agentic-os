from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from runtime.storage import WORKSPACE

TABLES = {
    "connectors",
    "social_campaigns",
    "social_drafts",
    "email_drafts",
    "image_jobs",
    "video_jobs",
    "automations",
    "automation_runs",
    "approvals",
    "action_logs",
    "agent_runs",
    "settings",
    "model_providers",
    "permission_profiles",
    "agent_profiles",
    "skill_installs",
    "knowledge_chunks",
    "knowledge_sources",
    "memories",
    "workspaces",
    "exported_files",
    "onboarding_state",
    "oauth_tokens",
    "telegram_messages",
    "telegram_reply_drafts",
    "verification_results",
    "backups",
    "secret_records",
    "sessions",
    "usage_events",
    "alert_history",
    "webhook_deliveries",
    "discussion_cost_rounds",
}


def db_path() -> Path:
    return Path(os.environ.get("LIUANT_DB_PATH", WORKSPACE / "liuant.db"))


def connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def init_db(conn: sqlite3.Connection | None = None) -> None:
    own_conn = conn is None
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = conn or sqlite3.connect(path)
    try:
        for table in TABLES:
            if table == "usage_events":
                conn.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {table} (
                        id TEXT PRIMARY KEY,
                        provider TEXT,
                        model TEXT,
                        model_role TEXT,
                        feature TEXT,
                        estimated_input_tokens INTEGER,
                        estimated_output_tokens INTEGER,
                        estimated_total_tokens INTEGER,
                        estimated_cost REAL,
                        estimated INTEGER,
                        fallback_used INTEGER,
                        status TEXT,
                        discussion_id TEXT,
                        is_local INTEGER,
                        timestamp TEXT,
                        workspace_name TEXT,
                        latency_ms INTEGER
                    )
                    """
                )
            elif table == "alert_history":
                conn.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {table} (
                        id TEXT PRIMARY KEY,
                        level TEXT,
                        type TEXT,
                        message TEXT,
                        pct REAL,
                        daily_cost REAL,
                        daily_limit REAL,
                        monthly_cost REAL,
                        monthly_limit REAL,
                        workspace_name TEXT,
                        dismissed INTEGER,
                        timestamp TEXT
                    )
                    """
                )
            elif table == "webhook_deliveries":
                conn.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {table} (
                        id TEXT PRIMARY KEY,
                        event_type TEXT,
                        workspace TEXT,
                        url_hash TEXT,
                        status TEXT,
                        status_code INTEGER,
                        retry_count INTEGER,
                        error_redacted TEXT,
                        created_at TEXT,
                        delivered_at TEXT,
                        payload_hash TEXT,
                        test_mode INTEGER,
                        timestamp TEXT
                    )
                    """
                )
            elif table == "discussion_cost_rounds":
                conn.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {table} (
                        id TEXT PRIMARY KEY,
                        discussion_id TEXT,
                        round_number INTEGER,
                        phase TEXT,
                        role TEXT,
                        provider TEXT,
                        model TEXT,
                        input_tokens INTEGER,
                        output_tokens INTEGER,
                        total_tokens INTEGER,
                        estimated_cost REAL,
                        exact_cost_available INTEGER,
                        fallback_used INTEGER,
                        status TEXT,
                        timestamp TEXT,
                        workspace_name TEXT
                    )
                    """
                )
            else:
                conn.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {table} (
                        id TEXT PRIMARY KEY,
                        data TEXT NOT NULL,
                        created_at TEXT,
                        updated_at TEXT
                    )
                    """
                )
        conn.commit()
    finally:
        if own_conn:
            conn.close()


def insert_record(table: str, item: dict[str, Any]) -> dict[str, Any]:
    _check_table(table)
    with connect() as conn:
        if table in ("usage_events", "alert_history", "webhook_deliveries", "discussion_cost_rounds"):
            keys = ", ".join(item.keys())
            placeholders = ", ".join(["?"] * len(item))
            conn.execute(f"INSERT OR REPLACE INTO {table} ({keys}) VALUES ({placeholders})", list(item.values()))
        else:
            conn.execute(
                f"INSERT OR REPLACE INTO {table} (id, data, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (
                    item["id"],
                    json.dumps(item, sort_keys=True),
                    item.get("created_at"),
                    item.get("updated_at") or item.get("decided_at") or item.get("last_run_at"),
                ),
            )
    return item


def list_records(table: str) -> list[dict[str, Any]]:
    _check_table(table)
    with connect() as conn:
        if table in ("usage_events", "alert_history", "webhook_deliveries", "discussion_cost_rounds"):
            cursor = conn.execute(f"SELECT * FROM {table} ORDER BY timestamp DESC, rowid DESC")
            cols = [d[0] for d in cursor.description]
            return [dict(zip(cols, r)) for r in cursor.fetchall()]
        else:
            rows = conn.execute(f"SELECT data FROM {table} ORDER BY created_at DESC, rowid DESC").fetchall()
            return [json.loads(row["data"]) for row in rows]


def get_record(table: str, item_id: str) -> dict[str, Any] | None:
    _check_table(table)
    with connect() as conn:
        row = conn.execute(f"SELECT data FROM {table} WHERE id = ?", (item_id,)).fetchone()
    return json.loads(row["data"]) if row else None


def update_record(table: str, item_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    item = get_record(table, item_id)
    if not item:
        raise ValueError(f"Record not found in {table}: {item_id}")
    item.update(updates)
    insert_record(table, item)
    return item


def delete_record(table: str, item_id: str) -> int:
    _check_table(table)
    with connect() as conn:
        cursor = conn.execute(f"DELETE FROM {table} WHERE id = ?", (item_id,))
        return cursor.rowcount


def delete_all_records(table: str) -> int:
    """Delete all records from a table."""
    _check_table(table)
    with connect() as conn:
        cursor = conn.execute(f"DELETE FROM {table}")
        return cursor.rowcount


def health() -> dict[str, Any]:
    init_db()
    path = db_path()
    return {
        "database_path": str(path),
        "database_exists": path.exists(),
        "tables": sorted(TABLES),
    }


def _check_table(table: str) -> None:
    if table not in TABLES:
        raise ValueError(f"Unknown table: {table}")

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

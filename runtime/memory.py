from __future__ import annotations

from typing import Any
from uuid import uuid4

from runtime.action_log import log_external_action
from runtime.db import delete_record, insert_record, list_records
from runtime.knowledge import cosine_similarity, safe_preview
from runtime.providers import ModelHub
from runtime.config import SettingsManager, utc_now


class MemoryManager:
    def list(self, memory_type: str | None = None) -> list[dict[str, Any]]:
        rows = list_records("memories")
        if memory_type:
            rows = [row for row in rows if row.get("memory_type") == memory_type]
        return rows

    def add(self, content: str, memory_type: str = "user", title: str | None = None, agent_slug: str | None = None, workspace_name: str | None = None, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        workspace = workspace_name or SettingsManager().get("default_workspace")["value"]
        embedding = ModelHub().create_embedding(content, provider_name="local_hash_embedding", metadata={"feature": "memory_add"})
        row = insert_record("memories", {
            "id": str(uuid4()),
            "workspace_name": workspace,
            "memory_type": memory_type if memory_type.endswith("_memory") else f"{memory_type}_memory",
            "agent_slug": agent_slug,
            "title": title or safe_preview(content, 60),
            "content": content,
            "content_preview": safe_preview(content),
            "embedding_json": embedding["embedding"],
            "metadata_json": metadata or {},
            "created_at": utc_now(),
            "updated_at": utc_now(),
        })
        log_external_action("memory_added", "completed", {"memory_id": row["id"], "memory_type": row["memory_type"], "preview": row["content_preview"]})
        return row

    def search(self, query: str, workspace_name: str | None = None, limit: int = 5) -> dict[str, Any]:
        workspace = workspace_name or SettingsManager().get("default_workspace")["value"]
        query_embedding = ModelHub().create_embedding(query, provider_name="local_hash_embedding", metadata={"feature": "memory_search"})["embedding"]
        rows = [row for row in list_records("memories") if row.get("workspace_name") == workspace or not workspace_name]
        results = []
        for row in rows:
            results.append({**row, "score": round(cosine_similarity(query_embedding, row.get("embedding_json") or []), 6)})
        results.sort(key=lambda row: row["score"], reverse=True)
        log_external_action("memory_searched", "completed", {"query_preview": safe_preview(query), "result_count": min(limit, len(results))})
        return {"status": "completed", "query": query, "results": results[:limit]}

    def delete(self, memory_id: str) -> dict[str, Any]:
        return {"status": "deleted", "id": memory_id, "deleted": delete_record("memories", memory_id)}

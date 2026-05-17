from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Any
from uuid import uuid4

from runtime.action_log import log_external_action
from runtime.db import delete_record, get_record, insert_record, list_records
from runtime.providers import ModelHub
from runtime.storage import WORKSPACE
from runtime.config import SettingsManager, utc_now


SECRET_FILENAMES = {".env", ".env.local"}
SECRET_TERMS = ("password", "otp", "api key", "token", "secret", "credit card", "aadhaar", "pan", "bank account")


class KnowledgeBase:
    def sources(self) -> list[dict[str, Any]]:
        return list_records("knowledge_sources")

    def add_text(self, text: str, title: str = "Text Note", workspace_name: str | None = None, source_type: str = "text", metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.index_text(text, title=title, workspace_name=workspace_name or _workspace(), source_type=source_type, metadata=metadata or {})

    def index_text(self, text: str, title: str, workspace_name: str = "default", source_type: str = "text", source_id: str | None = None, source_path: str = "", metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        safety = inspect_text(text)
        source_id = source_id or str(uuid4())
        chunks = chunk_text(text)
        source = insert_record("knowledge_sources", {
            "id": source_id,
            "workspace_name": workspace_name,
            "source_type": source_type,
            "source_path": source_path,
            "title": title,
            "status": "indexed",
            "chunk_count": len(chunks),
            "last_indexed_at": utc_now(),
            "metadata_json": {**(metadata or {}), "sensitive": safety["sensitive"]},
            "created_at": utc_now(),
            "updated_at": utc_now(),
        })
        for index, chunk in enumerate(chunks):
            embedding = ModelHub().create_embedding(chunk, provider_name=(metadata or {}).get("provider_name"), metadata={"feature": "knowledge_index", "source_id": source_id})
            if embedding["status"] != "completed":
                embedding = ModelHub().create_embedding(chunk, provider_name="local_hash_embedding", metadata={"feature": "knowledge_index_fallback", "source_id": source_id})
            insert_record("knowledge_chunks", {
                "id": f"{source_id}-{index}",
                "workspace_name": workspace_name,
                "source_type": source_type,
                "source_id": source_id,
                "source_path": source_path,
                "title": title,
                "content": chunk,
                "content_preview": safe_preview(chunk),
                "content_hash": hashlib.sha256(chunk.encode("utf-8")).hexdigest(),
                "embedding_json": embedding["embedding"],
                "embedding_provider": embedding["provider"],
                "embedding_model": embedding["model"],
                "metadata_json": {"chunk_index": index, **(metadata or {})},
                "created_at": utc_now(),
                "updated_at": utc_now(),
            })
        log_external_action("knowledge_source_indexed", "indexed", {"source_id": source_id, "title": title, "chunk_count": len(chunks), "preview": "[sensitive redacted]" if safety["sensitive"] else safe_preview(text)})
        return source

    def index_file(self, path: str, workspace_name: str | None = None) -> dict[str, Any]:
        file_path = _safe_workspace_path(path)
        text = file_path.read_text(encoding="utf-8")
        return self.index_text(text, title=file_path.name, workspace_name=workspace_name or _workspace(), source_type="file", source_path=str(file_path))

    def index_agent_run(self, run_id: str, workspace_name: str | None = None) -> dict[str, Any]:
        run = get_record("agent_runs", run_id)
        if not run:
            raise ValueError(f"Agent run not found: {run_id}")
        import json

        text = json.dumps(run.get("result", run), indent=2, sort_keys=True)
        return self.index_text(text, title=f"Agent run {run_id}", workspace_name=workspace_name or _workspace(), source_type="agent_run", source_id=f"agent-run-{run_id}", metadata={"agent_run_id": run_id})

    def search(self, query: str, workspace_name: str | None = None, limit: int = 5) -> dict[str, Any]:
        workspace = workspace_name or _workspace()
        query_embedding = ModelHub().create_embedding(query, provider_name="local_hash_embedding", metadata={"feature": "knowledge_search"})["embedding"]
        rows = [row for row in list_records("knowledge_chunks") if row.get("workspace_name") == workspace or not workspace_name]
        results = []
        for row in rows:
            score = cosine_similarity(query_embedding, row.get("embedding_json") or [])
            results.append({**row, "score": round(score, 6)})
        results.sort(key=lambda item: item["score"], reverse=True)
        log_external_action("knowledge_search", "completed", {"query_preview": safe_preview(query), "workspace_name": workspace, "result_count": min(limit, len(results))})
        return {"status": "completed", "query": query, "workspace_name": workspace, "results": results[:limit]}

    def delete_source(self, source_id: str) -> dict[str, Any]:
        source_deleted = delete_record("knowledge_sources", source_id)
        chunk_deleted = 0
        for row in list_records("knowledge_chunks"):
            if row.get("source_id") == source_id:
                chunk_deleted += delete_record("knowledge_chunks", row["id"])
        return {"status": "deleted", "source_id": source_id, "sources_deleted": source_deleted, "chunks_deleted": chunk_deleted}

    def reindex_source(self, source_id: str) -> dict[str, Any]:
        source = get_record("knowledge_sources", source_id)
        if not source:
            raise ValueError(f"Knowledge source not found: {source_id}")
        if source.get("source_type") == "file" and source.get("source_path"):
            self.delete_source(source_id)
            return self.index_file(source["source_path"], source.get("workspace_name"))
        chunks = [row for row in list_records("knowledge_chunks") if row.get("source_id") == source_id]
        text = "\n\n".join(row.get("content", "") for row in sorted(chunks, key=lambda row: row.get("metadata_json", {}).get("chunk_index", 0)))
        self.delete_source(source_id)
        return self.index_text(text, source.get("title", "Reindexed source"), source.get("workspace_name", "default"), source.get("source_type", "text"), source_id)


def chunk_text(text: str, chunk_size: int = 900, overlap: int = 120) -> list[str]:
    clean = (text or "").strip()
    if not clean:
        return []
    chunks = []
    start = 0
    while start < len(clean):
        chunks.append(clean[start : start + chunk_size])
        start += max(1, chunk_size - overlap)
    return chunks


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    size = min(len(a), len(b))
    dot = sum(a[i] * b[i] for i in range(size))
    na = math.sqrt(sum(value * value for value in a[:size])) or 1.0
    nb = math.sqrt(sum(value * value for value in b[:size])) or 1.0
    return dot / (na * nb)


def inspect_text(text: str) -> dict[str, Any]:
    lower = (text or "").lower()
    matches = [term for term in SECRET_TERMS if term in lower]
    return {"sensitive": bool(matches), "matches": matches}


def safe_preview(text: str, limit: int = 180) -> str:
    if inspect_text(text)["sensitive"]:
        return "[sensitive redacted]"
    value = " ".join((text or "").split())
    return value if len(value) <= limit else value[: limit - 1] + "..."


def _safe_workspace_path(path: str) -> Path:
    raw = Path(path).expanduser()
    file_path = raw if raw.is_absolute() else WORKSPACE / raw
    resolved = file_path.resolve()
    workspace = WORKSPACE.resolve()
    if not str(resolved).startswith(str(workspace)):
        raise ValueError("File indexing is limited to the workspace.")
    if resolved.name in SECRET_FILENAMES or any(term in resolved.name.lower() for term in ("key", "token", "oauth")) or resolved.suffix in {".db", ".sqlite"}:
        raise ValueError("Secret, token, key, environment, and database files are not indexed by default.")
    if not resolved.exists() or not resolved.is_file():
        raise ValueError(f"File not found: {resolved}")
    return resolved


def _workspace() -> str:
    try:
        return SettingsManager().get("default_workspace")["value"]
    except Exception:
        return "default"

# Liuant Knowledge Base

v0.2.7 adds a SQLite-backed local knowledge base for text notes, workspace files, agent runs, and future local artifacts.

## CLI

```bash
./liuant knowledge add-text "Liuant Agentic OS is a local-first AI workforce platform"
./liuant knowledge index-file notes.md
./liuant knowledge index-agent-run <run_id>
./liuant knowledge search "What is Liuant Agentic OS?"
./liuant knowledge sources
./liuant knowledge delete-source <source_id>
./liuant knowledge reindex <source_id>
```

## API

- `GET /api/knowledge/sources`
- `POST /api/knowledge/add-text`
- `POST /api/knowledge/index-file`
- `POST /api/knowledge/index-agent-run`
- `POST /api/knowledge/search`
- `DELETE /api/knowledge/sources/{source_id}`
- `POST /api/knowledge/sources/{source_id}/reindex`

## Tables

- `knowledge_sources`: source metadata, title, status, chunk count, last indexed time.
- `knowledge_chunks`: chunk content, safe preview, embedding, provider/model, metadata.

## File Indexing Safety

File indexing is workspace-only. Liuant rejects path traversal and secret-like files by default:

- `.env`, `.env.local`
- key/token/OAuth files
- SQLite/database files

Cloud embeddings are not used by default. `local_hash_embedding` keeps indexing local unless the user explicitly selects a cloud embedding provider.

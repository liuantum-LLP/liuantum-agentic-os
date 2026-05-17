# Liuant RAG

RAG is opt-in in v0.2.7. Liuant agents remain deterministic and useful without a model provider or knowledge base.

## Agent RAG

```bash
./liuant agents run tutor-agent "Create a lesson plan using my knowledge base" --rag
```

When `--rag` is enabled:

1. Liuant searches local knowledge chunks and memories.
2. Retrieved previews and scores are attached to the agent run result.
3. The deterministic local agent output is still created first.
4. If AI enhancement is also enabled, the retrieved context can be included in provider refinement.
5. If RAG search fails, the agent run still completes.

## Settings

Defaults:

- `rag_enabled=false`
- `rag_default_limit=5`
- `rag_workspace_scope=true`
- `rag_include_user_memory=true`
- `rag_include_project_memory=true`
- `email_rag_enabled=false`
- `telegram_knowledge_search_enabled=false`
- `scheduler_rag_enabled=false`

## External Channels

Email, Telegram, and scheduler RAG are disabled by default. This prevents private workspace knowledge from being exposed through an external channel unless the user explicitly opts in.

## Current Limits

- SQLite vector search is intentionally simple.
- `local_hash_embedding` is deterministic and test-friendly, but not as semantically rich as a production embedding model.
- OpenAI and Ollama embedding paths exist, but cloud/local provider use is explicit.

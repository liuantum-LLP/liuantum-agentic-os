# Liuant Memory

v0.2.7 adds local-first memory for user, project, agent, and task context.

## Memory Types

- `user_memory`: durable user preferences and working style.
- `project_memory`: workspace/project facts.
- `agent_memory`: agent-specific learned context.
- `task_memory`: recent task outputs or useful notes.

## CLI

```bash
./liuant memory add "User prefers premium dark UI" --type user
./liuant memory search "UI preference"
./liuant memory list
./liuant memory delete <id>
```

## API

- `GET /api/memory`
- `POST /api/memory/add`
- `POST /api/memory/search`
- `DELETE /api/memory/{id}`

## Storage

Memory rows are stored in SQLite in `memories`. Embeddings use `local_hash_embedding` by default, so adding/searching memory does not require a cloud provider.

## Safety

Sensitive content is redacted in logs. Memory is local by default and is only used in agent runs when RAG is enabled explicitly or through settings.

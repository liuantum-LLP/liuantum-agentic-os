# Discussion Streaming (v1.4.0)

Discussion Mode streaming enables real-time, progressive display of model-to-model discussions in the Liuant Agentic OS.

## Overview

Instead of waiting for the entire discussion to complete before showing results, `stream_discussion()` yields structured Server-Sent Events (SSE) that allow the UI to display each role's contribution as it happens.

## Engine: `stream_discussion()`

Located in `runtime/chat/discussion.py`, the `stream_discussion()` function is a generator that yields structured events:

### Event Types

| Event | Description | Key Fields |
|-------|-------------|------------|
| `discussion_start` | Discussion begins | `roles`, `rounds`, `final_role`, `discussion_id` |
| `role_start` | A role begins contributing | `role`, `round`, `provider`, `model` |
| `role_token` | Token from role's response | `role`, `round`, `content` |
| `role_done` | Role finished | `role`, `round`, `status`, `fallback_used`, `estimated_tokens` |
| `role_skip` | Role skipped (not configured) | `role`, `reason` |
| `role_error` | Role encountered error | `role`, `content` (redacted) |
| `final_start` | Final synthesis begins | `role` |
| `final_token` | Token from final answer | `content` |
| `usage_update` | Usage/cost update | `estimated_tokens`, `estimated_cost`, `estimated` |
| `discussion_done` | Discussion complete | `status`, `fallback_used`, `warnings`, `estimated_tokens`, `estimated_cost` |

## API Endpoint

`POST /api/chat/discussion-stream`

Request body:
```json
{
  "message": "Plan Liuant Agentic OS launch",
  "roles": ["thinking", "planning"],
  "rounds": 2,
  "final_role": "thinking"
}
```

Response: `text/event-stream` with SSE events.

## Safety

- **No hidden reasoning streamed**: Only user-visible role outputs are streamed.
- **Secrets redacted**: User messages are passed through `redact_secrets()` before model calls.
- **Errors redacted**: Error messages are truncated to 100 characters and sensitive patterns are redacted.
- **No token/chunk logging**: Tokens are streamed to the client but not logged server-side.

## Cost Estimation

- Costs are marked `estimated=true` unless exact provider usage is returned.
- Local providers (ollama, lmstudio) show zero cloud cost.
- Cloud providers use the configurable pricing table in `runtime/usage/tracker.py`.

## CLI Usage

```bash
./liuant chat --discussion --stream "Plan Liuant launch"
```

## Limitations

- Anthropic and Gemini streaming currently fall back to non-streaming `generate_text` due to SDK complexity.
- Cost estimation is approximate; exact costs require provider-specific usage metadata.
- Discussion mode is optional and disabled by default.
- Maximum rounds capped at 4.

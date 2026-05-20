# Streaming — Liuant Agentic OS v1.4.0

Streaming enables progressive token delivery from AI providers, giving users real-time feedback during generation.

## Discussion Mode Streaming (v1.4.0)

Discussion Mode now supports real-time SSE streaming via `stream_discussion()`. See [DISCUSSION_STREAMING.md](DISCUSSION_STREAMING.md) for full details.

```bash
./liuant chat --discussion --stream "Plan Liuant launch"
```

Events: `discussion_start`, `role_start`, `role_token`, `role_done`, `final_start`, `final_token`, `usage_update`, `discussion_done`.

## Supported Providers

| Provider | Streaming Support | Notes |
|----------|------------------|-------|
| **Ollama** | ✅ Full | `/api/generate` with `stream=true` |
| **OpenAI-compatible** | ✅ Full | `/chat/completions` with `stream=true` |
| **OpenRouter** | ✅ Full | OpenAI-compatible endpoint |
| **Groq** | ✅ Full | OpenAI-compatible endpoint |
| **LMStudio** | ✅ Full | OpenAI-compatible endpoint |
| **Anthropic** | ⚠️ Fallback | Falls back to non-streaming `generate_text` |
| **Gemini** | ⚠️ Fallback | Falls back to non-streaming `generate_text` |
| **Mistral/Together/Fireworks** | ✅ Full | OpenAI-compatible endpoint |

## Chunk Format

Each streaming chunk has this shape:

```json
{
  "type": "token | metadata | warning | error | done",
  "content": "...",
  "provider": "openrouter",
  "model": "openai/gpt-4.1-mini",
  "role": "coding",
  "fallback_used": false
}
```

- `metadata`: First chunk, contains provider/model/role info
- `token`: Contains incremental text from the model
- `warning`: Non-fatal issue (e.g., rate limit approaching)
- `error`: Fatal error, streaming stops
- `done`: Final chunk, streaming complete

## CLI Usage

```bash
# Stream chat response
./liuant chat --stream "Explain Liuant Agentic OS"

# Stream with specific model role
./liuant chat --stream --model-role coding "Write a Python CSV cleaner"

# Stream text generation
./liuant text generate --stream "Write a launch caption" --provider openrouter

# Stream agent run
./liuant agents run coding-agent "Fix this error" --stream --model-role coding
```

## API Usage

### POST /api/chat/stream

```json
{
  "message": "Explain Liuant Agentic OS",
  "provider": "openrouter",
  "model": "openai/gpt-4.1-mini",
  "role": "default"
}
```

Returns Server-Sent Events stream.

### POST /api/models/stream

```json
{
  "prompt": "Write a launch caption",
  "provider": "openrouter",
  "model": "openai/gpt-4.1-mini",
  "role": "planning"
}
```

### POST /api/agents/{slug}/stream

```json
{
  "prompt": "Fix this Flask error",
  "model_role": "coding"
}
```

## Chat UI

- **Streaming toggle**: Enable/disable streaming in chat controls
- **Progressive display**: Tokens appear in real-time as they arrive
- **Stop button**: Abort streaming mid-generation
- **Provider/model badge**: Shows which provider and model generated the response
- **Discussion Mode + Streaming**: Shows warning and falls back to non-streaming discussion

## Safety

- **No token logging**: Streaming chunks are not logged by default
- **Secret redaction**: API keys, Bearer tokens, passwords are redacted in errors
- **Sensitive prompt detection**: Prompts with sensitive patterns are redacted in logs
- **No hidden reasoning**: Only final user-visible answer is streamed

## Limitations

- Anthropic and Gemini providers fall back to non-streaming `generate_text`
- Discussion Mode does not support streaming in v1.3.0
- Streaming requires provider to support SSE or line-delimited JSON
- Network interruptions may cause incomplete responses

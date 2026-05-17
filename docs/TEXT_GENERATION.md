# Text Generation

Liuant Agentic OS v0.2.3 adds real text generation routing through the Model Hub while keeping deterministic local agent outputs as the default.

## Provider Routing

Text generation resolves providers in this order:

1. Explicit request provider, such as `--provider ollama`.
2. Agent provider preference, when AI enhancement is enabled.
3. Global `default_text_provider`.
4. Configured `fallback_text_provider` if the primary provider fails.

The response always uses this shape:

```json
{
  "status": "completed",
  "provider": "openai",
  "model": "gpt-4.1-mini",
  "text": "...",
  "error": null,
  "usage": {},
  "fallback_used": false,
  "fallback_provider": null
}
```

Failure states are explicit: `needs_provider_setup`, `provider_error`, `local_unreachable`, and `placeholder`.

## Supported Text Providers

Implemented text calls:

- OpenAI via `/chat/completions`
- OpenRouter via OpenAI-compatible `/chat/completions`
- Ollama via `/api/tags` and `/api/generate`
- LM Studio via OpenAI-compatible `/chat/completions`
- Custom OpenAI-compatible providers

Config-ready placeholders:

- Anthropic
- Gemini
- Groq
- Mistral
- Together
- Fireworks

## Commands

```bash
./liuant text providers
./liuant text test openai
./liuant text generate "Write a 5-line marketing caption for Liuant Agentic OS"
./liuant text generate "Write a 5-line marketing caption" --provider openrouter --model "openai/gpt-4o-mini"
./liuant text generate "Write a 5-line marketing caption" --provider ollama --model llama3.1
```

## Test Config vs Generate Test Text

Test Config checks configuration only:

- Cloud providers: key/config presence.
- Local providers: endpoint reachability.
- Placeholder providers: honest placeholder/config-ready status.

Generate Test Text makes a tiny real text generation request and only exists for text providers.

## Configuration

OpenAI:

```text
OPENAI_API_KEY=your_key_here
```

OpenRouter:

```text
OPENROUTER_API_KEY=your_key_here
```

Ollama:

```bash
ollama serve
./liuant providers test ollama
./liuant text generate "Say hello" --provider ollama --model llama3.1
```

LM Studio:

- Start the local OpenAI-compatible server.
- Use `http://127.0.0.1:1234/v1` as the base URL.

Custom OpenAI-compatible provider:

```bash
./liuant providers set-default text custom_openai_compatible
```

Then configure `base_url`, `api_key_env`, and `default_model` through the Model Hub UI or provider setup route.

## Agent AI Enhancement

Agents remain usable without any AI provider. By default, they produce deterministic local outputs.

AI enhancement is optional:

```bash
./liuant agents run marketing-agent "Create campaign for Python course" --ai
./liuant agents run coding-agent "Plan Flask CRUD app" --ai --provider ollama --model llama3.1
```

When enabled:

1. Liuant creates the deterministic local output first.
2. The local output is sent to `generate_text` for refinement.
3. The agent run stores `local_output`, `ai_enhanced_output` when successful, provider/model metadata, and provider status.
4. Provider failure does not fail the whole agent run.

## Safety

- Raw API keys are never logged or returned.
- Provider errors are redacted.
- Action logs store short summaries, not full long text.
- Prompts containing terms such as password, OTP, credit card, Aadhaar, PAN, secret, API key, or token are marked `sensitive_redacted`.

## Pending

- Real social OAuth.
- Real video providers.
- Production multi-user tenancy and hosted identity management.
- Higher-quality vector search backend beyond the local SQLite RAG MVP.

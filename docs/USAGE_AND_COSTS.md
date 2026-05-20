# Usage & Cost Tracking (v1.4.0)

Liuant Agentic OS tracks API usage and provides cost estimates across all providers and features.

## Overview

The `UsageTracker` class in `runtime/usage/tracker.py` records usage events and provides aggregated summaries. All costs are estimates unless exact provider usage metadata is available.

## Features

- **Per-provider tracking**: Track usage by OpenAI, Anthropic, Gemini, Groq, etc.
- **Per-role tracking**: Track usage by model role (thinking, coding, planning, default).
- **Per-feature tracking**: Track usage by feature (chat, agent, discussion, text).
- **Local vs Cloud**: Local providers (ollama, lmstudio) show zero cloud cost.
- **Cost estimation**: Configurable pricing table for cloud providers.
- **Reset capability**: Clear local usage data with confirmation.

## Pricing Table

Located in `runtime/usage/tracker.py`:

```python
PRICING_TABLE = {
    "openai": {"input_per_1k": 0.0025, "output_per_1k": 0.01},
    "openrouter": {"input_per_1k": 0.001, "output_per_1k": 0.005},
    "anthropic": {"input_per_1k": 0.003, "output_per_1k": 0.015},
    "gemini": {"input_per_1k": 0.00035, "output_per_1k": 0.00105},
    "groq": {"input_per_1k": 0.0001, "output_per_1k": 0.0004},
    "mistral": {"input_per_1k": 0.0001, "output_per_1k": 0.0003},
    "together": {"input_per_1k": 0.0002, "output_per_1k": 0.0008},
    "fireworks": {"input_per_1k": 0.0002, "output_per_1k": 0.0008},
}
```

## Local Providers (Zero Cloud Cost)

```python
LOCAL_PROVIDERS = {"ollama", "lmstudio", "local_hash_embedding", "whisper_local", "piper_local", "coqui_local"}
```

Local providers always record `estimated_cost=0.0` and `is_local=True`.

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/usage/summary` | GET | Overall usage summary |
| `/api/usage/today` | GET | Today's usage |
| `/api/usage/by-provider` | GET | Usage grouped by provider |
| `/api/usage/by-role` | GET | Usage grouped by model role |
| `/api/usage/reset` | POST | Reset usage data (requires `confirm=true`) |

## CLI Commands

```bash
./liuant usage summary       # Overall summary
./liuant usage today         # Today's usage
./liuant usage by-provider   # By provider
./liuant usage by-role       # By role
./liuant usage reset --confirm true  # Reset data
```

## Safety

- **No secrets stored**: Usage events only store provider, model, role, tokens, and cost.
- **Estimated by default**: Costs are marked `estimated=true` unless exact provider usage is returned.
- **Local data only**: Usage data is stored locally and can be reset at any time.
- **No external reporting**: Usage data is not sent to external services.

## Limitations

- Cost estimation is approximate based on token counts and published pricing.
- Exact costs require provider-specific usage metadata (not all providers return this).
- Usage data is local only; no cloud sync or backup.
- Reset clears all local usage data permanently.

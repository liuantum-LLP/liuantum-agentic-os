# Discussion Costs (v1.9.0)

Track and analyze API costs per role and per round during Discussion Mode sessions.

## Overview

Discussion Mode uses multiple model roles to collaborate on responses. Each role's contribution is tracked separately with token counts and estimated costs, enabling detailed cost analysis per discussion session.

## Cost Breakdown Structure

```json
{
  "discussion_id": "disc_abc123",
  "roles": {
    "thinking": {
      "tokens": 1800,
      "estimated_cost": 0.006,
      "provider": "openrouter",
      "model": "deepseek/deepseek-reasoner"
    },
    "planning": {
      "tokens": 1200,
      "estimated_cost": 0.003,
      "provider": "openrouter",
      "model": "moonshotai/kimi-k2.5"
    }
  },
  "final": {
    "role": "thinking",
    "tokens": 900,
    "estimated_cost": 0.003
  },
  "total_tokens": 3900,
  "total_cost": 0.012,
  "timestamp": "2026-05-18T10:00:00Z"
}
```

## CLI Usage

```bash
# View all discussion costs
./liuant usage discussion-costs

# View latest discussion cost breakdown
./liuant usage discussion-costs --latest

# View latest with per-round breakdown
./liuant usage discussion-costs --latest --rounds

# View specific discussion by ID
./liuant usage discussion-costs --discussion-id disc_abc123

# Filter by workspace
./liuant usage discussion-costs --workspace current
```

## Per-Round Breakdown (v1.8.0)

Discussion costs are now tracked per round with phase information:

```json
{
  "discussion_id": "disc_abc123",
  "rounds": {
    "round_1_initial": {
      "round_number": 1,
      "phase": "initial",
      "roles": {
        "critic": {
          "input_tokens": 100,
          "output_tokens": 200,
          "total_tokens": 300,
          "estimated_cost": 0.003,
          "provider": "openai",
          "model": "gpt-4",
          "fallback_used": false
        }
      },
      "total_tokens": 300,
      "total_cost": 0.003
    },
    "round_2_review": {
      "round_number": 2,
      "phase": "review",
      "roles": { ... },
      "total_tokens": 400,
      "total_cost": 0.005
    }
  },
  "total_tokens": 1200,
  "total_cost": 0.010,
  "timestamp": "2026-05-19T04:00:00Z"
}
```

### Phases

| Phase | Description |
|-------|-------------|
| `initial` | First round of role responses |
| `review` | Subsequent review rounds (if configured) |
| `final` | Final synthesis by synthesizer role |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/usage/discussion-costs` | GET | Get all discussion costs |
| `/api/usage/discussion-costs/latest` | GET | Get latest discussion cost breakdown |
| `/api/usage/discussion-costs/{discussion_id}` | GET | Get specific discussion with per-round breakdown |

## Cost Estimation

- All costs are **estimated** unless exact provider usage metadata is returned
- Local providers (ollama, lmstudio) show **zero cloud cost**
- Costs are calculated using the configured pricing table
- Token counts are approximate (characters / 4)

## UI Display (v1.9.0)

The Usage & Costs dashboard shows:

### Discussion Cost Breakdown Panel
- Latest discussion ID (monospace)
- Total estimated cost (green, monospace)
- Total tokens (monospace)
- Refresh Latest button

### Per-Round Breakdown
- Collapsible round rows with phase label (initial/review/final)
- Round-level total cost and tokens
- Role-level breakdown within each round:
  - Role name (accent color)
  - Provider/model (monospace)
  - Estimated cost (monospace)
  - Token count (monospace)
  - Fallback warning badge (yellow) if fallback was used

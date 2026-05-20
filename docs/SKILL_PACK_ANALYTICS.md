# Skill Pack Analytics

Track local-only pack usage events. No cloud telemetry, no prompts, no secrets.

## Tracked Events

| Event | When Recorded |
|-------|---------------|
| `imported` | Pack is imported |
| `installed` | Skill from pack is installed |
| `upgraded` | Pack is upgraded |
| `removed` | Pack is removed |
| `verified` | Pack signature is verified |
| `failed_validation` | Pack validation fails |
| `run` | Skill from pack is executed |

## Event Data

Each event records:
- `pack_id` — Pack identifier
- `skill_id` — Skill identifier (if applicable)
- `event_type` — Event type
- `timestamp` — ISO 8601 timestamp
- `workspace` — Workspace path
- `status` — Event status
- `risk_level` — Pack risk level
- `trust_state` — Pack trust state

## CLI Commands

### View Analytics

```bash
./liuant skills pack analytics
./liuant skills pack analytics analytics-starter-pack
```

### Export Analytics

```bash
./liuant skills pack analytics --export markdown
./liuant skills pack analytics --export json
./liuant skills pack analytics --export csv
```

## Summary Fields

- `total_events` — Total number of events
- `by_type` — Event counts by type
- `by_pack` — Event counts by pack
- `last_imported` — Timestamp of last import
- `last_installed` — Timestamp of last install
- `last_verified` — Timestamp of last verification
- `last_run` — Timestamp of last run
- `validation_failures` — Number of failed validations

## Privacy

- **Local-only** — Data never leaves your machine
- **No prompts** — No user prompts or content stored
- **No secrets** — No API keys or sensitive data
- **No file contents** — No file contents stored
- **Configurable** — Analytics can be cleared at any time

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/skills/packs/analytics` | Get all analytics |
| GET | `/api/skills/packs/{pack_id}/analytics` | Get pack-specific analytics |

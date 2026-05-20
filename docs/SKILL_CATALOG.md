# Local Skill Catalog

The local skill catalog provides a browsable list of available skill packs without requiring an internet connection or marketplace server.

## How It Works

The catalog is stored in `workspace/skills/catalog.json` and is populated by scanning `examples/skill-packs/` for valid `.liuantskillpack` files.

## CLI Commands

### View Catalog

```bash
./liuant skills catalog
```

### Refresh Catalog

```bash
./liuant skills catalog refresh
```

Scans `examples/skill-packs/` and updates `catalog.json`.

### Search Catalog

```bash
./liuant skills catalog search analytics
```

Searches pack ID, name, description, skills, and tags.

### Install from Catalog

```bash
./liuant skills catalog install analytics-starter-pack
```

Validates the pack, imports it, and installs skills (disabled by default).

### Inspect Catalog Entry

```bash
./liuant skills catalog inspect analytics-starter-pack
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/skills/catalog` | Get catalog |
| POST | `/api/skills/catalog/refresh` | Refresh catalog |
| GET | `/api/skills/catalog/search?q=` | Search catalog |
| POST | `/api/skills/catalog/install` | Install from catalog |

## Catalog Schema

```json
{
  "packs": [
    {
      "pack_id": "analytics-starter-pack",
      "name": "Analytics Starter Skill Pack",
      "version": "0.1.0",
      "description": "...",
      "path": "examples/skill-packs/analytics-starter-pack/analytics-starter-pack.liuantskillpack",
      "skills": ["csv-summary-skill", "prompt-review-skill"],
      "risk_summary": {"low": 1, "medium": 1, "high": 0, "critical": 0},
      "verified": true
    }
  ]
}
```

## Rules

- Local catalog only — no online marketplace
- Catalog paths must be local
- Catalog install still validates pack/checksums before install
- `verified: true` means the pack passed validation during catalog refresh

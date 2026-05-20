# Skill Pack Dependencies

Skill packs can declare dependencies on other packs. Dependencies are resolved locally — no automatic downloads.

## Dependency Format

In `skill-pack.json`:

```json
{
  "dependencies": [
    {
      "pack_id": "base-analytics-pack",
      "version": ">=0.1.0",
      "required": true
    }
  ]
}
```

### Version Constraints

| Operator | Meaning |
|----------|---------|
| `>=` | Greater than or equal |
| `<=` | Less than or equal |
| `>` | Greater than |
| `<` | Less than |
| `==` | Equal (default) |
| `!=` | Not equal |

## Resolution

Dependencies are checked against:
1. Locally imported packs (`workspace/skills/packs/imported/`)
2. Local catalog (`workspace/skills/catalog.json`)

### Resolution States

- **Resolved** — Dependency found and version matches
- **Missing** — Dependency not found (blocks install if required)
- **Version Conflict** — Dependency found but version doesn't match

## CLI Commands

### Check Dependencies

```bash
./liuant skills pack dependencies ./pack.liuantskillpack
```

### View Install Plan

```bash
./liuant skills pack install-plan ./pack.liuantskillpack
```

Shows which dependencies need to be installed and which are missing.

### Install with Dependencies

```bash
./liuant skills pack install ./pack.liuantskillpack --include-dependencies
```

## Safety Rules

- Dependencies are local-only — no internet downloads
- Missing required dependencies block install
- Version conflicts are reported but don't block install
- Dependencies are not auto-installed without confirmation
- Each dependency is validated before install

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/skills/packs/dependencies` | Resolve dependencies |
| POST | `/api/skills/packs/install-plan` | Get install plan |

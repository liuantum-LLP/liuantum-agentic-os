# Skill Packs

Skill packs allow you to package, export, import, validate, and install collections of skills as local `.liuantskillpack` files.

## Pack Format

A skill pack is a ZIP archive with the `.liuantskillpack` extension containing:

```
skill-pack.json          # Pack manifest
skills/                  # Skill directories
  hello-skill/
    skill.json
    skill.py
    README.md
README.md                # Pack README
CHECKSUMS.json           # SHA256 checksums of all files
```

### skill-pack.json Schema

```json
{
  "schema_version": "1.0",
  "pack_id": "analytics-starter-pack",
  "name": "Analytics Starter Skill Pack",
  "version": "0.1.0",
  "description": "Starter skills for data analytics workflows.",
  "author": "Liuant contributors",
  "license": "MIT",
  "homepage": null,
  "repository": null,
  "tags": ["analytics", "csv", "reports"],
  "skills": [
    {
      "id": "csv-summary-skill",
      "version": "0.1.0",
      "path": "skills/csv-summary-skill"
    }
  ],
  "created_at": "2026-05-19T00:00:00+00:00",
  "liuant_min_version": "2.2.0"
}
```

### Rules

- `pack_id` must be slug-safe (lowercase alphanumeric with hyphens/underscores)
- `version` must be semver-like
- All listed skills must exist inside the pack
- No absolute paths or path traversal
- No secrets in pack metadata
- No executable install scripts
- `CHECKSUMS.json` must include SHA256 for all files except itself

## CLI Commands

### Validate a Pack

```bash
./liuant skills pack validate ./path/to/pack.liuantskillpack
```

Checks archive integrity, manifest schema, skill validation, checksums, and security.

### Inspect a Pack

```bash
./liuant skills pack inspect ./path/to/pack.liuantskillpack
```

Shows pack metadata, included skills, permissions, and risk summary without installing.

### Export a Pack

```bash
./liuant skills pack export \
  --skills hello-skill,csv-summary-skill \
  --pack-id analytics-starter-pack \
  --name "Analytics Starter Skill Pack" \
  --version 0.1.0 \
  --output workspace/outputs/skill-packs/analytics-starter-pack.liuantskillpack
```

Packages installed skills into a `.liuantskillpack` archive. Validates all skills before export. Excludes `__pycache__`, `.env`, `.git`, `node_modules`, and secrets.

### Import a Pack

```bash
./liuant skills pack import ./path/to/pack.liuantskillpack
```

Extracts the pack to `workspace/skills/packs/imported/<pack_id>/`. Does NOT install or enable skills.

### Install a Pack

```bash
./liuant skills pack install ./path/to/pack.liuantskillpack
./liuant skills pack install ./path/to/pack.liuantskillpack --skills hello-skill
```

Imports the pack and installs selected (or all) skills into `workspace/skills/installed/`. Installed skills are **disabled by default**.

### List Imported Packs

```bash
./liuant skills pack list
```

### Remove a Pack

```bash
./liuant skills pack remove analytics-starter-pack --confirm true
```

Removes imported pack metadata. Does NOT uninstall skills that were already installed.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/skills/packs/validate` | Validate a pack |
| POST | `/api/skills/packs/inspect` | Inspect a pack |
| POST | `/api/skills/packs/import` | Import a pack |
| POST | `/api/skills/packs/install` | Install a pack |
| GET | `/api/skills/packs` | List imported packs |
| GET | `/api/skills/packs/{pack_id}` | Get pack status |
| POST | `/api/skills/packs/{pack_id}/remove` | Remove a pack |

## Safety Rules

- Packs are validated before import/install
- Checksums are verified on import
- Secret-like values cause validation failure
- Install scripts are rejected
- Path traversal is blocked
- Installed skills are **disabled by default**
- Critical permissions require explicit approval before enable/run
- No skills run automatically during import/install
- URL imports are staged first — separate confirmation required for import and install (v2.5.0)
- Lint auto-fix suggestions only create safe templates — never modify code or permissions (v2.5.0)

## Official Starter Packs

See `examples/skill-packs/` for official packs:

- `hello-starter-pack` — Minimal greeting skill
- `analytics-starter-pack` — CSV analysis and prompt review skills

## Building Packs

Use the build script:

```bash
python3 examples/skill-packs/build_packs.py
```

Or use the CLI export command to package installed skills.

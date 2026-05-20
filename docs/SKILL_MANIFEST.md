# Skill Manifest

The `skill.json` manifest defines a skill's metadata, requirements, and capabilities.

## Schema Version

Current schema version: `1.0`

## Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `schema_version` | string | Must be "1.0" |
| `id` | string | Slug-safe identifier (lowercase, hyphens, numbers) |
| `name` | string | Human-readable name |
| `version` | string | Semver-like version (e.g., "0.1.0") |
| `description` | string | Brief description of the skill |
| `author` | string | Author name |
| `license` | string | License identifier (e.g., "MIT") |
| `entrypoint` | string | Main Python file (e.g., "skill.py") |
| `runtime` | string | Runtime environment (currently: "python") |
| `category` | string | Skill category (analytics, productivity, development, etc.) |

## Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `permissions` | array | List of permission strings |
| `commands` | array | List of command definitions |
| `triggers` | array | List of trigger definitions |
| `ui` | object | UI configuration |
| `tags` | array | List of tag strings |

## Example

```json
{
  "schema_version": "1.0",
  "id": "hello-skill",
  "name": "Hello Skill",
  "version": "0.1.0",
  "description": "A minimal starter skill.",
  "author": "Liuant contributors",
  "license": "MIT",
  "entrypoint": "skill.py",
  "runtime": "python",
  "category": "utility",
  "permissions": [],
  "commands": [
    {
      "name": "hello",
      "description": "Greet the user",
      "input_schema": {
        "message": {"type": "string", "description": "Name to greet"}
      }
    }
  ],
  "triggers": [
    {"type": "keyword", "pattern": "hello", "description": "Trigger on hello"}
  ],
  "ui": {},
  "tags": ["starter", "greeting"]
}
```

## Validation Rules

- `id` must match pattern: `^[a-z0-9][a-z0-9_-]*[a-z0-9]$`
- `version` must match semver pattern: `^\d+\.\d+\.\d+`
- `runtime` must be in supported runtimes: `{"python"}`
- All permissions must be in the known permissions list
- Manifest must not contain secret-like values (api keys, tokens, passwords)
- Manifest must not contain suspicious absolute paths

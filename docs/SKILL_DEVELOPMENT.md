# Skill Development Guide

How to build a skill for Liuant Agentic OS.

## Directory Structure

```
my-skill/
  skill.json      # Manifest (required)
  skill.py        # Entrypoint (required)
  README.md       # Documentation (recommended)
  tests/          # Tests (recommended)
```

## Step 1: Create the Manifest

Create `skill.json` with required fields:

```json
{
  "schema_version": "1.0",
  "id": "my-skill",
  "name": "My Skill",
  "version": "0.1.0",
  "description": "What this skill does.",
  "author": "Your Name",
  "license": "MIT",
  "entrypoint": "skill.py",
  "runtime": "python",
  "category": "utility",
  "permissions": [],
  "commands": [],
  "triggers": [],
  "ui": {},
  "tags": []
}
```

## Step 2: Create the Entrypoint

Create `skill.py` with an `execute()` or `run()` function:

```python
def execute(ctx, inputs):
    """Execute the skill.

    Args:
        ctx: SkillContext with permissions, workspace info, and safe clients.
        inputs: User-provided inputs dictionary.

    Returns:
        Dictionary with status, result, actions, warnings, approval_required.
    """
    return {
        "status": "completed",
        "result": {"message": "Hello from my skill!"},
        "actions": [],
        "warnings": [],
        "approval_required": False,
    }
```

## Step 3: Use the Context

The `ctx` (SkillContext) provides:

```python
ctx.skill_id          # Skill identifier
ctx.inputs            # User inputs
ctx.permissions       # Declared permissions
ctx.approved_permissions  # Approved permissions
ctx.workspace         # Workspace path
ctx.skill_dir         # Skill directory path

# Check permissions
ctx.has_permission("filesystem.read")
ctx.has_any_permission("filesystem.read", "workspace.read")

# Resolve paths (restricted to workspace/skill dirs)
ctx.resolve_path("data/file.csv")

# Get safe clients
ctx.get_model_client()
ctx.get_usage_client()
```

## Step 4: Validate and Test

```bash
# Validate the skill
./liuant skills validate ./my-skill

# Install locally
./liuant skills install ./my-skill

# Enable
./liuant skills enable my-skill

# Run
./liuant skills run my-skill --input '{"key":"value"}'
```

## Return Shape

```json
{
  "status": "completed | blocked | approval_required | failed",
  "skill_id": "my-skill",
  "result": {},
  "actions": [],
  "warnings": [],
  "approval_required": false
}
```

## Best Practices

- Keep skills focused on a single task
- Declare only the permissions you need
- Handle errors gracefully and return structured output
- Include a README with usage instructions
- Add tests for your skill
- Never include secrets in the manifest or code
- Use `ctx.resolve_path()` for all file access
- Check permissions before accessing resources

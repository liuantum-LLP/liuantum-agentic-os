# Pack Lint Safe Fixes

**Version:** v2.5.0  
**Status:** Implemented

## Overview

Lint auto-fix suggestions provide safe, non-destructive templates to improve pack quality. These fixes only create missing documentation files and add empty metadata fields — they never modify code, permissions, or skill logic.

## What Safe Fixes Do

### Create Missing Files
- `README.md` — template with pack name, description, skills list, and placeholders
- `sample_input.json` — empty input template for each skill
- `expected_output.json` — empty output template for each skill

### Add Missing Metadata
- `changelog` — empty array `[]` in `skill-pack.json`
- `tags` — placeholder `["untagged"]` in `skill-pack.json`

## What Safe Fixes Do NOT Do

- **Never** modify code files (`main.py`, etc.)
- **Never** add or change permissions
- **Never** alter skill logic or behavior
- **Never** delete existing files
- **Never** modify existing metadata (only adds missing fields)

## Usage

### Generate Fix Suggestions (Dry Run)

```python
from runtime.skills import lint_pack

result = lint_pack("path/to/pack", fix_suggestions=True)
# result["fix_suggestions"] contains parsed fix objects
# result["auto_fix_available"] is True if fixes are available
```

### Apply Safe Fixes

```python
from runtime.skills import apply_safe_lint_fixes

# Without confirmation — returns pending status
result = apply_safe_lint_fixes("path/to/pack", confirm=False)
# {"status": "pending", "message": "Apply safe lint fixes? Pass --confirm true to proceed."}

# With confirmation — applies fixes
result = apply_safe_lint_fixes("path/to/pack", confirm=True)
# {"status": "applied", "fixes_applied": ["Created README template", ...]}
```

### CLI

```bash
# Show fix suggestions
liuant skills pack lint path/to/pack --fix-suggestions

# Apply fixes (requires confirmation)
liuant skills pack lint path/to/pack --fix-suggestions --confirm true
```

## Fix Suggestion Format

Each fix suggestion is a JSON object:

```json
{
  "issue": "README.md missing",
  "fix_type": "create_file",
  "path": "README.md",
  "suggested_content": "# Pack Name\n\n..."
}
```

Or for manifest fields:

```json
{
  "issue": "Missing changelog",
  "fix_type": "add_manifest_field",
  "field": "changelog",
  "suggested_value": []
}
```

## Safety Guarantees

1. **Confirmation required** — fixes are never applied without `confirm=True`
2. **Templates only** — only predefined templates are used
3. **No code modification** — `.py` files and skill logic are untouched
4. **No permission changes** — security settings are never altered
5. **Idempotent** — running fixes twice won't duplicate content (checks for existing files/fields first)

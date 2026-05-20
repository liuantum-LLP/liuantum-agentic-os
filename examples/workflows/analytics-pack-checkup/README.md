# Analytics Pack Checkup Workflow

Inspect and lint local analytics skill packs to ensure they meet quality standards.

## Overview

This workflow performs a comprehensive checkup on analytics skill packs, including inspection, linting, and generating a safety checklist. It helps maintain pack quality and ensures compliance with Liuant standards.

## Skills Used

- `pack-inspection-skill`: Inspects pack structure and metadata
- `pack-lint-skill`: Lints pack for quality issues
- `prompt-review-skill`: Generates safety checklist from inspection results

## Installation

This workflow is part of the official Liuant workflow examples. No additional installation required.

## Usage

```bash
liuant skills workflow preview analytics-pack-checkup --input '{"pack_path":"workspace/skills/packs/analytics-starter-pack"}'
liuant skills workflow permissions analytics-pack-checkup
liuant skills workflow run analytics-pack-checkup --input '{"pack_path":"workspace/skills/packs/analytics-starter-pack"}'
```

## Permissions

This workflow requires:
- `filesystem.read` - To read pack files from your workspace

## Input

```json
{
  "pack_path": "workspace/skills/packs/analytics-starter-pack"
}
```

## Output

The workflow produces:
- `inspection`: Complete inspection report of the pack structure and metadata
- `lint_result`: Linting results with quality scores and issues
- `checklist`: Safety checklist generated from inspection results

## Example

```bash
liuant skills workflow run analytics-pack-checkup --input '{"pack_path":"workspace/skills/packs/analytics-starter-pack"}'
```

## Notes

- Ensure the pack path exists and is readable
- This workflow helps maintain pack quality
- Safety checklist ensures pack compliance

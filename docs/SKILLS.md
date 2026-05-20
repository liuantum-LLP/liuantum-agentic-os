# Skills Ecosystem

Liuant Agentic OS v2.0.0 introduces a local-first plugin/skill ecosystem foundation.

## Overview

Skills are self-contained plugins that extend Liuant's capabilities. They are:
- **Local-first**: No marketplace or cloud sync required
- **Manifest-based**: Each skill declares its requirements in `skill.json`
- **Permission-gated**: Skills declare what they need access to
- **Approval-required**: Critical permissions require explicit user approval
- **Disabled by default**: Installed skills must be explicitly enabled

## Quick Start

```bash
# List installed skills
./liuant skills list

# Install a skill from local path
./liuant skills install ./examples/skills/hello-skill

# Enable a skill
./liuant skills enable hello-skill

# Run a skill
./liuant skills run hello-skill --input '{"message":"Liuant"}'

# Disable a skill
./liuant skills disable hello-skill

# Uninstall a skill
./liuant skills uninstall hello-skill --confirm true
```

## Starter Skills

Three official example skills are included:

### 1. hello-skill
- **Category**: Utility
- **Permissions**: None
- **Risk**: Low
- **Description**: Minimal greeting skill demonstrating basic structure

### 2. csv-summary-skill
- **Category**: Analytics
- **Permissions**: filesystem.read, workspace.read
- **Risk**: Medium
- **Description**: Analyzes CSV files and creates summary reports

### 3. prompt-review-skill
- **Category**: Review
- **Permissions**: models.generate
- **Risk**: Medium
- **Description**: Reviews and improves prompts with clarity scoring

## Directory Structure

```
skills/
  installed/          # Installed skill folders
    hello-skill/
      skill.json
      skill.py
      README.md
  enabled/            # Symlinks to enabled skills
  registry.json       # Skill registry metadata
  templates/          # Skill templates
```

## Safety Rules

- Skills are **disabled by default** after installation
- **Critical permissions** require explicit approval before enabling
- Skills **cannot access secrets** by default
- Skills **cannot access filesystem** outside their folder and workspace without permission
- **External actions** (email, social, shell) require approval gating
- **No marketplace** — skills are installed from local paths only
- **No cloud sync** — all skills are local

## See Also

- [SKILL_MANIFEST.md](SKILL_MANIFEST.md) — Manifest format reference
- [SKILL_PERMISSIONS.md](SKILL_PERMISSIONS.md) — Permission model reference
- [SKILL_DEVELOPMENT.md](SKILL_DEVELOPMENT.md) — How to build a skill
- [SKILL_SECURITY.md](SKILL_SECURITY.md) — Security model and rules

# Workflow Permission Review

**Version:** v2.5.0  
**Status:** Implemented

## Overview

Workflow permission review aggregates permissions across all workflow steps and checks their approval state before execution. This ensures users can see exactly what permissions a workflow requires before running it.

## How It Works

1. The `workflow_permission_summary` function scans all steps in a workflow
2. For each step, it collects the skill's declared permissions
3. It checks each permission against the skill's approved permissions
4. It identifies critical permissions that may trigger external actions
5. It returns a summary with approval status for each permission

## Permission Risk Levels

Permissions are classified by risk level:
- **low** — read-only operations (e.g., `filesystem.read`)
- **medium** — write operations (e.g., `filesystem.write`)
- **high** — external service calls (e.g., `email.send`)
- **critical** — irreversible or sensitive actions (e.g., `system.execute`)

## API

### Python

```python
from runtime.skills import workflow_permission_summary

result = workflow_permission_summary("csv-analysis-report")

# Result structure:
# {
#   "workflow_id": "csv-analysis-report",
#   "permissions": [
#     {
#       "permission": "filesystem.read",
#       "required_by": ["csv-skill", "report-skill"],
#       "risk_level": "low",
#       "approved": true
#     }
#   ],
#   "critical_permissions": [],
#   "missing_approvals": [],
#   "can_run": true
# }
```

### CLI

```bash
# Check permissions for a workflow
liuant skills workflow permissions csv-analysis-report
```

### REST API

```
GET /api/workflows/<workflow_id>/permissions
```

## Chat Intents

- "what permissions does this workflow need" → `workflow_permissions`
- "workflow permissions for csv-analysis" → `workflow_permissions`
- "check workflow permissions" → `workflow_permissions`

## Execution Guard

When running a workflow:
1. `preview_workflow_run` checks skill installation and enabled state
2. `workflow_permission_summary` checks permission approvals
3. `run_workflow` requires `user_confirmed=True` for actual execution
4. External actions (critical permissions) require separate approval via the approval system

## Safety Rules

- Workflows **never** run automatically after import
- External actions remain **approval-gated** regardless of workflow context
- Imported skills are **disabled by default**
- Permission approvals are per-skill, not per-workflow

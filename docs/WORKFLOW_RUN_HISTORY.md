# Workflow Run History

**Version:** v2.5.0  
**Status:** Implemented

## Overview

Workflow run history provides a complete record of all workflow executions, including dry runs, successful runs, failures, and approval-required states.

## Data Model

Each run record contains:
- Unique `run_id` (UUID-based)
- Workflow identifier
- Execution status
- Timing information (started, completed, duration)
- Step progress (completed vs total)
- Failure details (which step failed, redacted error)
- Approval and external action counts
- Dry-run flag

## Querying Run History

### List All Runs

```python
from runtime.skills import list_workflow_runs, get_workflow_audit

# All runs (default limit 20)
runs = list_workflow_runs()

# Filter by workflow
runs = list_workflow_runs(workflow_id="csv-analysis-report", limit=50)

# Using audit module directly
runs = get_workflow_audit(workflow_id="csv-analysis-report", limit=20)
```

### Get Specific Run

```python
from runtime.skills import get_workflow_run

run = get_workflow_run("abc123-def456")
```

### Get Latest Run for Workflow

```python
from runtime.skills.workflow_audit import get_latest_workflow_run

latest = get_latest_workflow_run("csv-analysis-report")
```

### Get Steps for a Run

```python
from runtime.skills.workflow_audit import get_workflow_steps

steps = get_workflow_steps("abc123-def456")
```

### Export Run

```python
from runtime.skills import export_workflow_run

# JSON format
json_output = export_workflow_run("abc123-def456", format="json")

# Markdown format
md_output = export_workflow_run("abc123-def456", format="markdown")
```

## CLI Commands

```bash
# List all runs
liuant skills workflow runs

# List runs for specific workflow
liuant skills workflow runs csv-analysis-report

# Get run details
liuant skills workflow run-detail <run_id>

# Export run
liuant skills workflow export-run <run_id> --format json
liuant skills workflow export-run <run_id> --format markdown
```

## Run States

| State | Description |
|-------|-------------|
| `running` | Workflow execution in progress |
| `completed` | All steps executed successfully |
| `failed` | A step failed; check `failed_step_id` |
| `dry_run` | Simulated execution (no skills ran) |
| `blocked` | Execution blocked (e.g., confirmation required) |
| `approval_required` | External action needs user approval |

## Retention

Run history is stored locally in `workspace/skills/workflow_audit/workflow_runs.json`. There is no automatic cleanup — runs persist until manually removed.

## Integration with Failure Recovery

When a run fails, the `failed_step_id` is recorded. This enables the rerun-from-step feature:

```python
from runtime.skills import preview_rerun_from_step

plan = preview_rerun_from_step(run_id, "step2")
# Returns: can_rerun, preceding_steps_completed, remaining_steps, warnings
```

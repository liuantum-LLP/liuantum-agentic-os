# Workflow Audit Logs

**Version:** v2.5.0  
**Status:** Implemented

## Overview

Workflow audit logs record metadata about workflow executions without storing secrets, raw prompts, file contents, API keys, or tokens. All sensitive data is redacted before storage.

## Storage Location

Audit logs are stored in `workspace/skills/workflow_audit/`:
- `workflow_runs.json` — run-level metadata
- `workflow_steps.json` — step-level execution records

## What Is Recorded

### Run-Level Metadata
- `run_id` — unique identifier
- `workflow_id` — workflow identifier
- `workspace` — workspace identifier
- `status` — running, completed, failed, dry_run, blocked, approval_required
- `started_at` / `completed_at` — ISO timestamps
- `duration_ms` — execution duration
- `step_count` / `completed_steps` — step progress
- `failed_step_id` — which step failed (if applicable)
- `approval_required` — whether external actions need approval
- `warnings_count` — number of warnings
- `error_redacted` — error message with secrets removed
- `external_actions_count` — number of external action requests
- `dry_run` — whether this was a dry run
- `user_confirmed` — whether user confirmed execution

### Step-Level Metadata
- `run_id` / `step_id` — identifiers
- `skill_id` / `command` — what was executed
- `status` — completed, failed, approval_required
- `duration_ms` — step duration
- `output_key` — output key for chaining
- `warnings_count` — step warnings
- `error_redacted` — error with secrets removed

## What Is NOT Recorded

The following are **never** stored in audit logs:
- API keys, tokens, or secrets
- Raw prompts or LLM responses
- File contents (inputs or outputs)
- Passwords or credentials
- Personal identifiable information

## Secret Redaction

Secrets are redacted using compiled regex patterns before storage:

```python
SECRET_PATTERNS = [
    r"(?i)(api[_-]?key|apikey)\s*[:=]\s*['\"]?[a-zA-Z0-9]{16,}",
    r"(?i)(secret|token|password|passwd)\s*[:=]\s*['\"]?[^\s'\"]{8,}",
    r"sk-[a-zA-Z0-9]{20,}",
    r"ghp_[a-zA-Z0-9]{36}",
]
```

Matched patterns are replaced with `[REDACTED]`.

## API

### Python

```python
from runtime.skills.workflow_audit import (
    record_workflow_run_start,
    record_workflow_run_complete,
    record_workflow_step,
    get_workflow_audit,
    get_latest_workflow_run,
    get_workflow_steps,
)

# Record run start (returns run_id)
run_id = record_workflow_run_start(
    workflow_id="csv-analysis-report",
    workspace="default",
    dry_run=False,
    user_confirmed=True,
    step_count=3,
)

# Record run completion
record_workflow_run_complete(run_id, "completed", completed_steps=3)

# Record step execution
record_workflow_step(run_id, "step1", "csv-skill", "analyze", "completed", duration_ms=150)

# Query audit logs
runs = get_workflow_audit(workflow_id="csv-analysis-report", limit=20)
latest = get_latest_workflow_run("csv-analysis-report")
steps = get_workflow_steps(run_id)
```

### CLI

```bash
# Show all runs
liuant skills workflow audit

# Show runs for specific workflow
liuant skills workflow audit csv-analysis-report

# Show latest run
liuant skills workflow audit csv-analysis-report --latest
```

### REST API

```
GET /api/workflows/audit                    # All runs
GET /api/workflows/audit?workflow_id=xxx    # Filter by workflow
GET /api/workflows/audit?latest=true        # Latest run
```

## Chat Intents

The chat interface detects these audit-related intents:
- "show workflow runs" → `workflow_audit`
- "workflow audit history" → `workflow_audit`
- "why did the workflow fail" → `workflow_audit`

## Security Guarantees

1. **No secrets stored** — all error messages are redacted before persistence
2. **No file contents** — only metadata about execution is recorded
3. **No raw prompts** — LLM interactions are not logged here
4. **Local-only** — audit logs never leave the workspace directory
5. **No telemetry** — no network calls are made with audit data

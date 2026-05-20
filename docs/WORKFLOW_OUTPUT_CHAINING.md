# Workflow Output Chaining

**Version:** v2.5.0  
**Status:** Implemented

## Overview

Output chaining connects workflow steps by passing the output of one step as input to the next. This enables multi-step pipelines where each step builds on the previous one's results.

## How It Works

Each workflow step can declare:
- `output_key` — a name for this step's output
- `input_from` — a mapping of parameter names to output keys from previous steps
- `defaults` — fallback values when input sources are unavailable

## Resolution Order

Step inputs are resolved in this order:
1. **Direct context match** — if `input_from` source matches a key in the execution context
2. **Nested key resolution** — dot-notation paths like `csv_summary.summary_text`
3. **Defaults** — values from the `defaults` map for parameters not in `input_from`
4. **User inputs** — explicit inputs passed to `run_workflow`

## Dot-Notation Nested Keys

Output chaining supports nested key paths:

```json
{
  "step_id": "step2",
  "skill_id": "report-skill",
  "command": "generate",
  "input_from": {
    "summary": "csv_summary.summary_text",
    "row_count": "csv_summary.row_count"
  },
  "output_key": "final_report"
}
```

The resolver traverses the nested structure:
```python
context = {
    "csv_summary": {
        "summary_text": "Total: 150 rows",
        "row_count": 150
    }
}
# "csv_summary.summary_text" → "Total: 150 rows"
# "csv_summary.row_count" → 150
```

## Example Workflow

```json
{
  "schema_version": "1.0",
  "workflow_id": "csv-analysis-report",
  "name": "CSV Analysis Report",
  "steps": [
    {
      "step_id": "analyze",
      "skill_id": "csv-skill",
      "command": "analyze",
      "input_from": {"file_path": "csv_path"},
      "output_key": "csv_summary"
    },
    {
      "step_id": "report",
      "skill_id": "report-skill",
      "command": "generate",
      "input_from": {
        "summary": "csv_summary.summary_text",
        "rows": "csv_summary.row_count"
      },
      "defaults": {"format": "markdown"},
      "output_key": "final_report"
    }
  ]
}
```

## Error Handling

When an `input_from` source is not found:
- An error is added to the step's error list
- If `continue_on_error` is `false` (default), the workflow fails
- If `continue_on_error` is `true`, the workflow continues with a warning

**Note:** Defaults only apply to parameters **not** listed in `input_from`. If a parameter is in `input_from` but the source is missing, it's an error — the default does not override this.

## API

```python
from runtime.skills import run_workflow

result = run_workflow(
    workflow_id="csv-analysis-report",
    inputs={"csv_path": "data/sample.csv"},
    dry_run=False,
    user_confirmed=True,
)
```

## Dry-Run Preview

In dry-run mode, the execution plan shows how inputs will be chained:

```python
result = run_workflow(workflow_id="csv-analysis-report", dry_run=True)
# result["execution_plan"] shows:
#   step 1: input_from: {file_path: "<missing:csv_path>"}
#   step 2: input_from: {summary: "<nested:csv_summary.summary_text>"}
```

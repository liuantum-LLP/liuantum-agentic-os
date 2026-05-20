# Usage Exports (v1.5.0)

Export your API usage data in CSV, JSON, or Markdown format for analysis and reporting.

## Overview

Usage exports include all recorded usage events with provider, model, role, feature, token counts, estimated costs, and metadata. Exports are saved to `workspace/outputs/usage/`.

## Export Formats

### CSV

Tabular format suitable for spreadsheet analysis.

```bash
./liuant usage export --format csv
```

Columns: timestamp, provider, model, model_role, feature, estimated_input_tokens, estimated_output_tokens, estimated_total_tokens, estimated_cost, estimated, fallback_used, status, discussion_id, is_local

### JSON

Structured format for programmatic processing.

```bash
./liuant usage export --format json
```

### Markdown

Human-readable report with summary statistics.

```bash
./liuant usage export --format markdown
```

## Output Location

All exports are saved to: `workspace/outputs/usage/usage_YYYYMMDD_HHMMSS.{csv,json,md}`

## API Endpoint

```
POST /api/usage/export
Body: {"format": "csv|json|markdown"}
```

## Safety

- Export files contain only usage metadata (provider, model, tokens, cost).
- No API keys, secrets, or prompt content is included in exports.
- Usage data is local only; exports are not sent externally.

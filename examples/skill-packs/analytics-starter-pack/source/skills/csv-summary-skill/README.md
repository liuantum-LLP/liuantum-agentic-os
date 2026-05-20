# CSV Summary Skill

Analyze CSV files and create summary reports.

## Description

Reads a CSV file and generates a summary including row count, column count, column names, and missing value analysis.

## Permissions

- `filesystem.read` - Read CSV files
- `workspace.read` - Access workspace files

## Usage

```bash
./liuant skills install ./examples/skills/csv-summary-skill
./liuant skills approve-permissions csv-summary-skill --permissions filesystem.read,workspace.read --confirm true
./liuant skills enable csv-summary-skill
./liuant skills run csv-summary-skill --input '{"csv_path":"data/sample.csv"}'
```

## Input

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| csv_path | string | Yes | Path to CSV file (must be within workspace or skill directory) |

## Output

```json
{
  "file": "/workspace/data/sample.csv",
  "row_count": 100,
  "column_count": 5,
  "columns": ["name", "email", "age", "city", "notes"],
  "missing_values": {"name": 0, "email": 2, "age": 5, "city": 0, "notes": 45},
  "total_missing": 52
}
```

## Security

- File access restricted to workspace and skill directories
- Cannot read files outside allowed paths
- No write access

## Risk Level

Medium (requires filesystem.read permission)

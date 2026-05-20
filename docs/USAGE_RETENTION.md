# Usage Retention (v1.8.0)

Liuant Agentic OS provides configurable local data retention policies for usage events, alert history, and provider health data, with an automated cleanup scheduler.

## Overview

Retention policies automatically clean up old local usage data to manage database size. All cleanup operations are local-only and require explicit confirmation.

## Retention Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `usage_retention_days` | `90` | Days to keep usage events |
| `alert_retention_days` | `90` | Days to keep alert history |
| `provider_health_retention_days` | `90` | Days to keep provider health data |
| `auto_cleanup_enabled` | `false` | Enable automatic cleanup |

## Safety Rules

- **Never deletes current-day records**: Today's data is always preserved
- **Dry run first**: Shows what would be deleted without deleting
- **Confirmation required**: Actual deletion requires `--confirm true`
- **Local only**: No external data is affected
- **Export recommended**: Export data before cleanup

## CLI Usage

```bash
# View current retention settings
./liuant usage retention

# Set retention days (applies to all tables)
./liuant usage retention-set --days 90

# Dry run: see what would be deleted
./liuant usage cleanup --dry-run

# Confirm and delete old records
./liuant usage cleanup --confirm true
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/usage/retention` | GET | Get retention settings |
| `/api/usage/retention` | POST | Set retention days |
| `/api/usage/cleanup` | GET | Dry run cleanup (default) |
| `/api/usage/cleanup?dry_run=false` | GET | Execute cleanup |
| `/api/usage/cleanup-scheduler/status` | GET | Get scheduler status |
| `/api/usage/cleanup-scheduler/enable` | POST | Enable scheduler |
| `/api/usage/cleanup-scheduler/disable` | POST | Disable scheduler |
| `/api/usage/cleanup-scheduler/run-now` | POST | Run cleanup now |

## Cleanup Scheduler (v1.8.0)

The cleanup scheduler automates retention cleanup on a weekly schedule.

```bash
# Check scheduler status
./liuant usage cleanup-scheduler status

# Enable scheduler (requires confirmation)
./liuant usage cleanup-scheduler enable --confirm true

# Disable scheduler
./liuant usage cleanup-scheduler disable

# Run now (dry run)
./liuant usage cleanup-scheduler run-now --dry-run

# Run now with confirmation
./liuant usage cleanup-scheduler run-now --confirm true
```

## Export-Before-Cleanup (v1.8.0)

```bash
# Show export plan with dry run
./liuant usage cleanup --dry-run --show-export-plan

# Cleanup with export
./liuant usage cleanup --confirm true --export-before-cleanup
```

## Dry Run Output

```json
{
  "usage_records_to_delete": 150,
  "alert_records_to_delete": 45,
  "total_records_to_delete": 195,
  "cutoff_date": "2026-02-18",
  "message": "Run cleanup --confirm true to delete these records."
}
```

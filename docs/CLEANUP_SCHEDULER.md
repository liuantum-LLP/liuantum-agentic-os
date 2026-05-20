# Cleanup Scheduler

Liuant Agentic OS v1.9.0 includes a local cleanup scheduler for managing usage data retention with full UI support.

## Overview

The cleanup scheduler automatically deletes old usage events, alert history, and provider health records based on configurable retention policies. It is **disabled by default** and requires explicit confirmation to enable.

## Configuration

### Default Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `auto_cleanup_enabled` | `false` | Whether automatic cleanup is enabled |
| `cleanup_schedule` | `weekly` | Schedule frequency |
| `cleanup_day` | `Sunday` | Day of week for cleanup |
| `cleanup_time` | `03:00` | Time of day (UTC) for cleanup |
| `export_before_cleanup` | `true` | Export usage data before deletion |
| `allow_cleanup_without_export` | `false` | Allow cleanup if export fails |

### Check Status

```bash
./liuant usage cleanup-scheduler status
```

### Enable Scheduler

```bash
./liuant usage cleanup-scheduler enable --confirm true
```

Requires explicit confirmation. Enables weekly cleanup on Sunday at 03:00 UTC.

### Disable Scheduler

```bash
./liuant usage cleanup-scheduler disable
```

### Run Now

```bash
# Dry run (preview what would be deleted)
./liuant usage cleanup-scheduler run-now --dry-run

# Run with confirmation
./liuant usage cleanup-scheduler run-now --confirm true

# Run without export (if configured)
./liuant usage cleanup-scheduler run-now --confirm true --export-before false
```

## Export-Before-Cleanup

By default, the scheduler exports usage data to JSON before deleting records. The export is saved to:

```
workspace/outputs/usage/usage_YYYYMMDD_HHMMSS.json
```

If the export fails, cleanup will not proceed unless `allow_cleanup_without_export` is set to `true`.

## Safety Rules

- **Disabled by default**: Must be explicitly enabled with confirmation.
- **Never deletes current-day records**: Records from today are always preserved.
- **Confirmation required**: Both enabling and running cleanup require `--confirm true`.
- **Export-first**: Usage data is exported before deletion by default.
- **Local only**: Cleanup only affects local SQLite database records.
- **Irreversible**: Deleted records cannot be recovered unless exported first.

## Dry Run with Export Plan

```bash
./liuant usage cleanup --dry-run --show-export-plan
```

Shows:
- Number of usage events to delete
- Number of alerts to delete
- Oldest and newest record dates affected
- Export path if export-before-cleanup is enabled
- Warning that deletion is irreversible

## Cleanup with Export

```bash
./liuant usage cleanup --confirm true --export-before-cleanup
```

Exports usage data to JSON, then deletes old records past retention period.

## API Endpoints

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/api/usage/cleanup-scheduler/status` | Get scheduler status |
| POST | `/api/usage/cleanup-scheduler/enable` | Enable scheduler (requires confirm=true) |
| POST | `/api/usage/cleanup-scheduler/disable` | Disable scheduler |
| POST | `/api/usage/cleanup-scheduler/run-now` | Run cleanup now (dry_run, confirm, export_before params) |

## Retention Periods

Retention periods are configured separately via `usage retention-set --days <N>`:

- `usage_retention_days`: Usage events (default 90)
- `alert_retention_days`: Alert history (default 90)
- `provider_health_retention_days`: Provider health records (default 90)

## UI (v1.9.0)

The Usage & Costs settings page includes:

### Cleanup Scheduler Card
- Shows: enabled status, schedule, cleanup day/time, last run, next run, export-before-cleanup status
- Buttons: Dry Run, Run Now (danger button), Enable Scheduler, Disable Scheduler
- Disabled by default, enable requires confirmation dialog
- Run Now requires confirmation dialog with warning

### Export-Before-Cleanup Panel
- Appears after dry run
- Shows: usage records to delete, alert records to delete, oldest/newest record dates, export path
- Warning banner: "WARNING: Deletion is local and irreversible unless exported. Current-day records are protected."
- Export path shows where the JSON export will be saved

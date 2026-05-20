# Budgets & Alerts (v1.5.0)

Liuant Agentic OS provides local budget management and alert thresholds for API usage costs.

## Overview

Set daily and monthly cost limits to monitor and optionally block cloud provider usage when thresholds are exceeded. Local providers (Ollama, LM Studio) are never blocked by budget limits.

## Budget Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `daily_estimated_cost_limit` | `0.0` (disabled) | Maximum estimated daily cost in USD |
| `monthly_estimated_cost_limit` | `0.0` (disabled) | Maximum estimated monthly cost in USD |
| `per_provider_limit` | `0.0` (disabled) | Maximum per-provider daily cost |
| `per_role_limit` | `0.0` (disabled) | Maximum per-role daily cost |
| `discussion_mode_cost_warning_threshold` | `0.50` | Cost threshold for discussion mode warning |
| `cloud_model_warning_enabled` | `true` | Show warnings for cloud model usage |
| `budget_blocking_enabled` | `false` | Block cloud calls when budget exceeded |

## Alert Levels

| Level | Threshold | Description |
|-------|-----------|-------------|
| `info` | 70% | Daily/monthly cost at 70% of limit |
| `warning` | 90% | Daily/monthly cost at 90% of limit |
| `critical` | 100% | Daily/monthly cost exceeds limit |

## Behavior

- **Warnings only**: By default, alerts are informational only.
- **Blocking**: When `budget_blocking_enabled=true` and a critical alert is triggered, cloud provider calls may be blocked.
- **Local providers never blocked**: Ollama, LM Studio, and other local providers are exempt from budget blocking.
- **Estimated costs**: All costs are estimates unless exact provider usage metadata is available.

## CLI Usage

```bash
# View current budget
./liuant usage budget

# Set budget limits
./liuant usage budget-set --daily 2.00 --monthly 30.00

# Reset budget to defaults
./liuant usage budget-reset

# Check current alerts
./liuant usage alerts

# Check cost anomalies
./liuant usage anomalies
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/usage/budget` | GET | Get current budget settings |
| `/api/usage/budget` | POST | Set budget values |
| `/api/usage/budget-reset` | POST | Reset budget to defaults |
| `/api/usage/alerts` | GET | Check current budget alerts |
| `/api/usage/anomalies` | GET | Detect cost anomalies |

## Safety

- Budget data is stored locally in SQLite settings.
- Costs are always marked as estimated unless exact provider usage is returned.
- Local providers are never affected by budget limits.
- Budget blocking is disabled by default.

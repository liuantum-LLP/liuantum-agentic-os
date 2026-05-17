# Safe Local Scheduler

Version: v0.2.6

Liuant Agentic OS includes a safe local scheduler for recurring automations. It is tick-based in the MVP: users can run one scheduler pass manually through CLI/API/UI. No production daemon is installed.

## What Works

- Scheduled automation records.
- Manual, interval, daily, weekly, monthly, and config-ready cron-like schedules.
- Next-run calculation.
- Due automation listing.
- `tick` and `run-due`.
- Run history in `automation_runs`.
- Local agent outputs.
- Local markdown reports.
- Draft-only social/email outputs with approval records.
- Safety blocking for shell, delete, auto-send, auto-publish, and key-exposure prompts.

## CLI

```bash
./liuant scheduler status
./liuant scheduler due
./liuant scheduler tick
./liuant scheduler run-due
./liuant scheduler runs
./liuant scheduler run-show <run_id>

./liuant automations create-daily "Daily Plan" --time 09:00 --agent personal-assistant-agent --task "Create my daily plan"
./liuant automations create-weekly "Weekly Content Calendar" --day monday --time 10:00 --agent content-creator-agent --task "Create weekly content calendar"
./liuant automations create-interval "Check leads" --minutes 60 --agent front-desk-management-agent --task "Create enquiry follow-up draft"
./liuant automations history <automation_id>
```

## API

- `GET /api/scheduler/status`
- `GET /api/scheduler/due`
- `POST /api/scheduler/tick`
- `POST /api/scheduler/run-due`
- `GET /api/scheduler/runs`
- `GET /api/scheduler/runs/{run_id}`
- `POST /api/automations/create-daily`
- `POST /api/automations/create-weekly`
- `POST /api/automations/create-interval`
- `GET /api/automations/{automation_id}/history`

## Safety

The scheduler cannot:

- run shell commands,
- delete files,
- send Gmail emails,
- publish social posts,
- auto-send Telegram messages by default,
- perform unapproved external actions.

If an automation task includes unsafe instructions such as "run shell command", "delete files", "send without approval", "publish automatically", or "expose key", the run is marked `approval_required` and a local report is created.

## Roadmap

- v0.2.7 Embeddings/RAG: implemented as local-first memory and knowledge search.
- v0.3 Social OAuth and publishing after approval: LinkedIn/X architecture implemented.
- v0.4 Real video provider integrations.
- Production daemon later, after auth, tenancy, and encrypted secrets.

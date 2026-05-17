# Automations

Liuant automations define repeatable local agent tasks. In v0.2.6 they can be manual or scheduled, but scheduler execution remains local and safe-by-default.

## Automation Fields

Automations include:

- name and description,
- trigger type,
- schedule JSON,
- assigned agent,
- task prompt,
- workspace,
- allowed outputs,
- approval requirement,
- run counters,
- last and next run timestamps.

## Allowed Outputs

Default output:

- `local_report`

Optional draft outputs:

- `social_draft`
- `email_draft`
- `image_package`
- `video_package`

External sends and publishes are not executed in v0.2.6. Draft outputs create approvals.

## Run History

Each run creates an `automation_runs` record with:

- status,
- timestamps,
- report path,
- agent run ID,
- approval IDs,
- errors.

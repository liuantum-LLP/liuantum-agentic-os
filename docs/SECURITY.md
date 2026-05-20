# Liuant Security Notes

## Secret Handling

- API keys are read from environment variables, `.env`, or `.env.local`.
- Raw API keys are not stored in SQLite by the Model Hub.
- CLI/API/UI responses expose only masked key status such as `sk-a...1234`.
- Logs must never include raw provider secrets.
- `liuant security audit-secrets` scans logs and exports for obvious raw key/token patterns.
- `liuant env template` and `liuant env missing` print variable names only, never values.
- `liuant secrets migrate` moves legacy local token fields into the active secret backend and leaves only secret references in SQLite.
- `liuant secrets list` returns metadata only, never raw values.
- `liuant auth token` creates the local API token; the token hash is stored in settings and the token value is stored in the active secret backend.

Production requires OS keychain or encrypted secret storage with deployment-grade access controls.

## Local API Authentication

v0.5.0 enables local API authentication by default.

- Safe status endpoints remain public.
- Sensitive endpoints require `Authorization: Bearer <local_api_token>` or a valid local session.
- UI sessions are single-user local sessions stored as hashes in `sessions`.
- Token rotation revokes active sessions.
- This is not hosted multi-user identity or role-based authorization.

## External Actions

Liuant remains approval-gated in the local MVP:

- Social publishing is disabled by default and requires explicit draft approval plus per-connector manual publish enablement.
- Email sending is disabled.
- Provider tests do not generate media or send messages.
- Text generation only calls a provider when the user explicitly runs `text generate`, Generate Test Text, or agent AI enhancement.
- Image generation only calls a provider when the user explicitly runs generation.
- Replicate Video provider jobs are implemented and hardened. Liuant creates/polls/downloads only when the user explicitly runs video generation or job actions.
- Gmail uses `gmail.readonly` and `gmail.compose` scopes only.
- Gmail draft creation is allowed, but Gmail sending is not implemented.
- Telegram uses Bot API only. Auto-reply is disabled by default and reply drafts require approval.
- Telegram messages cannot trigger shell tools, Gmail actions, social publishing, or workspace file operations.
- Scheduler jobs cannot run shell commands, delete files, send Gmail emails, publish social posts, or auto-send Telegram messages by default.
- RAG is disabled by default. Email, Telegram, and scheduler knowledge search are also disabled by default.

## Provider Status Honesty

Provider states are intentionally explicit:

- `configured`: required configuration is present.
- `missing_key`: expected API key was not found.
- `local_unreachable`: local endpoint is not reachable.

## Discussion Streaming Safety (v1.4.0)

- **No hidden reasoning streamed**: Only user-visible role outputs are streamed via SSE.
- **Secrets redacted**: User messages pass through `redact_secrets()` before model calls. Patterns include passwords, OTPs, API keys, tokens, and Bearer tokens.
- **Errors redacted**: Error messages are truncated to 100 characters and sensitive patterns are redacted.
- **No token/chunk logging**: Tokens are streamed to the client but not logged server-side.
- **Role content restricted**: Discussion role content is limited to concise, visible output only.

## Usage Tracking Safety (v1.4.0)

- **No secrets stored**: Usage events only store provider, model, role, tokens, and cost.
- **Estimated by default**: Costs are marked `estimated=true` unless exact provider usage is returned.
- **Local data only**: Usage data is stored locally in SQLite and can be reset at any time.
- **No external reporting**: Usage data is not sent to external services.
- **Local providers zero cost**: ollama, lmstudio, and other local providers show zero cloud cost.
- `placeholder`: provider is config-ready but real calls are not implemented.
- `ready`: local skill or endpoint is available.
- `provider_error`: provider call failed and no fake output was created.

## Text Generation Logging

- `text_provider_test` logs only provider, category, status, and success.
- `text_generation_started`, `text_generation_completed`, and `text_generation_failed` redact sensitive prompt summaries.
- `agent_ai_enhancement_*` logs provider/model/status metadata only.
- Raw prompts containing password, OTP, credit card, Aadhaar, PAN, secret, API key, or token are marked `sensitive_redacted`.

## Workspace Boundary

Generated packages and media are saved under `workspace/outputs`. Provider integrations must not write outside the workspace.

## Video Provider Safety

- Liuant does not create fake rendered video files.
- Provider output is only claimed when a provider returns a URL or a local file is actually saved.
- Video downloads must use HTTPS.
- Allowed video extensions are `.mp4`, `.webm`, and `.mov`.
- Downloaded files are saved only in `workspace/outputs/videos`.
- Provider tokens are never written to action logs.
- No YouTube upload, social upload, or automatic publishing is implemented.

## Workflow Audit Log Safety (v2.5.0)

- **No secrets stored**: Audit logs record metadata only — run IDs, statuses, durations, step counts.
- **Secret redaction**: Error messages pass through `_redact_secrets()` before storage. Patterns include API keys, tokens, passwords, and secret-like values.
- **No file contents**: Input/output data is never logged. Only output keys and step status are recorded.
- **No raw prompts**: LLM interactions are not stored in audit logs.
- **Local-only**: Audit logs are stored in `workspace/skills/workflow_audit/` and never transmitted.
- **No telemetry**: No network calls are made with audit data.

## Workflow Execution Safety (v2.5.0)

- **Preview before run**: `preview_workflow_run()` checks readiness without executing any skills.
- **Permission review**: `workflow_permission_summary()` shows all required permissions before execution.
- **Confirmation required**: `run_workflow()` requires `user_confirmed=True` for actual execution.
- **Output chaining is safe**: Missing input keys cause step failure (not silent fallback). Defaults only apply to params not in `input_from`.
- **Dry-run is safe**: Dry-run mode never calls `run_skill()`. Shows execution plan with input resolution.
- **Rerun is preview-only**: `preview_rerun_from_step()` returns a plan — actual rerun requires confirmation.

## Recommendation Safety (v2.5.0)

- **Local-only**: Recommendations use only local catalog, installed skills, and workflow data.
- **No network calls**: `recommend_packs()` and `get_recommendations()` never make HTTP requests.
- **No telemetry**: Usage data is not sent to external services for ranking.
- **Factor transparency**: `explain=True` returns factor breakdown so users understand why a pack is recommended.

## Verification And Backups

- Verification checks are safe by default and do not trigger paid media generation unless a live-generate flag is explicitly passed.
- Gmail, Telegram, and social verification checks do not send or publish.
- Default backups create sanitized snapshots under `workspace/backups`.
- `.env`, `.env.local`, raw provider keys, raw OAuth tokens, and bot tokens are excluded or redacted by default.

## Knowledge And RAG Safety

- `local_hash_embedding` is the default embedding provider and does not call an external API.
- File indexing is workspace-only.
- `.env`, `.env.local`, token/key files, OAuth token storage, SQLite/database files, and obvious secret files are rejected by default.
- Sensitive source text is redacted in previews and action logs.
- Private knowledge is not exposed to Telegram, email, or scheduled jobs unless the relevant opt-in setting is enabled.
- Cloud embedding providers can be selected explicitly, but users should only do that for data they are willing to send to that provider.

## Gmail Token Storage

Gmail tokens are stored through the secret backend in v0.5.0. The `oauth_tokens` table stores metadata and secret references. CLI/API/UI responses remove raw token fields and expose only masked token metadata. Production requires OS keychain or managed encrypted secret storage.

## Social OAuth Token Storage

LinkedIn and X tokens are stored through the secret backend in v0.5.0. The `oauth_tokens` table stores metadata and secret references. CLI/API/UI responses remove raw token fields and expose only masked token metadata. Production requires OS keychain or managed encrypted secret storage.

Social safety rules:

- No scraping.
- No password collection.
- No auto-publishing.
- No publishing without an approved draft and approved approval record.
- No publishing unless `manual_publish_enabled=true` for the connector.
- No publishing if OAuth scopes or API tier do not allow it.
- Sensitive content requires explicit confirmation before a publish attempt.
- Bulk publish is blocked above 5 drafts at once.
- Provider/API errors are recorded as failures and never claimed as published.

## Telegram Bot Token Storage

Telegram bot tokens are read from `TELEGRAM_BOT_TOKEN` or stored through the secret backend when explicitly provided. Connector records store secret references and masked metadata only. Production requires OS keychain or managed encrypted secret storage.

## Telegram Message Safety

- Incoming Telegram messages are untrusted input.
- Prompt-injection patterns such as "ignore previous instructions", "run shell command", "send email", and "publish post" are flagged as high risk.
- Sensitive terms such as password, OTP, token, Aadhaar, PAN, bank account, secret, and confidential trigger redacted logs.
- Approval previews show the incoming message preview, draft reply, assigned agent, action type, and warnings.
- Manual sending remains blocked unless `telegram_manual_send_enabled=true` and the draft approval is approved.

## Scheduler Safety

Scheduled automations are local and tick-based. They create reports and drafts only. Unsafe prompts such as "run shell command", "delete files", "send without approval", "publish automatically", and "expose key" are blocked and converted into approval-required local reports.

## Remaining Production Work

- Add production multi-user authentication and authorization.
- Enforce production-grade managed secret storage for hosted deployments.
- Add per-user tenancy before hosted deployment.
- Add stronger audit-log retention and tamper protection.

## Desktop Release Safety

v0.5.6 keeps desktop packaging and signing-readiness checks with conservative defaults:

- Desktop builds are not marked signed unless real signing is configured.
- macOS notarization remains false unless a real notarization pipeline runs.
- Package scripts do not overwrite `.env`.
- Update checks are local metadata only; automatic downloads and installs are disabled by default.
- Release manifests and checksums must not contain raw provider keys, OAuth tokens, or local API tokens.
- Desktop backend mode defaults to `external_backend`.
- `managed_backend` uses the same local server helper and refuses non-localhost binding.
- `bundled_sidecar` remains pending and is not represented as a working packaged executable.

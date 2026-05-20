# Changelog

## [v3.1.0] - 2026-05-20
### Added
- Browser & Desktop Automation layer with approval gating.
- Voice wake assistant foundation (simulation-first).
- Comprehensive multi-provider API support (Bedrock, OpenRouter, Gemini, Ollama, LM Studio, etc.).
- Robust documentation overhaul focusing on local-first safety and known limitations.

## v2.6.0

- **Official workflow examples**: 4 new workflows — csv-analysis-report, prompt-improvement-review, starter-greeting-workflow, analytics-pack-checkup. All include workflow.json, README.md, sample_input.json, expected_output.json.
- **Workflow discovery**: `list_workflows()` includes examples/workflows/ directory. `discover_workflows()` finds workflows from specified paths or defaults.
- **Workflow registry**: `_get_workflow_by_id()` checks examples/workflows/ in addition to registry and skill-packs. `validate_workflow()` accepts workflow_id parameter.
- **CLI commands**: `liuant skills workflow discover [--paths path1,path2]`, `liuant skills workflow validate --workflow-id <id>`.
- **API endpoints**: `GET /api/skills/workflows`, `POST /api/skills/workflows/discover`, `POST /api/skills/workflows/validate` (workflow_id support).
- **Desktop workflow UI**: Workflow Templates section with cards showing name, ID, description, source, required skills, permissions, risk level, status, latest run.
- **Workflow preview panel**: Shows status, steps, skill installed/enabled state, permissions required, input source, output key, warnings, blocked reason. No execution.
- **Workflow permission review panel**: Shows permission, required by skills, risk level, approved, missing approval. Approve button requires confirmation.
- **Dry-run and run confirmation**: Dry-run shows execution plan without executing skills. Run requires confirmation dialog with workflow ID, permissions, external actions status.
- **Workflow audit and run history**: Shows latest runs, workflow ID, run ID, status, duration, step count, completed steps, failed step, warnings, timestamp. No secrets shown.
- **URL staging confirmation flow**: URL input, preview URL, staged_id, validation result, pack metadata, trust status, risk summary, dependencies, import staged, install staged.
- **Lint fix suggestions UI**: Shows lint score, grade, issues, recommendations, safe fix suggestions. Apply safe fixes requires confirmation.
- **Recommendation ranking UI**: Shows recommended pack/skill, score, reason, factor breakdown, source, installed status, risk summary, trust state.
- **Chat-first workflow bridge**: Workflow preview, permissions, audit, dry-run, rerun plan intents. No auto-run from chat.
- **Safety**: No marketplace server, no cloud sync, no auto-install, no auto-enable, no auto-run. External actions remain approval-gated.
- **789 tests pass**, TypeScript clean, frontend builds clean.
- **Version 2.6.0** across all files.

## v2.5.0

- **Workflow run preview**: Step-by-step readiness check without executing any skills. Reports missing skills, disabled skills, and permission status.
- **Workflow permission summary**: Aggregates permissions across all workflow steps, checks approval state, identifies critical permissions.
- **Output chaining**: Dot-notation nested mapping between workflow steps (`csv_summary.summary_text`). Defaults for parameters not in `input_from`.
- **Workflow audit logs**: Metadata-only run/step history with secret redaction. Never stores secrets, raw prompts, file contents, or tokens.
- **Run history**: List, get, and export workflow runs as JSON or markdown. Filter by workflow ID.
- **Dry-run improvements**: Execution plan shows input dependencies and chaining resolution (`<from:key>`, `<nested:key>`, `<missing:key>`).
- **Failure recovery**: Failed step records `recovery_suggestion`. `preview_rerun_from_step` returns safe preview of what would happen.
- **Lint auto-fix suggestions**: Safe templates only — creates missing `README.md`, `sample_input.json`, `expected_output.json`, empty `changelog`/`tags`. Never modifies code or permissions.
- **Staged URL import**: `preview_url_import` returns `staged_id` for separate import and install confirmation steps. HTTPS-only, 25 MB limit.
- **Recommendation ranking**: Factor breakdown (`query_match`, `skill_gap_fill`, `workflow_match`, `low_risk_bonus`, `starter_priority`, `verified_bonus`). No telemetry.
- **Chat-first workflow intents**: 6 new intent patterns — workflow preview, permissions, audit, dry-run, rerun plan, run.
- **789 tests pass**, TypeScript clean, frontend builds clean.
- **Version 2.5.0** across all files.

## v2.0.0

- **Plugin/Skill Ecosystem Foundation**: Local-first skill system with manifest-based validation, permission gating, and approval-required execution.
- **Skill Manifest Format**: `skill.json` with required fields (id, name, version, description, author, license, entrypoint, runtime, category), permissions, commands, triggers, UI config, tags.
- **Permission Model**: 13 permission types across 4 risk levels (low, medium, high, critical). Critical permissions (secrets.read, tools.shell, network.http, tools.email_draft, tools.social_draft) require explicit approval.
- **Skill Registry**: Install, uninstall, enable, disable, validate, list skills. Installed skills disabled by default. Duplicate ID rejection unless --upgrade.
- **Skill Validator**: Validates manifest fields, slug-safe IDs, semver versions, known permissions, entrypoint existence, README presence, no secret-like values, no suspicious install scripts.
- **Skill Execution Sandbox**: Restricted context with permission checking, path resolution limited to workspace/skill directories, no direct secret access, approval-gated external actions.
- **Starter Skills**: hello-skill (no permissions), csv-summary-skill (filesystem.read, workspace.read), prompt-review-skill (models.generate).
- **CLI Expanded**: `skills list|installed|validate|install|enable|disable|uninstall|status|permissions|approve-permissions|run|templates`.
- **API Expanded**: `/api/skills`, `/api/skills/{id}`, `/api/skills/validate`, `/api/skills/install`, `/api/skills/{id}/enable|disable|uninstall|permissions|approve-permissions|run`, `/api/skills/templates`.
- **Settings UI — Skills Section**: Installed skills list with risk badges, validation status, enable/disable/run/uninstall buttons, install path input, CLI commands reference.
- **Safety**: Skills disabled by default, critical permissions require approval, no secret access by default, filesystem restricted to workspace/skill dirs, no external actions without approval.
- **654 tests passing**, TypeScript clean, frontend builds clean.
- **Version 2.0.0** across all files.

## v1.9.0

- **Usage dashboard UI — Webhook Delivery History**: Table showing event type, workspace, status, status code, retry count, URL hash, payload hash, test mode, delivered at. Buttons for send test, retry failed, refresh. Never shows full URL or payload body.
- **Usage dashboard UI — HMAC Status**: Card showing HMAC enabled status, secret configured status, signature/timestamp header names. Buttons for signature test, rotate secret. Secret never displayed.
- **Usage dashboard UI — Cleanup Scheduler**: Card showing enabled status, schedule, cleanup day/time, last run, next run, export-before-cleanup. Buttons for dry run, run now, enable, disable. Disabled by default, confirmation required for destructive actions.
- **Usage dashboard UI — Export-Before-Cleanup Panel**: Shows records to delete, oldest/newest dates, export path, irreversible deletion warning. Visually dangerous confirm button. Current-day records protected.
- **Usage dashboard UI — Per-Round Discussion Cost Breakdown**: Shows latest discussion ID, total cost, total tokens, per-round breakdown with phase (initial/review/final), role-level costs, provider/model, fallback warnings.
- **Local webhook test server**: Integration tests use local mock HTTP server to test real HTTP delivery, HMAC verification, retry logic (429/500 retry, 400 no retry), delivery history hash storage.
- **HTTP localhost exception for tests**: `http://127.0.0.1` and `http://localhost` URLs allowed in test mode only. Never allowed in production. Controlled by `LIUANT_WEBHOOK_TEST_ALLOW_HTTP_LOCALHOST` env flag.
- **Cleanup scheduler foundation**: `check_and_run_due_cleanup()` architecture ready, next-run calculation, disabled-by-default enforcement, manual run-now only.
- **API expanded**: `/api/usage/webhook/signature-test`, `/api/usage/webhook/rotate-secret`.
- **632 tests passing**, TypeScript clean, frontend builds clean.
- **Version 1.9.0** across all files.

## v1.8.0

- **Real HTTP webhook delivery**: POST JSON payload with configurable timeout, retry with exponential backoff (max retries configurable, retry only for timeout/429/5xx, no retry for 4xx except 429).
- **HMAC signature verification**: HMAC-SHA256(secret, timestamp + "." + raw_json_body) with X-Liuant-Signature and X-Liuant-Timestamp headers. Secret never logged or exposed.
- **Webhook delivery log**: `webhook_deliveries` table stores url_hash and payload_hash only, never full URL or payload. Records status, status_code, retry_count, redacted_error, timestamps.
- **Per-round discussion cost breakdown**: `discussion_cost_rounds` table tracks discussion_id, round_number, phase (initial/review/final), role, provider, model, tokens, cost, fallback_used.
- **Cleanup scheduler**: Local scheduler disabled by default, weekly schedule (Sunday 03:00 UTC), export-before-cleanup enabled by default, confirmation required to enable, never deletes current-day records.
- **Export-before-cleanup warnings**: Dry-run shows records to delete, oldest/newest dates, export path, irreversible deletion warning.
- **CLI expanded**: `usage webhook send-test`, `delivery-history`, `retry-failed --confirm true`, `set-secret --confirm true`, `rotate-secret --confirm true`, `signature-test`. `usage discussion-costs --latest --rounds`, `--discussion-id <id>`. `usage cleanup-scheduler status|enable|disable|run-now`. `usage cleanup --dry-run --show-export-plan`, `--export-before-cleanup`.
- **API expanded**: `/api/usage/webhook/send-test`, `/delivery-history`, `/retry-failed`. `/api/usage/discussion-costs/{discussion_id}`. `/api/usage/cleanup-scheduler/status|enable|disable|run-now`.
- **Safety**: Webhooks disabled by default, HTTPS required, HMAC secret never printed, delivery log stores hashes only, cleanup requires confirmation, scheduler disabled by default, export-before-cleanup works, external actions approval-gated.
- **637 tests passing**, TypeScript clean, frontend builds clean.
- **Version 1.8.0** across all files.

## v1.7.0

- **Webhook alert delivery**: Approval-gated, disabled by default, test mode only. HTTPS URL validation, safe payloads with no secrets/prompts/raw errors.
- **Provider latency percentiles**: p50, p95, p99 latency tracking with fastest/slowest call metrics.
- **Discussion cost-per-role breakdown**: Track cost/tokens per role, provider, model during Discussion Mode.
- **Usage retention policies**: Configurable retention days (default 90), dry-run cleanup, confirmation-required deletion, never deletes current-day records.
- **CLI expanded**: `usage webhook status|set-url|test|enable|disable`, `usage discussion-costs [--latest]`, `usage retention`, `usage retention-set --days 90`, `usage cleanup [--dry-run] [--confirm true]`.
- **API expanded**: `/api/usage/webhook/*`, `/api/usage/discussion-costs`, `/api/usage/discussion-costs/latest`, `/api/usage/retention`, `/api/usage/cleanup`.
- **Safety**: Webhooks disabled by default, require confirmation, test mode enforced, payloads redacted, cleanup requires confirmation, retention preserves today's records.
- **620 tests passing**, TypeScript clean, frontend builds clean.
- **Version 1.7.0** across all files.

## v1.6.0

- **Auto-tracked provider health**: Every provider call now automatically records success/error/timeout/rate-limit status.
- **Provider latency tracking**: Tracks latency_ms per call, rolling average, slow call count, p95 estimate.
- **Per-workspace usage tracking**: Usage events now include workspace_name; summary/export/trends support workspace filtering.
- **Usage history and trends**: Daily trends (7/30 days), monthly trends, provider/role trends.
- **Real-time cost updates during discussion streaming**: Cumulative usage updates emitted during streaming, final usage recorded after completion.
- **Budget alert history**: Alerts stored with timestamp, level, message, workspace; dismissible via API/CLI.
- **Webhook alerts preparation**: Architecture ready for future webhook alerts (disabled by default, approval-gated).
- **CLI expanded**: `usage summary --workspace current`, `usage trends --days 7|30`, `usage trends --monthly`, `usage alerts --history`, `usage export --workspace current`.
- **API expanded**: Workspace query params on usage endpoints, `/api/usage/trends`, `/api/usage/alerts/history`, `/api/usage/alerts/{id}/dismiss`.
- **Safety**: Provider errors redacted, no prompts stored, no API keys logged, local providers exempt from budget blocking.
- **600 tests passing**, TypeScript clean, frontend builds clean.
- **Version 1.6.0** across all files.

## v1.5.0

- **Usage budgeting**: Daily/monthly cost limits with 70%/90%/100% alert thresholds.
- **Budget blocking**: Optional cloud provider call blocking when budget exceeded (disabled by default).
- **Local provider exemption**: Ollama/LM Studio never blocked by cloud budget limits.
- **Usage export**: CSV, JSON, and Markdown export to workspace/outputs/usage/.
- **Cost anomaly detection**: Detects cost spikes, discussion call surges, fallback cloud usage, repeated errors, high token usage.
- **Provider health tracking**: Track last success, last error, error/timeout/rate-limit counts, degraded status.
- **Provider health API**: GET/POST endpoints for health status, error recording, rate limit tracking.
- **Settings UI updated**: Usage & Costs section with budget cards, alert display, usage summary grid, export buttons.
- **CLI expanded**: `usage budget`, `budget-set`, `budget-reset`, `alerts`, `export`, `anomalies`, `models provider-health`.
- **Safety**: No secrets in exports, errors redacted, costs always estimated unless exact usage returned.
- **580 tests passing**, TypeScript clean, frontend builds clean.
- **Version 1.5.0** across all files.

## v1.4.0

- **Discussion Mode streaming**: `stream_discussion()` engine yields structured SSE events for real-time discussion display.
- **API endpoint**: `POST /api/chat/discussion-stream` returns `text/event-stream` with role cards, progressive tokens, and usage updates.
- **Usage & cost tracking**: `UsageTracker` with configurable pricing table for cost estimation across all providers.
- **Usage APIs**: `/api/usage/summary`, `/today`, `/by-provider`, `/by-role`, `/reset` endpoints added.
- **CLI commands**: `./liuant usage summary|today|by-provider|by-role|reset --confirm true` added.
- **CLI discussion streaming**: `./liuant chat --discussion --stream "message"` for streaming discussion mode.
- **Chat UI updated**: Role cards showing provider/model/status per contribution, usage/cost panel, stop button, "Models discussing (streaming)..." loading state.
- **Safety**: No hidden reasoning streamed, secrets redacted, errors redacted, no token logging.
- **Local providers**: ollama, lmstudio show zero cloud cost.
- **Cost estimation**: Marked `estimated=true` unless exact provider usage returned.
- **Database schema**: `usage_events` table added for local usage tracking.
- **562 tests passing**, TypeScript clean, frontend builds clean.
- **Version 1.4.0** across all files.

## v1.0.2

- **Python package discovery fixed**: Explicit `[tool.setuptools.packages.find]` with `runtime*`, `cli*`, `sidecar*` — no more flat-layout pip install errors.
- **One-click startup**: `./liuant desktop one-click-check` and `./liuant desktop launch-check` commands added. Desktop app auto-polls backend with loading screen.
- **CI ready**: GitHub Actions runs without Apple credentials, provider keys, Rust/Tauri builds, signing, or notarization.
- **Public install docs**: README and INSTALLATION.md document `pip install -e .`, one-click startup, and optional sidecar build.
- **Gitignore audit**: Verified zero generated/tracked workspace, sidecar build, desktop build, or egg-info files.
- **Six pre-existing test failures fixed**: version alignment, Rich rendering format assertions.
- **531 tests passing**, TypeScript clean, frontend builds clean.
- **Version 1.0.2** across all files.

## v1.0.0

- **v1.0.0 stable local desktop release**.
- **Security contact fixed**: SECURITY.md now uses `admin@liuantum.com` instead of placeholder `security@example.com`.
- **Version bumped**: All files updated to 1.0.0, release channel: `stable-open-source`.
- **Community DMG rebuilt**: `Liuant Agentic OS_1.0.0_aarch64.dmg` (3.7 MB, unsigned, notarized=false).
- **Sidecar rebuilt**: PyInstaller binary rebuilt at `sidecar/liuant-backend` (9.7 MB).
- **All 15/15 candidate checks pass**: version aligned, open-source files, env security, sidecar honest, signing honest, frontend built, security contact verified.
- **466 tests passing**, TypeScript clean, frontend builds.

## v0.9.1

- **Sidecar build trial**: Built and tested with PyInstaller (~9.7 MB, ~60s build). Verified `run`, `check`, `stop`, PID tracking, localhost-only binding, local auth.
- **Sidecar run fix**: Fixed `sidecar run` to use `serve` command instead of `start` — now works reliably with PyInstaller executable.
- **bundled_sidecar mode fully working**: Verified `backend-start`/`backend-stop` with bundled_sidecar mode. Fixed `backend-status` to report sidecar process as running.
- **v1.0 Release Candidate checklist**: New `docs/V1_RELEASE_CANDIDATE.md` with comprehensive checklist. New `./liuant release candidate-check` command for automated assessment.
- **466 tests passing** (11 new: sidecar build mock, status, check, candidate-check, version alignment, mode switching).
- **Version updated**: 0.9.1 across all versioned files.

## v0.9.0

- **Bundled sidecar backend**: New `runtime/sidecar.py` module with CLI commands (`sidecar status`, `sidecar build`, `sidecar check`, `sidecar run`, `sidecar stop`). Sidecar is a standalone executable built from source via PyInstaller or Nuitka. Binds only to 127.0.0.1. Preserves local auth.
- **Three backend modes fully supported**: `external_backend` (default, manual), `managed_backend` (CLI-managed), `bundled_sidecar` (config-ready executable).
- **Sidecar CLI**: `./liuant sidecar status`, `./liuant sidecar build --confirm`, `./liuant sidecar check`, `./liuant sidecar run`, `./liuant sidecar stop --confirm`.
- **Desktop UI updated**: BackendSettings shows sidecar availability status, sidecar commands, and mode descriptions. Settings page shows `0.9.0`.
- **Documentation updated**: SIDECAR_BACKEND.md, DESKTOP_PACKAGING.md, INSTALLATION.md, OPEN_SOURCE.md all reframed for v0.9.0 sidecar support.
- **Version updated**: 0.9.0 across config, release.json, package.json, tauri.conf.json, pyproject.toml.
- **15 new sidecar tests**: Status unavailable, build requires confirm, no packaging tool, run refuses non-localhost, run without executable, check without executable, stop requires confirm, stop without running, bundled_sidecar mode check, external/managed modes preserved, UI mentions sidecar, docs explain build, no secrets in sidecar status, CLI commands registered.
- **455 tests passing** (440 existing + 15 new), TypeScript clean, frontend builds in ~274ms.

## v0.8.0-open-source

- **Open-source release**: MIT License, CONTRIBUTING.md, CODE_OF_CONDUCT.md, SECURITY.md, GOVERNANCE.md, ROADMAP.md, SUPPORT.md.
- **GitHub community files**: Issue templates (bug, feature, security, docs), PR template, CI workflow.
- **CI without Apple credentials**: `pytest -q`, TypeScript check, frontend build — no secrets required.
- **`.gitignore`** added: ignores `.env`, database files, workspace secrets, build artifacts.
- **`.env.example`** added: variable names only, no real secrets, with warning.
- **Public README rewrite**: Open-source friendly with quick start, features, safety principles, license, and contributing guide.
- **Documentation updated**: All signing docs now clearly state signing is optional for maintainers only. RELEASE.md, DESKTOP_PACKAGING.md, TROUBLESHOOTING.md reframed for community builds.
- **Community build model**: Unsigned by default. No Apple Developer ID required. Right-click Open documented for macOS.
- **Version updated**: 0.8.0 across config, release.json, package.json, tauri.conf.json. Channel changed to `open-source`.
- **Open-source documentation**: `docs/OPEN_SOURCE.md` explains project philosophy, goals, and local-first values.
- **Secret/privacy audit**: No API keys, tokens, or private credentials in tracked files.
- **8 new open-source tests**: License, contributing, code of conduct, security, roadmap, .env.example, .gitignore, README mentions open-source, approval-gated mentioned, CI no-Apple, signing docs say optional, release doc community builds, no real secrets.
- **435 tests passing** (427 existing + 8 new), TypeScript clean, frontend build.

## v0.7.2

- **Brand icon polish**: SVG and PNG icon generator updated with premium neural orbit mark design — luminous core, orbiting agent nodes, radial data rings. Improved gradient palette, SVG animations, and small-icon rounded-square mask. All 16 icon files regenerated.
- **Desktop visual polish**: Sidebar version fixed from v0.6.4 to v0.7.1. Offline banner redesigned with brand icon, refined spacing, Retry/Login buttons. Settings page version fixed, signing blocked section now shows Developer ID guidance with env var, command, and doc link. CSS refinements throughout.
- **Signing blocked experience**: `signing_status()` and `signing_macos_status()` messages now clearly state "Signing blocked — Apple Developer ID Application certificate not configured" and include the identity check command and docs reference.
- **Release polish-check**: Added `./liuant release polish-check` (alias for `desktop polish-check`). Verifies version alignment, DMG exists, checksum valid, icons complete, signing honest, docs exist.
- **Improved styling for signing blocked UI**: New `.signing-blocked` box, `.blocked-env`, `.blocked-cmd`, `.signing-doc-link` CSS classes for the Settings page.
- **8 new tests**: Icon generation offline, icons-check passes, release polish-check shape, signing blocked Developer ID guidance, macOS status blocked message, desktop report signed=false, macOS QA still passes, signing status references docs.
- **427 tests passing** (419 existing + 8 new), TypeScript clean, frontend build in 269ms.

## v0.7.1

- **Signing preflight improved**: Now checks DMG checksum match against stored checksum, verifies app version alignment, detects Developer ID Application certificate identity type, and reports missing checks with specific names.
- **Signing manifest integration**: `signing_macos_sign()` updates `release/manifest.json` signing block, artifact `signed` flags, and regenerates `release/checksums.json` after successful signing.
- **Version alignment**: All version references updated from 0.6.4 to 0.7.1 across `runtime/config.py`, `release.json`, `apps/desktop/package.json`, `apps/desktop/src-tauri/tauri.conf.json`, `installer/package_macos.sh`, docs, and README.
- **8 new signing tests**: Preflight not_ready, secret masking, confirm requirement, failure keeps signed=false, mocked success sets signed=true, codesign_verified=true, notarized remains false, checksums regenerated, backward compatibility with existing tests.
- **DMG rebuilt from v0.6.0 to v0.7.1**: Native Tauri build recreated the DMG at current version (`Liuant Agentic OS_0.7.1_aarch64.dmg`, 3.8 MB, SHA256 `6029a7be...`). Preflight `version_matches` now passes.
- **Current-version artifact detection**: `release_artifacts()` returns `current_version_artifact` and `stale_native_artifacts`. Preflight checks `current_version_artifact_exists` and `stale_artifact_count`.
- **5 new stale-artifact tests**: Stale version detection, old artifact not deleted, preflight prefers current-version artifact, version_matches passes with current artifact, preflight reports current_version_artifact_missing.
- **Documentation updates**: IMPLEMENTATION_STATUS.md, MACOS_SIGNING_NOTARIZATION.md, SIGNING.md, RELEASE.md, UNSIGNED_BUILDS.md, CHANGELOG.md, README.md updated for DMG rebuild and current-version artifact detection.
- **419 tests passing** (414 existing + 5 new stale-artifact tests), TypeScript clean, frontend build in 256ms.

## v0.7.0

- **macOS code-signing and notarization pipeline**: Complete local pipeline wrapping Apple's `codesign`, `notarytool`, and `stapler` tools. No cloud service required.
- **Signing readiness detection**: `signing_status()` now checks `APPLE_DEVELOPER_ID_APPLICATION`, `APPLE_ID`, `APPLE_TEAM_ID`, `APPLE_APP_SPECIFIC_PASSWORD`, `APPLE_KEYCHAIN_PROFILE`, `TAURI_SIGNING_PRIVATE_KEY`, and `security find-identity` for available certificates. No secret values printed.
- **6 new CLI signing commands**: `macos-status` (readiness check), `macos-guide` (setup guide), `macos-export-env-template` (env variable names), `macos-preflight` (artifact checks), `macos-sign` (codesign wrapper), `macos-notarize` (notarytool wrapper). All support `--dry-run` and `--confirm` flags.
- **Preflight checks**: `macos-preflight` verifies artifact existence, env credentials, certificate identity, notarytool/stapler availability, and bundle ID. Returns `ready`/`not_ready`.
- **Code signing**: `macos-sign` signs with `codesign --deep --force --verify --timestamp --options=runtime`, then verifies with `codesign --verify` and `spctl --assess`. Never claims `signed=true` unless verification passes.
- **Notarization**: `macos-notarize` submits via `xcrun notarytool submit --wait`, staples via `xcrun stapler staple`, validates via `xcrun stapler validate`. Never claims `notarized=true` unless all steps succeed.
- **Release manifest signing block**: Added `signed`, `notarized`, `codesign_verified`, `spctl_accepted`, `notarization_status`, `stapled`, `signed_at`, `notarized_at` — all default to `false`/`null`.
- **Release desktop report signing block**: Includes `signing_readiness` with `codesign_ready`, `notarize_ready`, and credential statuses.
- **6 API endpoints for signing**: `/api/signing/macos-status`, `/api/signing/macos-guide`, `/api/signing/macos-export-env-template`, `/api/signing/macos-preflight`, `/api/signing/macos-sign` (POST), `/api/signing/macos-notarize` (POST).
- **`installer/package_macos.sh` updated**: Added `--sign`, `--notarize`, `--dry-run-signing` flags. Default remains unsigned (`DO_SIGN=false`, `DO_NOTARIZE=false`).
- **Secret redaction helper**: `_redact_secrets()` regex-based redaction of Apple IDs, passwords, and Tauri keys from error output.
- **Settings UI updated**: Release & Updates section displays Codesign Ready / Notarize Ready statuses, signing commands, and credential guidance.
- **17 signing pipeline tests**: Environment detection, secret masking, export template, preflight, dry-run, confirm requirement, manifest shape, unsigned-build-check preservation.
- **409 tests passing** (384 existing + 17 signing + 8 regression), TypeScript clean, frontend build in 256ms.

## v0.6.4
## v0.6.4

- **ChatIntentRouter test suite**: 384 tests covering all 11 intents, confidence scoring, required fields, preview generation, field extraction, execute_intent_action, unknown fallback, response structure invariants, and 15 chat safety tests.
- **Chat safety tests**: Verify secrets masked in responses, prompt injection blocked, external actions (send email, publish social) remain unexecuted, all regex patterns balanced, required_fields marked as secret appropriately.
- **First-user onboarding wizard**: 6-step guided setup (Welcome → Backend Mode → Connect Provider → Create Agent → Create Automation → Connect Services). Skip button available at every step. State persisted via localStorage.
- **Settings helper text**: Each Settings section now shows a brief description explaining its purpose.
- **Settings empty states**: Enhanced empty state messages across all sections with Chat guidance.
- **Knowledge search handler fix**: Fixed TypeError when `KnowledgeBase.search()` returns dict with `results` key (was iterating over dict directly).
- **384 tests passing**, TypeScript clean, frontend build in 256ms.

## v0.6.3

- **Minimal UI redesign**: 6-item navigation (Chat, Dashboard, Agents, Automations, Knowledge, Settings) replaces the previous complex sidebar hierarchy.
- **Chat-first control system**: Chat page is the primary interface for configuring Liuant through natural language.
- **Chat intent routing**: Deterministic ChatIntentRouter with 11 intent categories (provider_setup, connector_setup, agent_create, automation_create, skill_install, memory_add, knowledge_search, system_status, approval_action, release_status, unknown).
- **Chat-guided provider setup**: Set up AI providers through chat with secure credential collection stored in SecretStore.
- **Chat-guided connector setup**: Configure Gmail, Telegram, LinkedIn, and X connectors through chat.
- **Chat-guided agent creation**: Create agents through natural language with preview and confirmation.
- **Chat-guided automation creation**: Create recurring automations through chat with schedule selection.
- **Settings as configuration center**: 10 organized sections (General, Models & Providers, Connectors, Agents, Automations, Skills, Memory & Knowledge, Security, Desktop & Backend, Release & Updates).
- **Dashboard page**: System overview with live status cards for version, backend mode, agents, approvals, automations, providers, and connectors.
- **Knowledge page**: Unified view of knowledge sources and memory entries.
- **Agents page**: Clean list view with enabled/disabled status.
- **Automations page**: Clean list view with next-run information.
- **Secret/token handling**: All secrets collected through chat stored in encrypted SecretStore; never displayed after input; redacted in logs.
- **Confirmation/preview gating**: All chat actions that create or change resources require preview and explicit confirmation before execution.
- **No cloud AI dependency**: Deterministic pattern matching in ChatIntentRouter; AI text provider is optional enhancement only.
- **Preserved all existing CLI commands, API endpoints, backend features, and workflows.**
- **10 Settings API endpoints**: `/api/settings`, `/api/settings/*` for all configuration sections.
- **3 Chat API endpoints**: `/api/chat/message`, `/api/chat/action`, `/api/chat/intents`.
- **TypeScript fixes**: AgentsPage, AutomationsPage, ChatPage type safety resolved (unknown → ReactNode, optional chaining).
- **Test updates**: 8 test assertions updated for new App.tsx UI text and Settings page relocation.
- **289 tests passing**, TypeScript clean, frontend build in 250ms.
- External actions remain approval-gated. No email sending, Telegram auto-send, or social auto-publishing was added.

## v0.6.2

- Backend mode hardening: external_backend (default), managed_backend (working), bundled_sidecar (documented).
- Managed backend improvements: PID tracking, duplicate prevention, safe start/stop/restart.
- Added `./liuant desktop backend-restart` command.
- Desktop UI shows backend mode and mode-specific instructions.
- Bundled sidecar properly reports `sidecar_not_available` with helpful guidance.
- First-run check includes mode-specific setup instructions for each backend mode.
- Sidecar backend strategy documented in `docs/SIDECAR_BACKEND.md` with complete roadmap.
- Backend status shows: mode, reachability, managed process PID, sidecar availability.
- Safety: Managed backend refuses non-localhost binding.
- Security: Never prints auth token automatically.

## v0.6.1

- macOS unsigned install QA guide created at `docs/MACOS_UNSIGNED_INSTALL_QA.md`.

## v0.6.1

- Added macOS unsigned install QA guide: `docs/MACOS_UNSIGNED_INSTALL_QA.md`.
- Added `release macos-qa` command for macOS DMG artifact verification.
- Added `desktop first-run-check` command for backend connectivity and setup verification.
- Improved desktop first-launch UI with clear "Backend is not running" message and `./liuant start` instructions.
- Added troubleshooting section to desktop offline state with retry button and diagnostic commands.
- Added 10 new tests for macOS QA and first-run check functionality.
- DMG artifact QA: verifies checksum, signed=false, notarized=false, docs exist, backend instructions present.
- First-run check: reports backend reachability, auth status, UI files, backend mode, setup instructions.

## v0.6.0

- **First real native build artifact produced**: macOS `.dmg` installer (3.7 MB) successfully created.
- Enhanced native build workflow with comprehensive build report generation including timestamps, dependency versions, and error summaries.
- Added `release build-report` and `release unsigned-build-check` commands for unsigned build QA verification.
- Added detailed artifact detection with SHA256 checksums, creation timestamps, and platform detection.
- Updated packaging scripts (`package_macos.sh`, `package_linux.sh`, `package_windows.ps1`) to run unsigned-build-check and display honest unsigned build summaries.
- Build reports now include: started_at, completed_at, platform, frontend_typecheck_status, frontend_build_status, native_build_status, dependencies, artifacts, error_summary, and logs_path.
- Unsigned build check verifies: native artifacts exist, checksums exist, version matches, bundle identifier is correct, icons exist, backend mode is documented, security docs exist, signed=False, notarized=False.
- All artifacts are honestly marked as unsigned and not notarized by default.
- Expanded tests to include 10 new v0.6.0 unsigned native build tests.

## v0.5.6

- Added a full local placeholder platform icon set for Tauri, including SVG, PNG, ICO, ICNS, and Windows Store logo variants.
- Added `scripts/generate_icons.py` plus `liuant desktop icons-check` and `liuant desktop icons-generate`.
- Added cross-platform native build guide helpers for macOS, Linux, and Windows that record `release/build-report.json` without signing claims.
- Added unsigned artifact reporting and artifact verification commands.
- Expanded release manifest and desktop report metadata with icon status, frontend-only state, unsigned artifact state, and build report status.
- Expanded tests to 279 passing.

## v0.5.2

- Added desktop packaging readiness checks.
- Added `desktop`, `release`, `signing`, `update-info`, and `update-config` CLI commands.
- Added release manifest and checksum generation.
- Added macOS, Linux, and Windows packaging scripts.
- Added Release UI page and API status routes.
- Added signing readiness checks with honest unsigned/not notarized defaults.
- Added local update metadata settings with automatic updates disabled by default.
- Expanded tests to 238 passing.

## v0.5.1

- Added installer scripts, release commands, repair/reset/update-check/release-check, logs helpers, and troubleshooting.

## v0.5.0

- Added secure local secret storage, secret migration, local API token auth, and UI session records.

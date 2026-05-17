# Changelog

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

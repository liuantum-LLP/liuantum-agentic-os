# Liuant Agentic OS

**Open-source, local-first AI agent operating system for building, managing, and automating AI agents from chat.**

---

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![CI](https://github.com/liuant/liuant-agentic-os/actions/workflows/ci.yml/badge.svg)](https://github.com/liuant/liuant-agentic-os/actions/workflows/ci.yml)
[![Version](https://img.shields.io/badge/version-1.0.0-brightgreen.svg)](CHANGELOG.md)

Liuant Agentic OS is a local-first AI agent operating system. It is **not a cloud service** — everything runs on your machine. You configure providers, create agents, set up automations, connect social accounts, and manage drafts — all through a chat interface.

**No auto-send. No auto-publish. No cloud dependency for core functionality. Approval-gated by default.**

---

## Key Features

- **Chat-first agent setup** — Configure providers, connectors, agents, and automations through natural language. Secrets collected securely and stored in the encrypted local SecretStore.
- **Minimal desktop UI** — Tauri + React + TypeScript desktop app with 6-item navigation (Chat, Dashboard, Agents, Automations, Knowledge, Settings).
- **Multi-provider Model Hub** — Text, image, video, embedding, speech-to-text, text-to-speech. OpenAI, OpenRouter, Ollama, LM Studio, and custom APIs.
- **Local-first secrets** — API keys and OAuth tokens stored in the encrypted local SecretStore. Never displayed, never logged.
- **Agents and automations** — Deterministic agent runs with optional AI enhancement. Local tick-based scheduler for recurring tasks.
- **Gmail draft-only** — Read inbox, search, create drafts. Sending is **not implemented**.
- **Telegram bot connector** — Bot-only, draft-only by default. Auto-reply disabled. Prompt-injection warnings.
- **Approval-gated social architecture** — LinkedIn and X OAuth. Publishing requires approval + manual per-connector enablement.
- **Memory and RAG** — Local hash embeddings, SQLite knowledge base, opt-in RAG for agent runs.
- **Image/video generation architecture** — Model-based and HyperFrames modes. No fake rendered output.
- **Unsigned desktop builds** — Community builds are unsigned. Signing is optional for maintainers only.

## Safety Principles

| Principle | Detail |
|---|---|
| No auto-send | Gmail sending is not implemented. |
| No auto-publish | Social publishing requires approval + manual enablement per connector. |
| No passwords collected | Liuant does not ask for passwords. |
| Approval-gated | Every external action creates an approval record. |
| Local-first secrets | Secrets stored in encrypted SecretStore. Never logged. |
| No cloud dependency | ChatIntentRouter uses deterministic pattern matching. AI is optional. |
| Unsigned builds | Community DMG builds are unsigned. No Apple Developer ID required. |

## Quick Start

```bash
# Clone and set up
git clone https://github.com/liuant/liuant-agentic-os.git
cd liuant_ai
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .

# Run tests
pytest -q

# Start the backend
cp .env.example .env   # edit with your API keys if desired
./liuant start

# Open the desktop UI
cd apps/desktop
npm install
npm run typecheck
npm run build
npm run tauri:dev       # requires Rust/Cargo
```

## CLI Examples

```bash
./liuant doctor
./liuant status
./liuant auth token

# Configure through chat
./liuant chat "Connect Telegram"
./liuant chat "Create a marketing agent"
./liuant chat "Every morning create a task list"

# Text generation
./liuant text generate "Write a 5-line marketing caption"

# Image generation
./liuant image generate "AI-powered software company poster" --mode hyperframes_skill

# Social
./liuant social campaign create
./liuant approvals list
./liuant social publish-approved <draft_id> --connector linkedin

# Desktop build
./liuant desktop build --native
./liuant release polish-check

# Signing (optional, maintainers only)
./liuant signing macos-status
```

## Desktop

The desktop app is a Tauri + React + TypeScript shell. It connects to the local backend at `http://127.0.0.1:8765`.

**Community builds are unsigned.** On macOS, you may need to right-click and Open the app the first time. Signing and notarization are optional and only needed for official distribution without Gatekeeper warnings. See `docs/MACOS_SIGNING_NOTARIZATION.md` for the maintainer signing workflow.

```bash
./liuant desktop status
./liuant desktop build --native   # produces unsigned DMG
./liantu release candidate-check  # v1.0 release candidate checks
./liantu release polish-check     # verify release health
```

### Backend Modes

Three backend modes are supported:

| Mode | Description | Status |
|------|-------------|--------|
| `external_backend` | User starts backend manually (`./liuant start`) | ✅ Default |
| `managed_backend` | CLI manages backend process (PID tracking) | ✅ Working |
| `bundled_sidecar` | Standalone executable for auto startup | ✅ Working (requires build) |

To build and use the sidecar:
```bash
pip install pyinstaller            # or: pip install liuant-agentic-os[sidecar]
./liantu sidecar build --confirm   # builds ~9.7 MB executable
./liantu sidecar run               # starts the backend
./liantu desktop backend-mode set bundled_sidecar  # switch mode
```

## Project Structure

```
liuant_ai/
  cli/liuant.py              # CLI entry point
  runtime/                   # Backend runtime
    config.py                # Settings, providers, permissions
    release.py               # Release, signing, checksums
    chat/intent_router.py    # ChatIntentRouter
  apps/desktop/              # Tauri + React desktop app
  docs/                      # Documentation
  scripts/                   # Build and utility scripts
  installer/                 # Install and package scripts
  tests/                     # Python test suite
```

## Documentation

| Document | Purpose |
|---|---|
| `docs/INSTALLATION.md` | Full setup guide |
| `docs/DESKTOP_PACKAGING.md` | Desktop build and packaging |
| `docs/SIDECAR_BACKEND.md` | Sidecar backend strategy and usage |
| `docs/V1_RELEASE_CANDIDATE.md` | v1.0 release readiness checklist |
| `docs/CHAT_FIRST_UX.md` | Chat-first UX design |
| `docs/SIGNING.md` | Optional maintainer signing pipeline |
| `docs/SECURITY.md` | Security model and policies |
| `docs/TROUBLESHOOTING.md` | Common issues and backend troubleshooting |
| `CONTRIBUTING.md` | How to contribute |
| `ROADMAP.md` | Project roadmap |

## License

MIT License — see [LICENSE](LICENSE).

Copyright (c) 2026 Liuant Agentic OS contributors.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). All contributions welcome — bug fixes, features, documentation, tests.

- Run `pytest -q` before submitting.
- No secrets in commits.
- Keep external actions approval-gated.

## Security

See [SECURITY.md](SECURITY.md) for our security policy and how to report vulnerabilities.

- Local-first secret storage.
- Approval-gated external actions.
- No secrets in logs.
- Report vulnerabilities privately to admin@liuantum.com.
# liuant-agentic-os

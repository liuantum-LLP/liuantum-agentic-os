# Open Source Release

## Current Status

**v1.0.0** — Stable local desktop release. 466 tests pass. Sidecar backend built and tested with PyInstaller. Community DMG rebuilt (unsigned, 3.7 MB). Security contact: `admin@liuantum.com`. All 15/15 candidate checks pass. Signing/notarization remain optional for maintainers only.

## Project Goals

Liuant Agentic OS is a **local-first AI agent operating system** designed to run entirely on your machine. It does not require cloud services, hosted APIs, or paid subscriptions for core functionality.

## License

MIT License — see [LICENSE](../LICENSE).

Copyright (c) 2026 Liuant Agentic OS contributors.

## Community Builds

Community builds are **unsigned** and **not notarized**. This is the expected default.

- No Apple Developer ID required.
- No paid signing certificate required.
- On macOS, unsigned apps may need **right-click → Open** on first launch.
- Build from source: `./liuant desktop build --native`
- Verify: `./liuant release polish-check`

## Contribution Process

See [CONTRIBUTING.md](../CONTRIBUTING.md).

- All contributions welcome.
- Tests must pass (`pytest -q`).
- No secrets in commits.
- External actions must remain approval-gated.
- Signing is not required for contributors.

## Security Rules

See [SECURITY.md](../SECURITY.md).

- Local-first secret storage.
- No auto-send or auto-publish.
- Approval-gated external actions.
- No secrets in logs.
- Report vulnerabilities privately.

## Local-First Philosophy

1. **Your data stays on your machine.** Secrets, drafts, knowledge, and memory are stored locally.
2. **No cloud dependency for core functions.** The ChatIntentRouter uses deterministic pattern matching.
3. **AI providers are optional.** You choose where to connect (OpenAI, Ollama, local models, etc.).
4. **Unsigned builds are the default.** No gatekeeper friction for open-source users.
5. **Safety by default.** No auto-send, no auto-publish, approval-gated by design.

## Open Roadmap

See [ROADMAP.md](../ROADMAP.md).

- v0.8: Open-source release readiness.
- v0.9: Sidecar backend and packaging improvements.
- v1.0: Stable local desktop release.

Non-goals: Cloud SaaS, multi-user tenancy, auto-publishing, App Store distribution.

## Sidecar Backend

v0.9.0 introduces a config-ready sidecar backend mechanism:
- Build a standalone executable from source: `./liuant sidecar build --confirm`
- Requires PyInstaller or Nuitka (optional dependency)
- The sidecar binds only to 127.0.0.1
- Community builds remain unsigned
- External_backend and managed_backend remain fully supported

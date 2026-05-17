# Governance

## Maintainer Model

Liuant Agentic OS operates under a **Benevolent Dictator for Life (BDFL)** model for the initial open-source release. Key decisions about architecture, safety, and release scope are made by the core maintainer. As the project grows, a maintainer committee may be formed.

## Decision Process

1. **Bug fixes and small improvements**: PRs reviewed and merged by any maintainer.
2. **New features**: Must include tests, documentation, and maintain safety guarantees (approval-gated actions, no auto-send).
3. **Breaking changes**: Require a discussion issue and consensus among maintainers.
4. **Security changes**: Require maintainer review and must not introduce unsafe defaults.
5. **Signing/notarization**: Optional maintainer workflow. Community builds remain unsigned.

## Roadmap Process

- The roadmap is maintained in `ROADWAY.md`.
- Feature requests are tracked via GitHub Issues.
- Major milestones are versioned (v0.8.x, v0.9.x, v1.0).
- Community contributors are welcome to propose roadmap items via discussion issues.

## Release Process

1. All tests must pass (`pytest -q`).
2. Frontend must typecheck and build (`npm run typecheck && npm run build`).
3. Release polish-check must pass (`./liuant release polish-check`).
4. Signed/notarized builds are optional and performed only by maintainers with Apple Developer credentials.
5. Community releases are unsigned DMG + source tarball + checksums.

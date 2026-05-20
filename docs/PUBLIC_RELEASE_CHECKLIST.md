# Public Release Checklist

Before tagging and publishing a new release to GitHub, ensure all of the following steps have been successfully executed and validated.

## 1. Technical Verification
- [ ] `python3 -m pytest -q` passes with 0 failures.
- [ ] `npm run typecheck` passes in `apps/desktop`.
- [ ] `npm run build` succeeds in `apps/desktop`.

## 2. Configuration & Integrity
- [ ] Version is fully aligned across `pyproject.toml`, `tauri.conf.json`, `package.json`, `app.py`, and `release.json`.
- [ ] No plaintext secrets or real API keys exist in the codebase, `.env.example`, or `examples/` directory.

## 3. Documentation
- [ ] `README.md` clearly states local-first design and approval-gated automation.
- [ ] `CHANGELOG.md` is updated with the current version block.
- [ ] `docs/RELEASE_NOTES_V3_1_0.md` (or relevant version) is created and summarizes the safety model.
- [ ] `docs/KNOWN_LIMITATIONS.md` is updated to reflect current missing features (no marketplace, no cloud sync).
- [ ] `docs/SCREENSHOTS_AND_DEMOS.md` reflects current UI.
- [ ] `docs/INSTALLATION.md` and `docs/PACKAGING.md` are current.

## 4. Ecosystem & CLI
- [ ] `./liuant release ecosystem-check` passes or outputs only documented warnings.
- [ ] `./liuant release public-release-check` passes.

## 5. Release Publishing
- [ ] GitHub Topics are updated (e.g., `local-first`, `ai-agent`, `agentic-os`).
- [ ] Git tag created: `git tag v3.1.0` and `git push origin v3.1.0`.

## 6. Artifact Assets
- [ ] Native macOS (Intel/Silicon) `.dmg` and `.app` bundles are attached to the release.
- [ ] Windows/Linux installers attached (if supported in this release).
- [ ] Source code `.zip` and `.tar.gz` attached.
- [ ] SHA256 checksums are published in the release body for all artifacts.

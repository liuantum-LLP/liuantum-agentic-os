# v1.0.0 Stable Release

**Version**: 1.0.0
**Channel**: stable-open-source
**Status**: ✅ Released

## Checklist

### Tests
- [x] 466 tests pass (`pytest -q`)
- [x] Open-source tests (8 tests)
- [x] Sidecar tests (15 + 11 = 26 tests)
- [x] Signing tests (17 tests)
- [x] Release tests

### Frontend
- [x] TypeScript typecheck clean (`npm run typecheck`)
- [x] Frontend builds (`npm run build`)
- [x] Settings page shows version (1.0.0), backend mode, sidecar status
- [x] Sidebar version aligned (v1.0.0)

### Desktop Native Build
- [x] Tauri config version aligned
- [x] DMG rebuilt: `Liuant Agentic OS_1.0.0_aarch64.dmg` (3.7 MB)
- [x] Hardened runtime enabled for macOS
- [ ] Hardened runtime entitlements verified with actual codesign
- [ ] Tauri externalBin configured for sidecar (optional, CLI-managed instead)

### Sidecar Backend
- [x] Module exists (`runtime/sidecar.py`)
- [x] CLI commands: `status`, `build`, `check`, `run`, `stop`
- [x] Built with PyInstaller (9.7 MB executable at `sidecar/liuant-backend`)
- [x] Executable binds to `127.0.0.1` only
- [x] Local auth enabled
- [x] `bundled_sidecar` backend mode works
- [x] Stop cleans PID and status
- [x] `sidecar status` reports honestly

### Open-Source Docs
- [x] MIT License (`LICENSE`)
- [x] `CONTRIBUTING.md`
- [x] `CODE_OF_CONDUCT.md`
- [x] `SECURITY.md` — security contact: `admin@liuantum.com`
- [x] `GOVERNANCE.md`
- [x] `ROADMAP.md`
- [x] `SUPPORT.md`
- [x] Community issue/PR templates
- [x] CI workflow (GitHub Actions, no Apple credentials)
- [x] `.gitignore` covers secrets, builds, node_modules
- [x] `.env.example` contains variable names only, no real secrets

### Security
- [x] No secrets, credentials, or private tokens in repo
- [x] Local auth enabled by default
- [x] Localhost-only backend binding enforced
- [x] Security contact set: `admin@liuantum.com`
- [x] `SECURITY.md` vulnerability reporting policy

### Community Builds
- [x] Unsigned builds work by default
- [x] No Apple Developer ID required for contributors
- [x] Signing/notarization documented as optional maintainer workflow

### Optional Signing
- [x] Signing CLI commands (6 commands with `--dry-run`/`--confirm`)
- [x] Signing API endpoints (6 endpoints)
- [x] Settings/Release UI signing status
- [x] Preflight checks (DMG checksum, version, Developer ID cert, missing checks)
- [x] `signing status` reports `signed=false`/`notarized=false` honestly

### Known Limitations
- **Hardened runtime entitlements**: Need verification with actual codesign session
- **Tauri externalBin for sidecar**: Not configured in `tauri.conf.json` — sidecar is CLI-managed
- **Notarization**: Requires Apple Developer account, not tested
- **Windows/Linux signing**: Not planned
- **PyInstaller/Nuitka**: Optional dependencies — sidecar executable not pre-built in repo

### Artifacts
- DMG: `Liuant Agentic OS_1.0.0_aarch64.dmg` (3,879,108 bytes, 3.7 MB)
- DMG SHA256: `8486db982053265ba781b1cd1e8dbfed900a8f0e7bf334d7b6d20b411a99a871`
- Signed: `false`
- Notarized: `false`
- Sidecar executable: `sidecar/liuant-backend` (9,706 KB, built with PyInstaller)

### Verification
Run `./liuant release candidate-check` — all 15/15 checks should pass.

## Git Tag
```bash
git tag -a v1.0.0 -m "v1.0.0 stable open-source local desktop release"
git push origin v1.0.0
```

## GitHub Release Assets
- DMG: `apps/desktop/src-tauri/target/release/bundle/dmg/Liuant Agentic OS_1.0.0_aarch64.dmg`
- Release notes: see CHANGELOG.md v1.0.0 entry

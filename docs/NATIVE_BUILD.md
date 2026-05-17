# Native Build

v0.5.6 adds native desktop readiness checks without claiming native artifacts.

## Checks

```bash
./liuant desktop native-check
./liuant desktop rust-check
./liuant desktop tauri-check
./liuant desktop icons-check
./liuant desktop icons-generate
./liuant desktop build-guide
./liuant desktop build-report
./liuant desktop build --frontend-only
./liuant desktop build --native
```

`--frontend-only` runs the React/TypeScript build and records frontend artifacts under `apps/desktop/dist`.

`--native` runs the frontend build first, then checks Rust/Cargo/Tauri prerequisites before attempting a Tauri build. If Rust/Cargo are missing, it returns `dependency_missing` and does not claim native artifacts.

## macOS Prerequisites

- Xcode Command Line Tools: `xcode-select --install`
- Rust/Cargo through rustup
- Node.js with npm or pnpm
- Project dependencies installed in `apps/desktop`

## Windows Prerequisites

- Visual Studio Build Tools with Desktop development with C++
- Microsoft Edge WebView2 runtime
- Rust/Cargo through rustup
- Node.js with npm or pnpm

## Linux Prerequisites

- WebKitGTK/Tauri system packages for your distribution
- build-essential or equivalent compiler tools
- curl/wget
- Rust/Cargo through rustup
- Node.js with npm or pnpm

## Artifact Paths

Frontend artifacts:

- `apps/desktop/dist/index.html`
- `apps/desktop/dist/assets/*.js`
- `apps/desktop/dist/assets/*.css`

Native artifacts are only valid when actual files exist under:

- `apps/desktop/src-tauri/target/release/bundle`

Signing and notarization remain pending.

## Helper Scripts

```bash
scripts/build_desktop_macos.sh
scripts/build_desktop_linux.sh
scripts/build_desktop_windows.ps1
```

These scripts check prerequisites, run frontend typecheck/build, and only attempt Tauri build when Rust/Cargo exist. They write `release/build-report.json`, do not request privileged installs, and never mark artifacts as signed.

## Icons

Run:

```bash
./liuant desktop icons-generate
./liuant desktop icons-check
```

The icon set is the premium neural orbit mark (v0.7.2). All 16 files are generated offline. Regenerate at any time with `./liuant desktop icons-generate`.

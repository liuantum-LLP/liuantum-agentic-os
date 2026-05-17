# Installation

## macOS and Linux

```bash
./installer/install_macos.sh
./installer/install_linux.sh
```

The scripts create `.venv`, install Liuant in editable mode, create workspace folders, copy `.env.example` only if `.env` is missing, then run repair and doctor checks.

## Windows

```powershell
.\installer\install_windows.ps1
```

## First Run

```bash
./liuant repair
./liuant doctor
./liuant auth token
./liuant start
./liuant open
```

## Sidecar Backend (Optional)

Build a standalone backend executable for automatic desktop integration:

```bash
# Install PyInstaller (optional dependency)
pip install liuant-agentic-os[sidecar]
# or: pip install pyinstaller

# Build the sidecar executable (~9.7 MB)
./liuant sidecar build --confirm

# Verify and run
./liuant sidecar check
./liuant sidecar status
./liuant sidecar run

# Switch backend mode
./liuant desktop backend-mode set bundled_sidecar
```

The executable binds only to `127.0.0.1`. Or use `external_backend` / `managed_backend` without building anything.

## Native Desktop Development

The Tauri scaffold exists under `apps/desktop`.

```bash
./liuant desktop check
./liuant desktop icons-generate
./liuant desktop icons-check
./liuant desktop native-check
./liuant desktop build-guide
./liuant signing status
./liuant start 8765
cd apps/desktop
pnpm install
pnpm run typecheck
pnpm run build
pnpm tauri dev
```

If `pnpm` is unavailable, use `npm install`, `npm run typecheck`, `npm run build`, and `npm run tauri:dev`.

Native Tauri dev/build requires Rust and Cargo. If those are missing, `desktop check` shows setup instructions and release checks remain honest. Native builds remain unsigned and not notarized.

Platform build helper scripts are available after local dependencies are installed:

```bash
scripts/build_desktop_macos.sh
scripts/build_desktop_linux.sh
scripts/build_desktop_windows.ps1
```

They write `release/build-report.json` and do not request privileged installs.

## Backend Mode

The desktop app defaults to external backend mode:

```bash
./liuant desktop backend-mode
./liuant start 8765
```

For local managed mode:

```bash
./liuant desktop backend-mode set managed_backend
./liuant desktop backend-start
```

The backend still binds only to `127.0.0.1`. Bundled sidecar is available after `./liuant sidecar build --confirm`.

# Installation

## Developer Installation (Editable)

```bash
# Clone
git clone https://github.com/liuant/liuant-agentic-os.git
cd liuant_ai

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install in editable mode
python -m pip install -e .

# Verify
./liuant doctor
```

## First Run

```bash
./liuant repair
./liuant doctor
./liuant start
```

## One-Click Startup

Check what auto-start strategies are available, then attempt launch:

```bash
./liuant desktop one-click-check
./liuant desktop launch-check
```

The desktop app also auto-polls the backend on launch with a loading screen.

## Sidecar Backend (Optional)

Build a standalone backend executable for automatic desktop integration:

```bash
# Install PyInstaller (optional dependency)
pip install -e ".[sidecar]"

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
npm install
npm run typecheck
npm run build
npm run tauri:dev      # or: npm run tauri build
```

Native Tauri dev/build requires Rust and Cargo platform prerequisites.
Native builds remain unsigned and not notarized — see `docs/MACOS_SIGNING_NOTARIZATION.md` for optional maintainer signing.

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

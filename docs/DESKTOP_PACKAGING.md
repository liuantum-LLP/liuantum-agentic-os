# Desktop Packaging Guide

To distribute Liuant Agentic OS as a standalone desktop application, we package the Python backend via PyInstaller and the React frontend via Tauri.

## 1. Prerequisites
- **Python 3.11+** (Use `python3`)
- **Node.js 20+** and **npm**
- **Rust / Cargo** (Required for Tauri)

## 2. Prepare the Sidecar Backend
```bash
./liuant sidecar build
./liuant sidecar status
```

## 3. Package the Frontend
```bash
cd apps/desktop
npm install
npm run build
npm run tauri build
```

## 4. Distributing Unsigned Builds
When packaging the app on your local machine, the output is unsigned.
- On macOS, users will encounter a warning saying the app cannot be opened. They must right-click the app bundle and select **Open** to bypass this.
- Signing is entirely **optional** and primarily intended for core maintainers.

Please refer to the [Known Limitations](KNOWN_LIMITATIONS.md) before distributing your local build.

## Note on sidecar build
The sidecar build creates a bundled backend.

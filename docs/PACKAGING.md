# Liuant Agentic OS Packaging

Packaging Liuant Agentic OS requires assembling both the Python sidecar and the Tauri frontend into a cohesive, standalone distribution.

## Sidecar Build
The backend engine must first be bundled using PyInstaller.

```bash
# Verify your environment is active
source venv/bin/activate

# Build the sidecar executable
./liuant sidecar build

# Check the build status
./liuant sidecar status
```

## Frontend Build
Once the sidecar is successfully prepared, you must compile the Tauri desktop frontend.

```bash
cd apps/desktop
npm install
npm run tauri build
```

## Community vs. Official Builds
**By default, all generated builds are unsigned.** 

- **Unsigned Community Builds**: Anyone can compile Liuant. On macOS, unsigned builds require a right-click → **Open** to bypass Gatekeeper.
- **Official Signed Builds**: Only core maintainers utilize codesigning and notarization.

For instructions on signing (Maintainer only), read [macOS Signing & Notarization](MACOS_SIGNING_NOTARIZATION.md).

# macOS Signing & Notarization

**Note: macOS signing and notarization are entirely optional and reserved strictly for official core maintainers.**

If you are a community developer building from source, your builds will remain **unsigned**. Users can execute an unsigned macOS build by right-clicking the `.app` bundle and selecting **Open**.

## For Core Maintainers

To sign and notarize the official release, ensure you have the required Apple Developer Certificates installed in your keychain:
- Developer ID Application
- Developer ID Installer

### 1. Build and Sign the Sidecar
The PyInstaller sidecar must be signed before it is bundled into the Tauri app.

```bash
codesign --force --options runtime --sign "Developer ID Application: Your Name (XXXX)" release/build/liuant-backend
```

### 2. Build and Sign Tauri
Configure Tauri to use your Developer ID by setting environment variables before running the build:

```bash
export APPLE_CERTIFICATE="Developer ID Application: Your Name (XXXX)"
export APPLE_CERTIFICATE_PASSWORD="..."
export APPLE_ID="..."
export APPLE_PASSWORD="..."
export APPLE_TEAM_ID="..."

cd apps/desktop
npm run tauri build
```

The resulting `.dmg` and `.app` files will be notarized automatically by the Tauri bundler if the credentials are valid.

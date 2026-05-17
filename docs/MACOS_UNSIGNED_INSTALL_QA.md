# macOS Unsigned Install QA Guide

## Overview

This guide documents the QA process for installing the unsigned macOS version of Liuant Agentic OS v0.6.0+.

**Important**: This is an UNSIGNED and NOT NOTARIZED build. macOS will show security warnings during first launch. This is expected behavior.

## Prerequisites

- macOS 12+ (Monterey or later)
- Apple Silicon (M1/M2/M3) or Intel Mac
- DMG file: `Liuant Agentic OS_0.6.0_aarch64.dmg`
- SHA256: `0464df41a96dfb5ea82b048a08f35aa5afa1581c403bd56f7561e63ab5f1e4f1`

## QA Checklist

### 1. Verify DMG Integrity

```bash
# Check file exists
ls -lh "/Users/likhithbb/Downloads/liuant_ai/apps/desktop/src-tauri/target/release/bundle/dmg/Liuant Agentic OS_0.6.0_aarch64.dmg"

# Verify SHA256 checksum
shasum -a 256 "Liuant Agentic OS_0.6.0_aarch64.dmg"
# Expected: 0464df41a96dfb5ea82b048a08f35aa5afa1581c403bd56f7561e63ab5f1e4f1
```

### 2. Open DMG

1. Double-click the `.dmg` file
2. A window should appear showing:
   - Liuant Agentic OS app icon
   - Applications folder shortcut
   - Background graphic (if included)

### 3. Install Application

1. Drag "Liuant Agentic OS" icon to the Applications folder shortcut
2. Wait for copy to complete (3.5 MB, should be quick)
3. Eject the DMG by clicking the eject icon in Finder sidebar

### 4. First Launch - Unsigned Warning

**Expected behavior**: macOS will block the app from opening because it is unsigned.

You will see one of these warnings:
- "Liuant Agentic OS" can't be opened because it is from an unidentified developer
- macOS cannot verify the developer of "Liuant Agentic OS"

### 5. Workaround - Right-Click Open

To launch the unsigned app:

1. Open Finder → Applications
2. Right-click (or Control+click) on "Liuant Agentic OS"
3. Select "Open" from the context menu
4. Click "Open" in the security dialog that appears
5. The app will now launch

**Note**: This only needs to be done once. Subsequent launches can be done normally.

### 6. Backend Requirement

**Expected**: App launches but shows "Backend is not running" message.

The desktop app requires the local backend server to be running separately.

### 7. Start Backend

In a terminal, run:

```bash
# Navigate to app directory
cd /Users/likhithbb/Downloads/liuant_ai

# Start the backend
./liuant start

# Or specify a port
./liuant start 8765
```

The backend will start on `http://127.0.0.1:8765` by default.

### 8. Token Authentication

If local auth is enabled (default), the desktop app will show a token login form.

To get the token:

```bash
./liuant auth token
```

Enter this token in the desktop app's login form.

### 9. Verify Connection

In the desktop app:
- Backend status should show "Connected"
- API preview should show live data
- Dashboard should populate

## Troubleshooting

### Issue: "App is damaged" warning

**Cause**: macOS Gatekeeper may flag unsigned apps.

**Solution**:
```bash
# Remove the quarantine attribute
xattr -d com.apple.quarantine /Applications/Liuant\ Agentic\ OS.app

# Or disable Gatekeeper for this app only
xattr -cr /Applications/Liuant\ Agentic\ OS.app
```

### Issue: Backend connection refused

**Cause**: Backend server not running.

**Solution**:
```bash
# Check backend status
./liuant status

# Start backend
./liuant start

# Check if port is in use
lsof -i :8765
```

### Issue: Token not accepted

**Cause**: Token may have expired or auth may be disabled.

**Solution**:
```bash
# Generate new token
./liuant auth token

# Check auth status
./liuant auth status
```

### Issue: UI shows "Loading..." forever

**Cause**: Backend unreachable or CORS issue.

**Solution**:
1. Verify backend is running: `curl http://127.0.0.1:8765/api/status`
2. Check Tauri CSP configuration
3. Check browser console for errors

## Verification Commands

```bash
# Run macOS QA check
./liuant release macos-qa

# Run first-run check
./liuant desktop first-run-check

# Verify artifacts
./liuant release verify-artifacts

# Check signing status
./liuant signing status
```

## Security Notes

- This is an unsigned build. Only install if you trust the source.
- The backend binds to localhost only (127.0.0.1) for security.
- Local auth tokens are required by default.
- No auto-updates or network connections are made without explicit action.

## Version Information

- Version: 0.6.0
- Platform: macOS Apple Silicon (aarch64)
- Bundle ID: com.liuant.agenticos
- Backend Mode: external_backend
- Signed: false
- Notarized: false

## Support

For issues specific to the unsigned macOS build:
1. Check this QA document
2. Run `./liuant doctor` for diagnostics
3. Check `./liuant troubleshoot` output
4. Review logs: `./liuant logs tail`

---

Last updated: v0.6.1

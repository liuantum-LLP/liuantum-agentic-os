# Sidecar Backend Strategy

Version: v1.0.0

## Overview

Liuant Agentic OS supports three backend connection modes for the desktop application. This document explains each mode, their current status, and how to build the bundled sidecar.

## Backend Modes

### 1. external_backend (Default, Recommended)

**Status:** ✅ Fully Working

The user starts the backend manually using the CLI, and the desktop app connects to it.

```bash
./liuant start
./liuant start 8765   # custom port
```

**Characteristics:**
- Most stable and reliable
- Backend runs as separate process
- User has full control over backend lifecycle
- Works across all platforms

### 2. managed_backend (Working, Development-Friendly)

**Status:** ✅ Working with PID tracking

The desktop app or CLI can start and stop the backend process directly. Still localhost-only and safe.

```bash
./liuant desktop backend-mode set managed_backend
./liuant desktop backend-start
./liuant desktop backend-stop
./liuant desktop backend-restart
```

**Characteristics:**
- Convenient for development
- PID tracking prevents duplicate processes
- Binds only to localhost (127.0.0.1)
- Local auth remains active

### 3. bundled_sidecar (v0.9.0)

**Status:** ✅ Config-ready with build tooling

A packaged backend executable that the desktop app can launch directly. The sidecar is built from source using PyInstaller or Nuitka. Community builds remain unsigned.

```bash
# Check availability
./liuant sidecar status

# Build from source (requires PyInstaller)
./liuant sidecar build --confirm

# Verify the executable
./liuant sidecar check

# Run the sidecar
./liuant sidecar run

# Stop the sidecar
./liuant sidecar stop --confirm
```

**Prerequisites for building:**
- Python 3.11+
- PyInstaller (`pip install pyinstaller`) or Nuitka (`pip install nuitka`)
- All project dependencies installed
- Or: `pip install liuant-agentic-os[sidecar]` to include PyInstaller

**How it works:**
1. `./liuant sidecar build --confirm` packages the CLI entry point into a standalone executable
2. The executable is placed at `sidecar/liuant-backend`
3. `./liuant sidecar run` starts the executable as a background process
4. `./liuant sidecar check` verifies the executable responds
5. The desktop app can detect sidecar availability and use it as the backend

**Safety:**
- Sidecar binds only to 127.0.0.1
- Local API auth is preserved
- No secrets printed in status output
- PID-based lifecycle management
- SIGTERM for clean shutdown

## Mode Comparison

| Feature | external_backend | managed_backend | bundled_sidecar |
|---------|------------------|-----------------|-----------------|
| Status | ✅ Working | ✅ Working | ✅ Working (requires build) |
| Complexity | Low | Medium | Medium |
| User Control | Full | Partial | Minimal |
| Convenience | Manual | Semi-automatic | Automatic |
| Recommended For | Production | Development | Packaged distribution |

## Security Rules

All backend modes must follow these security principles:

1. **Localhost Only:** Backend must bind to 127.0.0.1 or localhost
2. **Auth Required:** Local API auth is not bypassed
3. **No Token Exposure:** Auth token is never printed automatically
4. **Safe Shutdown:** Backend stops cleanly without data loss
5. **No Remote Exposure:** Remote backend exposure is not enabled by default

## CLI Commands Reference

### Sidecar Commands

```bash
./liuant sidecar status        # Check if sidecar executable exists and is running
./liuant sidecar build --confirm  # Build the sidecar executable
./liuant sidecar check         # Verify the sidecar executable works
./liuant sidecar run           # Start the sidecar backend
./liuant sidecar stop --confirm   # Stop the sidecar backend
```

### Desktop Backend Commands

```bash
./liuant desktop backend-status    # Check backend reachability
./liuant desktop backend-mode      # View/set backend mode
./liuant desktop backend-start     # Start backend (managed/sidecar)
./liuant desktop backend-stop      # Stop backend (managed/sidecar)
./liuant desktop backend-restart   # Restart backend
```

## Migration Path

Users can switch between modes at any time:

```bash
./liuant desktop backend-mode set external_backend
./liuant desktop backend-mode set managed_backend
./liuant desktop backend-mode set bundled_sidecar   # requires sidecar executable
```

## Current Recommendation

**For v1.0.0:** Use `external_backend` for stability or `managed_backend` for development. Build the sidecar with `./liuant sidecar build --confirm` if you want automatic backend startup. Community builds remain unsigned.

## Build Status

The sidecar has been built and tested with PyInstaller:

- **Build tool**: PyInstaller (--onefile)
- **Executable size**: ~9.7 MB
- **Build time**: ~60 seconds
- **Status**: ✅ Successfully built and tested

### Verified Behaviors
1. `sidecar run` starts the executable as a background process
2. PID tracking works — status shows `running: true` with correct PID
3. Server binds to `127.0.0.1:8765` (localhost only)
4. Local API auth remains enabled (returns `unauthorized` without token)
5. `sidecar stop` sends SIGTERM, PID/status cleaned
6. `bundled_sidecar` backend mode switches correctly and starts the sidecar

### Dependency Note
PyInstaller is an optional dependency (`pip install liuant-agentic-os[sidecar]`). The sidecar executable is **not pre-built** in the repository. Contributors must install PyInstaller and run `./liuant sidecar build --confirm` to create it.

## Documentation References

- `docs/DESKTOP_PACKAGING.md` - Desktop build instructions
- `docs/TROUBLESHOOTING.md` - Backend troubleshooting
- `docs/INSTALLATION.md` - Installation guide

---

Last updated: v1.0.0

## Note on sidecar build
Provides sidecar build instructions.

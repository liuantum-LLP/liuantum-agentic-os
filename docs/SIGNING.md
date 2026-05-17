# Signing Pipeline

> **Optional maintainer workflow.** Community builds are unsigned and do not require this.

## Overview

Liuant includes a complete macOS code-signing and notarization pipeline wrapping Apple's `codesign`, `notarytool`, and `stapler` tools. It is designed for **project maintainers** who want to distribute signed builds without Gatekeeper warnings. It is **not required** for contributors, local development, or community builds.

## Quick Start

```bash
./liuant signing macos-status
./liuant signing macos-preflight
./liuant signing macos-sign --dry-run
./liuant signing macos-sign --confirm true
./liuant signing macos-notarize --dry-run
./liuant signing macos-notarize --confirm true
```

## Community Build

Community builds remain unsigned by default:

```bash
./liuant release unsigned-artifacts
./liuant release verify-artifacts
./liuant release polish-check
```

All return `signed: false, notarized: false`. That is the expected default.

## For Contributors

- You do not need Apple Developer credentials.
- You do not need to sign builds.
- Unsigned DMG works for local development.

See `docs/MACOS_SIGNING_NOTARIZATION.md` for full maintainer documentation.

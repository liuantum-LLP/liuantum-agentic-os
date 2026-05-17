#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "Liuant macOS packaging readiness (v0.7.1)"
echo "=========================================="

# Parse optional flags
DO_SIGN=false
DO_NOTARIZE=false
DRY_RUN_SIGNING=false
POSITIONAL=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --sign) DO_SIGN=true; shift ;;
    --notarize) DO_NOTARIZE=true; shift ;;
    --dry-run-signing) DRY_RUN_SIGNING=true; shift ;;
    -h|--help)
      echo "Usage: $0 [--sign] [--notarize] [--dry-run-signing]"
      echo ""
      echo "  --sign             Attempt code-signing after build (requires Apple credentials)"
      echo "  --notarize         Attempt notarization after signing (requires Apple credentials)"
      echo "  --dry-run-signing  Show signing plan without executing"
      echo ""
      echo "Default (no flags): unsigned build only."
      exit 0
      ;;
    *) POSITIONAL+=("$1"); shift ;;
  esac
done

echo ""
python3 -m cli.liuant release-check
echo ""
python3 -m cli.liuant desktop check
echo ""

if [ ! -d "apps/desktop/src-tauri" ]; then
  echo "No Tauri desktop project found at apps/desktop/src-tauri."
  echo "Create the Tauri project and install Node.js + Rust/Cargo before building .app/.dmg artifacts."
  exit 2
fi

if ! command -v cargo >/dev/null 2>&1; then
  echo "Rust/Cargo is required for Tauri packaging."
  echo "Run: curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh"
  echo "Then: source $HOME/.cargo/env"
  exit 2
fi

if command -v pnpm >/dev/null 2>&1; then
  (cd apps/desktop && pnpm tauri build)
elif command -v npm >/dev/null 2>&1; then
  (cd apps/desktop && npm run tauri:build)
else
  echo "Node.js package tooling is required: install pnpm or npm."
  exit 2
fi

echo ""
echo "Running release checks..."
python3 -m cli.liuant release manifest
python3 -m cli.liuant release checksum

# Signing
if [ "$DO_SIGN" = true ] || [ "$DRY_RUN_SIGNING" = true ]; then
  echo ""
  echo "--- Signing phase ---"
  if [ "$DRY_RUN_SIGNING" = true ]; then
    python3 -m cli.liuant signing macos-sign --dry-run
  fi
  if [ "$DO_SIGN" = true ]; then
    echo "Attempting real signing..."
    python3 -m cli.liuant signing macos-sign --confirm
  fi
  if [ "$DO_NOTARIZE" = true ]; then
    echo "Attempting notarization..."
    python3 -m cli.liuant signing macos-notarize --confirm
  fi
fi

echo ""
python3 -m cli.liuant release unsigned-build-check
echo ""
echo "========================================="
echo "UNSIGNED BUILD SUMMARY"
echo "========================================="
python3 -m cli.liuant release unsigned-artifacts
echo ""
echo "========================================="
echo "Build report:"
python3 -m cli.liuant release build-report | grep -E "(path|status)" | head -5
echo "========================================="
echo ""
echo "Packaging complete. This is an UNSIGNED build."
echo "If you used --sign/--notarize, check ./liuant signing status for results."
echo "No auto-publishing or cloud distribution is performed."

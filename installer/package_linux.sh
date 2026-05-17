#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "Liuant Linux packaging readiness (v0.6.0)"
echo "=========================================="
python3 -m cli.liuant release-check
echo ""
python3 -m cli.liuant desktop check
echo ""

if [ ! -d "apps/desktop/src-tauri" ]; then
  echo "No Tauri desktop project found at apps/desktop/src-tauri."
  echo "Create the Tauri project and install Node.js + Rust/Cargo before building AppImage/deb/rpm artifacts."
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
echo "Package signing remains pending."
echo "No auto-publishing or cloud distribution is performed."

#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT="$ROOT_DIR/release/build-report.json"
mkdir -p "$ROOT_DIR/release"

missing=()
command -v node >/dev/null 2>&1 || missing+=("node")
command -v npm >/dev/null 2>&1 || missing+=("npm")
command -v rustc >/dev/null 2>&1 || missing+=("rustc")
command -v cargo >/dev/null 2>&1 || missing+=("cargo")
command -v rustup >/dev/null 2>&1 || missing+=("rustup")
command -v pkg-config >/dev/null 2>&1 || missing+=("pkg-config")

echo "Liuant Linux desktop build helper"
echo "This script does not request privileged elevation and does not sign packages."
if ((${#missing[@]})); then
  printf 'Missing dependencies: %s\n' "${missing[*]}"
  echo "Install WebKitGTK, build-essential, curl/wget, pkg-config, libssl-dev, librsvg2-dev, Rust, and Node.js using your distribution's package manager."
fi

cd "$ROOT_DIR/apps/desktop"
npm run typecheck
npm run build

native_status="dependency_missing"
if command -v cargo >/dev/null 2>&1 && command -v rustc >/dev/null 2>&1; then
  npm run tauri:build && native_status="tauri_build_attempted"
fi

cat > "$REPORT" <<JSON
{
  "platform": "linux",
  "frontend_build_status": "passed",
  "native_build_status": "$native_status",
  "signed": false,
  "notarized": false,
  "missing": [$(printf '"%s",' "${missing[@]}" | sed 's/,$//')]
}
JSON
echo "Build report written to $REPORT"

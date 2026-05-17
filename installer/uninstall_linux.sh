#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "Stopping Liuant local server if it is running..."
./liuant stop || true

echo "Removing local virtual environment only. Workspace, .env, backups, and outputs are preserved."
rm -rf .venv

echo "Uninstall complete. To remove user data manually, inspect workspace/ first."

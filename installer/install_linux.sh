#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "Installing Liuant Agentic OS for Linux..."
python3 - <<'PY'
import sys
if sys.version_info < (3, 11):
    raise SystemExit("Python 3.11 or newer is required.")
PY

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .

mkdir -p workspace/outputs workspace/backups workspace/logs workspace/security
if [ ! -f .env ] && [ -f .env.example ]; then
  cp .env.example .env
  echo "Created .env from .env.example. Add your own provider keys when ready."
else
  echo ".env already exists or .env.example is missing; not overwriting."
fi

./liuant repair
./liuant doctor

echo "Next steps:"
echo "  ./liuant auth token"
echo "  ./liuant start"
echo "  ./liuant open"

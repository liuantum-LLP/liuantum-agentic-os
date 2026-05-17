from __future__ import annotations

import os
import socket
import sys
from pathlib import Path
from typing import Any

from runtime.storage import ROOT, WORKSPACE


EXPECTED_ENV = [
    "OPENAI_API_KEY",
    "OPENROUTER_API_KEY",
    "REPLICATE_API_TOKEN",
    "REPLICATE_VIDEO_MODEL",
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
    "GOOGLE_REDIRECT_URI",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_WEBHOOK_SECRET",
    "LINKEDIN_CLIENT_ID",
    "LINKEDIN_CLIENT_SECRET",
    "LINKEDIN_REDIRECT_URI",
    "X_CLIENT_ID",
    "X_CLIENT_SECRET",
    "X_REDIRECT_URI",
    "OLLAMA_BASE_URL",
]


class EnvironmentValidator:
    def check(self) -> dict[str, Any]:
        folders = [WORKSPACE, WORKSPACE / "outputs", WORKSPACE / "outputs" / "images", WORKSPACE / "outputs" / "videos"]
        for folder in folders:
            folder.mkdir(parents=True, exist_ok=True)
        checks = {
            "python_version": sys.version.split()[0],
            "python_supported": sys.version_info >= (3, 11),
            "workspace_writable": all(os.access(folder, os.W_OK) for folder in folders),
            "sqlite_db_path": os.environ.get("LIUANT_DB_PATH", str(WORKSPACE / "liuant.db")),
            "env_files_present": [name for name in (".env", ".env.local") if (ROOT / name).exists()],
            "expected_env": {key: bool(os.environ.get(key) or self._read_env_file(key)) for key in EXPECTED_ENV},
            "ui_files_present": all((ROOT / "ui" / name).exists() for name in ("index.html", "app.js", "styles.css")),
            "api_port_8765_available": self._port_available(8765),
            "api_port_8000_available": self._port_available(8000),
        }
        missing = [key for key, present in checks["expected_env"].items() if not present]
        return {"status": "ok", "checks": checks, "missing": missing, "setup_instructions": ["Use `liuant env template` to print safe variable names only."]}

    def template(self) -> dict[str, Any]:
        return {"status": "template", "variables": EXPECTED_ENV}

    def missing(self) -> dict[str, Any]:
        result = self.check()
        return {"status": "missing", "variables": result["missing"]}

    def _read_env_file(self, key: str) -> str:
        for name in (".env.local", ".env"):
            path = ROOT / name
            if not path.exists():
                continue
            for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
                if not line.strip() or line.strip().startswith("#") or "=" not in line:
                    continue
                env_key, value = line.split("=", 1)
                if env_key.strip() == key:
                    return value.strip().strip('"').strip("'")
        return ""

    def _port_available(self, port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.2)
            return sock.connect_ex(("127.0.0.1", port)) != 0

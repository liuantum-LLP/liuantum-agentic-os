import json
from pathlib import Path
from typing import Any
import os
from runtime.storage import ROOT

def get_workspace_dir() -> Path:
    ws = os.environ.get("LIUANT_WORKSPACE")
    return Path(ws) if ws else ROOT / "workspace"

DEFAULT_SETTINGS = {
    "browser_automation_enabled": False,
    "browser_provider": "playwright",
    "headless": False,
    "default_browser": "chromium",
    "allow_screenshots": False,
    "allow_downloads": False,
    "allow_form_fill": False,
    "allow_clicks": False,
    "require_confirmation_for_navigation": True,
    "require_confirmation_for_clicks": True,
    "require_confirmation_for_forms": True,
    "store_screenshots": False,
    "store_page_text": False,
    "redact_page_text": True,
    "max_page_text_chars": 20000,
    "search_provider": "none",
    "search_requires_confirmation": True,
}

def get_settings_path() -> Path:
    return get_workspace_dir() / "config" / "browser_settings.json"

def get_browser_settings() -> dict[str, Any]:
    path = get_settings_path()
    if not path.exists():
        return DEFAULT_SETTINGS.copy()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        settings = DEFAULT_SETTINGS.copy()
        settings.update(data)
        return settings
    except Exception:
        return DEFAULT_SETTINGS.copy()

def update_browser_settings(updates: dict[str, Any]) -> dict[str, Any]:
    settings = get_browser_settings()
    for key, value in updates.items():
        if key in DEFAULT_SETTINGS:
            settings[key] = value
    path = get_settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    return settings

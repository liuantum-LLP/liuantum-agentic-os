from __future__ import annotations

import json
import re
from typing import Any
from runtime.db import get_record, insert_record, update_record

def utc_now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()

VOICE_SETTINGS_KEY = "voice_assistant_settings"

VOICE_DEFAULTS = {
    "voice_enabled": False,
    "wake_listening_enabled": False,
    "assistant_name": "Liuant",
    "wake_phrases": ["Hey Liuant", "Liuant", "Okay Liuant", "Hello Liuant"],
    "wake_response": "Yes, what do you want?",
    "stt_provider": "local_mock",
    "tts_provider": "system",
    "voice_reply_enabled": True,
    "push_to_talk_enabled": True,
    "always_listening_warning_acknowledged": False,
    "store_transcripts": False,
    "redact_transcripts": True,
    "confirmation_required_for_actions": True,
    "voice_default_model_role": "default",
    "voice_wake_response_mode": "fixed",
    "voice_command_discussion_mode": False
}

def validate_assistant_name(name: str) -> str:
    if not name or not isinstance(name, str):
        raise ValueError("Assistant name must be a non-empty string.")
    name = name.strip()
    if len(name) < 2 or len(name) > 30:
        raise ValueError("Assistant name must be between 2 and 30 characters.")
    if not re.match(r"^[A-Za-z0-9\s\-_]+$", name):
        raise ValueError("Assistant name contains invalid characters. Only letters, numbers, spaces, hyphens, and underscores are allowed.")
    return name

def get_voice_settings() -> dict[str, Any]:
    row = get_record("settings", VOICE_SETTINGS_KEY)
    if not row:
        # Save defaults immediately to make sure it exists
        defaults = dict(VOICE_DEFAULTS)
        save_voice_settings(defaults)
        return defaults
    
    # Merge with defaults in case of missing keys
    try:
        saved_data = json.loads(row["value"]) if "value" in row else row
        if not isinstance(saved_data, dict):
            saved_data = {}
    except Exception:
        saved_data = {}
        
    merged = dict(VOICE_DEFAULTS)
    merged.update(saved_data)
    return merged

def save_voice_settings(settings: dict[str, Any]) -> dict[str, Any]:
    now = utc_now()
    value_str = json.dumps(settings, sort_keys=True)
    
    # We follow SettingsManager format where 'value' field stores the config string
    record = {
        "id": VOICE_SETTINGS_KEY,
        "key": VOICE_SETTINGS_KEY,
        "value": value_str,
        "created_at": now,
        "updated_at": now
    }
    insert_record("settings", record)
    return settings

def update_voice_setting(key: str, value: Any) -> dict[str, Any]:
    settings = get_voice_settings()
    
    if key == "assistant_name":
        value = validate_assistant_name(value)
        settings["assistant_name"] = value
        # Automatically update wake phrases
        settings["wake_phrases"] = [
            f"Hey {value}",
            value,
            f"Okay {value}",
            f"Hello {value}"
        ]
    elif key in ("voice_enabled", "wake_listening_enabled", "voice_reply_enabled", 
                 "push_to_talk_enabled", "always_listening_warning_acknowledged", 
                 "store_transcripts", "redact_transcripts", "confirmation_required_for_actions",
                 "voice_command_discussion_mode"):
        if isinstance(value, str):
            value = value.lower() in ("true", "yes", "1", "on")
        settings[key] = bool(value)
    else:
        settings[key] = value
        
    save_voice_settings(settings)
    return settings

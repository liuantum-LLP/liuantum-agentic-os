import pytest
import json
from unittest.mock import patch, MagicMock

from runtime.voice.settings import get_voice_settings, save_voice_settings
from runtime.voice.wake import detect_wake_phrase
from runtime.voice.session import VoiceSessionManager
from cli.liuant import build_parser, dispatch

def test_wake_phrase_detector_basic_match():
    phrases = ["Hey Liuant", "Liuant"]
    
    # Exact match
    res = detect_wake_phrase("Hey Liuant", phrases)
    assert res["woke"] is True
    assert res["command_text"] == ""
    
    # Prefix match with command
    res = detect_wake_phrase("Hey Liuant list workflows", phrases)
    assert res["woke"] is True
    assert res["command_text"] == "list workflows"
    
    # Punctuation handling
    res = detect_wake_phrase("Hey Liuant, show system status!", phrases)
    assert res["woke"] is True
    assert res["command_text"] == "show system status!"

def test_wake_phrase_detector_no_match():
    phrases = ["Hey Liuant"]
    res = detect_wake_phrase("Hello world", phrases)
    assert res["woke"] is False
    assert res["command_text"] == ""

def test_voice_settings_privacy_defaults():
    settings = get_voice_settings()
    # By default, wake listening is disabled
    assert settings.get("wake_listening_enabled") is False
    # By default, microphone is disabled
    assert settings.get("voice_enabled") is False
    # Redaction should be enabled by default
    assert settings.get("redact_transcripts", True) is True

def test_session_manager_transcript_redaction():
    session = VoiceSessionManager()
    
    # Redaction test
    secret = "s" + "k" + "-" + "1234567890abcdef1234567890abcdef"
    transcript = f"My key is {secret}"
    res = session.simulate_voice_command(transcript)
    
    # Secret should not be visible in raw redacted form
    assert secret[:3] not in res.get("transcript", "") or "REDACTED" in res.get("transcript_redacted", True)

def test_voice_enable_requires_confirmation():
    parser = build_parser()
    args = parser.parse_args(["voice", "enable"])
    
    # Dispatch should return error dict
    res = dispatch(args)
    assert res.get("status") == "error"
    assert "--confirm true" in res.get("message", "")

def test_voice_wake_enable_requires_confirmation():
    parser = build_parser()
    args = parser.parse_args(["voice", "wake-enable"])
    
    res = dispatch(args)
    assert res.get("status") == "error"
    assert "--confirm true" in res.get("message", "")

@patch("runtime.voice.session.get_voice_settings")
def test_simulate_voice_command(mock_get_settings):
    mock_get_settings.return_value = {
        "voice_enabled": True,
        "wake_listening_enabled": True,
        "assistant_name": "Liuant",
        "wake_phrases": ["Hey Liuant"],
        "voice_reply_enabled": False
    }
    session = VoiceSessionManager()
    res = session.simulate_voice_command("Hey Liuant, show system status")
    
    assert res.get("status") == "completed"
    assert res.get("wake_detected") is True
    assert res.get("command_text") == "show system status"
    assert "intent_result" in res
    assert res["intent_result"].get("intent") == "system_status"

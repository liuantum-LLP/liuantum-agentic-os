from __future__ import annotations

import logging
import subprocess
import sys

logger = logging.getLogger("liuant.voice.tts")

class TextToSpeechProvider:
    def speak(self, text: str) -> dict:
        raise NotImplementedError("Subclasses must implement speak()")

class MockTTSProvider(TextToSpeechProvider):
    def speak(self, text: str) -> dict:
        return {
            "success": True,
            "provider": "mock",
            "text": text,
            "audio_duration_seconds": max(1.0, len(text) * 0.07),
            "mock_path": "workspace/outputs/speech.wav"
        }

class SystemTTSProvider(TextToSpeechProvider):
    def speak(self, text: str) -> dict:
        # Darwin platform supports the native 'say' command
        if sys.platform == "darwin":
            try:
                subprocess.run(["say", text], check=True, timeout=10)
                return {
                    "success": True,
                    "provider": "system",
                    "text": text,
                    "method": "say"
                }
            except Exception as e:
                logger.warning(f"Failed to use macOS say command: {e}")
                
        # If not macOS or if command fails, fall back to logging
        logger.info(f"[TTS SYSTEM FALLBACK] {text}")
        return {
            "success": True,
            "provider": "system",
            "text": text,
            "method": "log_fallback"
        }

class OpenAI_TTSProvider(TextToSpeechProvider):
    def speak(self, text: str) -> dict:
        # Stub wrapper for OpenAI TTS endpoint, fall back to mock
        return MockTTSProvider().speak(text)

def get_tts_provider(provider_name: str) -> TextToSpeechProvider:
    provider_name = (provider_name or "").lower().strip()
    if provider_name == "system":
        return SystemTTSProvider()
    elif provider_name == "openai_tts":
        return OpenAI_TTSProvider()
    return MockTTSProvider()

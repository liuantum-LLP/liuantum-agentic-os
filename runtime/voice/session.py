from __future__ import annotations

import logging
import re
from typing import Any
from runtime.voice.settings import get_voice_settings
from runtime.voice.wake import detect_wake_phrase
from runtime.voice.stt import get_stt_provider
from runtime.voice.tts import get_tts_provider
from runtime.chat.intent_router import route_chat_message

logger = logging.getLogger("liuant.voice.session")

def redact_secrets(text: str) -> str:
    if not text:
        return text
    # Pattern for sk-... (e.g. sk-Proj...)
    text = re.sub(r"\bsk-[a-zA-Z0-9]{20,}\b", "[REDACTED_API_KEY]", text)
    # Pattern for AIza...
    text = re.sub(r"\bAIza[0-9A-Za-z\-_]{35}\b", "[REDACTED_API_KEY]", text)
    # Pattern for Bearer <token>
    text = re.sub(r"\bBearer\s+[a-zA-Z0-9\-\._~\+\/]+=*", "Bearer [REDACTED_TOKEN]", text)
    # Pattern for password=something
    text = re.sub(r"\bpassword\s*=\s*[^\s]+", "password=[REDACTED_PASSWORD]", text, flags=re.IGNORECASE)
    # Pattern for AWS keys
    text = re.sub(r"\bAWS_ACCESS_KEY_ID\s*=\s*[^\s]+", "AWS_ACCESS_KEY_ID=[REDACTED_KEY]", text)
    text = re.sub(r"\bAWS_SECRET_ACCESS_KEY\s*=\s*[^\s]+", "AWS_SECRET_ACCESS_KEY=[REDACTED_KEY]", text)
    return text

class VoiceSessionManager:
    def __init__(self):
        self.state = "idle"  # idle, listening, processing, speaking
        
    def get_status(self) -> dict[str, Any]:
        settings = get_voice_settings()
        return {
            "state": self.state,
            "voice_enabled": settings.get("voice_enabled", False),
            "wake_listening_enabled": settings.get("wake_listening_enabled", False),
            "assistant_name": settings.get("assistant_name", "Liuant")
        }
        
    def process_audio(self, audio_source: str) -> dict[str, Any]:
        settings = get_voice_settings()
        if not settings.get("voice_enabled"):
            return {
                "status": "disabled",
                "message": "Voice assistant is disabled."
            }
            
        stt = get_stt_provider(settings.get("stt_provider", "local_mock"))
        self.state = "processing"
        try:
            transcript = stt.transcribe(audio_source)
        except Exception as e:
            self.state = "idle"
            return {
                "status": "error",
                "message": f"STT Transcription failed: {e}"
            }
            
        return self.simulate_voice_command(transcript)

    def simulate_voice_command(self, transcript: str) -> dict[str, Any]:
        settings = get_voice_settings()
        if not settings.get("voice_enabled"):
            return {
                "status": "disabled",
                "message": "Voice assistant is disabled."
            }
            
        # Transcript Redaction
        original_transcript = transcript
        is_redacted = False
        if settings.get("redact_transcripts", True):
            transcript = redact_secrets(transcript)
            if transcript != original_transcript:
                is_redacted = True

        # Log transcript if enabled (must never log raw secrets)
        if settings.get("store_transcripts", False):
            # Log the redacted version
            logger.info(f"[Voice Audit Logs] Transcript: {transcript}")

        # Wake Word Detection
        wake_info = detect_wake_phrase(transcript, settings.get("wake_phrases", []))
        
        # If wake word listening is turned on but no wake phrase was detected:
        if settings.get("wake_listening_enabled", False) and not wake_info["woke"]:
            self.state = "idle"
            return {
                "status": "ignored",
                "wake_detected": False,
                "transcript": transcript,
                "transcript_redacted": is_redacted,
                "message": "Transcript did not match wake phrase."
            }
            
        # Wake response greeting:
        response_text = ""
        command_text = wake_info.get("command_text", "").strip()
        
        # Wake-only Flow (e.g. "Hey Liu")
        if wake_info["woke"] and not command_text:
            response_text = settings.get("wake_response", "Yes, what do you want?")
            self.state = "speaking"
            tts = get_tts_provider(settings.get("tts_provider", "mock"))
            tts_res = tts.speak(response_text)
            self.state = "idle"
            
            return {
                "status": "waiting_for_command",
                "wake_detected": True,
                "transcript": transcript,
                "transcript_redacted": is_redacted,
                "response_text": response_text,
                "tts_result": tts_res
            }
            
        # Command execution:
        actual_command = command_text if wake_info["woke"] else transcript.strip()
        
        # Route to Intent Router
        self.state = "processing"
        try:
            intent_result = route_chat_message(actual_command)
            response_text = intent_result.get("message", "Processed successfully.")
        except Exception as e:
            response_text = f"An error occurred routing command: {e}"
            intent_result = {"status": "error", "message": response_text}
            
        # Redact secrets from output response text before speaking
        if settings.get("redact_transcripts", True):
            response_text = redact_secrets(response_text)
            
        # TTS Synthesize response
        tts_res = None
        if settings.get("voice_reply_enabled", True):
            self.state = "speaking"
            tts = get_tts_provider(settings.get("tts_provider", "mock"))
            tts_res = tts.speak(response_text)
            
        self.state = "idle"
        
        return {
            "status": "completed",
            "wake_detected": wake_info["woke"],
            "transcript": transcript,
            "transcript_redacted": is_redacted,
            "command_text": actual_command,
            "response_text": response_text,
            "intent_result": intent_result,
            "tts_result": tts_res
        }

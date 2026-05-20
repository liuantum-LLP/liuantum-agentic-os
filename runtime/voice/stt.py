from __future__ import annotations

import os

class SpeechToTextProvider:
    def transcribe(self, audio_source: str) -> str:
        raise NotImplementedError("Subclasses must implement transcribe()")

class LocalMockSTTProvider(SpeechToTextProvider):
    def transcribe(self, audio_source: str) -> str:
        if not audio_source:
            return ""
        name = os.path.basename(audio_source).lower()
        if "audio_status" in name or "status" in name:
            return "show system status"
        elif "audio_hey_liuant" in name or "hey_liuant" in name:
            return "Hey Liuant"
        elif "audio_hey_liu_workflows" in name or "hey_liu_workflows" in name:
            return "Hey Liu, list workflows"
        elif "audio_hey_liu" in name or "hey_liu" in name:
            return "Hey Liu"
        elif "workflow" in name:
            return "run workflow backup"
        elif "nonsense" in name or "invalid" in name:
            return "nonsense words"
        
        # If it doesn't end with audio extension, it might be a mock transcript text itself passed for testing
        if not (audio_source.endswith(".wav") or audio_source.endswith(".mp3") or audio_source.endswith(".ogg")):
            return audio_source
            
        return "show system status"

class SystemSTTProvider(SpeechToTextProvider):
    def transcribe(self, audio_source: str) -> str:
        # Fall back to local mock for v2.9.0 simulation stability
        return LocalMockSTTProvider().transcribe(audio_source)

class OpenAI_STTProvider(SpeechToTextProvider):
    def transcribe(self, audio_source: str) -> str:
        # Stub wrapper for OpenAI Whisper API
        return LocalMockSTTProvider().transcribe(audio_source)

def get_stt_provider(provider_name: str) -> SpeechToTextProvider:
    provider_name = (provider_name or "").lower().strip()
    if provider_name == "system":
        return SystemSTTProvider()
    elif provider_name == "openai_stt":
        return OpenAI_STTProvider()
    return LocalMockSTTProvider()

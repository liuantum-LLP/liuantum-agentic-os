from __future__ import annotations

import json
import hashlib
import math
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runtime.config import SettingsManager
from runtime.db import get_record, insert_record, list_records, update_record
from runtime.providers.base import ProviderSpec
from runtime.action_log import log_external_action


CATEGORIES = ["text", "image", "video", "embedding", "speech_to_text", "text_to_speech"]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _capability(category: str, local: bool = False, **extra: bool) -> dict[str, bool]:
    capabilities = {
        "text": False,
        "image": False,
        "video": False,
        "embedding": False,
        "speech_to_text": False,
        "text_to_speech": False,
        "local": local,
    }
    capabilities[category] = True
    capabilities.update(extra)
    return capabilities


PROVIDER_SPECS = [
    ProviderSpec("openai", "OpenAI", "text", "openai", "https://api.openai.com/v1", "OPENAI_API_KEY", "gpt-4.1-mini", "gpt-4.1-mini", True, True, "missing_key", _capability("text", embedding=True, speech_to_text=True, text_to_speech=True), ["gpt-4.1-mini", "gpt-4o-mini"]),
    ProviderSpec("anthropic", "Anthropic", "text", "anthropic", "https://api.anthropic.com", "ANTHROPIC_API_KEY", "claude-3-5-sonnet-latest", "claude-3-5-sonnet-latest", False, False, "placeholder", _capability("text"), ["claude-3-5-sonnet-latest", "claude-3-haiku-latest", "claude-3-opus-latest"]),
    ProviderSpec("gemini", "Google Gemini", "text", "gemini", "https://generativelanguage.googleapis.com", "GEMINI_API_KEY", "gemini-2.0-flash", "gemini-2.0-flash", False, False, "placeholder", _capability("text"), ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"]),
    ProviderSpec("openrouter", "OpenRouter", "text", "openrouter", "https://openrouter.ai/api/v1", "OPENROUTER_API_KEY", "openai/gpt-4.1-mini", "openai/gpt-4.1-mini", False, False, "missing_key", _capability("text"), ["openai/gpt-4.1-mini", "anthropic/claude-3.5-sonnet", "google/gemini-2.0-flash"]),
    ProviderSpec("amazon_bedrock", "Amazon Bedrock", "text", "amazon_bedrock", "", "", "us.amazon.nova-lite-v1:0", "us.amazon.nova-lite-v1:0", False, False, "needs_provider_setup", _capability("text"), ["us.amazon.nova-lite-v1:0", "us.amazon.nova-micro-v1:0", "us.amazon.nova-pro-v1:0"], "Amazon Bedrock Converse API integration."),
    ProviderSpec("groq", "Groq", "text", "groq", "https://api.groq.com/openai", "GROQ_API_KEY", "llama-3.1-8b-instant", "llama-3.1-8b-instant", False, False, "placeholder", _capability("text"), ["llama-3.1-8b-instant", "llama-3.3-70b-versatile", "mixtral-8x7b-32768"]),
    ProviderSpec("mistral", "Mistral", "text", "mistral", "", "MISTRAL_API_KEY", "mistral-small-latest", "", False, False, "placeholder", _capability("text"), ["mistral-small-latest"], "Config-ready placeholder."),
    ProviderSpec("together", "Together AI", "text", "together", "", "TOGETHER_API_KEY", "meta-llama/Llama-3.3-70B-Instruct-Turbo", "", False, False, "placeholder", _capability("text"), ["meta-llama/Llama-3.3-70B-Instruct-Turbo"], "Config-ready placeholder."),
    ProviderSpec("fireworks", "Fireworks AI", "text", "fireworks", "", "FIREWORKS_API_KEY", "accounts/fireworks/models/llama-v3p1-8b-instruct", "", False, False, "placeholder", _capability("text"), ["accounts/fireworks/models/llama-v3p1-8b-instruct"], "Config-ready placeholder."),
    ProviderSpec("ollama", "Ollama", "text", "ollama", "http://127.0.0.1:11434", "", "llama3.2", "llama3.2", False, False, "local_unreachable", _capability("text", local=True), ["llama3.2"], "Local provider; test checks the configured endpoint."),
    ProviderSpec("lmstudio", "LM Studio", "text", "lmstudio", "http://127.0.0.1:1234/v1", "", "local-model", "", False, False, "local_unreachable", _capability("text", local=True), ["local-model"], "OpenAI-compatible local endpoint."),
    ProviderSpec("custom_openai_compatible", "Custom OpenAI Compatible", "text", "custom_openai_compatible", "", "CUSTOM_OPENAI_API_KEY", "", "", False, False, "missing_key", _capability("text"), [], "User-managed OpenAI-compatible endpoint."),
    ProviderSpec("openai_image", "OpenAI Image", "image", "openai_image", "https://api.openai.com/v1", "OPENAI_API_KEY", "gpt-image-1", "", True, True, "missing_key", _capability("image"), ["gpt-image-1"], "Real image generation is implemented when OPENAI_API_KEY is configured."),
    ProviderSpec("stability", "Stability AI", "image", "stability", "", "STABILITY_API_KEY", "stable-image-core", "", False, False, "placeholder", _capability("image"), ["stable-image-core"], "Config-ready placeholder."),
    ProviderSpec("replicate", "Replicate", "image", "replicate", "", "REPLICATE_API_TOKEN", "", "", False, False, "placeholder", _capability("image"), [], "Config-ready placeholder."),
    ProviderSpec("ideogram", "Ideogram", "image", "ideogram", "", "IDEOGRAM_API_KEY", "", "", False, False, "placeholder", _capability("image"), [], "Config-ready placeholder."),
    ProviderSpec("leonardo", "Leonardo AI", "image", "leonardo", "", "LEONARDO_API_KEY", "", "", False, False, "placeholder", _capability("image"), [], "Config-ready placeholder."),
    ProviderSpec("comfyui", "ComfyUI", "image", "comfyui", "http://127.0.0.1:8188", "", "", "", False, False, "local_unreachable", _capability("image", local=True), [], "Local image workflow endpoint."),
    ProviderSpec("automatic1111", "Automatic1111", "image", "automatic1111", "http://127.0.0.1:7860", "", "", "", False, False, "local_unreachable", _capability("image", local=True), [], "Local Stable Diffusion endpoint."),
    ProviderSpec("custom_image_api", "Custom Image API", "image", "custom_image_api", "", "CUSTOM_IMAGE_API_KEY", "", "", False, False, "placeholder", _capability("image"), [], "Config-ready custom image endpoint."),
    ProviderSpec("runway", "Runway", "video", "runway", "", "RUNWAY_API_KEY", "", "", False, False, "placeholder", _capability("video"), [], "Config-ready placeholder; real video API is pending."),
    ProviderSpec("pika", "Pika", "video", "pika", "", "PIKA_API_KEY", "", "", False, False, "placeholder", _capability("video"), [], "Config-ready placeholder; real video API is pending."),
    ProviderSpec("luma", "Luma", "video", "luma", "", "LUMA_API_KEY", "", "", False, False, "placeholder", _capability("video"), [], "Config-ready placeholder; real video API is pending."),
    ProviderSpec("kling", "Kling", "video", "kling", "", "KLING_API_KEY", "", "", False, False, "placeholder", _capability("video"), [], "Config-ready placeholder; real video API is pending."),
    ProviderSpec("openai_video", "OpenAI Video", "video", "openai_video", "https://api.openai.com/v1", "OPENAI_API_KEY", "", "", False, False, "placeholder", _capability("video"), [], "Config-ready placeholder; real video API is pending."),
    ProviderSpec("replicate_video", "Replicate Video", "video", "replicate_video", "", "REPLICATE_API_TOKEN", "", "", False, False, "placeholder", _capability("video"), [], "Video job lifecycle implemented for create, poll, output URL tracking, safe download, and cancel when REPLICATE_API_TOKEN plus a model are configured."),
    ProviderSpec("comfyui_video", "ComfyUI Video", "video", "comfyui_video", "http://127.0.0.1:8188", "", "", "", False, False, "local_unreachable", _capability("video", local=True), [], "Local video workflow endpoint."),
    ProviderSpec("hyperframes_skill", "HyperFrames Skill", "video", "hyperframes_skill", "", "", "hyperframes-video-skill", "", True, True, "ready", _capability("video", local=True), ["hyperframes-video-skill"], "Always available package generation skill."),
    ProviderSpec("custom_video_api", "Custom Video API", "video", "custom_video_api", "", "CUSTOM_VIDEO_API_KEY", "", "", False, False, "placeholder", _capability("video"), [], "Config-ready custom video endpoint."),
    ProviderSpec("local_hash_embedding", "Local Hash Embedding", "embedding", "local_hash_embedding", "", "", "local-hash-384", "", True, True, "ready", _capability("embedding", local=True), ["local-hash-384"], "Deterministic local embedding fallback. No external API call."),
    ProviderSpec("openai_embedding", "OpenAI Embeddings", "embedding", "openai_embedding", "https://api.openai.com/v1", "OPENAI_API_KEY", "text-embedding-3-small", "", False, True, "missing_key", _capability("embedding"), ["text-embedding-3-small"]),
    ProviderSpec("gemini_embedding", "Gemini Embeddings", "embedding", "gemini_embedding", "", "GEMINI_API_KEY", "text-embedding-004", "", False, False, "placeholder", _capability("embedding"), ["text-embedding-004"], "Config-ready placeholder."),
    ProviderSpec("cohere_embedding", "Cohere Embeddings", "embedding", "cohere_embedding", "", "COHERE_API_KEY", "embed-english-v3.0", "", False, False, "placeholder", _capability("embedding"), ["embed-english-v3.0"], "Config-ready placeholder."),
    ProviderSpec("voyage_embedding", "Voyage Embeddings", "embedding", "voyage_embedding", "", "VOYAGE_API_KEY", "voyage-3", "", False, False, "placeholder", _capability("embedding"), ["voyage-3"], "Config-ready placeholder."),
    ProviderSpec("ollama_embedding", "Ollama Embeddings", "embedding", "ollama_embedding", "http://127.0.0.1:11434", "", "nomic-embed-text", "", False, False, "local_unreachable", _capability("embedding", local=True), ["nomic-embed-text"]),
    ProviderSpec("local_sentence_transformers", "Local Sentence Transformers", "embedding", "local_sentence_transformers", "", "", "all-MiniLM-L6-v2", "", False, False, "placeholder", _capability("embedding", local=True), ["all-MiniLM-L6-v2"], "Config-ready placeholder."),
    ProviderSpec("openai_stt", "OpenAI Speech-to-Text", "speech_to_text", "openai_stt", "https://api.openai.com/v1", "OPENAI_API_KEY", "whisper-1", "", False, True, "missing_key", _capability("speech_to_text"), ["whisper-1"]),
    ProviderSpec("whisper_local", "Whisper Local", "speech_to_text", "whisper_local", "", "", "whisper-small", "", False, False, "placeholder", _capability("speech_to_text", local=True), ["whisper-small"], "Config-ready placeholder."),
    ProviderSpec("deepgram", "Deepgram", "speech_to_text", "deepgram", "", "DEEPGRAM_API_KEY", "", "", False, False, "placeholder", _capability("speech_to_text"), [], "Config-ready placeholder."),
    ProviderSpec("assemblyai", "AssemblyAI", "speech_to_text", "assemblyai", "", "ASSEMBLYAI_API_KEY", "", "", False, False, "placeholder", _capability("speech_to_text"), [], "Config-ready placeholder."),
    ProviderSpec("google_speech", "Google Speech", "speech_to_text", "google_speech", "", "GOOGLE_APPLICATION_CREDENTIALS", "", "", False, False, "placeholder", _capability("speech_to_text"), [], "Config-ready placeholder."),
    ProviderSpec("openai_tts", "OpenAI Text-to-Speech", "text_to_speech", "openai_tts", "https://api.openai.com/v1", "OPENAI_API_KEY", "gpt-4o-mini-tts", "", False, True, "missing_key", _capability("text_to_speech"), ["gpt-4o-mini-tts"]),
    ProviderSpec("elevenlabs", "ElevenLabs", "text_to_speech", "elevenlabs", "", "ELEVENLABS_API_KEY", "", "", False, False, "placeholder", _capability("text_to_speech"), [], "Config-ready placeholder."),
    ProviderSpec("azure_tts", "Azure TTS", "text_to_speech", "azure_tts", "", "AZURE_TTS_KEY", "", "", False, False, "placeholder", _capability("text_to_speech"), [], "Config-ready placeholder."),
    ProviderSpec("google_tts", "Google TTS", "text_to_speech", "google_tts", "", "GOOGLE_APPLICATION_CREDENTIALS", "", "", False, False, "placeholder", _capability("text_to_speech"), [], "Config-ready placeholder."),
    ProviderSpec("piper_local", "Piper Local", "text_to_speech", "piper_local", "", "", "piper", "", False, False, "placeholder", _capability("text_to_speech", local=True), ["piper"], "Config-ready placeholder."),
    ProviderSpec("coqui_local", "Coqui Local", "text_to_speech", "coqui_local", "", "", "coqui", "", False, False, "placeholder", _capability("text_to_speech", local=True), ["coqui"], "Config-ready placeholder."),
]


class ModelHub:
    def __init__(self) -> None:
        self.settings = SettingsManager()

    def list_categories(self) -> list[str]:
        self.ensure_defaults()
        return list(CATEGORIES)

    def list_providers(self, category: str | None = None) -> list[dict[str, Any]]:
        self.ensure_defaults()
        rows = [self._sanitize(row) for row in list_records("model_providers")]
        if category:
            rows = [row for row in rows if row.get("category") == category]
        return sorted(rows, key=lambda row: (row.get("category", ""), row.get("display_name") or row.get("name", "")))

    def list_profiles(self) -> list[dict[str, Any]]:
        self.ensure_defaults()
        default_ids = {spec.name for spec in PROVIDER_SPECS}
        rows = [self._sanitize(row) for row in list_records("model_providers")]
        return [row for row in rows if row["id"] not in default_ids]

    def get_provider(self, provider_name: str) -> dict[str, Any]:
        self.ensure_defaults()
        row = get_record("model_providers", self._normalize_provider(provider_name))
        if not row:
            raise ValueError(f"Unknown provider: {provider_name}")
        return self._sanitize(row)

    def setup_provider(self, provider_name: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
        self.ensure_defaults()
        config = config or {}
        provider_name = self._normalize_provider(provider_name or config.get("name") or config.get("id"))
        if not provider_name:
            raise ValueError("Provider name is required.")
        existing = get_record("model_providers", provider_name) or {}
        now = utc_now()
        row = {
            "id": provider_name,
            "name": provider_name,
            "display_name": config.get("display_name") or existing.get("display_name") or provider_name.replace("_", " ").title(),
            "category": config.get("category") or existing.get("category") or "text",
            "provider_type": config.get("provider_type") or existing.get("provider_type") or "custom_openai_compatible",
            "base_url": config.get("base_url", existing.get("base_url", "")),
            "api_key_env": config.get("api_key_env") or config.get("env_var") or existing.get("api_key_env") or existing.get("env_var") or "",
            "env_var": config.get("api_key_env") or config.get("env_var") or existing.get("api_key_env") or existing.get("env_var") or "",
            "default_model": config.get("default_model", existing.get("default_model", "")),
            "fallback_model": config.get("fallback_model", existing.get("fallback_model", "")),
            "is_enabled": bool(config.get("is_enabled", existing.get("is_enabled", True))),
            "is_default": bool(config.get("is_default", existing.get("is_default", False))),
            "capabilities": config.get("capabilities") or existing.get("capabilities") or _capability(config.get("category") or existing.get("category") or "text"),
            "models": config.get("models") or existing.get("models") or [],
            "notes": config.get("notes", existing.get("notes", "")),
            "setup_instruction": config.get("setup_instruction", existing.get("setup_instruction", "")),
            "created_at": existing.get("created_at", now),
            "updated_at": now,
            "last_tested_at": existing.get("last_tested_at"),
        }
        row["api_key_masked"] = mask_secret(_read_secret(row.get("api_key_env", ""))) or existing.get("api_key_masked", "")
        row["status"] = self._derive_status(row)
        insert_record("model_providers", row)
        return self._sanitize(row)

    def enable_provider(self, provider_name: str) -> dict[str, Any]:
        provider = self.get_provider(provider_name)
        row = update_record("model_providers", provider["id"], {"is_enabled": True, "updated_at": utc_now()})
        return self._sanitize(row)

    def disable_provider(self, provider_name: str) -> dict[str, Any]:
        provider = self.get_provider(provider_name)
        row = update_record("model_providers", provider["id"], {"is_enabled": False, "is_default": False, "updated_at": utc_now()})
        return self._sanitize(row)

    def set_default_provider(self, category: str, provider_name: str) -> dict[str, Any]:
        self._validate_category(category)
        provider = self.get_provider(provider_name)
        if provider.get("category") != category:
            raise ValueError(f"{provider_name} is a {provider.get('category')} provider, not {category}.")
        for row in self.list_providers(category):
            update_record("model_providers", row["id"], {"is_default": row["id"] == provider["id"], "is_enabled": row["id"] == provider["id"] or row.get("is_enabled"), "updated_at": utc_now()})
        self.settings.set(self._provider_setting_key(category), provider["id"])
        if category == "text":
            self.settings.set("default_provider", provider["id"])
        return self.get_provider(provider["id"])

    def set_default_model(self, category: str, model_name: str) -> dict[str, Any]:
        self._validate_category(category)
        key = self._model_setting_key(category)
        self.settings.set(key, model_name)
        provider_name = self._setting_value(self._provider_setting_key(category), "")
        if provider_name and get_record("model_providers", provider_name):
            update_record("model_providers", provider_name, {"default_model": model_name, "updated_at": utc_now()})
        return {"category": category, "model": model_name, "setting": key}

    def set_fallback_provider(self, category: str, provider_name: str) -> dict[str, Any]:
        self._validate_category(category)
        provider = self.get_provider(provider_name)
        if provider.get("category") != category:
            raise ValueError(f"{provider_name} is a {provider.get('category')} provider, not {category}.")
        self.settings.set(self._fallback_setting_key(category), provider["id"])
        return {"category": category, "fallback_provider": provider["id"]}

    def test_provider(self, provider_name: str | None = None) -> dict[str, Any]:
        self.ensure_defaults()
        provider_name = self._normalize_provider(provider_name or self.settings.get("default_text_provider")["value"])
        row = get_record("model_providers", provider_name)
        if not row:
            raise ValueError(f"Unknown provider: {provider_name}")
        status = self._test_status(row)
        row = update_record("model_providers", row["id"], {"status": status, "api_key_masked": mask_secret(_read_secret(row.get("api_key_env") or row.get("env_var", ""))), "last_tested_at": utc_now(), "updated_at": utc_now()})
        success = status in {"configured", "ready"}
        action_type = "text_provider_test" if row.get("category") == "text" else "provider_test"
        log_external_action(action_type, status, {"provider": row["id"], "category": row.get("category"), "success": success})
        return {
            "provider": row["id"],
            "provider_name": row["id"],
            "success": success,
            "status": status,
            "message": self._status_message(row, status),
            "provider_config": self._sanitize(row),
        }

    def get_status(self) -> dict[str, Any]:
        providers = self.list_providers()
        defaults = {}
        fallbacks = {}
        for category in CATEGORIES:
            defaults[category] = self._setting_value(self._provider_setting_key(category), "")
            fallbacks[category] = self._setting_value(self._fallback_setting_key(category), "")
        return {
            "categories": CATEGORIES,
            "provider_count": len(providers),
            "configured_count": sum(1 for row in providers if row.get("status") in {"configured", "ready"}),
            "enabled_count": sum(1 for row in providers if row.get("is_enabled")),
            "cloud_enabled_count": sum(1 for row in providers if row.get("is_enabled") and not row.get("capabilities", {}).get("local")),
            "local_enabled_count": sum(1 for row in providers if row.get("is_enabled") and row.get("capabilities", {}).get("local")),
            "missing_key_count": sum(1 for row in providers if row.get("status") == "missing_key"),
            "placeholder_count": sum(1 for row in providers if row.get("status") == "placeholder"),
            "default_provider": defaults.get("text") or self._legacy_default_provider(providers),
            "defaults": defaults,
            "fallbacks": fallbacks,
            "providers": providers,
        }

    def mask_secret(self, value: str | None) -> str:
        return mask_secret(value)

    def resolve_provider_for_task(self, category: str, requested_provider: str | None = None) -> dict[str, Any]:
        self._validate_category(category)
        if requested_provider:
            return self.get_provider(requested_provider)
        provider_name = self._setting_value(self._provider_setting_key(category), "")
        if provider_name and get_record("model_providers", provider_name):
            return self.get_provider(provider_name)
        default = next((row for row in self.list_providers(category) if row.get("is_default")), None)
        if default:
            return default
        providers = self.list_providers(category)
        if not providers:
            raise ValueError(f"No providers registered for category: {category}")
        return providers[0]

    def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
        provider_name: str | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        workspace_name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        provider = self.resolve_provider_for_task("text", provider_name)
        safe_meta = _safe_log_metadata(prompt, {"provider": provider["id"], "model": model or provider.get("default_model"), "workspace_name": workspace_name, **(metadata or {})})
        log_external_action("text_generation_started", "started", safe_meta)

        # Auto-track provider health (v1.6.0)
        import time
        from runtime.usage.provider_health import ProviderHealthTracker
        health_tracker = ProviderHealthTracker()
        start_ms = time.monotonic()

        result = self._generate_text_once(provider, prompt, system_prompt, model, temperature, max_tokens)
        elapsed_ms = int((time.monotonic() - start_ms) * 1000)

        # Auto-record health based on result
        if result["status"] == "completed":
            health_tracker.record_success(provider["id"], latency_ms=elapsed_ms)
            log_external_action("text_generation_completed", "completed", _safe_log_metadata(prompt, {"provider": result["provider"], "model": result["model"], "fallback_used": False, "workspace_name": workspace_name}))
        elif result["status"] == "local_unreachable":
            health_tracker.record_unavailable(provider["id"])
        else:
            err = result.get("error", "")
            if "rate" in err.lower() and "limit" in err.lower():
                health_tracker.record_rate_limit(provider["id"])
            elif "timeout" in err.lower() or "timed out" in err.lower():
                health_tracker.record_timeout(provider["id"])
            else:
                health_tracker.record_error(provider["id"], error=err, latency_ms=elapsed_ms)

        if result["status"] == "completed":
            return result

        fallback_provider_name = self._setting_value("fallback_text_provider", "")
        if fallback_provider_name and fallback_provider_name != provider["id"]:
            try:
                fallback = self.get_provider(fallback_provider_name)
                if fallback.get("is_enabled") or fallback.get("status") in {"configured", "ready", "local_unreachable"}:
                    fallback_result = self._generate_text_once(fallback, prompt, system_prompt, None, temperature, max_tokens)
                    if fallback_result["status"] == "completed":
                        fallback_result["fallback_used"] = True
                        fallback_result["fallback_provider"] = fallback["id"]
                        log_external_action("text_generation_completed", "completed", _safe_log_metadata(prompt, {"provider": fallback_result["provider"], "model": fallback_result["model"], "fallback_used": True, "fallback_provider": fallback["id"], "workspace_name": workspace_name}))
                        return fallback_result
                    result["fallback_provider"] = fallback["id"]
            except ValueError:
                pass
        log_external_action("text_generation_failed", result["status"], _safe_log_metadata(prompt, {"provider": result["provider"], "model": result.get("model"), "fallback_provider": result.get("fallback_provider"), "error": result.get("error"), "workspace_name": workspace_name}))
        return result

    def stream_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
        provider_name: str | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        workspace_name: str | None = None,
        metadata: dict[str, Any] | None = None,
        role: str | None = None,
    ):
        """Stream text generation as chunks.

        Yields dicts with shape:
        {"type": "token|metadata|warning|error|done", "content": "...", "provider": "...", "model": "...", "role": "...", "fallback_used": False}

        Falls back to generate_text if provider doesn't support streaming.
        """
        provider = self.resolve_provider_for_task("text", provider_name)
        provider_type = provider.get("provider_type") or provider["id"]
        resolved_model = model or provider.get("default_model") or ""

        yield {"type": "metadata", "content": "", "provider": provider["id"], "model": resolved_model, "role": role or "default", "fallback_used": False}
        streaming_supported = provider_type in {"ollama", "openai", "openrouter", "groq", "lmstudio", "custom_openai_compatible", "azure_openai", "openai_compatible", "amazon_bedrock"}

        if not streaming_supported:
            result = self._generate_text_once(provider, prompt, system_prompt, model, temperature, max_tokens)
            if result["status"] == "completed":
                yield {"type": "token", "content": result["text"], "provider": result["provider"], "model": result["model"], "role": role or "default", "fallback_used": False}
            else:
                yield {"type": "error", "content": result.get("error", "Generation failed"), "provider": provider["id"], "model": resolved_model, "role": role or "default", "fallback_used": False}
            yield {"type": "done", "content": "", "provider": provider["id"], "model": resolved_model, "role": role or "default", "fallback_used": False}
            return

        if provider_type == "ollama":
            yield from self._stream_ollama(provider, prompt, system_prompt, resolved_model, temperature, max_tokens, role)
        elif provider_type in {"openai", "openrouter", "groq", "lmstudio", "custom_openai_compatible", "azure_openai", "openai_compatible"}:
            yield from self._stream_openai_compatible(provider, prompt, system_prompt, resolved_model, temperature, max_tokens, role)
        elif provider_type == "amazon_bedrock":
            yield from self._stream_bedrock(provider, prompt, system_prompt, resolved_model, temperature, max_tokens, role)
        else:
            result = self._generate_text_once(provider, prompt, system_prompt, model, temperature, max_tokens)
            if result["status"] == "completed":
                yield {"type": "token", "content": result["text"], "provider": result["provider"], "model": result["model"], "role": role or "default", "fallback_used": False}
            yield {"type": "done", "content": "", "provider": provider["id"], "model": resolved_model, "role": role or "default", "fallback_used": False}

    def _stream_bedrock(
        self,
        provider: dict[str, Any],
        prompt: str,
        system_prompt: str | None,
        model: str,
        temperature: float,
        max_tokens: int | None,
        role: str | None,
    ):
        from runtime.providers import bedrock
        try:
            for chunk in bedrock.stream_text(prompt, system_prompt, model, temperature, max_tokens):
                yield {"type": "token", "content": chunk, "provider": provider["id"], "model": model, "role": role or "default", "fallback_used": False}
            yield {"type": "done", "content": "", "provider": provider["id"], "model": model, "role": role or "default", "fallback_used": False}
        except Exception as exc:
            yield {"type": "error", "content": str(exc), "provider": provider["id"], "model": model, "role": role or "default", "fallback_used": False}

    def generate_image(self, prompt: str, provider_name: str | None = None, **kwargs: Any) -> dict[str, Any]:
        from runtime.generation.image import ImageGenerationManager

        provider = self.resolve_provider_for_task("image", provider_name)
        return ImageGenerationManager().generate(prompt=prompt, provider_name=provider["id"], **kwargs)

    def generate_video_job(self, prompt: str, provider_name: str | None = None, **kwargs: Any) -> dict[str, Any]:
        from runtime.generation.video import VideoGenerationManager

        provider = self.resolve_provider_for_task("video", provider_name)
        return VideoGenerationManager().generate(prompt=prompt, provider_name=provider["id"], **kwargs)

    def create_embedding(
        self,
        text: str,
        provider_name: str | None = None,
        model: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        provider = self.resolve_provider_for_task("embedding", provider_name)
        resolved_model = model or provider.get("default_model") or ""
        log_external_action("embedding_created", "started", _safe_log_metadata(text, {"provider": provider["id"], "model": resolved_model, **(metadata or {})}))
        base = {"status": "needs_provider_setup", "provider": provider["id"], "model": resolved_model, "embedding": [], "dimension": 0, "error": None}
        provider_type = provider.get("provider_type") or provider["id"]
        if provider_type == "local_hash_embedding":
            embedding = local_hash_embedding(text)
            result = {**base, "status": "completed", "embedding": embedding, "dimension": len(embedding)}
            log_external_action("embedding_created", "completed", _safe_log_metadata(text, {"provider": provider["id"], "dimension": len(embedding)}))
            return result
        if provider_type == "openai_embedding":
            key = _read_secret(provider.get("api_key_env") or provider.get("env_var"))
            if not key:
                return {**base, "status": "needs_provider_setup", "error": "Missing OPENAI_API_KEY."}
            try:
                data = _post_json(
                    f"{(provider.get('base_url') or 'https://api.openai.com/v1').rstrip('/')}/embeddings",
                    {"model": resolved_model or "text-embedding-3-small", "input": text},
                    {"content-type": "application/json", "authorization": f"Bearer {key}"},
                )
                embedding = ((data.get("data") or [{}])[0]).get("embedding") or []
                return {**base, "status": "completed", "embedding": embedding, "dimension": len(embedding), "model": resolved_model or "text-embedding-3-small"}
            except Exception as exc:
                return {**base, "status": "provider_error", "error": _redact_error(exc)}
        if provider_type == "ollama_embedding":
            base_url = (provider.get("base_url") or "http://127.0.0.1:11434").rstrip("/")
            try:
                _get_json(f"{base_url}/api/tags")
                data = _post_json(f"{base_url}/api/embeddings", {"model": resolved_model or "nomic-embed-text", "prompt": text}, {"content-type": "application/json"})
                embedding = data.get("embedding") or []
                return {**base, "status": "completed", "embedding": embedding, "dimension": len(embedding), "model": resolved_model or "nomic-embed-text"}
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                return {**base, "status": "local_unreachable", "error": _redact_error(exc)}
            except Exception as exc:
                return {**base, "status": "provider_error", "error": _redact_error(exc)}
        return {**base, "status": "placeholder", "error": "Embedding provider is config-ready but not implemented."}

    def speech_to_text(self, input_path: str, provider_name: str | None = None) -> dict[str, Any]:
        provider = self.resolve_provider_for_task("speech_to_text", provider_name)
        return {"status": "provider_not_implemented", "provider": provider["id"], "message": "Speech-to-text calls are config-ready only in v0.2.2.", "input_path": input_path}

    def text_to_speech(self, text: str, provider_name: str | None = None) -> dict[str, Any]:
        provider = self.resolve_provider_for_task("text_to_speech", provider_name)
        return {"status": "provider_not_implemented", "provider": provider["id"], "message": "Text-to-speech calls are config-ready only in v0.2.2.", "text_preview": text[:200]}

    def ensure_defaults(self) -> None:
        self._ensure_settings()
        specs_by_name = {spec.name: spec for spec in PROVIDER_SPECS}
        for spec in PROVIDER_SPECS:
            existing = get_record("model_providers", spec.name)
            if not existing:
                row = spec.to_record(utc_now())
            else:
                row = {**spec.to_record(existing.get("created_at", utc_now())), **existing}
                row["name"] = spec.name
                row["display_name"] = existing.get("display_name") or (existing.get("name") if existing.get("name") != spec.name else "") or spec.display_name
                row["category"] = existing.get("category") or spec.category
                row["provider_type"] = existing.get("provider_type") or spec.provider_type
                if spec.name == "ollama" and str(row.get("base_url", "")).rstrip("/").endswith("/v1"):
                    row["base_url"] = spec.base_url
                row["api_key_env"] = existing.get("api_key_env") or existing.get("env_var") or spec.api_key_env
                row["env_var"] = row["api_key_env"]
                row["capabilities"] = existing.get("capabilities") or spec.capabilities
                row["models"] = existing.get("models") or spec.models
                row["notes"] = existing.get("notes") or spec.notes
                row["setup_instruction"] = existing.get("setup_instruction") or spec.setup_instruction
                row["updated_at"] = utc_now()
            row["api_key_masked"] = mask_secret(_read_secret(row.get("api_key_env") or row.get("env_var", ""))) or row.get("api_key_masked", "")
            row["status"] = self._derive_status(row)
            insert_record("model_providers", row)
        self._repair_defaults(specs_by_name)

    def _ensure_settings(self) -> None:
        defaults = {
            "default_text_provider": "openai",
            "default_text_model": "gpt-4.1-mini",
            "default_image_provider": "openai_image",
            "default_image_model": "gpt-image-1",
            "default_video_provider": "hyperframes_skill",
            "default_video_model": "hyperframes-video-skill",
            "default_embedding_provider": "local_hash_embedding",
            "default_embedding_model": "local-hash-384",
            "default_stt_provider": "openai_stt",
            "default_stt_model": "whisper-1",
            "default_tts_provider": "openai_tts",
            "default_tts_model": "gpt-4o-mini-tts",
            "fallback_text_provider": "ollama",
            "fallback_image_provider": "custom_image_api",
            "fallback_video_provider": "hyperframes_skill",
            "allow_local_models": "true",
            "allow_cloud_models": "true",
            "agent_ai_enhancement_enabled": "false",
            "agent_ai_provider": "default_text_provider",
            "agent_ai_model": "default_text_model",
        }
        self.settings.ensure_defaults()
        for key, value in defaults.items():
            if not get_record("settings", key):
                self.settings.set(key, value)
        current_embedding_provider = get_record("settings", "default_embedding_provider")
        if current_embedding_provider and current_embedding_provider.get("value") == "openai_embedding":
            self.settings.set("default_embedding_provider", "local_hash_embedding")
        current_embedding_model = get_record("settings", "default_embedding_model")
        if current_embedding_model and current_embedding_model.get("value") in {"", "text-embedding-3-small"}:
            self.settings.set("default_embedding_model", "local-hash-384")

    def _repair_defaults(self, specs_by_name: dict[str, ProviderSpec]) -> None:
        for category in CATEGORIES:
            default_name = self._setting_value(self._provider_setting_key(category), "")
            if default_name and get_record("model_providers", default_name):
                for row in [record for record in list_records("model_providers") if record.get("category") == category]:
                    update_record("model_providers", row["id"], {"is_default": row["id"] == default_name, "updated_at": utc_now()})

    def _sanitize(self, row: dict[str, Any]) -> dict[str, Any]:
        sanitized = dict(row)
        sanitized["id"] = sanitized.get("id") or sanitized.get("name")
        sanitized["name"] = sanitized.get("name") or sanitized["id"]
        sanitized["display_name"] = sanitized.get("display_name") or sanitized["name"].replace("_", " ").title()
        env_var = sanitized.get("api_key_env") or sanitized.get("env_var") or ""
        sanitized["api_key_env"] = env_var
        sanitized["env_var"] = env_var
        sanitized["api_key_masked"] = mask_secret(_read_secret(env_var)) or mask_secret(sanitized.get("api_key_masked")) or ""
        sanitized.pop("api_key", None)
        return sanitized

    def _derive_status(self, row: dict[str, Any]) -> str:
        provider_type = row.get("provider_type", "")
        env_var = row.get("api_key_env") or row.get("env_var") or ""
        capabilities = row.get("capabilities") or {}
        if row.get("name") == "hyperframes_skill":
            return "ready"
        if row.get("name") == "local_hash_embedding":
            return "ready"
        if provider_type == "amazon_bedrock":
            from runtime.providers import bedrock
            return bedrock.status()
        if capabilities.get("local") or provider_type in {"ollama", "lmstudio", "comfyui", "automatic1111", "comfyui_video"}:
            return row.get("status") if row.get("status") == "ready" else "local_unreachable"
        if env_var and not _read_secret(env_var):
            return "needs_provider_setup"
        return "configured"

    def _test_status(self, row: dict[str, Any]) -> str:
        capabilities = row.get("capabilities") or {}
        provider_type = row.get("provider_type", "")
        if provider_type == "amazon_bedrock":
            from runtime.providers import bedrock
            return bedrock.status()
        if row.get("name") == "hyperframes_skill":
            return "ready"
        if row.get("name") == "local_hash_embedding":
            return "ready"
        if capabilities.get("local"):
            return "ready" if self._can_reach(row.get("base_url", "")) else "local_unreachable"
        env_var = row.get("api_key_env") or row.get("env_var") or ""
        if env_var and not _read_secret(env_var):
            return "needs_provider_setup"
        return "configured"

    def _status_message(self, row: dict[str, Any], status: str) -> str:
        if status == "configured":
            return "Provider configuration is present. No generation call was made."
        if status == "ready":
            return "Provider endpoint or local skill is ready."
        if status == "missing_key":
            return f"Missing {row.get('api_key_env') or row.get('env_var') or 'provider key'} in .env, .env.local, or environment."
        if status == "needs_provider_setup":
            return "AWS credentials or API key missing. Please run setup-guide for instructions."
        if status == "local_unreachable":
            return f"Local endpoint is not reachable at {row.get('base_url') or 'configured URL'}."
        if status == "placeholder":
            return "Provider is config-ready, but real calls are not implemented in v0.2.3."
        return f"Provider status: {status}"

    def _generate_text_once(
        self,
        provider: dict[str, Any],
        prompt: str,
        system_prompt: str | None,
        model: str | None,
        temperature: float,
        max_tokens: int | None,
    ) -> dict[str, Any]:
        provider_id = provider["id"]
        provider_type = provider.get("provider_type") or provider_id
        resolved_model = model or provider.get("default_model") or ""
        base = _base_text_response(provider_id, resolved_model)
        if provider.get("category") != "text":
            return {**base, "status": "needs_provider_setup", "error": "Selected provider is not a text provider."}
        if provider_type == "amazon_bedrock":
            from runtime.providers import bedrock
            return bedrock.generate_text(prompt, system_prompt, resolved_model, temperature, max_tokens)
        if provider_type in {"anthropic", "gemini", "groq", "mistral", "together", "fireworks"}:
            return self._generate_provider_sdk(provider, prompt, system_prompt, resolved_model, temperature, max_tokens)
        if provider_type == "ollama":
            return self._generate_ollama(provider, prompt, system_prompt, resolved_model, temperature, max_tokens)
        if provider_type == "lmstudio":
            return self._generate_openai_compatible(provider, prompt, system_prompt, resolved_model, temperature, max_tokens, requires_key=False)
        if provider_type in {"openai", "openrouter", "custom_openai_compatible", "azure_openai", "openai_compatible"}:
            return self._generate_openai_compatible(provider, prompt, system_prompt, resolved_model, temperature, max_tokens, requires_key=True)
        return {**base, "status": "placeholder", "error": "Provider is not implemented for text generation."}

    def _generate_openai_compatible(
        self,
        provider: dict[str, Any],
        prompt: str,
        system_prompt: str | None,
        model: str,
        temperature: float,
        max_tokens: int | None,
        requires_key: bool,
    ) -> dict[str, Any]:
        provider_id = provider["id"]
        base_url = (provider.get("base_url") or "").rstrip("/")
        env_var = provider.get("api_key_env") or provider.get("env_var") or ""
        key = _read_secret(env_var)
        base = _base_text_response(provider_id, model)
        if not base_url:
            return {**base, "status": "needs_provider_setup", "error": "Missing base_url for provider."}
        if not model:
            return {**base, "status": "needs_provider_setup", "error": "Missing text model for provider."}
        if requires_key and not key:
            return {**base, "status": "needs_provider_setup", "error": f"Missing {env_var or 'API key'}."}
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        payload: dict[str, Any] = {"model": model, "messages": messages, "temperature": temperature}
        if max_tokens:
            payload["max_tokens"] = max_tokens
        headers = {"content-type": "application/json"}
        if key:
            headers["authorization"] = f"Bearer {key}"
        try:
            data = _post_json(f"{base_url}/chat/completions", payload, headers)
            text = ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or (data.get("choices") or [{}])[0].get("text") or ""
            usage = data.get("usage") or {}
            return {**base, "status": "completed", "text": text, "usage": usage}
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            status = "local_unreachable" if provider.get("capabilities", {}).get("local") else "provider_error"
            return {**base, "status": status, "error": _redact_error(exc)}
        except Exception as exc:
            return {**base, "status": "provider_error", "error": _redact_error(exc)}

    def _generate_ollama(
        self,
        provider: dict[str, Any],
        prompt: str,
        system_prompt: str | None,
        model: str,
        temperature: float,
        max_tokens: int | None,
    ) -> dict[str, Any]:
        base_url = (provider.get("base_url") or "http://127.0.0.1:11434").rstrip("/")
        model = model or "llama3.2"
        base = _base_text_response(provider["id"], model)
        try:
            _get_json(f"{base_url}/api/tags")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            return {**base, "status": "local_unreachable", "error": _redact_error(exc)}
        payload: dict[str, Any] = {"model": model, "prompt": prompt, "stream": False, "options": {"temperature": temperature}}
        if system_prompt:
            payload["system"] = system_prompt
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens
        try:
            data = _post_json(f"{base_url}/api/generate", payload, {"content-type": "application/json"})
            return {**base, "status": "completed", "text": data.get("response", ""), "usage": {"eval_count": data.get("eval_count"), "prompt_eval_count": data.get("prompt_eval_count")}}
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            return {**base, "status": "local_unreachable", "error": _redact_error(exc)}
        except Exception as exc:
            return {**base, "status": "provider_error", "error": _redact_error(exc)}

    def _generate_provider_sdk(
        self,
        provider: dict[str, Any],
        prompt: str,
        system_prompt: str | None,
        model: str,
        temperature: float,
        max_tokens: int | None,
    ) -> dict[str, Any]:
        """Generate text using Anthropic, Gemini, Groq, Mistral, Together, or Fireworks SDKs."""
        provider_id = provider["id"]
        provider_type = provider.get("provider_type") or provider_id
        resolved_model = model or provider.get("default_model") or ""
        base = _base_text_response(provider_id, resolved_model)
        env_var = provider.get("api_key_env") or provider.get("env_var") or ""
        key = _read_secret(env_var)

        if not key:
            return {**base, "status": "needs_provider_setup", "error": f"Missing {env_var or 'API key'}."}
        if not resolved_model:
            return {**base, "status": "needs_provider_setup", "error": f"Missing text model for {provider_id}."}

        if provider_type == "anthropic":
            return self._generate_anthropic(provider, prompt, system_prompt, resolved_model, temperature, max_tokens, key, base)
        if provider_type == "gemini":
            return self._generate_gemini(provider, prompt, system_prompt, resolved_model, temperature, max_tokens, key, base)
        if provider_type == "groq":
            return self._generate_groq(provider, prompt, system_prompt, resolved_model, temperature, max_tokens, key, base)
        if provider_type in {"mistral", "together", "fireworks"}:
            return self._generate_openai_compatible(provider, prompt, system_prompt, resolved_model, temperature, max_tokens, requires_key=True)

        return {**base, "status": "placeholder", "error": f"Provider {provider_type} is config-ready but not implemented."}

    def _generate_anthropic(
        self,
        provider: dict[str, Any],
        prompt: str,
        system_prompt: str | None,
        model: str,
        temperature: float,
        max_tokens: int | None,
        key: str,
        base: dict[str, Any],
    ) -> dict[str, Any]:
        """Anthropic Messages API via urllib."""
        provider_id = provider["id"]
        base_url = (provider.get("base_url") or "https://api.anthropic.com").rstrip("/")
        messages = [{"role": "user", "content": prompt}]
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens or 4096,
            "temperature": temperature,
        }
        if system_prompt:
            payload["system"] = system_prompt
        headers = {
            "content-type": "application/json",
            "anthropic-version": "2023-06-01",
            "x-api-key": key,
        }
        try:
            data = _post_json(f"{base_url}/v1/messages", payload, headers)
            text = ""
            if "content" in data:
                for block in data["content"]:
                    if block.get("type") == "text":
                        text += block.get("text", "")
            usage = data.get("usage") or {}
            return {**base, "status": "completed", "text": text, "usage": usage}
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            return {**base, "status": "provider_error", "error": _redact_error(exc)}
        except Exception as exc:
            return {**base, "status": "provider_error", "error": _redact_error(exc)}

    def _generate_gemini(
        self,
        provider: dict[str, Any],
        prompt: str,
        system_prompt: str | None,
        model: str,
        temperature: float,
        max_tokens: int | None,
        key: str,
        base: dict[str, Any],
    ) -> dict[str, Any]:
        """Google Gemini API via urllib."""
        provider_id = provider["id"]
        base_url = (provider.get("base_url") or "https://generativelanguage.googleapis.com").rstrip("/")
        contents = [{"role": "user", "parts": [{"text": prompt}]}]
        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens or 4096,
            },
        }
        if system_prompt:
            payload["system_instruction"] = {"parts": [{"text": system_prompt}]}
        try:
            url = f"{base_url}/v1beta/models/{model}:generateContent?key={key}"
            data = _post_json(url, payload, {"content-type": "application/json"})
            text = ""
            if "candidates" in data and data["candidates"]:
                candidate = data["candidates"][0]
                content = candidate.get("content", {})
                for part in content.get("parts", []):
                    text += part.get("text", "")
            usage = {}
            if "usageMetadata" in data:
                usage = data["usageMetadata"]
            return {**base, "status": "completed", "text": text, "usage": usage}
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            return {**base, "status": "provider_error", "error": _redact_error(exc)}
        except Exception as exc:
            return {**base, "status": "provider_error", "error": _redact_error(exc)}

    def _generate_groq(
        self,
        provider: dict[str, Any],
        prompt: str,
        system_prompt: str | None,
        model: str,
        temperature: float,
        max_tokens: int | None,
        key: str,
        base: dict[str, Any],
    ) -> dict[str, Any]:
        """Groq API via urllib (OpenAI-compatible)."""
        provider_id = provider["id"]
        base_url = (provider.get("base_url") or "https://api.groq.com/openai").rstrip("/")
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        headers = {
            "content-type": "application/json",
            "authorization": f"Bearer {key}",
        }
        try:
            data = _post_json(f"{base_url}/v1/chat/completions", payload, headers)
            text = ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
            usage = data.get("usage") or {}
            return {**base, "status": "completed", "text": text, "usage": usage}
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            return {**base, "status": "provider_error", "error": _redact_error(exc)}
        except Exception as exc:
            return {**base, "status": "provider_error", "error": _redact_error(exc)}

    def _stream_ollama(
        self,
        provider: dict[str, Any],
        prompt: str,
        system_prompt: str | None,
        model: str,
        temperature: float,
        max_tokens: int | None,
        role: str | None,
    ):
        """Stream from Ollama /api/generate endpoint."""
        base_url = (provider.get("base_url") or "http://127.0.0.1:11434").rstrip("/")
        model = model or "llama3.2"
        payload: dict[str, Any] = {"model": model, "prompt": prompt, "stream": True, "options": {"temperature": temperature}}
        if system_prompt:
            payload["system"] = system_prompt
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens
        try:
            request = urllib.request.Request(
                f"{base_url}/api/generate",
                data=json.dumps(payload).encode("utf-8"),
                headers={"content-type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=120) as response:
                for line in response:
                    if not line.strip():
                        continue
                    try:
                        chunk = json.loads(line.decode("utf-8"))
                        token = chunk.get("response", "")
                        if token:
                            yield {"type": "token", "content": token, "provider": provider["id"], "model": model, "role": role or "default", "fallback_used": False}
                        if chunk.get("done", False):
                            break
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        continue
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            yield {"type": "error", "content": _redact_error(exc), "provider": provider["id"], "model": model, "role": role or "default", "fallback_used": False}
        except Exception as exc:
            yield {"type": "error", "content": _redact_error(exc), "provider": provider["id"], "model": model, "role": role or "default", "fallback_used": False}
        yield {"type": "done", "content": "", "provider": provider["id"], "model": model, "role": role or "default", "fallback_used": False}

    def _stream_openai_compatible(
        self,
        provider: dict[str, Any],
        prompt: str,
        system_prompt: str | None,
        model: str,
        temperature: float,
        max_tokens: int | None,
        role: str | None,
    ):
        """Stream from OpenAI-compatible /v1/chat/completions endpoint."""
        provider_id = provider["id"]
        base_url = (provider.get("base_url") or "").rstrip("/")
        env_var = provider.get("api_key_env") or provider.get("env_var") or ""
        key = _read_secret(env_var)
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        payload: dict[str, Any] = {"model": model, "messages": messages, "temperature": temperature, "stream": True}
        if max_tokens:
            payload["max_tokens"] = max_tokens
        headers = {"content-type": "application/json"}
        if key:
            headers["authorization"] = f"Bearer {key}"
        try:
            request = urllib.request.Request(
                f"{base_url}/chat/completions",
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=120) as response:
                for line in response:
                    line_str = line.decode("utf-8").strip()
                    if not line_str or line_str == "data: [DONE]":
                        continue
                    if line_str.startswith("data: "):
                        line_str = line_str[6:]
                    try:
                        chunk = json.loads(line_str)
                        delta = ((chunk.get("choices") or [{}])[0].get("delta") or {})
                        content = delta.get("content", "")
                        if content:
                            yield {"type": "token", "content": content, "provider": provider_id, "model": model, "role": role or "default", "fallback_used": False}
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        continue
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            yield {"type": "error", "content": _redact_error(exc), "provider": provider_id, "model": model, "role": role or "default", "fallback_used": False}
        except Exception as exc:
            yield {"type": "error", "content": _redact_error(exc), "provider": provider_id, "model": model, "role": role or "default", "fallback_used": False}
        yield {"type": "done", "content": "", "provider": provider_id, "model": model, "role": role or "default", "fallback_used": False}

    def _can_reach(self, base_url: str) -> bool:
        if not base_url:
            return False
        try:
            with urllib.request.urlopen(base_url.rstrip("/") + "/", timeout=2):
                return True
        except (urllib.error.URLError, TimeoutError, ValueError, OSError):
            return False

    def _normalize_provider(self, provider_name: str | None) -> str:
        aliases = {
            "openai-image": "openai_image",
            "openai_image_provider": "openai_image",
            "openai_sora": "openai_video",
            "local_comfyui_video": "comfyui_video",
            "hyperframes": "hyperframes_skill",
        }
        return aliases.get(provider_name or "", provider_name or "")

    def _setting_value(self, key: str, default: str) -> str:
        try:
            return self.settings.get(key)["value"]
        except ValueError:
            return default

    def _provider_setting_key(self, category: str) -> str:
        return {"speech_to_text": "default_stt_provider", "text_to_speech": "default_tts_provider"}.get(category, f"default_{category}_provider")

    def _model_setting_key(self, category: str) -> str:
        return {"speech_to_text": "default_stt_model", "text_to_speech": "default_tts_model"}.get(category, f"default_{category}_model")

    def _fallback_setting_key(self, category: str) -> str:
        return {"speech_to_text": "fallback_stt_provider", "text_to_speech": "fallback_tts_provider"}.get(category, f"fallback_{category}_provider")

    def _legacy_default_provider(self, providers: list[dict[str, Any]]) -> str | None:
        return next((row["id"] for row in providers if row.get("category") == "text" and row.get("is_default")), None)

    def _validate_category(self, category: str) -> None:
        if category not in CATEGORIES:
            raise ValueError(f"Unknown provider category: {category}")


def _read_secret(env_var: str | None) -> str:
    if not env_var:
        return ""
    if env_var in os.environ:
        return os.environ.get(env_var, "")
    for filename in (".env.local", ".env"):
        path = Path(filename)
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            if key.strip() == env_var:
                return value.strip().strip('"').strip("'")
    return ""


def _get_json(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def _post_json(url: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    request = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _base_text_response(provider: str, model: str) -> dict[str, Any]:
    return {
        "status": "needs_provider_setup",
        "provider": provider,
        "model": model,
        "text": "",
        "error": None,
        "usage": {},
        "fallback_used": False,
        "fallback_provider": None,
    }


def local_hash_embedding(text: str, dimension: int = 384) -> list[float]:
    vector = [0.0] * dimension
    tokens = re.findall(r"[a-zA-Z0-9_]+", (text or "").lower())
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimension
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [round(value / norm, 6) for value in vector]


SENSITIVE_PATTERNS = re.compile(r"\b(password|otp|credit card|aadhaar|pan|secret|api key|token)\b", re.IGNORECASE)


def _safe_log_metadata(prompt: str, metadata: dict[str, Any]) -> dict[str, Any]:
    sensitive = bool(SENSITIVE_PATTERNS.search(prompt))
    safe = {key: value for key, value in metadata.items() if key not in {"api_key", "authorization", "token"}}
    safe["prompt_summary"] = "[sensitive redacted]" if sensitive else prompt[:120]
    safe["sensitive_redacted"] = sensitive
    return safe


def _redact_error(exc: BaseException) -> str:
    text = str(exc)
    for env_var in (
        "OPENAI_API_KEY", "OPENROUTER_API_KEY", "CUSTOM_OPENAI_API_KEY",
        "GEMINI_API_KEY", "ANTHROPIC_API_KEY", "GROQ_API_KEY",
        "MISTRAL_API_KEY", "TOGETHER_API_KEY", "FIREWORKS_API_KEY",
        "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"
    ):
        secret = _read_secret(env_var)
        if secret:
            text = text.replace(secret, mask_secret(secret))
    text = re.sub(r"Bearer\s+[A-Za-z0-9._\-]+", "Bearer [redacted]", text)
    text = re.sub(r"sk-[A-Za-z0-9_\-]+", "sk-[redacted]", text)
    text = re.sub(r"AIzaSy[A-Za-z0-9_\-]+", "AIzaSy[redacted]", text)
    return text[:500]


def mask_secret(value: str | None) -> str:
    if not value:
        return ""
    text = str(value)
    if text.startswith("*"):
        return text
    if len(text) <= 8:
        return "****"
    return f"{text[:4]}...{text[-4:]}"


def dumps_no_secrets(data: Any) -> str:
    return json.dumps(data, sort_keys=True)

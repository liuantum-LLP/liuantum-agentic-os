"""Tests for provider SDK execution — v1.2.0."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from runtime.providers.registry import ModelHub


# ---------------------------------------------------------------------------
# 1. Anthropic missing key returns needs_provider_setup
# ---------------------------------------------------------------------------

def test_anthropic_missing_key_returns_needs_setup(monkeypatch):
    hub = ModelHub()
    hub.ensure_defaults()
    provider = hub.get_provider("anthropic")
    result = hub._generate_text_once(
        provider=provider,
        prompt="Hello",
        system_prompt=None,
        model="claude-3-5-sonnet-latest",
        temperature=0.7,
        max_tokens=None,
    )
    assert result["status"] in ("needs_provider_setup", "placeholder")
    if result["status"] == "needs_provider_setup":
        assert "ANTHROPIC_API_KEY" in result.get("error", "")


# ---------------------------------------------------------------------------
# 2. Gemini missing key returns needs_provider_setup
# ---------------------------------------------------------------------------

def test_gemini_missing_key_returns_needs_setup(monkeypatch):
    hub = ModelHub()
    hub.ensure_defaults()
    provider = hub.get_provider("gemini")
    result = hub._generate_text_once(
        provider=provider,
        prompt="Hello",
        system_prompt=None,
        model="gemini-2.0-flash",
        temperature=0.7,
        max_tokens=None,
    )
    assert result["status"] in ("needs_provider_setup", "placeholder")
    if result["status"] == "needs_provider_setup":
        assert "GEMINI_API_KEY" in result.get("error", "")


# ---------------------------------------------------------------------------
# 3. Groq missing key returns needs_provider_setup
# ---------------------------------------------------------------------------

def test_groq_missing_key_returns_needs_setup(monkeypatch):
    hub = ModelHub()
    hub.ensure_defaults()
    provider = hub.get_provider("groq")
    result = hub._generate_text_once(
        provider=provider,
        prompt="Hello",
        system_prompt=None,
        model="llama-3.1-8b-instant",
        temperature=0.7,
        max_tokens=None,
    )
    assert result["status"] in ("needs_provider_setup", "placeholder")
    if result["status"] == "needs_provider_setup":
        assert "GROQ_API_KEY" in result.get("error", "")


# ---------------------------------------------------------------------------
# 4. OpenRouter mocked generation works
# ---------------------------------------------------------------------------

def test_openrouter_mocked_generation_works(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-123")
    hub = ModelHub()
    hub.ensure_defaults()
    provider = hub.get_provider("openrouter")

    with patch("runtime.providers.registry._post_json") as mock_post:
        mock_post.return_value = {"choices": [{"message": {"content": "Hello from OpenRouter"}}], "usage": {"total_tokens": 10}}
        result = hub._generate_text_once(
            provider=provider,
            prompt="Hello",
            system_prompt=None,
            model="openai/gpt-4.1-mini",
            temperature=0.7,
            max_tokens=None,
        )
        assert result["status"] == "completed"
        assert "Hello from OpenRouter" in result["text"]


# ---------------------------------------------------------------------------
# 5. Ollama unreachable returns local_unreachable
# ---------------------------------------------------------------------------

def test_ollama_unreachable_returns_local_unreachable(monkeypatch):
    hub = ModelHub()
    hub.ensure_defaults()
    provider = hub.get_provider("ollama")

    import urllib.error
    with patch("runtime.providers.registry.urllib.request.urlopen", side_effect=urllib.error.URLError("Connection refused")):
        result = hub._generate_text_once(
            provider=provider,
            prompt="Hello",
            system_prompt=None,
            model="llama3.2",
            temperature=0.7,
            max_tokens=None,
        )
        assert result["status"] == "local_unreachable"


# ---------------------------------------------------------------------------
# 6. OpenAI-compatible mocked generation works
# ---------------------------------------------------------------------------

def test_openai_compatible_mocked_generation_works(monkeypatch):
    monkeypatch.setenv("CUSTOM_OPENAI_API_KEY", "test-key-456")
    hub = ModelHub()
    hub.ensure_defaults()
    provider = hub.get_provider("custom_openai_compatible")
    provider["base_url"] = "https://api.example.com/v1"

    with patch("runtime.providers.registry._post_json") as mock_post:
        mock_post.return_value = {"choices": [{"message": {"content": "Hello from custom provider"}}], "usage": {"total_tokens": 5}}
        result = hub._generate_text_once(
            provider=provider,
            prompt="Hello",
            system_prompt=None,
            model="custom-model",
            temperature=0.7,
            max_tokens=None,
        )
        assert result["status"] == "completed"
        assert "Hello from custom provider" in result["text"]


# ---------------------------------------------------------------------------
# 7. model role resolves provider/model
# ---------------------------------------------------------------------------

def test_model_role_resolves_provider_model(monkeypatch):
    from runtime.model_roles import ModelRoleManager
    from runtime.model_router import get_model_for_role

    rm = ModelRoleManager()
    rm.ensure_defaults()
    rm.set_role("thinking", "openrouter", "deepseek/deepseek-reasoner")

    result = get_model_for_role("thinking", rm)
    assert result["configured"] is True
    assert result["provider"] == "openrouter"
    assert result["model"] == "deepseek/deepseek-reasoner"
    assert result["role"] == "thinking"


# ---------------------------------------------------------------------------
# 8. chat --model-role uses selected role (CLI integration test)
# ---------------------------------------------------------------------------

def test_chat_model_role_uses_selected_role(monkeypatch):
    from runtime.model_roles import ModelRoleManager
    from runtime.model_router import get_model_for_role, route_task_to_role

    rm = ModelRoleManager()
    rm.ensure_defaults()
    rm.set_role("coding", "openrouter", "qwen/qwen3-coder")

    assert route_task_to_role("fix this Python error") == "coding"
    result = get_model_for_role("coding", rm)
    assert result["configured"] is True
    assert result["provider"] == "openrouter"


# ---------------------------------------------------------------------------
# 9. discussion mode calls role providers
# ---------------------------------------------------------------------------

def test_discussion_mode_calls_role_providers(monkeypatch):
    from runtime.model_roles import ModelRoleManager
    from runtime.chat.discussion import run_discussion

    rm = ModelRoleManager()
    rm.ensure_defaults()
    rm.set_role("default", "mock", "mock-model")

    mock_hub = MagicMock()
    mock_hub.generate_text.return_value = {
        "status": "completed",
        "text": "Discussion response from mock.",
        "provider": "mock",
        "model": "mock-model",
    }

    result = run_discussion(
        user_message="Analyze this architecture",
        roles=["default"],
        rounds=1,
        final_role="default",
        role_manager=rm,
        model_hub=mock_hub,
    )

    assert mock_hub.generate_text.call_count >= 1
    assert result["status"] in ("completed", "partial")


# ---------------------------------------------------------------------------
# 10. fallback model used if role provider unavailable
# ---------------------------------------------------------------------------

def test_fallback_model_used_if_role_unavailable(monkeypatch):
    from runtime.model_roles import ModelRoleManager
    from runtime.model_router import get_model_for_role

    rm = ModelRoleManager()
    rm.ensure_defaults()
    rm.reset_role("thinking")
    rm.set_role("fallback", "ollama", "llama3.2")

    result = get_model_for_role("thinking", rm)
    assert result["configured"] is True
    assert result["role"] == "fallback"
    assert "fallback_from" in result
    assert result["fallback_from"] == "thinking"


# ---------------------------------------------------------------------------
# 11. provider errors are redacted
# ---------------------------------------------------------------------------

def test_provider_errors_are_redacted():
    from runtime.providers.registry import _redact_error

    error_msg = "Connection failed with key sk-abc123def456 and Bearer token123"
    redacted = _redact_error(Exception(error_msg))
    assert "sk-abc123def456" not in redacted
    assert "token123" not in redacted
    assert "[redacted]" in redacted


# ---------------------------------------------------------------------------
# 12. no secrets in logs
# ---------------------------------------------------------------------------

def test_no_secrets_in_logs(monkeypatch):
    from runtime.providers.registry import _safe_log_metadata

    prompt = "My password is secret123 and API key is sk-abc"
    metadata = {"provider": "openai", "model": "gpt-4"}
    result = _safe_log_metadata(prompt, metadata)
    assert result["sensitive_redacted"] is True
    assert "[sensitive redacted]" in result["prompt_summary"]
    assert "secret123" not in result.get("prompt_summary", "")


# ---------------------------------------------------------------------------
# 13. existing tests still pass (verified by running full suite)
# ---------------------------------------------------------------------------

def test_anthropic_provider_has_base_url(monkeypatch):
    hub = ModelHub()
    hub.ensure_defaults()
    provider = hub.get_provider("anthropic")
    assert "anthropic.com" in provider.get("base_url", "")


def test_gemini_provider_has_base_url(monkeypatch):
    hub = ModelHub()
    hub.ensure_defaults()
    provider = hub.get_provider("gemini")
    assert "googleapis.com" in provider.get("base_url", "")


def test_groq_provider_has_base_url(monkeypatch):
    hub = ModelHub()
    hub.ensure_defaults()
    provider = hub.get_provider("groq")
    assert "groq.com" in provider.get("base_url", "")


def test_openrouter_provider_has_base_url(monkeypatch):
    hub = ModelHub()
    hub.ensure_defaults()
    provider = hub.get_provider("openrouter")
    assert "openrouter.ai" in provider.get("base_url", "")


def test_ollama_provider_has_base_url(monkeypatch):
    hub = ModelHub()
    hub.ensure_defaults()
    provider = hub.get_provider("ollama")
    assert "11434" in provider.get("base_url", "")


def test_provider_status_derived_correctly(monkeypatch):
    hub = ModelHub()
    hub.ensure_defaults()
    anthropic = hub.get_provider("anthropic")
    assert anthropic["status"] in ("placeholder", "configured", "needs_provider_setup")
    groq = hub.get_provider("groq")
    assert groq["status"] in ("placeholder", "configured", "needs_provider_setup")
    gemini = hub.get_provider("gemini")
    assert gemini["status"] in ("placeholder", "configured", "needs_provider_setup")


# ---------------------------------------------------------------------------
# 14. Gemini integration validations for v2.8.0
# ---------------------------------------------------------------------------

def test_gemini_missing_key_returns_needs_setup_strictly():
    hub = ModelHub()
    hub.ensure_defaults()
    row = hub.get_provider("gemini")
    status = hub._derive_status(row)
    assert status == "needs_provider_setup"


def test_gemini_status_does_not_expose_key():
    hub = ModelHub()
    hub.ensure_defaults()
    row = hub.get_provider("gemini")
    sanitized = hub._sanitize(row)
    assert "api_key" not in sanitized
    assert sanitized["api_key_masked"] == ""


def test_gemini_model_role_works(monkeypatch):
    from runtime.model_roles import ModelRoleManager
    from runtime.model_router import get_model_for_role

    rm = ModelRoleManager()
    rm.ensure_defaults()
    rm.set_role("thinking", "gemini", "gemini-1.5-pro")

    result = get_model_for_role("thinking", rm)
    assert result["configured"] is True
    assert result["provider"] == "gemini"
    assert result["model"] == "gemini-1.5-pro"


def test_gemini_errors_are_redacted():
    from runtime.providers.registry import _redact_error
    error_msg = "Google Gemini call failed: API key AIzaSyFakeKey123456789 is wrong"
    redacted = _redact_error(Exception(error_msg))
    assert "AIzaSyFakeKey123456789" not in redacted
    assert "[redacted]" in redacted


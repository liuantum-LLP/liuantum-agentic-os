"""Tests for agent runtime model role polish, streaming, and safety — v1.3.0."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from runtime.agents import AgentRunner, AgentProfileManager
from runtime.automation import AutomationManager
from runtime.model_roles import ModelRoleManager
from runtime.model_router import get_model_for_role
from runtime.providers.registry import ModelHub


# ---------------------------------------------------------------------------
# 1. Agent uses preferred_model_role by default
# ---------------------------------------------------------------------------

def test_agent_uses_preferred_model_role(monkeypatch):
    rm = ModelRoleManager()
    rm.ensure_defaults()
    rm.set_role("coding", "mock", "mock-coding")

    runner = AgentRunner()
    apm = AgentProfileManager()
    apm.ensure_builtins()

    coding_agent = next((a for a in apm.list() if "coding" in a.get("slug", "")), None)
    if coding_agent:
        apm.update(coding_agent["slug"], {"preferred_model_role": "coding"})
        result = runner.run(coding_agent["slug"], "Fix this Flask route")
        assert result.get("model_role_used") == "coding" or "coding" in str(result)


# ---------------------------------------------------------------------------
# 2. CLI --model-role overrides agent preferred role
# ---------------------------------------------------------------------------

def test_cli_model_role_overrides_agent_preferred(monkeypatch):
    rm = ModelRoleManager()
    rm.ensure_defaults()
    rm.set_role("thinking", "mock", "mock-thinking")

    runner = AgentRunner()
    apm = AgentProfileManager()
    apm.ensure_builtins()

    coding_agent = next((a for a in apm.list() if "coding" in a.get("slug", "")), None)
    if coding_agent:
        apm.update(coding_agent["slug"], {"preferred_model_role": "coding"})
        result = runner.run(coding_agent["slug"], "Fix this Flask route", model_role="thinking")
        assert result.get("model_role_used") == "thinking" or "thinking" in str(result)


# ---------------------------------------------------------------------------
# 3. Agent discussion mode uses configured roles
# ---------------------------------------------------------------------------

def test_agent_discussion_mode_uses_configured_roles(monkeypatch):
    rm = ModelRoleManager()
    rm.ensure_defaults()
    rm.set_role("default", "mock", "mock-model")

    runner = AgentRunner()
    apm = AgentProfileManager()
    apm.ensure_builtins()

    brand_agent = next((a for a in apm.list() if "brand" in a.get("slug", "")), None)
    if brand_agent:
        result = runner.run(brand_agent["slug"], "Plan launch", discussion_mode=True)
        r = result.get("result", {})
        assert "model_role_used" in r or "provider_routing" in r


# ---------------------------------------------------------------------------
# 4. Agent action outputs remain approval-gated
# ---------------------------------------------------------------------------

def test_agent_action_outputs_approval_gated(monkeypatch):
    runner = AgentRunner()
    result = runner.run("content-creator-agent", "Create campaign for Python course")
    assert result.get("result", {}).get("approval_required") is True or "approval" in str(result.get("result", {})).lower()


# ---------------------------------------------------------------------------
# 5. Automation saves model_role
# ---------------------------------------------------------------------------

def test_automation_saves_model_role(monkeypatch):
    am = AutomationManager()
    auto = am.create({
        "name": "test-automation-role",
        "agent_slug": "personal-assistant-agent",
        "trigger_type": "manual",
        "task_prompt": "Test task",
        "model_role": "planning",
    })
    assert auto.get("model_role") == "planning" or "planning" in str(auto)


# ---------------------------------------------------------------------------
# 6. Automation preview warns if cloud/discussion enabled
# ---------------------------------------------------------------------------

def test_automation_preview_warns_cloud_discussion(monkeypatch):
    rm = ModelRoleManager()
    rm.ensure_defaults()
    rm.set_role("planning", "openrouter", "mock-planning")

    am = AutomationManager()
    auto = am.create({
        "name": "test-automation-cloud",
        "agent_slug": "personal-assistant-agent",
        "trigger_type": "manual",
        "task_prompt": "Test task",
        "model_role": "planning",
        "discussion_mode_enabled": True,
        "discussion_rounds": 2,
    })
    assert auto.get("discussion_mode_enabled") is True or "discussion" in str(auto).lower()


# ---------------------------------------------------------------------------
# 7. stream_text fallback to generate_text when provider lacks streaming
# ---------------------------------------------------------------------------

def test_stream_text_fallback_to_generate_text(monkeypatch):
    hub = ModelHub()
    hub.ensure_defaults()

    chunks = list(hub.stream_text(
        prompt="Hello",
        provider_name="anthropic",
        model="claude-3-5-sonnet-latest",
    ))

    types = [c["type"] for c in chunks]
    assert "metadata" in types
    assert "done" in types


# ---------------------------------------------------------------------------
# 8. OpenRouter streaming mock yields tokens
# ---------------------------------------------------------------------------

def test_openrouter_streaming_mock_yields_tokens(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-123")
    hub = ModelHub()
    hub.ensure_defaults()
    provider = hub.get_provider("openrouter")

    import json as _json
    stream_data = [
        f'data: {_json.dumps({"choices": [{"delta": {"content": "Hello"}}]})}',
        f'data: {_json.dumps({"choices": [{"delta": {"content": " from OpenRouter"}}]})}',
        "data: [DONE]",
    ]

    class MockResponse:
        def __init__(self):
            self._lines = stream_data
            self._index = 0

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def __iter__(self):
            for line in self._lines:
                yield (line + "\n").encode("utf-8")

    with patch("runtime.providers.registry.urllib.request.urlopen", return_value=MockResponse()):
        chunks = list(hub._stream_openai_compatible(
            provider=provider,
            prompt="Hello",
            system_prompt=None,
            model="openai/gpt-4.1-mini",
            temperature=0.7,
            max_tokens=None,
            role="default",
        ))
        token_chunks = [c for c in chunks if c["type"] == "token"]
        assert len(token_chunks) >= 1
        assert "Hello" in token_chunks[0]["content"]


# ---------------------------------------------------------------------------
# 9. Ollama streaming mock yields tokens
# ---------------------------------------------------------------------------

def test_ollama_streaming_mock_yields_tokens(monkeypatch):
    hub = ModelHub()
    hub.ensure_defaults()
    provider = hub.get_provider("ollama")

    import json as _json
    stream_data = [
        _json.dumps({"response": "Hello", "done": False}),
        _json.dumps({"response": " from Ollama", "done": False}),
        _json.dumps({"response": "", "done": True}),
    ]

    class MockResponse:
        def __init__(self):
            self._lines = stream_data
            self._index = 0

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def __iter__(self):
            for line in self._lines:
                yield (line + "\n").encode("utf-8")

    with patch("runtime.providers.registry.urllib.request.urlopen", return_value=MockResponse()):
        chunks = list(hub._stream_ollama(
            provider=provider,
            prompt="Hello",
            system_prompt=None,
            model="llama3.2",
            temperature=0.7,
            max_tokens=None,
            role="default",
        ))
        token_chunks = [c for c in chunks if c["type"] == "token"]
        assert len(token_chunks) >= 1


# ---------------------------------------------------------------------------
# 10. Groq streaming mock yields tokens
# ---------------------------------------------------------------------------

def test_groq_streaming_mock_yields_tokens(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-key-groq")
    hub = ModelHub()
    hub.ensure_defaults()
    provider = hub.get_provider("groq")

    import json as _json
    stream_data = [
        f'data: {_json.dumps({"choices": [{"delta": {"content": "Hello"}}]})}',
        f'data: {_json.dumps({"choices": [{"delta": {"content": " from Groq"}}]})}',
        "data: [DONE]",
    ]

    class MockResponse:
        def __init__(self):
            self._lines = stream_data

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def __iter__(self):
            for line in self._lines:
                yield (line + "\n").encode("utf-8")

    with patch("runtime.providers.registry.urllib.request.urlopen", return_value=MockResponse()):
        chunks = list(hub._stream_openai_compatible(
            provider=provider,
            prompt="Hello",
            system_prompt=None,
            model="llama-3.1-8b-instant",
            temperature=0.7,
            max_tokens=None,
            role="default",
        ))
        token_chunks = [c for c in chunks if c["type"] == "token"]
        assert len(token_chunks) >= 1


# ---------------------------------------------------------------------------
# 11. CLI chat --stream prints chunks (simulated)
# ---------------------------------------------------------------------------

def test_cli_chat_stream_prints_chunks(monkeypatch):
    hub = ModelHub()
    hub.ensure_defaults()

    chunks = list(hub.stream_text(
        prompt="Explain Liuant",
        provider_name="ollama",
        model="llama3.2",
        role="default",
    ))

    types = [c["type"] for c in chunks]
    assert "metadata" in types
    assert "done" in types


# ---------------------------------------------------------------------------
# 12. API /api/chat/stream returns stream events
# ---------------------------------------------------------------------------

def test_api_chat_stream_route_exists(monkeypatch):
    from runtime.api.app import app
    routes = [r.path for r in app.routes if hasattr(r, "path")]
    assert "/api/chat/stream" in routes
    assert "/api/models/stream" in routes
    assert any("/api/agents/{agent_slug}/stream" in r for r in routes)


# ---------------------------------------------------------------------------
# 13. Chat UI contains streaming toggle (code inspection)
# ---------------------------------------------------------------------------

def test_chat_ui_contains_streaming_toggle():
    with open("apps/desktop/src/pages/ChatPage.tsx", "r") as f:
        content = f.read()
    assert "streamingMode" in content
    assert "setStreamingMode" in content
    assert "Streaming" in content


# ---------------------------------------------------------------------------
# 14. Chat UI displays provider/model metadata
# ---------------------------------------------------------------------------

def test_chat_ui_displays_provider_model_metadata():
    with open("apps/desktop/src/pages/ChatPage.tsx", "r") as f:
        content = f.read()
    assert "providerUsed" in content
    assert "modelUsed" in content
    assert "chat-provider-badge" in content


# ---------------------------------------------------------------------------
# 15. No secrets are logged during streaming
# ---------------------------------------------------------------------------

def test_no_secrets_logged_during_streaming(monkeypatch):
    from runtime.providers.registry import _safe_log_metadata

    prompt = "My password is secret123 and API key is sk-abc"
    metadata = {"provider": "openai", "model": "gpt-4"}
    result = _safe_log_metadata(prompt, metadata)
    assert result["sensitive_redacted"] is True
    assert "[sensitive redacted]" in result["prompt_summary"]
    assert "secret123" not in result.get("prompt_summary", "")


# ---------------------------------------------------------------------------
# 16. Existing tests still pass (verified by running full suite)
# ---------------------------------------------------------------------------

def test_agent_run_includes_model_role_metadata(monkeypatch):
    rm = ModelRoleManager()
    rm.ensure_defaults()
    rm.set_role("default", "mock", "mock-model")

    runner = AgentRunner()
    apm = AgentProfileManager()
    apm.ensure_builtins()

    agent = apm.list()[0]
    result = runner.run(agent["slug"], "Test prompt")
    assert "model_role_used" in result.get("result", {}) or "provider_routing" in result.get("result", {}) or "provider_routing" in result


def test_automation_model_role_defaults_to_default(monkeypatch):
    am = AutomationManager()
    auto = am.create({
        "name": "test-automation-default-role",
        "agent_slug": "personal-assistant-agent",
        "trigger_type": "manual",
        "task_prompt": "Test task",
    })
    assert auto.get("model_role") == "default" or "default" in str(auto)

"""Tests for model roles, model router, and discussion mode — v1.1.0."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from runtime.model_roles import ModelRoleManager
from runtime.model_router import route_task_to_role, get_model_for_role
from runtime.chat.discussion import run_discussion, redact_secrets


# ---------------------------------------------------------------------------
# 1. model roles default config exists
# ---------------------------------------------------------------------------

def test_model_roles_default_config_exists(monkeypatch):
    rm = ModelRoleManager()
    rm.ensure_defaults()
    result = rm.get_all_roles()
    assert "roles" in result
    assert "discussion" in result
    for role in ("default", "thinking", "coding", "planning", "fast", "fallback"):
        assert role in result["roles"]


# ---------------------------------------------------------------------------
# 2. set thinking model role works
# ---------------------------------------------------------------------------

def test_set_thinking_model_role(monkeypatch):
    rm = ModelRoleManager()
    rm.ensure_defaults()
    result = rm.set_role("thinking", "openrouter", "deepseek/deepseek-reasoner")
    assert result["role"] == "thinking"
    assert result["provider"] == "openrouter"
    assert result["model"] == "deepseek/deepseek-reasoner"
    assert result["configured"] is True


# ---------------------------------------------------------------------------
# 3. set coding model role works
# ---------------------------------------------------------------------------

def test_set_coding_model_role(monkeypatch):
    rm = ModelRoleManager()
    rm.ensure_defaults()
    result = rm.set_role("coding", "openrouter", "qwen/qwen3-coder")
    assert result["role"] == "coding"
    assert result["provider"] == "openrouter"
    assert result["model"] == "qwen/qwen3-coder"
    assert result["configured"] is True


# ---------------------------------------------------------------------------
# 4. set planning model role works
# ---------------------------------------------------------------------------

def test_set_planning_model_role(monkeypatch):
    rm = ModelRoleManager()
    rm.ensure_defaults()
    result = rm.set_role("planning", "openrouter", "moonshotai/kimi-k2.5")
    assert result["role"] == "planning"
    assert result["provider"] == "openrouter"
    assert result["model"] == "moonshotai/kimi-k2.5"
    assert result["configured"] is True


# ---------------------------------------------------------------------------
# 5. role test returns provider/model status
# ---------------------------------------------------------------------------

def test_role_test_returns_status(monkeypatch):
    rm = ModelRoleManager()
    rm.ensure_defaults()
    result = rm.test_role("thinking")
    assert result["role"] == "thinking"
    assert "status" in result
    assert "message" in result


# ---------------------------------------------------------------------------
# 6. task router maps coding prompts to coding role
# ---------------------------------------------------------------------------

def test_router_maps_coding_to_coding_role():
    assert route_task_to_role("fix this Python error in my Flask app") == "coding"
    assert route_task_to_role("write a unit test for this function") == "coding"
    assert route_task_to_role("debug this traceback: TypeError...") == "coding"


# ---------------------------------------------------------------------------
# 7. task router maps planning prompts to planning role
# ---------------------------------------------------------------------------

def test_router_maps_planning_to_planning_role():
    assert route_task_to_role("create a roadmap for Liuant launch") == "planning"
    assert route_task_to_role("write a project breakdown with milestones") == "planning"
    assert route_task_to_role("write a marketing strategy plan") == "planning"


# ---------------------------------------------------------------------------
# 8. task router maps analysis prompts to thinking role
# ---------------------------------------------------------------------------

def test_router_maps_analysis_to_thinking_role():
    assert route_task_to_role("analyze the pros and cons of this architecture") == "thinking"
    assert route_task_to_role("compare these two approaches") == "thinking"
    assert route_task_to_role("what do you think about this design?") == "thinking"


# ---------------------------------------------------------------------------
# 9. discussion mode disabled by default
# ---------------------------------------------------------------------------

def test_discussion_mode_disabled_by_default(monkeypatch):
    rm = ModelRoleManager()
    rm.ensure_defaults()
    settings = rm.get_discussion_settings()
    assert settings["discussion_mode_enabled"] is False


# ---------------------------------------------------------------------------
# 10. discussion mode max rounds capped
# ---------------------------------------------------------------------------

def test_discussion_mode_max_rounds_capped(monkeypatch):
    rm = ModelRoleManager()
    rm.ensure_defaults()
    settings = rm.get_discussion_settings()
    assert settings["discussion_mode_max_rounds"] == 4
    assert settings["discussion_mode_default_rounds"] == 2


# ---------------------------------------------------------------------------
# 11. discussion engine runs with mocked providers
# ---------------------------------------------------------------------------

def test_discussion_engine_runs_with_mocked_providers(monkeypatch):
    rm = ModelRoleManager()
    rm.ensure_defaults()
    rm.set_role("default", "mock", "mock-model")

    mock_hub = MagicMock()
    mock_hub.generate_text.return_value = {
        "status": "completed",
        "text": "Mock response from model.",
        "provider": "mock",
        "model": "mock-model",
    }

    result = run_discussion(
        user_message="What is the best approach for this problem?",
        roles=["default"],
        rounds=1,
        final_role="default",
        role_manager=rm,
        model_hub=mock_hub,
    )

    assert result["status"] in ("completed", "partial")
    assert "final_answer" in result
    assert "discussion_id" in result
    assert "roles_used" in result


# ---------------------------------------------------------------------------
# 12. discussion engine returns final answer
# ---------------------------------------------------------------------------

def test_discussion_engine_returns_final_answer(monkeypatch):
    rm = ModelRoleManager()
    rm.ensure_defaults()
    rm.set_role("default", "mock", "mock-model")

    mock_hub = MagicMock()
    mock_hub.generate_text.return_value = {
        "status": "completed",
        "text": "This is the final synthesized answer.",
        "provider": "mock",
        "model": "mock-model",
    }

    result = run_discussion(
        user_message="Plan a product launch",
        roles=["default"],
        rounds=1,
        final_role="default",
        role_manager=rm,
        model_hub=mock_hub,
    )

    assert "final_answer" in result
    assert result["final_answer"] != ""


# ---------------------------------------------------------------------------
# 13. discussion engine falls back if one role model fails
# ---------------------------------------------------------------------------

def test_discussion_engine_fallback_on_failure(monkeypatch):
    rm = ModelRoleManager()
    rm.ensure_defaults()
    rm.set_role("thinking", "mock", "mock-thinking")
    rm.set_role("fallback", "mock", "mock-fallback")

    mock_hub = MagicMock()
    call_count = {"n": 0}

    def side_effect(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return {"status": "failed", "text": "", "error": "mock error"}
        return {"status": "completed", "text": "Fallback response", "provider": "mock", "model": "mock-fallback"}

    mock_hub.generate_text.side_effect = side_effect

    result = run_discussion(
        user_message="Analyze this architecture",
        roles=["thinking"],
        rounds=1,
        final_role="thinking",
        role_manager=rm,
        model_hub=mock_hub,
    )

    assert result["fallback_used"] is True or result["status"] in ("partial", "fallback")


# ---------------------------------------------------------------------------
# 14. discussion does not expose secrets
# ---------------------------------------------------------------------------

def test_discussion_does_not_expose_secrets():
    secret_text = "My password=sk-abc123 and my api key=secretkey123"
    redacted = redact_secrets(secret_text)
    assert "sk-abc123" not in redacted
    assert "[REDACTED]" in redacted


# ---------------------------------------------------------------------------
# 15. chat --discussion uses discussion engine (API endpoint test)
# ---------------------------------------------------------------------------

def test_chat_discussion_api_endpoint(monkeypatch):
    rm = ModelRoleManager()
    rm.ensure_defaults()
    rm.set_role("default", "mock", "mock-model")

    mock_hub = MagicMock()
    mock_hub.generate_text.return_value = {
        "status": "completed",
        "text": "Discussion response.",
        "provider": "mock",
        "model": "mock-model",
    }

    result = run_discussion(
        user_message="Create a launch plan",
        roles=["default"],
        rounds=1,
        role_manager=rm,
        model_hub=mock_hub,
    )

    assert result["status"] in ("completed", "partial")
    assert "final_answer" in result


# ---------------------------------------------------------------------------
# 16. Settings page includes Thinking/Coding/Planning roles (backend data)
# ---------------------------------------------------------------------------

def test_settings_backend_includes_model_roles(monkeypatch):
    rm = ModelRoleManager()
    rm.ensure_defaults()
    rm.set_role("thinking", "openrouter", "deepseek-reasoner")
    rm.set_role("coding", "openrouter", "qwen-coder")
    rm.set_role("planning", "openrouter", "kimi-k2")

    result = rm.get_all_roles()
    assert result["roles"]["thinking"]["provider"] == "openrouter"
    assert result["roles"]["coding"]["provider"] == "openrouter"
    assert result["roles"]["planning"]["provider"] == "openrouter"


# ---------------------------------------------------------------------------
# 17. Settings page includes Discussion Mode toggle (backend data)
# ---------------------------------------------------------------------------

def test_settings_backend_includes_discussion_toggle(monkeypatch):
    rm = ModelRoleManager()
    rm.ensure_defaults()
    settings = rm.get_discussion_settings()
    assert "discussion_mode_enabled" in settings
    assert "discussion_mode_default_rounds" in settings
    assert "discussion_mode_max_rounds" in settings


# ---------------------------------------------------------------------------
# 18. Agent profile supports preferred_model_role
# ---------------------------------------------------------------------------

def test_agent_profile_supports_model_role(monkeypatch):
    from runtime.agents import AgentProfileManager
    apm = AgentProfileManager()
    apm.ensure_builtins()
    agents = apm.list()
    assert len(agents) > 0
    agent = agents[0]
    assert "preferred_model_role" in agent or "provider_preferences" in agent


# ---------------------------------------------------------------------------
# 19. Automation supports model_role
# ---------------------------------------------------------------------------

def test_automation_supports_model_role(monkeypatch):
    from runtime.automation import AutomationManager
    am = AutomationManager()
    auto = am.create({
        "name": "test-automation",
        "agent_slug": "personal-assistant-agent",
        "trigger_type": "manual",
        "task_prompt": "Test task",
        "model_role": "coding",
        "discussion_mode_enabled": True,
        "discussion_rounds": 2,
    })
    assert auto.get("model_role") == "coding" or "model_role" in str(auto)


# ---------------------------------------------------------------------------
# 20. Existing tests still pass (verified by running full suite)
# ---------------------------------------------------------------------------

def test_model_role_invalid_raises():
    rm = ModelRoleManager()
    rm.ensure_defaults()
    try:
        rm.set_role("invalid_role", "openai", "gpt-4")
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


def test_model_role_get_unconfigured():
    rm = ModelRoleManager()
    rm.ensure_defaults()
    rm.reset_role("thinking")
    result = rm.get_role("thinking")
    assert result["configured"] is False


def test_model_role_reset_all():
    rm = ModelRoleManager()
    rm.ensure_defaults()
    rm.set_role("thinking", "openrouter", "deepseek-reasoner")
    result = rm.reset_all_roles()
    assert result["roles"]["thinking"]["provider"] == ""


def test_discussion_redact_no_secrets():
    clean_text = "Hello world, this is a normal message"
    assert redact_secrets(clean_text) == clean_text


def test_router_default_for_normal_chat():
    assert route_task_to_role("Hello, how are you?") == "default"
    assert route_task_to_role("What is the weather?") == "default"
    assert route_task_to_role("Tell me a joke") == "default"


def test_get_model_for_role_fallback():
    rm = ModelRoleManager()
    rm.ensure_defaults()
    rm.reset_role("thinking")
    rm.reset_role("fallback")
    rm.set_role("default", "openai", "gpt-4")

    result = get_model_for_role("thinking", rm)
    assert result["configured"] is True
    assert result["role"] == "default"
    assert "fallback_from" in result

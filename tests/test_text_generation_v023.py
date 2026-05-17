import json
import os
import subprocess
from pathlib import Path

from runtime.action_log import list_external_actions
from runtime.agents import AgentRunner
from runtime.api.app import text_generate, text_providers
from runtime.providers import ModelHub
import runtime.providers.registry as registry


def test_generate_text_missing_openai_key_returns_setup(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = ModelHub().generate_text("Write a caption", provider_name="openai")

    assert result["status"] == "needs_provider_setup"
    assert result["provider"] == "openai"


def test_generate_text_mocked_openai_success(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-secret")
    monkeypatch.setattr(registry, "_post_json", lambda *_args, **_kwargs: {"choices": [{"message": {"content": "Hello from Liuant."}}], "usage": {"total_tokens": 5}})

    result = ModelHub().generate_text("Say hello", provider_name="openai", model="gpt-test")

    assert result["status"] == "completed"
    assert result["text"] == "Hello from Liuant."
    assert result["usage"]["total_tokens"] == 5


def test_generate_text_mocked_openai_error(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-secret")

    def fail(*_args, **_kwargs):
        raise RuntimeError("provider exploded with sk-test-secret")

    monkeypatch.setattr(registry, "_post_json", fail)
    result = ModelHub().generate_text("Say hello", provider_name="openai")

    assert result["status"] == "provider_error"
    assert "sk-test-secret" not in result["error"]


def test_generate_text_mocked_openrouter_success(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-secret")
    monkeypatch.setattr(registry, "_post_json", lambda *_args, **_kwargs: {"choices": [{"message": {"content": "OpenRouter response"}}]})

    result = ModelHub().generate_text("Say hello", provider_name="openrouter", model="openai/gpt-test")

    assert result["status"] == "completed"
    assert result["provider"] == "openrouter"


def test_ollama_unreachable_returns_local_unreachable(monkeypatch):
    def fail(*_args, **_kwargs):
        raise OSError("not running")

    monkeypatch.setattr(registry, "_get_json", fail)
    result = ModelHub().generate_text("Say hello", provider_name="ollama", model="llama3.1")

    assert result["status"] == "local_unreachable"


def test_custom_provider_missing_base_url_returns_setup():
    hub = ModelHub()
    hub.setup_provider("custom_openai_compatible", {"category": "text", "provider_type": "custom_openai_compatible", "base_url": "", "default_model": "test-model", "api_key_env": ""})

    result = hub.generate_text("Say hello", provider_name="custom_openai_compatible")

    assert result["status"] == "needs_provider_setup"
    assert "base_url" in result["error"]


def test_fallback_provider_is_attempted_when_primary_fails(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("FALLBACK_KEY", "fallback-secret")
    hub = ModelHub()
    hub.setup_provider("fallback_custom", {"category": "text", "provider_type": "custom_openai_compatible", "base_url": "http://fallback/v1", "default_model": "fallback-model", "api_key_env": "FALLBACK_KEY"})
    hub.set_fallback_provider("text", "fallback_custom")
    monkeypatch.setattr(registry, "_post_json", lambda *_args, **_kwargs: {"choices": [{"message": {"content": "Fallback worked"}}]})

    result = hub.generate_text("Say hello", provider_name="openai")

    assert result["status"] == "completed"
    assert result["fallback_used"] is True
    assert result["fallback_provider"] == "fallback_custom"


def test_no_raw_api_key_in_text_generation_response(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-visible-secret")

    def fail(*_args, **_kwargs):
        raise RuntimeError("bad sk-visible-secret")

    monkeypatch.setattr(registry, "_post_json", fail)
    response = json.dumps(ModelHub().generate_text("Say hello", provider_name="openai"))

    assert "sk-visible-secret" not in response


def test_no_raw_api_key_in_action_logs(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-log-secret")
    monkeypatch.setattr(registry, "_post_json", lambda *_args, **_kwargs: {"choices": [{"message": {"content": "ok"}}]})
    ModelHub().generate_text("password is secret", provider_name="openai")

    logs = json.dumps(list_external_actions())
    assert "sk-log-secret" not in logs
    assert "[sensitive redacted]" in logs


def test_api_text_generate_works_with_mocked_provider(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-api-secret")
    monkeypatch.setattr(registry, "_post_json", lambda *_args, **_kwargs: {"choices": [{"message": {"content": "API text"}}]})

    result = text_generate({"prompt": "Say hello", "provider_name": "openai", "model": "gpt-test"})

    assert result["status"] == "completed"
    assert result["text"] == "API text"


def test_text_providers_endpoint():
    rows = text_providers()

    assert any(row["id"] == "openai" for row in rows)


def test_cli_text_generate_missing_key(tmp_path):
    env = dict(os.environ)
    env.pop("OPENAI_API_KEY", None)
    env["LIUANT_DB_PATH"] = str(tmp_path / "cli-text.db")
    result = subprocess.run(["./liuant", "text", "generate", "Write a caption", "--provider", "openai"], cwd=Path(__file__).resolve().parents[1], env=env, capture_output=True, text=True, check=False)

    assert result.returncode == 0
    assert "needs_provider_setup" in result.stdout


def test_agent_run_without_ai_remains_deterministic():
    result = AgentRunner().run("marketing-agent", "Create campaign for Python course")

    assert "campaign_plan" in result["result"]
    assert "ai_enhancement" not in result["result"]


def test_agent_run_with_ai_provider_failure_keeps_local_output(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = AgentRunner().run("marketing-agent", "Create campaign for Python course", ai_enhancement=True, provider_name="openai")

    assert "campaign_plan" in result["result"]
    assert result["result"]["ai_enhancement"]["status"] == "needs_provider_setup"
    assert "local_output" in result["result"]


def test_agent_run_with_ai_mocked_success(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-agent-secret")
    monkeypatch.setattr(registry, "_post_json", lambda *_args, **_kwargs: {"choices": [{"message": {"content": "Enhanced agent output"}}]})

    result = AgentRunner().run("marketing-agent", "Create campaign for Python course", ai_enhancement=True, provider_name="openai", model="gpt-test")

    assert result["result"]["ai_enhanced_output"] == "Enhanced agent output"
    assert result["result"]["ai_enhancement"]["status"] == "completed"

import json
import os
import subprocess
from pathlib import Path

from runtime.agents import AgentProfileManager
from runtime.api.app import model_providers, models_status, provider_categories, providers, providers_status
from runtime.generation.image import ImageGenerationManager
from runtime.generation.video import VideoGenerationManager
from runtime.providers import ModelHub


def test_provider_registry_categories():
    categories = ModelHub().list_categories()

    assert "text" in categories
    assert "image" in categories
    assert "text_to_speech" in categories


def test_provider_list_by_category():
    text = ModelHub().list_providers("text")

    assert any(provider["id"] == "openai" for provider in text)
    assert all(provider["category"] == "text" for provider in text)


def test_provider_status_summary():
    status = ModelHub().get_status()

    assert status["provider_count"] >= 40
    assert status["defaults"]["image"] == "openai_image"


def test_enable_disable_provider():
    hub = ModelHub()
    hub.disable_provider("openrouter")
    assert hub.get_provider("openrouter")["is_enabled"] is False
    hub.enable_provider("openrouter")
    assert hub.get_provider("openrouter")["is_enabled"] is True


def test_set_default_provider_per_category():
    hub = ModelHub()
    default = hub.set_default_provider("image", "openai_image")

    assert default["id"] == "openai_image"
    assert hub.get_status()["defaults"]["image"] == "openai_image"


def test_set_fallback_provider_per_category():
    fallback = ModelHub().set_fallback_provider("text", "ollama")

    assert fallback["fallback_provider"] == "ollama"
    assert ModelHub().get_status()["fallbacks"]["text"] == "ollama"


def test_secret_masking():
    assert ModelHub().mask_secret("sk-test-secret-value") == "sk-t...alue"
    assert ModelHub().mask_secret("short") == "****"


def test_custom_provider_creation():
    created = ModelHub().setup_provider(
        "my_router",
        {
            "display_name": "My Router",
            "category": "text",
            "provider_type": "custom_openai_compatible",
            "base_url": "http://127.0.0.1:9999/v1",
            "api_key_env": "MY_ROUTER_KEY",
            "default_model": "router-model",
        },
    )

    assert created["id"] == "my_router"
    assert ModelHub().get_provider("my_router")["default_model"] == "router-model"


def test_old_api_models_endpoints_still_work():
    assert any(provider["id"] == "openai" for provider in model_providers())
    assert models_status()["default_provider"]


def test_provider_api_endpoints_work():
    assert "video" in provider_categories()
    assert any(provider["id"] == "openai_image" for provider in providers("image"))
    assert providers_status()["defaults"]["video"] == "hyperframes_skill"


def test_old_liuant_models_status_still_works(tmp_path):
    env = dict(os.environ)
    env["LIUANT_DB_PATH"] = str(tmp_path / "cli.db")
    result = subprocess.run(["./liuant", "models", "status"], cwd=Path(__file__).resolve().parents[1], env=env, capture_output=True, text=True, check=False)

    assert result.returncode == 0
    assert "default_provider" in result.stdout


def test_image_providers_come_from_model_hub():
    providers = ImageGenerationManager().list_providers()

    assert any(provider["id"] == "openai_image" for provider in providers)
    assert any(provider["id"] == "ideogram" for provider in providers)


def test_video_providers_come_from_model_hub():
    providers = VideoGenerationManager().list_providers()

    assert any(provider["id"] == "hyperframes_skill" for provider in providers)
    assert any(provider["id"] == "runway" for provider in providers)


def test_agent_provider_preferences_save_load():
    agent = AgentProfileManager().create(
        {
            "name": "Provider Agent",
            "slug": "provider-agent",
            "instructions": "Use configured providers.",
            "provider_preferences": {"text_provider": "openrouter", "image_provider": "openai_image", "video_provider": "hyperframes_skill"},
        }
    )

    stored = AgentProfileManager().show(agent["slug"])
    assert stored["provider_preferences"]["text_provider"] == "openrouter"


def test_no_raw_api_key_in_provider_api_responses(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-raw-secret-123456")
    response_text = json.dumps(providers_status())

    assert "sk-raw-secret-123456" not in response_text
    assert "sk-r...3456" in response_text

import os
import pytest
from unittest import mock
from runtime.providers import ModelHub
from runtime.providers import bedrock
from runtime.usage.tracker import UsageTracker
from runtime.chat.discussion import _is_cloud_provider
from runtime.model_router import resolve_role_for_chat

@pytest.fixture(autouse=True)
def clean_env():
    """Ensure environment is controlled for tests."""
    keys = ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN", "AWS_DEFAULT_REGION", "AWS_PROFILE"]
    old_vals = {k: os.environ.get(k) for k in keys}
    for k in keys:
        os.environ.pop(k, None)
    yield
    for k, v in old_vals.items():
        if v is not None:
            os.environ[k] = v
        else:
            os.environ.pop(k, None)

def test_bedrock_credential_loading():
    # When no env vars
    creds = bedrock.get_aws_credentials()
    assert "AWS_ACCESS_KEY_ID" not in creds
    assert "AWS_SECRET_ACCESS_KEY" not in creds
    assert "AWS_SESSION_TOKEN" not in creds
    assert bedrock.status() == "needs_provider_setup"

    # With env vars
    os.environ["AWS_ACCESS_KEY_ID"] = "AKIAEXAMPLEKEY"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "secretkeyhere12345"
    os.environ["AWS_DEFAULT_REGION"] = "us-west-2"
    creds = bedrock.get_aws_credentials()
    assert creds["AWS_ACCESS_KEY_ID"] == "AKIAEXAMPLEKEY"
    assert creds["AWS_SECRET_ACCESS_KEY"] == "secretkeyhere12345"
    assert creds["AWS_DEFAULT_REGION"] == "us-west-2"
    
    # Session region resolution
    assert bedrock.get_session().region_name == "us-west-2"
    assert bedrock.status() == "ready"

def test_bedrock_error_redaction():
    msg = "AccessDeniedException: User AKIAEXAMPLEKEY is not authorized to perform: bedrock:InvokeModel"
    os.environ["AWS_ACCESS_KEY_ID"] = "AKIAEXAMPLEKEY"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "secretkeyhere12345"
    
    # Need credentials set to trigger redaction of specific secrets
    redacted = bedrock.redact_error(Exception(msg))
    assert "AKIAEXAMPLEKEY" not in redacted
    assert "AKIA...EKEY" in redacted

    msg2 = "The Secret Access Key is secretkeyhere12345"
    redacted2 = bedrock.redact_error(Exception(msg2))
    assert "secretkeyhere12345" not in redacted2
    assert "secr...2345" in redacted2

def test_bedrock_generate_text():
    os.environ["AWS_ACCESS_KEY_ID"] = "AKIAEXAMPLEKEY"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "secretkey"
    
    mock_client = mock.MagicMock()
    mock_client.converse.return_value = {
        "output": {
            "message": {
                "content": [{"text": "Hello from Bedrock Converse!"}]
            }
        },
        "usage": {
            "inputTokens": 10,
            "outputTokens": 20
        }
    }
    
    with mock.patch("boto3.Session") as mock_session_class:
        mock_session = mock.MagicMock()
        mock_session.client.return_value = mock_client
        mock_session_class.return_value = mock_session
        
        res = bedrock.generate_text("Hi", system_prompt="System", model="us.amazon.nova-lite-v1:0")
        assert res["status"] == "completed"
        assert res["text"] == "Hello from Bedrock Converse!"
        assert res["usage"]["prompt_tokens"] == 10
        assert res["usage"]["completion_tokens"] == 20

def test_bedrock_stream_text():
    os.environ["AWS_ACCESS_KEY_ID"] = "AKIAEXAMPLEKEY"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "secretkey"
    
    mock_client = mock.MagicMock()
    # Mock event stream response
    mock_client.converse_stream.return_value = {
        "stream": [
            {"contentBlockDelta": {"delta": {"text": "Hello "}}},
            {"contentBlockDelta": {"delta": {"text": "world!"}}},
            {"metadata": {"usage": {"inputTokens": 5, "outputTokens": 8}}}
        ]
    }
    
    with mock.patch("boto3.Session") as mock_session_class:
        mock_session = mock.MagicMock()
        mock_session.client.return_value = mock_client
        mock_session_class.return_value = mock_session
        
        chunks = list(bedrock.stream_text("Hi", model="us.amazon.nova-micro-v1:0"))
        assert "".join(chunks) == "Hello world!"

def test_provider_profiles_setup_and_listing():
    hub = ModelHub()
    # Set up dynamic user profile
    hub.setup_provider("my_custom_openai", {
        "provider_type": "openai_compatible",
        "base_url": "https://api.mycustomopenai.com/v1",
        "api_key_env": "MY_CUSTOM_KEY",
        "default_model": "custom-gpt-4",
    })
    
    # List profiles should show my_custom_openai but not default ones
    profiles = hub.list_profiles()
    assert any(p["id"] == "my_custom_openai" for p in profiles)
    assert not any(p["id"] == "openai" for p in profiles)
    
    # Verify fallback route works for it
    prov = hub.get_provider("my_custom_openai")
    assert prov["provider_type"] == "openai_compatible"
    assert prov["base_url"] == "https://api.mycustomopenai.com/v1"

def test_estimate_cost_bedrock_models():
    tracker = UsageTracker()
    
    # Nova Micro
    cost_micro = tracker.estimate_cost("amazon_bedrock", 10000, 10000, model="us.amazon.nova-micro-v1:0")
    # input: 10 * 0.000035 = 0.00035, output: 10 * 0.00014 = 0.0014, total = 0.00175
    assert cost_micro["estimated_cost"] == 0.00175
    
    # Nova Pro
    cost_pro = tracker.estimate_cost("amazon_bedrock", 1000, 1000, model="us.amazon.nova-pro-v1:0")
    # input: 1 * 0.0008 = 0.0008, output: 1 * 0.0032 = 0.0032, total = 0.004
    assert cost_pro["estimated_cost"] == 0.004

    # Nova Lite (Default)
    cost_lite = tracker.estimate_cost("amazon_bedrock", 1000, 1000, model="us.amazon.nova-lite-v1:0")
    # input: 1 * 0.00006 = 0.00006, output: 1 * 0.00024 = 0.00024, total = 0.0003
    assert cost_lite["estimated_cost"] == 0.0003

def test_cloud_provider_detection():
    # OpenAI/OpenRouter/Bedrock should be cloud
    assert _is_cloud_provider("openai") is True
    assert _is_cloud_provider("openrouter") is True
    assert _is_cloud_provider("amazon_bedrock") is True
    assert _is_cloud_provider("bedrock") is True
    assert _is_cloud_provider("my_custom_openai") is True
    
    # Ollama/LM Studio should be local (False)
    assert _is_cloud_provider("ollama") is False
    assert _is_cloud_provider("lmstudio") is False

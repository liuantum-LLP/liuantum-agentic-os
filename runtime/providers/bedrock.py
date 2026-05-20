from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Generator

try:
    import boto3
    from botocore.exceptions import ClientError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False


def _read_secret(env_var: str) -> str:
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


def get_aws_credentials() -> dict[str, str]:
    creds = {}
    for var in ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN", "AWS_DEFAULT_REGION", "AWS_PROFILE"]:
        val = _read_secret(var)
        if val:
            creds[var] = val
    return creds


def get_session() -> boto3.Session:
    creds = get_aws_credentials()
    kwargs: dict[str, Any] = {}
    if creds.get("AWS_ACCESS_KEY_ID"):
        kwargs["aws_access_key_id"] = creds["AWS_ACCESS_KEY_ID"]
    if creds.get("AWS_SECRET_ACCESS_KEY"):
        kwargs["aws_secret_access_key"] = creds["AWS_SECRET_ACCESS_KEY"]
    if creds.get("AWS_SESSION_TOKEN"):
        kwargs["aws_session_token"] = creds["AWS_SESSION_TOKEN"]
    if creds.get("AWS_PROFILE"):
        kwargs["profile_name"] = creds["AWS_PROFILE"]
    
    # Region resolution
    region = creds.get("AWS_DEFAULT_REGION") or os.environ.get("AWS_REGION") or "us-east-1"
    kwargs["region_name"] = region
    
    return boto3.Session(**kwargs)


def status() -> str:
    if not BOTO3_AVAILABLE:
        return "needs_provider_setup"
    creds = get_aws_credentials()
    
    try:
        session = get_session()
        credentials = session.get_credentials()
        if credentials:
            return "ready"
    except Exception:
        pass
        
    if creds.get("AWS_PROFILE"):
        return "ready"
        
    # Check if direct credentials in environment
    if creds.get("AWS_ACCESS_KEY_ID") and creds.get("AWS_SECRET_ACCESS_KEY"):
        return "ready"
        
    return "needs_provider_setup"


def redact_error(exc: Exception | BaseException) -> str:
    text = str(exc)
    creds = get_aws_credentials()
    for k, v in creds.items():
        if v and len(v) > 4:
            text = text.replace(v, f"{v[:4]}...{v[-4:]}")
    # Redact common AWS authorization patterns
    text = re.sub(r"access_key_id=[A-Za-z0-9+/=]+", "access_key_id=[redacted]", text)
    text = re.sub(r"secret_access_key=[A-Za-z0-9+/=]+", "secret_access_key=[redacted]", text)
    text = re.sub(r"session_token=[A-Za-z0-9+/=]+", "session_token=[redacted]", text)
    text = re.sub(r"Signature=[a-f0-9]+", "Signature=[redacted]", text)
    text = re.sub(r"AWSAccessKeyId=[A-Za-z0-9]+", "AWSAccessKeyId=[redacted]", text)
    return text[:500]


def test(model_id: str | None = None) -> dict[str, Any]:
    if status() == "needs_provider_setup":
        return {"status": "needs_provider_setup", "error": "AWS Bedrock credentials are not configured."}
    
    model_id = model_id or "us.amazon.nova-lite-v1:0"
    try:
        session = get_session()
        client = session.client("bedrock-runtime")
        messages = [{"role": "user", "content": [{"text": "Hello"}]}]
        client.converse(
            modelId=model_id,
            messages=messages,
            inferenceConfig={"maxTokens": 5}
        )
        return {"status": "ready", "message": "Amazon Bedrock is successfully configured and verified."}
    except Exception as exc:
        return {"status": "provider_error", "error": redact_error(exc)}


def generate_text(
    prompt: str,
    system_prompt: str | None = None,
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int | None = None,
) -> dict[str, Any]:
    model_id = model or "us.amazon.nova-lite-v1:0"
    base = {
        "status": "needs_provider_setup",
        "provider": "amazon_bedrock",
        "model": model_id,
        "text": "",
        "error": None,
        "usage": {},
        "fallback_used": False,
        "fallback_provider": None,
    }
    
    if status() == "needs_provider_setup":
        return {**base, "status": "needs_provider_setup", "error": "AWS Bedrock credentials are not configured."}
        
    try:
        session = get_session()
        client = session.client("bedrock-runtime")
        messages = [{"role": "user", "content": [{"text": prompt}]}]
        
        kwargs: dict[str, Any] = {
            "modelId": model_id,
            "messages": messages,
        }
        if system_prompt:
            kwargs["system"] = [{"text": system_prompt}]
            
        inference_config: dict[str, Any] = {}
        if temperature is not None:
            inference_config["temperature"] = temperature
        if max_tokens is not None:
            inference_config["maxTokens"] = max_tokens
        if inference_config:
            kwargs["inferenceConfig"] = inference_config
            
        response = client.converse(**kwargs)
        
        output_message = response.get("output", {}).get("message", {})
        content_list = output_message.get("content", [])
        text = "".join(content.get("text", "") for content in content_list if "text" in content)
        
        raw_usage = response.get("usage", {})
        usage = {
            "prompt_tokens": raw_usage.get("inputTokens", 0),
            "completion_tokens": raw_usage.get("outputTokens", 0),
            "total_tokens": raw_usage.get("totalTokens", 0),
        }
        
        return {
            **base,
            "status": "completed",
            "text": text,
            "usage": usage,
        }
    except Exception as exc:
        err_msg = redact_error(exc)
        status_code = "provider_error"
        if "AccessDeniedException" in err_msg or "access denied" in err_msg.lower():
            status_code = "access_denied"
        elif "ModelNotReadyException" in err_msg or "ModelAccess" in err_msg or "not authorized to access" in err_msg.lower():
            status_code = "model_access_required"
        elif "ValidationException" in err_msg:
            status_code = "region_or_model_unavailable"
            
        return {
            **base,
            "status": status_code,
            "error": err_msg,
        }


def stream_text(
    prompt: str,
    system_prompt: str | None = None,
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int | None = None,
) -> Generator[str, None, None]:
    model_id = model or "us.amazon.nova-lite-v1:0"
    if status() == "needs_provider_setup":
        raise ValueError("AWS Bedrock credentials are not configured.")
        
    try:
        session = get_session()
        client = session.client("bedrock-runtime")
        messages = [{"role": "user", "content": [{"text": prompt}]}]
        
        kwargs: dict[str, Any] = {
            "modelId": model_id,
            "messages": messages,
        }
        if system_prompt:
            kwargs["system"] = [{"text": system_prompt}]
            
        inference_config: dict[str, Any] = {}
        if temperature is not None:
            inference_config["temperature"] = temperature
        if max_tokens is not None:
            inference_config["maxTokens"] = max_tokens
        if inference_config:
            kwargs["inferenceConfig"] = inference_config
            
        response = client.converse_stream(**kwargs)
        stream = response.get("stream")
        if stream:
            for event in stream:
                if "contentBlockDelta" in event:
                    delta = event["contentBlockDelta"]["delta"]
                    if "text" in delta:
                        yield delta["text"]
    except Exception as exc:
        raise Exception(redact_error(exc))

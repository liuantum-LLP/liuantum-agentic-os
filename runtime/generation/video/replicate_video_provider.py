from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .base import VideoProvider


class ReplicateVideoProvider(VideoProvider):
    name = "replicate_video"
    display_name = "Replicate Video Models"
    docs_url = "https://replicate.com/docs"
    env_vars = ("REPLICATE_API_TOKEN",)
    api_base = "https://api.replicate.com/v1"

    def is_configured(self) -> bool:
        return bool(self._env("REPLICATE_API_TOKEN"))

    def create_video_job(
        self,
        prompt: str,
        model: str | None = None,
        duration_seconds: int = 5,
        aspect_ratio: str = "16:9",
        resolution: str = "720p",
        style: str | None = None,
        input_assets: list[str] | None = None,
        workspace_name: str = "default",
    ) -> dict[str, Any]:
        token = self._env("REPLICATE_API_TOKEN")
        selected_model = model or self._env("REPLICATE_VIDEO_MODEL")
        if not token:
            return {
                "status": "needs_provider_setup",
                "provider": self.name,
                "setup_instructions": [
                    "Set REPLICATE_API_TOKEN in .env.local or the environment.",
                    "Set REPLICATE_VIDEO_MODEL or pass --model with a Replicate video model/version.",
                ],
            }
        if not selected_model:
            return {
                "status": "needs_model_setup",
                "provider": self.name,
                "setup_instructions": ["Set REPLICATE_VIDEO_MODEL or pass --model with the Replicate video model/version."],
            }

        payload: dict[str, Any] = {
            "input": {
                "prompt": prompt,
                "duration": duration_seconds,
                "aspect_ratio": aspect_ratio,
                "resolution": resolution,
            }
        }
        if style:
            payload["input"]["style"] = style
        if input_assets:
            payload["input"]["input_assets"] = input_assets
        if "/" in selected_model and ":" not in selected_model:
            payload["model"] = selected_model
        else:
            payload["version"] = selected_model
        try:
            data = post_json(f"{self.api_base}/predictions", payload, token)
        except Exception as exc:  # pragma: no cover - tests monkeypatch the transport layer.
            return {"status": "provider_error", "provider": self.name, "error": redact_provider_error(exc)}
        return self._prediction_to_result(data, selected_model)

    def poll_video_job(self, provider_job_id: str) -> dict[str, Any]:
        token = self._env("REPLICATE_API_TOKEN")
        if not token:
            return {"status": "needs_provider_setup", "provider": self.name, "provider_job_id": provider_job_id}
        try:
            data = get_json(f"{self.api_base}/predictions/{provider_job_id}", token)
        except Exception as exc:  # pragma: no cover - tests monkeypatch the transport layer.
            return {"status": "provider_error", "provider": self.name, "provider_job_id": provider_job_id, "error": redact_provider_error(exc)}
        result = self._prediction_to_result(data, data.get("model") or data.get("version"))
        result["provider_job_id"] = provider_job_id
        return result

    def cancel_video_job(self, provider_job_id: str) -> dict[str, Any]:
        token = self._env("REPLICATE_API_TOKEN")
        if not token:
            return {"status": "needs_provider_setup", "provider": self.name, "provider_job_id": provider_job_id}
        try:
            post_json(f"{self.api_base}/predictions/{provider_job_id}/cancel", {}, token)
        except Exception as exc:  # pragma: no cover - tests monkeypatch the transport layer.
            return {"status": "provider_error", "provider": self.name, "provider_job_id": provider_job_id, "error": redact_provider_error(exc)}
        return {"status": "cancelled", "provider": self.name, "provider_job_id": provider_job_id}

    def _prediction_to_result(self, data: dict[str, Any], model: str | None = None) -> dict[str, Any]:
        status = _map_status(str(data.get("status", "queued")))
        output_url = _first_output_url(data.get("output"))
        urls = data.get("urls") or {}
        result = {
            "status": status,
            "provider": self.name,
            "model": model,
            "provider_job_id": data.get("id"),
            "provider_status_url": urls.get("get"),
            "provider_output_url": output_url,
            "error": redact_provider_error(data.get("error")) if data.get("error") else None,
            "raw_status": data.get("status"),
        }
        if status == "completed" and not output_url:
            result["status"] = "provider_error"
            result["error"] = result["error"] or "Provider completed but did not return a video URL."
        return result

    def _env(self, key: str) -> str:
        if os.environ.get(key):
            return os.environ[key]
        for filename in (".env.local", ".env"):
            path = Path(filename)
            if not path.exists():
                continue
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip() or line.strip().startswith("#") or "=" not in line:
                    continue
                name, value = line.split("=", 1)
                if name.strip() == key:
                    return value.strip().strip('"').strip("'")
        return ""


def post_json(url: str, payload: dict[str, Any], token: str) -> dict[str, Any]:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    return _request_json(request)


def get_json(url: str, token: str) -> dict[str, Any]:
    request = Request(url, headers={"Authorization": f"Bearer {token}"}, method="GET")
    return _request_json(request)


def _request_json(request: Request) -> dict[str, Any]:
    with urlopen(request, timeout=60) as response:  # noqa: S310 - fixed provider URL.
        return json.loads(response.read().decode("utf-8"))


def _map_status(status: str) -> str:
    normalized = status.lower()
    if normalized in {"starting", "processing", "running"}:
        return "running"
    if normalized in {"queued", "created"}:
        return "queued"
    if normalized in {"succeeded", "success", "completed"}:
        return "completed"
    if normalized in {"canceled", "cancelled"}:
        return "cancelled"
    if normalized in {"failed", "error"}:
        return "failed"
    return "running"


def _first_output_url(output: Any) -> str | None:
    if isinstance(output, str) and output.startswith("https://"):
        return output
    if isinstance(output, list):
        for item in output:
            if isinstance(item, str) and item.startswith("https://"):
                return item
    if isinstance(output, dict):
        for key in ("video", "url", "output"):
            value = output.get(key)
            if isinstance(value, str) and value.startswith("https://"):
                return value
    return None


def redact_provider_error(error: Any) -> str:
    if error is None:
        return ""
    text = str(error)
    for value in ("REPLICATE_API_TOKEN", os.environ.get("REPLICATE_API_TOKEN", "")):
        if value:
            text = text.replace(value, "[redacted]")
    if isinstance(error, (HTTPError, URLError)):
        text = error.__class__.__name__
    return text[:500]

from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from runtime.action_log import log_external_action
from runtime.config import ModelProviderConfigManager
from runtime.exports import ExportTracker
from runtime.storage import ROOT

from .base import ImageGenerationJob, ImageProvider


class OpenAIImageProvider(ImageProvider):
    name = "openai"
    display_name = "OpenAI Image Generation"
    docs_url = "https://platform.openai.com/docs/guides/image-generation"
    env_vars = ("OPENAI_API_KEY",)

    def is_configured(self) -> bool:
        return bool(self._api_key())

    def describe(self) -> dict:
        data = super().describe()
        provider = next((row for row in ModelProviderConfigManager().list() if row["id"] == "openai"), {})
        data.update(
            {
                "default_model": os.environ.get("OPENAI_IMAGE_MODEL") or provider.get("default_model") or "gpt-image-1",
                "provider_status": "configured" if self.is_configured() else "missing_key",
                "setup_instruction": None
                if self.is_configured()
                else "Set OPENAI_API_KEY in .env, .env.local, or your environment to enable real image generation. Without it, Liuant saves a prompt package.",
            }
        )
        return data

    def generate(self, job: ImageGenerationJob, output_dir: Path) -> ImageGenerationJob:
        if not self.is_configured():
            job.metadata["provider_status"] = "missing_key"
            log_external_action("image_generation_attempt", "needs_provider_setup", _safe_job_preview(job), self.name)
            return super().generate(job, output_dir)
        log_external_action("image_generation_attempt", "started", {"id": job.id, "provider": self.name, "prompt": job.prompt, "provider_status": "configured"}, self.name)
        try:
            image_bytes, mime_type = self._call_openai(job)
            suffix = ".png" if mime_type == "image/png" else ".jpg"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = (output_dir / f"{job.id}{suffix}").resolve()
            self._ensure_workspace_path(output_path)
            output_path.write_bytes(image_bytes)
            job.status = "completed"
            job.output_path = str(output_path)
            job.setup_instruction = None
            job.metadata["mime_type"] = mime_type
            job.metadata["model"] = os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-1")
            job.metadata["provider_status"] = "completed"
            ExportTracker().record("generated_image", "image_jobs", job.id, str(output_path), suffix.lstrip("."))
            log_external_action("image_generation_completed", "completed", {"id": job.id, "output_path": str(output_path)}, self.name)
        except Exception as exc:
            error = _redact_secret(str(exc), self._api_key())
            job.status = "provider_error"
            job.output_path = None
            job.setup_instruction = "OpenAI image generation failed. Check provider key, model, size, and API access."
            job.metadata["error"] = error
            job.metadata["provider_status"] = "provider_error"
            log_external_action("image_generation_failed", "provider_error", {"id": job.id, "error": error}, self.name)
        return job

    def _api_key(self) -> str | None:
        load_dotenv()
        return os.environ.get("OPENAI_API_KEY")

    def _call_openai(self, job: ImageGenerationJob) -> tuple[bytes, str]:
        key = self._api_key()
        if not key:
            raise ValueError("OPENAI_API_KEY is not configured")
        provider = next((row for row in ModelProviderConfigManager().list() if row["id"] == "openai"), {})
        base_url = (provider.get("base_url") or "https://api.openai.com/v1").rstrip("/")
        model = os.environ.get("OPENAI_IMAGE_MODEL") or provider.get("default_model") or "gpt-image-1"
        payload = {
            "model": model,
            "prompt": build_prompt(job),
            "size": normalize_size(job.size, model),
        }
        request = urllib.request.Request(
            f"{base_url}/images/generations",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenAI image API error {exc.code}: {body[:500]}") from exc
        item = data.get("data", [{}])[0]
        if item.get("b64_json"):
            return base64.b64decode(item["b64_json"]), "image/png"
        if item.get("url"):
            with urllib.request.urlopen(item["url"], timeout=120) as response:
                content_type = response.headers.get("content-type", "image/png").split(";")[0]
                return response.read(), content_type
        raise RuntimeError("OpenAI image API returned no image payload")

    def _ensure_workspace_path(self, path: Path) -> None:
        root = ROOT.resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise RuntimeError("Refusing to write generated image outside the workspace") from exc


def load_dotenv() -> None:
    env_path = ROOT / ".env"
    local_env_path = ROOT / ".env.local"
    for path in (env_path, local_env_path):
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


def build_prompt(job: ImageGenerationJob) -> str:
    parts = [job.prompt]
    if job.style:
        parts.append(f"Style: {job.style}.")
    if job.negative_prompt:
        parts.append(f"Avoid: {job.negative_prompt}.")
    return "\n".join(parts)


def normalize_size(size: str, model: str) -> str:
    if model.startswith("gpt-image") and size in {"1024x1792", "1792x1024"}:
        return "1024x1536" if size == "1024x1792" else "1536x1024"
    return size


def _redact_secret(value: str, secret: str | None) -> str:
    if secret:
        value = value.replace(secret, "[redacted]")
    return value


def _safe_job_preview(job: ImageGenerationJob) -> dict:
    preview = job.to_dict()
    preview.setdefault("metadata", {})["provider_status"] = "missing_key"
    return preview

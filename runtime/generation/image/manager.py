from __future__ import annotations

from pathlib import Path

from runtime.action_log import log_external_action
from runtime.db import get_record, insert_record, list_records
from runtime.exports import export_image_prompt_markdown
from runtime.generation.hyperframes_packages import create_hyperframes_image_package, write_image_package
from runtime.providers import ModelHub
from runtime.storage import WORKSPACE

from .automatic1111_provider import Automatic1111Provider
from .base import ImageGenerationJob, ImageProvider
from .comfyui_provider import ComfyUIProvider
from .openai_image_provider import OpenAIImageProvider
from .replicate_provider import ReplicateProvider
from .stability_provider import StabilityProvider


class ImageGenerationManager:
    def __init__(self) -> None:
        self.output_dir = WORKSPACE / "outputs" / "images"
        self.providers: dict[str, ImageProvider] = {
            provider.name: provider
            for provider in (
                OpenAIImageProvider(),
                StabilityProvider(),
                ReplicateProvider(),
                ComfyUIProvider(),
                Automatic1111Provider(),
            )
        }

    def list_providers(self) -> list[dict]:
        providers = ModelHub().list_providers("image")
        legacy_openai = next((provider for provider in providers if provider["id"] == "openai_image"), None)
        if legacy_openai:
            legacy = dict(legacy_openai)
            legacy["id"] = "openai"
            legacy["name"] = "openai"
            legacy["display_name"] = "OpenAI Image (legacy alias)"
            legacy["alias_for"] = "openai_image"
            providers.append(legacy)
        return providers

    def list_jobs(self) -> list[dict]:
        return list_records("image_jobs")

    def get_job(self, job_id: str) -> dict | None:
        return get_record("image_jobs", job_id)

    def generate(
        self,
        prompt: str,
        provider_name: str = "openai",
        provider: str | None = None,
        negative_prompt: str | None = None,
        size: str = "1024x1024",
        style: str = "clean editorial",
        generation_mode: str = "model_based",
        template_name: str | None = None,
        template: str | None = None,
        platform: str | None = None,
        workspace_name: str | None = None,
        creative_type: str | None = None,
    ) -> dict:
        if generation_mode == "hyperframes_skill":
            return self._generate_hyperframes_package(
                prompt=prompt,
                size=size,
                style=style,
                template_name=template_name or template,
                platform=platform,
                creative_type=creative_type,
                workspace_name=workspace_name,
            )

        provider_key = provider or provider_name
        if provider_key in {None, "", "openai"}:
            resolved = ModelHub().resolve_provider_for_task("image", None)
            provider_key = resolved["id"]
        else:
            resolved = ModelHub().resolve_provider_for_task("image", provider_key)
            provider_key = resolved["id"]
        image_provider = self.providers.get(self._provider_adapter_key(provider_key)) or ImageProvider()
        image_provider.name = provider_key
        image_provider.display_name = resolved.get("display_name", provider_key)
        image_provider.env_vars = tuple([resolved.get("api_key_env")] if resolved.get("api_key_env") else [])
        job = ImageGenerationJob(
            provider=provider_key,
            prompt=prompt,
            negative_prompt=negative_prompt,
            size=size,
            style=style,
            generation_mode="model_based",
            template_name=template_name or template,
            platform=platform,
            render_type="rendered_output",
        )
        self.output_dir.mkdir(parents=True, exist_ok=True)
        job = image_provider.generate(job, Path(self.output_dir))
        row = insert_record("image_jobs", job.to_dict())
        prompt_path = export_image_prompt_markdown(row["id"])
        if row["status"] == "completed" and row.get("output_path"):
            row.setdefault("metadata", {})["prompt_package_path"] = prompt_path
            row["output_package_path"] = prompt_path
            row["render_type"] = "rendered_output"
        else:
            row["output_path"] = prompt_path
            row["output_package_path"] = prompt_path
            row["render_type"] = "prompt_package"
        log_external_action(
            "image_generation",
            row["status"],
            {
                "job_id": row["id"],
                "provider": row["provider"],
                "generation_mode": row["generation_mode"],
                "render_type": row["render_type"],
                "workspace_name": workspace_name,
            },
        )
        return insert_record("image_jobs", row)

    def _provider_adapter_key(self, provider_key: str) -> str:
        aliases = {
            "openai_image": "openai",
            "custom_image_api": "custom",
            "ideogram": "custom",
            "leonardo": "custom",
        }
        return aliases.get(provider_key, provider_key)

    def _generate_hyperframes_package(
        self,
        prompt: str,
        size: str,
        style: str,
        template_name: str | None,
        platform: str | None,
        creative_type: str | None,
        workspace_name: str | None,
    ) -> dict:
        package = create_hyperframes_image_package(prompt, template_name, platform, creative_type)
        job = ImageGenerationJob(
            provider="hyperframes",
            prompt=prompt,
            size=size,
            style=style,
            status="package_ready",
            generation_mode="hyperframes_skill",
            skill_name="hyperframes-image-skill",
            template_name=package["template"],
            platform=package["platform"],
            render_type="prompt_package",
            metadata=package,
        )
        row = insert_record("image_jobs", job.to_dict())
        package_path = write_image_package(row)
        row["output_package_path"] = package_path
        row["output_path"] = package_path
        log_external_action(
            "image_hyperframes_package",
            "package_ready",
            {
                "job_id": row["id"],
                "generation_mode": "hyperframes_skill",
                "render_type": "prompt_package",
                "workspace_name": workspace_name,
            },
        )
        return insert_record("image_jobs", row)

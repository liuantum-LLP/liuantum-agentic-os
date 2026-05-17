from __future__ import annotations

from pathlib import Path

from runtime.action_log import log_external_action
from runtime.db import get_record, insert_record, list_records, update_record
from runtime.exports import export_video_storyboard_markdown
from runtime.generation.hyperframes_packages import write_video_package
from runtime.providers import ModelHub
from runtime.storage import WORKSPACE

from .base import VideoGenerationJob, VideoProvider, create_hyperframes_video_package, create_video_package, utc_now
from .kling_provider import KlingProvider
from .local_comfyui_video_provider import LocalComfyUIVideoProvider
from .luma_provider import LumaProvider
from .openai_sora_provider import OpenAISoraProvider
from .pika_provider import PikaProvider
from .replicate_video_provider import ReplicateVideoProvider
from .runway_provider import RunwayProvider


class VideoGenerationManager:
    def __init__(self) -> None:
        self.output_dir = WORKSPACE / "outputs" / "videos"
        self.providers: dict[str, VideoProvider] = {
            provider.name: provider
            for provider in (
                OpenAISoraProvider(),
                RunwayProvider(),
                PikaProvider(),
                LumaProvider(),
                KlingProvider(),
                ReplicateVideoProvider(),
                LocalComfyUIVideoProvider(),
            )
        }

    def list_providers(self) -> list[dict]:
        providers = ModelHub().list_providers("video")
        for provider_id, alias_for, display_name in (
            ("openai_sora", "openai_video", "OpenAI Sora (legacy alias)"),
            ("local_comfyui_video", "comfyui_video", "Local ComfyUI Video (legacy alias)"),
        ):
            source = next((provider for provider in providers if provider["id"] == alias_for), None)
            if source:
                legacy = dict(source)
                legacy["id"] = provider_id
                legacy["name"] = provider_id
                legacy["display_name"] = display_name
                legacy["alias_for"] = alias_for
                providers.append(legacy)
        return providers

    def list_jobs(self) -> list[dict]:
        return list_records("video_jobs")

    def get_job(self, job_id: str) -> dict | None:
        return get_record("video_jobs", job_id)

    def storyboard(
        self,
        topic: str | None = None,
        prompt: str | None = None,
        duration_seconds: int = 30,
        aspect_ratio: str = "9:16",
        generation_mode: str = "model_based",
        template_name: str | None = None,
        template: str | None = None,
        platform: str | None = None,
        workspace_name: str | None = None,
        scene_count: int = 4,
        provider_name: str | None = None,
        provider: str | None = None,
        style: str | None = None,
        resolution: str | None = None,
    ) -> dict:
        topic = topic or prompt or ""
        if generation_mode == "hyperframes_skill":
            return self._generate_hyperframes_package(
                prompt=topic,
                duration_seconds=duration_seconds,
                aspect_ratio=aspect_ratio,
                resolution="1080p",
                style="modern social video",
                template_name=template_name or template,
                platform=platform,
                workspace_name=workspace_name,
                scene_count=scene_count,
                status="package_ready",
            )
        package = create_video_package(topic, duration_seconds, aspect_ratio)
        job = VideoGenerationJob(
            provider="storyboard",
            prompt=topic,
            duration_seconds=duration_seconds,
            aspect_ratio=aspect_ratio,
            status="storyboard_ready",
            generation_mode="model_based",
            render_type="storyboard_package",
            metadata=package,
        )
        row = insert_record("video_jobs", job.to_dict())
        row["output_path"] = export_video_storyboard_markdown(row["id"])
        row["output_package_path"] = row["output_path"]
        log_external_action("video_storyboard", "storyboard_ready", {"job_id": row["id"], "generation_mode": "model_based"})
        return insert_record("video_jobs", row)

    def generate(
        self,
        prompt: str,
        provider_name: str = "openai_sora",
        provider: str | None = None,
        model: str | None = None,
        duration_seconds: int = 30,
        aspect_ratio: str = "9:16",
        resolution: str = "1080p",
        style: str = "modern social video",
        generation_mode: str = "model_based",
        template_name: str | None = None,
        template: str | None = None,
        platform: str | None = None,
        workspace_name: str | None = None,
        scene_count: int = 4,
        input_assets: list[str] | None = None,
    ) -> dict:
        if generation_mode == "hyperframes_skill":
            return self._generate_hyperframes_package(
                prompt=prompt,
                duration_seconds=duration_seconds,
                aspect_ratio=aspect_ratio,
                resolution=resolution,
                style=style,
                template_name=template_name or template,
                platform=platform,
                workspace_name=workspace_name,
                scene_count=scene_count,
                status="package_ready",
            )

        provider_key = provider or provider_name
        resolved_name = self._resolve_provider_name(provider_key)
        adapter_key = self._provider_adapter_key(resolved_name)
        video_provider = self.providers.get(adapter_key) or self.providers["openai_sora"]
        job = VideoGenerationJob(
            provider=provider_key if provider_key in {"openai_sora", "local_comfyui_video"} else resolved_name,
            prompt=prompt,
            model=model,
            duration_seconds=duration_seconds,
            aspect_ratio=aspect_ratio,
            resolution=resolution,
            style=style,
            generation_mode="model_based",
            template_name=template_name or template,
            platform=platform,
            render_type="provider_job" if resolved_name == "replicate_video" else "provider_ready_package",
            input_assets=input_assets or [],
        )
        self.output_dir.mkdir(parents=True, exist_ok=True)
        log_external_action(
            "video_job_created",
            "created",
            {"job_id": job.id, "provider": job.provider, "generation_mode": "model_based", "sensitive_redacted": self._contains_sensitive(prompt)},
        )
        if resolved_name == "replicate_video":
            log_external_action("video_provider_request_started", "started", {"job_id": job.id, "provider": job.provider})
            result = video_provider.create_video_job(
                prompt=prompt,
                model=model,
                duration_seconds=duration_seconds,
                aspect_ratio=aspect_ratio,
                resolution=resolution,
                style=style,
                input_assets=input_assets or [],
                workspace_name=workspace_name or "default",
            )
            job.status = result.get("status", "provider_error")
            job.model = result.get("model") or model
            job.provider_job_id = result.get("provider_job_id")
            job.provider_status_url = result.get("provider_status_url")
            job.provider_output_url = result.get("provider_output_url")
            job.setup_instructions = result.get("setup_instructions", [])
            job.setup_instruction = "; ".join(job.setup_instructions) if job.setup_instructions else None
            job.error = result.get("error")
            job.metadata.update({"provider_result": {k: v for k, v in result.items() if k not in {"error"}}})
            if job.status in {"needs_provider_setup", "needs_model_setup", "provider_error", "failed"}:
                job.metadata.update(create_video_package(prompt, duration_seconds, aspect_ratio))
            if job.status == "completed":
                job.completed_at = utc_now()
            log_external_action(
                "video_provider_request_completed" if job.status not in {"provider_error", "failed"} else "video_provider_request_failed",
                job.status,
                {"job_id": job.id, "provider": job.provider, "provider_job_id": job.provider_job_id, "error": bool(job.error)},
            )
        else:
            job = video_provider.generate(job, Path(self.output_dir))
        row = insert_record("video_jobs", job.to_dict())
        if row["status"] in {"placeholder", "needs_provider_setup", "needs_model_setup", "provider_error", "failed"} or row["render_type"] == "provider_ready_package":
            row["output_package_path"] = export_video_storyboard_markdown(row["id"])
            if row["render_type"] != "provider_job":
                row["output_path"] = row["output_package_path"]
        log_external_action(
            "video_generation",
            row["status"],
            {"job_id": row["id"], "provider": row["provider"], "generation_mode": "model_based", "render_type": row["render_type"]},
        )
        return insert_record("video_jobs", row)

    def poll_job(self, job_id: str) -> dict:
        row = get_record("video_jobs", job_id)
        if not row:
            return {"status": "not_found", "job_id": job_id}
        provider = self.providers.get(self._provider_adapter_key(row.get("provider", "")))
        if not provider or not row.get("provider_job_id"):
            return {"status": "placeholder", "job_id": job_id, "error": "No provider job id is available."}
        result = provider.poll_video_job(row["provider_job_id"])
        updates = self._provider_result_updates(result)
        if updates.get("status") == "completed" and updates.get("provider_output_url"):
            download = provider.download_video_output(updates["provider_output_url"], row.get("workspace_name", "default"), job_id, self.output_dir)
            if download.get("status") == "completed":
                updates["output_path"] = download["output_path"]
            else:
                updates["status"] = "output_url_available"
                updates["error"] = download.get("error")
        updates["updated_at"] = utc_now()
        if updates.get("status") == "completed":
            updates["completed_at"] = utc_now()
        saved = update_record("video_jobs", job_id, updates)
        log_external_action("video_job_polled", saved["status"], {"job_id": job_id, "provider": saved.get("provider"), "provider_job_id": saved.get("provider_job_id")})
        return saved

    def download_job(self, job_id: str) -> dict:
        row = get_record("video_jobs", job_id)
        if not row:
            return {"status": "not_found", "job_id": job_id}
        provider = self.providers.get(self._provider_adapter_key(row.get("provider", "")))
        if not provider or not row.get("provider_output_url"):
            return {"status": "provider_error", "job_id": job_id, "error": "No provider output URL is available."}
        result = provider.download_video_output(row["provider_output_url"], row.get("workspace_name", "default"), job_id, self.output_dir)
        updates = {"updated_at": utc_now(), "error": result.get("error")}
        if result.get("status") == "completed":
            updates.update({"status": "completed", "output_path": result["output_path"], "completed_at": utc_now()})
            log_external_action("video_output_downloaded", "completed", {"job_id": job_id, "output_path": result["output_path"]})
        else:
            updates.update({"status": "provider_error"})
            log_external_action("video_output_downloaded", "provider_error", {"job_id": job_id, "error": result.get("error")})
        return update_record("video_jobs", job_id, updates)

    def cancel_job(self, job_id: str) -> dict:
        row = get_record("video_jobs", job_id)
        if not row:
            return {"status": "not_found", "job_id": job_id}
        provider = self.providers.get(self._provider_adapter_key(row.get("provider", "")))
        result = provider.cancel_video_job(row.get("provider_job_id")) if provider and row.get("provider_job_id") else {"status": "cancelled"}
        saved = update_record("video_jobs", job_id, {"status": result.get("status", "cancelled"), "updated_at": utc_now(), "error": result.get("error")})
        log_external_action("video_job_cancelled", saved["status"], {"job_id": job_id, "provider": saved.get("provider")})
        return saved

    def export_job(self, job_id: str) -> dict:
        return {"video_storyboard_markdown": export_video_storyboard_markdown(job_id)}

    def _resolve_provider_name(self, provider_key: str | None) -> str:
        if provider_key in {None, ""}:
            return ModelHub().resolve_provider_for_task("video", None)["id"]
        aliases = {"openai_sora": "openai_video", "local_comfyui_video": "comfyui_video", "hyperframes": "hyperframes_skill"}
        return aliases.get(provider_key, provider_key)

    def _provider_adapter_key(self, provider_key: str) -> str:
        aliases = {"openai_video": "openai_sora", "comfyui_video": "local_comfyui_video", "hyperframes_skill": "openai_sora"}
        return aliases.get(provider_key, provider_key)

    def _generate_hyperframes_package(
        self,
        prompt: str,
        duration_seconds: int,
        aspect_ratio: str,
        resolution: str,
        style: str,
        template_name: str | None,
        platform: str | None,
        workspace_name: str | None,
        scene_count: int,
        status: str,
    ) -> dict:
        package = create_hyperframes_video_package(prompt, duration_seconds, aspect_ratio, template_name, platform, scene_count)
        job = VideoGenerationJob(
            provider="hyperframes",
            prompt=prompt,
            duration_seconds=duration_seconds,
            aspect_ratio=aspect_ratio,
            resolution=resolution,
            style=style,
            status=status,
            generation_mode="hyperframes_skill",
            skill_name="hyperframes-video-skill",
            template_name=package["template"],
            platform=package["platform"],
            render_type="html_package",
            metadata=package,
        )
        row = insert_record("video_jobs", job.to_dict())
        package_path = write_video_package(row)
        row["output_package_path"] = package_path
        row["output_path"] = package_path
        log_external_action(
            "video_hyperframes_package",
            status,
            {
                "job_id": row["id"],
                "generation_mode": "hyperframes_skill",
                "render_type": "html_package",
                "workspace_name": workspace_name,
            },
        )
        return insert_record("video_jobs", row)

    def _provider_result_updates(self, result: dict) -> dict:
        return {
            key: value
            for key, value in {
                "status": result.get("status"),
                "model": result.get("model"),
                "provider_job_id": result.get("provider_job_id"),
                "provider_status_url": result.get("provider_status_url"),
                "provider_output_url": result.get("provider_output_url"),
                "error": result.get("error"),
            }.items()
            if value is not None
        }

    def _contains_sensitive(self, text: str) -> bool:
        lowered = (text or "").lower()
        return any(term in lowered for term in ("password", "otp", "token", "api key", "confidential", "aadhaar", "pan", "credit card"))

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class VideoGenerationJob:
    provider: str
    prompt: str
    model: str | None = None
    duration_seconds: int = 30
    aspect_ratio: str = "9:16"
    resolution: str = "1080p"
    style: str = "modern social video"
    status: str = "created"
    output_path: str | None = None
    generation_mode: str = "model_based"
    skill_name: str | None = None
    template_name: str | None = None
    output_package_path: str | None = None
    platform: str | None = None
    render_type: str = "storyboard_package"
    input_assets: list[str] = field(default_factory=list)
    provider_job_id: str | None = None
    provider_status_url: str | None = None
    provider_output_url: str | None = None
    error: str | None = None
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    completed_at: str | None = None
    id: str = field(default_factory=lambda: str(uuid4()))
    setup_instruction: str | None = None
    setup_instructions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class VideoProvider:
    name = "custom"
    display_name = "Custom Video Provider"
    docs_url: str | None = None
    env_vars: tuple[str, ...] = ()

    def is_configured(self) -> bool:
        return False

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "docs_url": self.docs_url,
            "env_vars": list(self.env_vars),
            "configured": self.is_configured(),
        }

    def generate(self, job: VideoGenerationJob, output_dir: Path) -> VideoGenerationJob:
        job.status = "placeholder"
        job.setup_instruction = (
            f"Configure {self.display_name} for actual video generation. "
            "This provider is config-ready; Liuant returns script, scene plan, shot list, and provider-ready prompts."
        )
        job.setup_instructions = [job.setup_instruction]
        job.metadata.update(create_video_package(job.prompt, job.duration_seconds, job.aspect_ratio))
        return job

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
        return {
            "status": "placeholder",
            "provider": self.name,
            "model": model,
            "setup_instructions": [f"{self.display_name} is config-ready; no live API client is implemented yet."],
        }

    def poll_video_job(self, provider_job_id: str) -> dict[str, Any]:
        return {"status": "placeholder", "provider": self.name, "provider_job_id": provider_job_id}

    def download_video_output(self, provider_output_url: str, workspace_name: str, job_id: str, output_dir: Path) -> dict[str, Any]:
        return download_video_url(provider_output_url, output_dir, job_id)

    def cancel_video_job(self, provider_job_id: str) -> dict[str, Any]:
        return {"status": "placeholder", "provider": self.name, "provider_job_id": provider_job_id}


ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov"}


def validate_video_output_url(url: str) -> tuple[bool, str | None, str | None]:
    parsed = urlparse(url or "")
    if parsed.scheme != "https":
        return False, None, "Only https video output URLs can be downloaded."
    suffix = Path(parsed.path).suffix.lower()
    if suffix not in ALLOWED_VIDEO_EXTENSIONS:
        return False, None, f"Unsupported video extension: {suffix or 'none'}"
    return True, suffix, None


def download_url_bytes(url: str, headers: dict[str, str] | None = None, timeout: int = 60) -> bytes:
    request = Request(url, headers=headers or {})
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 - URL scheme is validated before this helper is used.
        return response.read()


def download_video_url(url: str, output_dir: Path, job_id: str) -> dict[str, Any]:
    valid, suffix, error = validate_video_output_url(url)
    if not valid:
        return {"status": "provider_error", "error": error}
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = (output_dir / f"video-output-{job_id}{suffix}").resolve()
    if not str(output_path).startswith(str(output_dir.resolve())):
        return {"status": "provider_error", "error": "Unsafe output path rejected."}
    output_path.write_bytes(download_url_bytes(url))
    return {"status": "completed", "output_path": str(output_path)}


def create_video_package(topic: str, duration_seconds: int = 30, aspect_ratio: str = "9:16") -> dict[str, Any]:
    return {
        "video_concept": f"A clear, benefit-led video about {topic}.",
        "scene_breakdown": [
            {"scene": 1, "duration": "0-5s", "goal": "Hook the viewer with the core problem."},
            {"scene": 2, "duration": "5-15s", "goal": "Show the transformation or learning outcome."},
            {"scene": 3, "duration": "15-25s", "goal": "Add proof, examples, or workflow visuals."},
            {"scene": 4, "duration": f"25-{duration_seconds}s", "goal": "Close with a direct call to action."},
        ],
        "shot_list": [
            "Fast opening title frame",
            "Instructor or product workflow shot",
            "Animated bullet highlights",
            "Final CTA frame",
        ],
        "image_prompts": [
            f"High-quality {aspect_ratio} visual for {topic}, modern education marketing style",
            f"Clean thumbnail concept for {topic}, readable title space, premium lighting",
        ],
        "voiceover_script": (
            f"If you want to understand {topic}, start with the outcome. "
            "Learn the workflow, practice with real tasks, and build something you can show."
        ),
        "on_screen_text": ["Start with the outcome", "Build real projects", "Practice with guidance", "Join now"],
        "video_generation_prompt": f"{duration_seconds}s {aspect_ratio} video: {topic}, modern, polished, educational.",
    }


def create_hyperframes_video_package(
    topic: str,
    duration_seconds: int = 30,
    aspect_ratio: str = "9:16",
    template_name: str | None = None,
    platform: str | None = None,
    scene_count: int = 4,
) -> dict[str, Any]:
    scenes = []
    for index in range(1, max(scene_count, 1) + 1):
        scenes.append(
            {
                "scene": index,
                "duration": f"{round((index - 1) * duration_seconds / max(scene_count, 1))}-{round(index * duration_seconds / max(scene_count, 1))}s",
                "goal": [
                    "Open with a sharp promise and visual hook.",
                    "Show the user problem in one concrete moment.",
                    "Demonstrate the Liuant workflow or product value.",
                    "Close with proof, CTA, and next action.",
                ][min(index - 1, 3)],
            }
        )
    return {
        "skill": "hyperframes-video-skill",
        "template": template_name or "premium-launch-story",
        "platform": platform or "general",
        "concept": f"A polished HyperFrames-ready video package for {topic}.",
        "storyboard": scenes,
        "scene_breakdown": scenes,
        "shot_list": [
            "Full-bleed opening title with product/context signal",
            "Fast workflow close-up with concise overlay text",
            "Benefit proof sequence with UI or campaign visuals",
            "CTA end frame with clear next step",
        ],
        "frame_prompts": [
            f"{aspect_ratio} keyframe for {topic}, premium product marketing, clean composition, readable space",
            f"{aspect_ratio} workflow visual for {topic}, crisp UI details, modern lighting",
            f"{aspect_ratio} CTA frame for {topic}, high contrast, simple focal point",
        ],
        "on_screen_text": ["Launch faster", "Plan with agents", "Approve every action", "Build with Liuant"],
        "voiceover_script": (
            f"Meet {topic}. Plan campaigns, create assets, prepare drafts, and keep every external action under approval."
        ),
        "cta": "Open Liuant Agentic OS and create your first agentic campaign.",
        "html_css_video_package_plan": {
            "rendered_output": False,
            "composition": "HyperFrames HTML/CSS package plan",
            "layout": "Full-bleed visual scene with restrained controls and platform-safe text zones.",
            "animation": "Seek-safe CSS or timeline-driven scene transitions; no external publishing.",
            "assets": "Use generated frame prompts or approved workspace assets only.",
        },
        "video_generation_prompt": f"{duration_seconds}s {aspect_ratio} video: {topic}, premium, clear CTA, platform {platform or 'general'}.",
    }

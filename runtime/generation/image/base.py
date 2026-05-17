from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ImageGenerationJob:
    provider: str
    prompt: str
    negative_prompt: str | None = None
    size: str = "1024x1024"
    style: str = "clean editorial"
    status: str = "queued"
    output_path: str | None = None
    generation_mode: str = "model_based"
    skill_name: str | None = None
    template_name: str | None = None
    output_package_path: str | None = None
    platform: str | None = None
    render_type: str = "prompt_package"
    created_at: str = field(default_factory=utc_now)
    id: str = field(default_factory=lambda: str(uuid4()))
    setup_instruction: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ImageProvider:
    name = "custom"
    display_name = "Custom Image Provider"
    docs_url: str | None = None
    env_vars: tuple[str, ...] = ()

    def is_configured(self) -> bool:
        return False

    def describe(self) -> dict[str, Any]:
        configured = self.is_configured()
        return {
            "name": self.name,
            "display_name": self.display_name,
            "docs_url": self.docs_url,
            "env_vars": list(self.env_vars),
            "configured": configured,
            "status": "configured" if configured else "missing_key",
            "setup_instruction": None if configured else f"Set {', '.join(self.env_vars) or 'provider credentials'} in .env, .env.local, or the environment.",
        }

    def generate(self, job: ImageGenerationJob, output_dir: Path) -> ImageGenerationJob:
        job.status = "needs_provider_setup"
        job.setup_instruction = (
            f"Configure {self.display_name} to generate images. "
            "For now, use this prompt directly in your chosen image tool."
        )
        job.metadata["ready_to_use_prompt"] = job.prompt
        return job

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from runtime.db import insert_record, list_records


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ContentPackage:
    topic: str
    platforms: list[str]
    campaign_goal: str
    target_audience: str
    tone: str = "practical, confident, friendly"
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(default_factory=utc_now)
    status: str = "draft"
    assets: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ContentCreator:
    def create_package(
        self,
        topic: str,
        platforms: list[str] | None = None,
        campaign_goal: str = "Create awareness and generate leads",
        target_audience: str = "Learners and business owners",
        tone: str = "practical, confident, friendly",
    ) -> dict[str, Any]:
        platforms = platforms or ["x", "linkedin", "instagram", "youtube"]
        assets = {
            "post_ideas": [f"{topic}: misconception", f"{topic}: practical roadmap", f"{topic}: success story"],
            "captions": {platform: f"{topic} made practical for {target_audience}. Start with one focused project." for platform in platforms},
            "hashtags": ["#AI", "#Learning", "#BuildInPublic", "#CareerGrowth"],
            "short_form_video_scripts": [
                {
                    "hook": f"Most people learn {topic} backwards.",
                    "body": "Start from a project, learn the pieces as you build, and ship something real.",
                    "cta": "Ask for the roadmap or join the next cohort.",
                }
            ],
            "carousel": [
                "Outcome first",
                "Tools you need",
                "Project roadmap",
                "Practice tasks",
                "How to join",
            ],
            "poster_copy": {
                "headline": f"Master {topic}",
                "subheadline": "Guided projects, practical tasks, and career-ready outcomes.",
                "cta": "Apply now",
            },
            "image_prompts": [f"Premium education poster for {topic}, clean layout, clear headline space"],
            "video_prompts": [f"30 second vertical promotional video for {topic}, modern learning brand"],
            "brand_tone_guide": {
                "voice": tone,
                "avoid": ["overpromising outcomes", "platform policy violations", "fake urgency"],
            },
            "content_calendar": [
                {"day": day, "theme": theme}
                for day, theme in enumerate(["problem", "roadmap", "proof", "behind the scenes", "offer"], start=1)
            ],
        }
        package = ContentPackage(
            topic=topic,
            platforms=platforms,
            campaign_goal=campaign_goal,
            target_audience=target_audience,
            tone=tone,
            assets=assets,
        )
        item = package.to_dict()
        item["record_type"] = "content_package"
        return insert_record("agent_runs", item)

    def list_packages(self) -> list[dict[str, Any]]:
        return list_records("agent_runs")

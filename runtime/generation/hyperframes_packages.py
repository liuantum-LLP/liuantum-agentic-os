from __future__ import annotations

from pathlib import Path
from typing import Any

from runtime.config import ExportTracker
from runtime.exports import outputs_dir, write_text


def create_hyperframes_image_package(
    prompt: str,
    template_name: str | None = None,
    platform: str | None = None,
    creative_type: str | None = None,
) -> dict[str, Any]:
    platform_name = platform or "general"
    template = template_name or "premium-social-visual"
    return {
        "skill": "hyperframes-image-skill",
        "template": template,
        "platform": platform_name,
        "creative_type": creative_type or "poster",
        "creative_brief": {
            "objective": f"Create a polished {platform_name} asset for: {prompt}",
            "audience": "Prospects who need a clear, premium, useful first impression.",
            "tone": "Confident, modern, practical, and approval-safe.",
        },
        "image_prompt_pack": [
            f"{prompt}, premium editorial composition, clear focal subject, refined lighting, no copied logos",
            f"{prompt}, platform-safe text space, high contrast, professional product marketing style",
            f"{prompt}, clean visual hierarchy, realistic workspace context, ready for campaign adaptation",
        ],
        "layout_plan": {
            "canvas": "Use the selected platform format with safe margins for headline, CTA, and brand lockup.",
            "structure": "Hero visual first, compact headline zone, supporting proof point, final CTA.",
            "accessibility": "Keep text readable, avoid dense copy, preserve contrast.",
        },
        "platform_asset_package": {
            "platform": platform_name,
            "deliverables": ["prompt package", "layout plan", "caption starter", "export checklist"],
            "caption_starter": f"Turn {prompt} into a clear offer, one proof point, and a direct call to action.",
        },
        "rendering_note": "No rendered bitmap is claimed unless a configured image provider returns one.",
    }


def write_image_package(job: dict[str, Any]) -> str:
    metadata = job.get("metadata", {})
    rows = [
        "# HyperFrames Image Package",
        "",
        f"- Job: {job['id']}",
        f"- Mode: {job.get('generation_mode')}",
        f"- Skill: {job.get('skill_name')}",
        f"- Template: {job.get('template_name')}",
        f"- Platform: {job.get('platform')}",
        f"- Render type: {job.get('render_type')}",
        "",
        "## Creative Brief",
        _format_block(metadata.get("creative_brief", {})),
        "",
        "## Image Prompt Pack",
        *[f"- {item}" for item in metadata.get("image_prompt_pack", [])],
        "",
        "## Layout Plan",
        _format_block(metadata.get("layout_plan", {})),
        "",
        "## Platform Asset Package",
        _format_block(metadata.get("platform_asset_package", {})),
        "",
        "## Rendering Note",
        metadata.get("rendering_note", ""),
        "",
    ]
    path = write_text(outputs_dir("images") / f"hyperframes-image-package-{job['id']}.md", "\n".join(rows))
    ExportTracker().record("hyperframes_image_package", "image_jobs", job["id"], path, "markdown")
    return path


def write_video_package(job: dict[str, Any]) -> str:
    metadata = job.get("metadata", {})
    rows = [
        "# HyperFrames Video Package",
        "",
        f"- Job: {job['id']}",
        f"- Mode: {job.get('generation_mode')}",
        f"- Skill: {job.get('skill_name')}",
        f"- Template: {job.get('template_name')}",
        f"- Platform: {job.get('platform')}",
        f"- Render type: {job.get('render_type')}",
        "",
        "## Concept",
        metadata.get("concept") or metadata.get("video_concept", ""),
        "",
        "## Storyboard",
        *[f"- Scene {scene.get('scene')} ({scene.get('duration')}): {scene.get('goal')}" for scene in metadata.get("storyboard", metadata.get("scene_breakdown", []))],
        "",
        "## Shot List",
        *[f"- {item}" for item in metadata.get("shot_list", [])],
        "",
        "## Frame Prompts",
        *[f"- {item}" for item in metadata.get("frame_prompts", metadata.get("image_prompts", []))],
        "",
        "## On-Screen Text",
        *[f"- {item}" for item in metadata.get("on_screen_text", [])],
        "",
        "## Voiceover",
        metadata.get("voiceover_script", ""),
        "",
        "## CTA",
        metadata.get("cta", ""),
        "",
        "## HTML/CSS/Video Package Plan",
        _format_block(metadata.get("html_css_video_package_plan", {})),
        "",
    ]
    path = write_text(outputs_dir("videos") / f"hyperframes-video-package-{job['id']}.md", "\n".join(rows))
    ExportTracker().record("hyperframes_video_package", "video_jobs", job["id"], path, "markdown")
    return path


def ensure_workspace_path(path: str) -> str:
    return str(Path(path).resolve())


def _format_block(value: Any) -> str:
    if isinstance(value, dict):
        return "\n".join(f"- {key}: {item}" for key, item in value.items())
    if isinstance(value, list):
        return "\n".join(f"- {item}" for item in value)
    return str(value)

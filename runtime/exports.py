from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from runtime.db import get_record
from runtime.config import ExportTracker, SettingsManager, WorkspaceManager
from runtime.storage import WORKSPACE


def outputs_dir(*parts: str) -> Path:
    export_root = Path(SettingsManager().get("export_root")["value"])
    path = export_root / Path(*parts)
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_text(path: Path, content: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return str(path)


def export_campaign_markdown(campaign_id: str) -> str:
    campaign = _must_get("social_campaigns", campaign_id)
    rows = [
        f"# {campaign['campaign_name']}",
        "",
        f"- Status: {campaign.get('status', 'draft')}",
        f"- Workspace: {campaign.get('workspace_name', '')}",
        f"- Platforms: {', '.join(campaign.get('platforms_json', []))}",
        "",
        "## Content Items",
    ]
    for item in campaign.get("content_items_json", []):
        rows.extend(
            [
                "",
                f"### Day {item.get('day')} - {item.get('platform')}",
                f"**Post:** {item.get('post_text')}",
                f"**Image prompt:** {item.get('image_prompt')}",
                f"**Video script:** {item.get('video_script')}",
            ]
        )
    path = write_text(outputs_dir("social") / f"campaign-{campaign_id}.md", "\n".join(rows) + "\n")
    ExportTracker().record("social_campaign", "social_campaigns", campaign_id, path, "markdown")
    return path


def export_content_calendar_csv(campaign_id: str) -> str:
    campaign = _must_get("social_campaigns", campaign_id)
    path = outputs_dir("social") / f"content-calendar-{campaign_id}.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["day", "platform", "goal", "audience", "post_text", "image_prompt", "video_script", "status"])
        writer.writeheader()
        for item in campaign.get("content_items_json", []):
            writer.writerow({field: item.get(field, "") for field in writer.fieldnames or []})
    ExportTracker().record("content_calendar", "social_campaigns", campaign_id, str(path), "csv")
    return str(path)


def export_image_prompt_markdown(job_id: str) -> str:
    job = _must_get("image_jobs", job_id)
    content = "\n".join(
        [
            f"# Image Prompt Package",
            "",
            f"- Job: {job_id}",
            f"- Provider: {job.get('provider')}",
            f"- Status: {job.get('status')}",
            f"- Size: {job.get('size')}",
            f"- Style: {job.get('style')}",
            "",
            "## Prompt",
            job.get("prompt", ""),
            "",
            "## Setup",
            job.get("setup_instruction") or "Provider configured.",
            "",
        ]
    )
    path = write_text(outputs_dir("images") / f"image-job-{job_id}.md", content)
    ExportTracker().record("image_prompt_package", "image_jobs", job_id, path, "markdown")
    return path


def export_video_storyboard_markdown(job_id: str) -> str:
    job = _must_get("video_jobs", job_id)
    metadata = job.get("metadata", {})
    rows = [
        "# Video Storyboard",
        "",
        f"- Job: {job_id}",
        f"- Prompt: {job.get('prompt')}",
        f"- Status: {job.get('status')}",
        f"- Aspect ratio: {job.get('aspect_ratio')}",
        "",
        "## Concept",
        metadata.get("video_concept", ""),
        "",
        "## Scene Breakdown",
    ]
    for scene in metadata.get("scene_breakdown", []):
        rows.append(f"- Scene {scene.get('scene')} ({scene.get('duration')}): {scene.get('goal')}")
    rows.extend(["", "## Shot List"])
    rows.extend([f"- {item}" for item in metadata.get("shot_list", [])])
    rows.extend(["", "## Voiceover", metadata.get("voiceover_script", ""), "", "## Generation Prompt", metadata.get("video_generation_prompt", "")])
    path = write_text(outputs_dir("videos") / f"video-storyboard-{job_id}.md", "\n".join(rows) + "\n")
    ExportTracker().record("video_storyboard", "video_jobs", job_id, path, "markdown")
    return path


def export_agent_run_markdown(run_id: str) -> str:
    run = _must_get("agent_runs", run_id)
    content = "\n".join(
        [
            "# Agent Run Report",
            "",
            f"- Run: {run_id}",
            f"- Agent: {run.get('agent_slug') or run.get('record_type', 'content_package')}",
            f"- Status: {run.get('status')}",
            f"- Created: {run.get('created_at')}",
            "",
            "## Prompt",
            run.get("prompt") or run.get("topic", ""),
            "",
            "## Result",
            "```json",
            _pretty_json(run.get("result", run)),
            "```",
            "",
        ]
    )
    path = write_text(outputs_dir("agents") / f"agent-run-{run_id}.md", content)
    ExportTracker().record("agent_run_report", "agent_runs", run_id, path, "markdown")
    return path


def save_social_draft_markdown(draft: dict[str, Any]) -> str:
    content = f"# Social Draft\n\n- Platform: {draft.get('platform')}\n- Status: {draft.get('status')}\n\n{draft.get('text', '')}\n"
    path = write_text(outputs_dir("social") / f"draft-{draft['id']}.md", content)
    ExportTracker().record("social_draft", "social_drafts", draft["id"], path, "markdown")
    return path


def save_email_draft_markdown(draft: dict[str, Any]) -> str:
    content = f"# Email Draft\n\n- Subject: {draft.get('subject')}\n- To: {', '.join(draft.get('to', []))}\n- Status: {draft.get('status')}\n\n{draft.get('body', '')}\n"
    path = write_text(outputs_dir("email") / f"email-draft-{draft['id']}.md", content)
    ExportTracker().record("email_draft", "email_drafts", draft["id"], path, "markdown")
    return path


def _must_get(table: str, item_id: str) -> dict[str, Any]:
    item = get_record(table, item_id)
    if not item:
        raise ValueError(f"Cannot export missing {table} record: {item_id}")
    return item


def _pretty_json(data: Any) -> str:
    import json

    return json.dumps(data, indent=2, sort_keys=True)

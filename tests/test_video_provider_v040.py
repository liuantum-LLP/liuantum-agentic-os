from __future__ import annotations

import json
from types import SimpleNamespace

from cli.liuant import dispatch
from runtime.action_log import list_external_actions
from runtime.api import app as api_app
from runtime.db import insert_record
from runtime.generation.video import VideoGenerationManager
from runtime.generation.video import replicate_video_provider as replicate
from runtime.generation.video import base as video_base
from runtime.generation.video.base import download_video_url
from runtime.storage import WORKSPACE


def test_video_generate_missing_replicate_token_returns_setup(monkeypatch):
    monkeypatch.delenv("REPLICATE_API_TOKEN", raising=False)
    job = VideoGenerationManager().generate("launch video", provider_name="replicate_video", model="owner/model")

    assert job["status"] == "needs_provider_setup"
    assert job["provider"] == "replicate_video"
    assert not job.get("output_path")
    assert job["output_package_path"].endswith(".md")


def test_video_generate_missing_model_returns_needs_model(monkeypatch):
    monkeypatch.setenv("REPLICATE_API_TOKEN", "r8_secret")
    monkeypatch.delenv("REPLICATE_VIDEO_MODEL", raising=False)

    job = VideoGenerationManager().generate("launch video", provider_name="replicate_video")

    assert job["status"] == "needs_model_setup"
    assert not json.dumps(job).find("r8_secret") >= 0


def test_mock_replicate_create_prediction_returns_queued(monkeypatch):
    monkeypatch.setenv("REPLICATE_API_TOKEN", "r8_secret")

    def fake_post(url, payload, token):
        return {"id": "pred-1", "status": "starting", "urls": {"get": "https://api.replicate.com/v1/predictions/pred-1"}}

    monkeypatch.setattr(replicate, "post_json", fake_post)
    job = VideoGenerationManager().generate("launch video", provider_name="replicate_video", model="owner/model")

    assert job["status"] == "running"
    assert job["provider_job_id"] == "pred-1"
    assert job["provider_status_url"].endswith("pred-1")


def test_mock_replicate_poll_running_updates_job(monkeypatch):
    monkeypatch.setenv("REPLICATE_API_TOKEN", "r8_secret")
    job = _replicate_job("pred-running")
    monkeypatch.setattr(replicate, "get_json", lambda url, token: {"id": "pred-running", "status": "processing"})

    updated = VideoGenerationManager().poll_job(job["id"])

    assert updated["status"] == "running"


def test_mock_replicate_poll_succeeded_stores_output_url(monkeypatch):
    monkeypatch.setenv("REPLICATE_API_TOKEN", "r8_secret")
    job = _replicate_job("pred-done")
    monkeypatch.setattr(
        replicate,
        "get_json",
        lambda url, token: {"id": "pred-done", "status": "succeeded", "output": ["https://cdn.example.com/out.mp4"]},
    )
    monkeypatch.setattr(replicate.ReplicateVideoProvider, "download_video_output", lambda self, url, workspace_name, job_id, output_dir: {"status": "provider_error", "error": "download unavailable"})

    updated = VideoGenerationManager().poll_job(job["id"])

    assert updated["provider_output_url"] == "https://cdn.example.com/out.mp4"
    assert updated["status"] == "output_url_available"


def test_mock_video_download_saves_file_inside_workspace(monkeypatch):
    monkeypatch.setattr(video_base, "download_url_bytes", lambda url: b"video-bytes")
    result = download_video_url("https://cdn.example.com/video.mp4", WORKSPACE / "outputs" / "videos", "job-1")

    assert result["status"] == "completed"
    assert result["output_path"].startswith(str((WORKSPACE / "outputs" / "videos").resolve()))


def test_download_rejects_non_https_url():
    result = download_video_url("http://cdn.example.com/video.mp4", WORKSPACE / "outputs" / "videos", "job-1")

    assert result["status"] == "provider_error"


def test_download_rejects_unsafe_extension():
    result = download_video_url("https://cdn.example.com/video.exe", WORKSPACE / "outputs" / "videos", "job-1")

    assert result["status"] == "provider_error"


def test_provider_error_does_not_claim_completed(monkeypatch):
    monkeypatch.setenv("REPLICATE_API_TOKEN", "r8_secret")
    monkeypatch.setattr(replicate, "post_json", lambda url, payload, token: (_ for _ in ()).throw(RuntimeError("boom r8_secret")))

    job = VideoGenerationManager().generate("launch video", provider_name="replicate_video", model="owner/model")

    assert job["status"] == "provider_error"
    assert not job.get("provider_job_id")
    assert "r8_secret" not in json.dumps(job)


def test_hyperframes_video_package_still_works():
    job = VideoGenerationManager().generate("launch video", generation_mode="hyperframes_skill")

    assert job["status"] == "package_ready"
    assert job["render_type"] == "html_package"
    assert job["output_package_path"].endswith(".md")


def test_video_jobs_record_includes_provider_job_status(monkeypatch):
    monkeypatch.setenv("REPLICATE_API_TOKEN", "r8_secret")
    monkeypatch.setattr(replicate, "post_json", lambda url, payload, token: {"id": "pred-record", "status": "queued"})

    job = VideoGenerationManager().generate("record test", provider_name="replicate_video", model="owner/model")
    saved = VideoGenerationManager().get_job(job["id"])

    assert saved["provider_job_id"] == "pred-record"
    assert saved["status"] == "queued"


def test_cli_video_poll_works(monkeypatch):
    monkeypatch.setenv("REPLICATE_API_TOKEN", "r8_secret")
    job = _replicate_job("pred-cli")
    monkeypatch.setattr(replicate, "get_json", lambda url, token: {"id": "pred-cli", "status": "processing"})

    result = dispatch(SimpleNamespace(area="video", command="poll", args=[job["id"]]))

    assert result["status"] == "running"


def test_api_video_poll_works(monkeypatch):
    monkeypatch.setenv("REPLICATE_API_TOKEN", "r8_secret")
    job = _replicate_job("pred-api")
    monkeypatch.setattr(replicate, "get_json", lambda url, token: {"id": "pred-api", "status": "processing"})

    result = api_app.video_job_poll(job["id"])

    assert result["status"] == "running"


def test_action_logs_redact_provider_key_and_sensitive_prompt(monkeypatch):
    monkeypatch.setenv("REPLICATE_API_TOKEN", "r8_secret")
    monkeypatch.setattr(replicate, "post_json", lambda url, payload, token: (_ for _ in ()).throw(RuntimeError("r8_secret failed")))

    VideoGenerationManager().generate("confidential token launch", provider_name="replicate_video", model="owner/model")
    logs = list_external_actions()
    payload = json.dumps(logs)

    assert "r8_secret" not in payload
    assert any(log["action_type"] == "video_job_created" and log["preview"].get("sensitive_redacted") for log in logs)


def test_video_export_endpoint_returns_markdown(monkeypatch):
    monkeypatch.delenv("REPLICATE_API_TOKEN", raising=False)
    job = VideoGenerationManager().generate("export video", provider_name="replicate_video", model="owner/model")

    result = api_app.video_job_export_get(job["id"])

    assert result["video_storyboard_markdown"].endswith(".md")


def _replicate_job(provider_job_id: str) -> dict:
    return insert_record(
        "video_jobs",
        {
            "id": f"job-{provider_job_id}",
            "provider": "replicate_video",
            "prompt": "test video",
            "generation_mode": "model_based",
            "render_type": "provider_job",
            "provider_job_id": provider_job_id,
            "status": "queued",
            "created_at": "2026-01-01T00:00:00+00:00",
        },
    )

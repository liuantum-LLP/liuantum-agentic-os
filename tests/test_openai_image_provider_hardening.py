from pathlib import Path

from runtime.api.app import image_generate, image_jobs
from runtime.generation.image import ImageGenerationManager
from runtime.generation.image.openai_image_provider import OpenAIImageProvider
from runtime.storage import ROOT


def test_openai_missing_key_returns_needs_provider_setup(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    job = ImageGenerationManager().generate("missing key poster", generation_mode="model_based")

    assert job["status"] == "needs_provider_setup"
    assert job["metadata"]["provider_status"] == "missing_key"
    assert job["output_path"].endswith(".md")
    assert Path(job["output_path"]).exists()


def test_openai_success_saves_image_file(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    def fake_call(self, job):
        return b"\x89PNG\r\n\x1a\nmock-image", "image/png"

    monkeypatch.setattr(OpenAIImageProvider, "_call_openai", fake_call)
    job = ImageGenerationManager().generate("successful poster", generation_mode="model_based")

    assert job["status"] == "completed"
    assert job["render_type"] == "rendered_output"
    assert job["output_path"].endswith(".png")
    assert Path(job["output_path"]).read_bytes().startswith(b"\x89PNG")
    assert job["output_package_path"].endswith(".md")


def test_openai_provider_error_status_and_prompt_package(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "secret-key-value")

    def fake_call(self, job):
        raise RuntimeError("provider rejected secret-key-value")

    monkeypatch.setattr(OpenAIImageProvider, "_call_openai", fake_call)
    job = ImageGenerationManager().generate("failing poster", generation_mode="model_based")

    assert job["status"] == "provider_error"
    assert job["render_type"] == "prompt_package"
    assert "[redacted]" in job["metadata"]["error"]
    assert "secret-key-value" not in job["metadata"]["error"]
    assert job["output_path"].endswith(".md")
    assert Path(job["output_path"]).exists()


def test_openai_completed_output_path_is_workspace_safe(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    def fake_call(self, job):
        return b"\x89PNG\r\n\x1a\nmock-image", "image/png"

    monkeypatch.setattr(OpenAIImageProvider, "_call_openai", fake_call)
    job = ImageGenerationManager().generate("workspace safe completed poster", generation_mode="model_based")

    Path(job["output_path"]).resolve().relative_to(ROOT.resolve())


def test_api_image_jobs_endpoint_returns_completed_and_provider_error(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    def fake_success(self, job):
        return b"\x89PNG\r\n\x1a\nmock-image", "image/png"

    monkeypatch.setattr(OpenAIImageProvider, "_call_openai", fake_success)
    completed = image_generate({"prompt": "api completed image", "generation_mode": "model_based"})

    def fake_error(self, job):
        raise RuntimeError("provider down")

    monkeypatch.setattr(OpenAIImageProvider, "_call_openai", fake_error)
    failed = image_generate({"prompt": "api failed image", "generation_mode": "model_based"})
    rows = image_jobs()

    assert completed["status"] == "completed"
    assert failed["status"] == "provider_error"
    assert any(row["id"] == completed["id"] for row in rows)
    assert any(row["id"] == failed["id"] for row in rows)

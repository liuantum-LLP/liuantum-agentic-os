from pathlib import Path

from runtime.api.app import image_generate, image_jobs, image_providers
from runtime.generation.image import ImageGenerationManager
from runtime.storage import ROOT


def test_image_generation_without_provider_key_returns_setup(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    job = ImageGenerationManager().generate("AI-powered software company poster")

    assert job["status"] == "needs_provider_setup"
    assert "Configure OpenAI" in job["setup_instruction"]


def test_image_job_is_saved(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    job = ImageGenerationManager().generate("poster for AI course")

    assert ImageGenerationManager().get_job(job["id"])["id"] == job["id"]


def test_prompt_export_is_saved(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    job = ImageGenerationManager().generate("prompt package")

    assert job["output_path"].endswith(".md")
    assert Path(job["output_path"]).exists()


def test_provider_list_endpoint_works():
    providers = image_providers()

    assert any(provider["name"] == "openai" for provider in providers)


def test_output_path_is_workspace_safe(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    job = ImageGenerationManager().generate("workspace safe")

    output_path = Path(job["output_path"]).resolve()
    output_path.relative_to(ROOT.resolve())


def test_api_image_job_listing_works(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    created = image_generate({"prompt": "api image job"})
    jobs = image_jobs()

    assert any(job["id"] == created["id"] for job in jobs)

from pathlib import Path

from runtime.config import ExportTracker, SkillManager
from runtime.generation.image import ImageGenerationManager
from runtime.generation.video import VideoGenerationManager
from runtime.storage import ROOT


def test_image_job_with_model_based_mode(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    job = ImageGenerationManager().generate("AI course poster", generation_mode="model_based")

    assert job["generation_mode"] == "model_based"
    assert job["status"] == "needs_provider_setup"
    assert job["render_type"] == "prompt_package"


def test_image_job_with_hyperframes_skill_mode():
    job = ImageGenerationManager().generate(
        "AI course poster",
        generation_mode="hyperframes_skill",
        template_name="premium-course-poster",
        platform="linkedin",
    )

    assert job["status"] == "package_ready"
    assert job["skill_name"] == "hyperframes-image-skill"
    assert job["template_name"] == "premium-course-poster"
    assert Path(job["output_package_path"]).exists()


def test_video_job_with_model_based_mode():
    job = VideoGenerationManager().generate("launch promo", generation_mode="model_based")

    assert job["generation_mode"] == "model_based"
    assert job["provider"] == "openai_sora"
    assert job["output_package_path"].endswith(".md")


def test_video_storyboard_with_hyperframes_skill_mode():
    job = VideoGenerationManager().storyboard(
        "Liuant launch video",
        generation_mode="hyperframes_skill",
        template_name="launch-story",
        platform="youtube",
    )

    assert job["status"] == "package_ready"
    assert job["skill_name"] == "hyperframes-video-skill"
    assert "html_css_video_package_plan" in job["metadata"]


def test_dual_mode_output_paths_are_workspace_safe():
    image_job = ImageGenerationManager().generate("safe image package", generation_mode="hyperframes_skill")
    video_job = VideoGenerationManager().generate("safe video package", generation_mode="hyperframes_skill")

    Path(image_job["output_package_path"]).resolve().relative_to(ROOT.resolve())
    Path(video_job["output_package_path"]).resolve().relative_to(ROOT.resolve())


def test_package_export_creation_and_skill_definitions():
    image_job = ImageGenerationManager().generate("exportable package", generation_mode="hyperframes_skill")
    video_job = VideoGenerationManager().generate("exportable video package", generation_mode="hyperframes_skill")
    exports = ExportTracker().list()
    skills = SkillManager().available_skills()

    assert any(row["source_id"] == image_job["id"] for row in exports)
    assert any(row["source_id"] == video_job["id"] for row in exports)
    assert any(row["skill_name"] == "hyperframes-image-skill" for row in skills)
    assert any(row["skill_name"] == "hyperframes-video-skill" for row in skills)

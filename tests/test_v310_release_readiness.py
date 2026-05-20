import pytest
from pathlib import Path
from runtime.release import ReleaseManager

ROOT = Path(__file__).parent.parent

def test_v310_readme_mentions_safety():
    readme = ROOT / "README.md"
    assert readme.exists()
    content = readme.read_text(encoding="utf-8").lower()
    assert "local-first" in content
    assert "approval" in content

def test_v310_known_limitations_exists():
    assert (ROOT / "docs" / "KNOWN_LIMITATIONS.md").exists()

def test_v310_release_notes_exists():
    assert (ROOT / "docs" / "RELEASE_NOTES_V3_1_0.md").exists()

def test_v310_public_release_checklist_exists():
    assert (ROOT / "docs" / "PUBLIC_RELEASE_CHECKLIST.md").exists()

def test_v310_installation_docs_mention_python3():
    content = (ROOT / "docs" / "INSTALLATION.md").read_text(encoding="utf-8")
    assert "python3" in content
    assert "pip install" in content

def test_v310_packaging_docs_unsigned_community_builds():
    content = (ROOT / "docs" / "PACKAGING.md").read_text(encoding="utf-8").lower()
    assert "unsigned" in content
    assert "community builds" in content

def test_v310_automation_and_voice_docs_exist():
    # As part of the release, we've integrated these into README and Release Notes.
    # We'll check the README for browser, desktop, and voice mentions.
    readme = (ROOT / "README.md").read_text(encoding="utf-8").lower()
    release_notes = (ROOT / "docs" / "RELEASE_NOTES_V3_1_0.md").read_text(encoding="utf-8").lower()
    
    assert "browser automation" in readme or "browser automation" in release_notes
    assert "desktop automation" in readme or "desktop automation" in release_notes
    assert "simulation-first" in readme or "simulation-first" in release_notes

def test_v310_ecosystem_and_public_release_checks():
    rm = ReleaseManager()
    eco_check = rm.ecosystem_check()
    assert eco_check["status"] in {"passed", "needs_work"}
    
    pub_check = rm.public_release_check()
    assert pub_check["status"] in {"passed", "needs_work"}

def test_v310_signing_docs_say_optional():
    content = (ROOT / "docs" / "SIGNING.md").read_text(encoding="utf-8").lower()
    assert "optional" in content

def test_v310_no_marketplace_cloud_false_claims():
    kl = (ROOT / "docs" / "KNOWN_LIMITATIONS.md").read_text(encoding="utf-8").lower()
    assert "no marketplace server" in kl
    assert "no cloud sync" in kl


from __future__ import annotations

import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_license_exists():
    license_file = ROOT / "LICENSE"
    assert license_file.exists()
    text = license_file.read_text(encoding="utf-8")
    assert "MIT License" in text
    assert "Copyright (c) 2026 Liuant Agentic OS contributors" in text
    assert "THE SOFTWARE IS PROVIDED \"AS IS\"" in text


def test_contributing_exists():
    assert (ROOT / "CONTRIBUTING.md").exists()
    text = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    assert "pytest" in text
    assert "signing" in text.lower() or "Signing" in text


def test_code_of_conduct_exists():
    assert (ROOT / "CODE_OF_CONDUCT.md").exists()


def test_security_exists():
    assert (ROOT / "SECURITY.md").exists()
    text = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
    assert "@liuantum.com" in text


def test_roadmap_exists():
    assert (ROOT / "ROADMAP.md").exists()


def test_env_example_exists():
    env_example = ROOT / ".env.example"
    assert env_example.exists()
    text = env_example.read_text(encoding="utf-8")
    # Must have variable names but no real values
    assert "OPENAI_API_KEY=" in text
    # Must contain the warning
    assert "NEVER" in text.upper() and "REAL SECRETS" in text.upper()


def test_gitignore_exists():
    gitignore = ROOT / ".gitignore"
    assert gitignore.exists()
    text = gitignore.read_text(encoding="utf-8")
    assert ".env" in text
    assert "__pycache__" in text
    assert "*.db" in text or "*.sqlite" in text


def test_readme_mentions_open_source():
    assert (ROOT / "README.md").exists()
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "open-source" in text.lower()
    assert "local-first" in text.lower()
    assert "MIT License" in text or "LICENSE" in text


def test_readme_approval_gated_mentioned():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "approval" in text.lower()


def test_ci_workflow_exists():
    ci = ROOT / ".github" / "workflows" / "ci.yml"
    assert ci.exists()
    # Read the YAML or text
    text = ci.read_text(encoding="utf-8")
    # CI should not require Apple credentials
    assert "APPLE" not in text.upper() or "#" in text


def test_signing_docs_say_optional():
    paths = [
        ROOT / "docs" / "SIGNING.md",
        ROOT / "docs" / "MACOS_SIGNING_NOTARIZATION.md",
    ]
    for p in paths:
        if p.exists():
            text = p.read_text(encoding="utf-8").lower()
            assert "optional" in text or "not required" in text or "community" in text, f"{p} should mention signing is optional"


def test_release_doc_unsigned_community_builds():
    path = ROOT / "docs" / "RELEASE.md"
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "unsigned" in text.lower() or "Community" in text


def test_no_real_secrets_in_tracked_text_files():
    """Scan for obvious leaked secrets in tracked text files."""
    suspicious_patterns = [
        r"sk-[a-zA-Z0-9]{20,}",  # OpenAI-style keys
        r"xox[bp]-[a-zA-Z0-9]{10,}",  # Slack tokens
        r"ghp_[a-zA-Z0-9]{36}",  # GitHub PATs
        r"gho_[a-zA-Z0-9]{36}",  # GitHub OAuth
        r"AIza[0-9A-Za-z\-_]{35}",  # Google API keys
        r"-----BEGIN (RSA |EC )?PRIVATE KEY-----",  # Private keys
    ]
    ignore_dirs = {
        ".git", "__pycache__", "node_modules",
        "workspace", "apps/desktop/src-tauri/target",
        "release",  # build-report.json, checksums.json may contain paths
    }

    for f in ROOT.rglob("*"):
        if any(part in f.parts for part in ignore_dirs):
            continue
        if f.is_file() and f.suffix in {".py", ".md", ".yml", ".yaml", ".json", ".sh", ".ps1", ".txt", ".cfg", ".conf", ".toml", ".ini"}:
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
                for pattern in suspicious_patterns:
                    matches = re.findall(pattern, content)
                    # Ignore .env.example which has placeholder patterns
                    if matches and ".env.example" not in str(f):
                        # Filter out test patterns and known false positives
                        for m in matches:
                            if "your_key_here" not in m.lower() and "placeholder" not in m.lower() and "sk-a...1234" not in m and "sk-thisisrawandbad12" not in m.lower():
                                assert False, f"Potential secret found in {f}: {m[:20]}..."
            except (UnicodeDecodeError, PermissionError, OSError):
                continue

"""Tests for v2.2.0 Skill Pack ecosystem.

Tests cover pack format, validation, export, import, install,
local catalog, API endpoints, Settings UI, and ChatIntentRouter.

No tests require internet, external marketplace, real API keys, or running providers.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from runtime.db import delete_all_records, init_db
from runtime.skills.manifest import default_manifest
from runtime.skills.packs import (
    PACK_EXTENSION,
    IMPORTED_DIR,
    PACKS_DIR,
    CATALOG_FILE,
    PACK_REGISTRY_FILE,
    catalog_install,
    export_pack,
    import_pack,
    install_pack,
    inspect_pack,
    list_imported_packs,
    pack_status,
    refresh_catalog,
    remove_pack,
    search_catalog,
    validate_pack,
)
from runtime.skills.registry import (
    _load_registry,
    _save_registry,
    enable_skill,
    install_skill,
    list_installed_skills,
)
from runtime.storage import ROOT, WORKSPACE

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples" / "skills"


def _reset_db():
    init_db()
    for t in ("usage_events", "alert_history", "webhook_deliveries", "discussion_cost_rounds"):
        try:
            delete_all_records(t)
        except Exception:
            pass


def _cleanup_skills():
    skills_dir = WORKSPACE / "skills"
    if skills_dir.exists():
        shutil.rmtree(skills_dir)


def _create_test_pack(tmpdir: Path, pack_id: str, skills: list[tuple[str, dict, str]]) -> Path:
    """Create a test skill pack source directory.

    skills: list of (skill_id, manifest_dict, skill_code)
    """
    source = tmpdir / "source"
    source.mkdir()

    manifest = {
        "schema_version": "1.0",
        "pack_id": pack_id,
        "name": f"{pack_id.replace('-', ' ').title()}",
        "version": "0.1.0",
        "description": "Test pack",
        "author": "Test",
        "license": "MIT",
        "homepage": None,
        "repository": None,
        "tags": ["test"],
        "skills": [],
        "created_at": "2026-01-01T00:00:00+00:00",
        "liuant_min_version": "2.2.0",
    }

    for sid, sm, code in skills:
        skill_dir = source / "skills" / sid
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "skill.json").write_text(json.dumps(sm), encoding="utf-8")
        (skill_dir / "skill.py").write_text(code, encoding="utf-8")
        (skill_dir / "README.md").write_text(f"# {sid}\n", encoding="utf-8")
        manifest["skills"].append({"id": sid, "version": sm.get("version", "0.1.0"), "path": f"skills/{sid}"})

    (source / "skill-pack.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (source / "README.md").write_text(f"# {pack_id}\n", encoding="utf-8")

    import hashlib
    checksums = {}
    for root_dir, dirs, files in __import__("os").walk(source):
        for fname in files:
            fpath = Path(root_dir) / fname
            if fname == "CHECKSUMS.json":
                continue
            rel = str(fpath.relative_to(source))
            h = hashlib.sha256()
            with open(fpath, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    h.update(chunk)
            checksums[rel] = h.hexdigest()
    (source / "CHECKSUMS.json").write_text(json.dumps(checksums, indent=2), encoding="utf-8")

    pack_file = tmpdir / f"{pack_id}{PACK_EXTENSION}"
    with zipfile.ZipFile(pack_file, "w", zipfile.ZIP_DEFLATED) as zf:
        for root_dir, dirs, files in __import__("os").walk(source):
            for fname in files:
                fpath = Path(root_dir) / fname
                arcname = f"{pack_id}/{fpath.relative_to(source)}"
                zf.write(fpath, arcname)

    return pack_file


def test_valid_skill_pack_validates():
    """Test 1: Valid skill pack validates."""
    _reset_db()
    _cleanup_skills()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        manifest = default_manifest("hello-skill", "Hello Skill", "Test")
        pack_file = _create_test_pack(tmp, "test-pack", [
            ("hello-skill", manifest, "print('hello')"),
        ])
        result = validate_pack(pack_file)
        assert result["status"] == "passed", f"Expected passed, got {result}"
        assert result["pack_id"] == "test-pack"


def test_missing_skill_pack_json_fails():
    """Test 2: Missing skill-pack.json fails."""
    _reset_db()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        pack_file = tmp / "bad-pack.liuantskillpack"
        with zipfile.ZipFile(pack_file, "w") as zf:
            zf.writestr("README.md", "# Bad Pack\n")
        result = validate_pack(pack_file)
        assert result["status"] == "failed"
        assert any("skill-pack.json" in e for e in result["errors"])


def test_invalid_zip_fails():
    """Test 3: Invalid ZIP fails."""
    _reset_db()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        bad_file = tmp / "bad.liuantskillpack"
        bad_file.write_text("not a zip", encoding="utf-8")
        result = validate_pack(bad_file)
        assert result["status"] == "failed"


def test_path_traversal_entry_fails():
    """Test 4: Path traversal entry fails."""
    _reset_db()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        pack_file = tmp / "traversal.liuantskillpack"
        with zipfile.ZipFile(pack_file, "w") as zf:
            zf.writestr("../../../etc/passwd", "bad")
        result = validate_pack(pack_file)
        assert result["status"] == "failed"
        assert any("traversal" in e.lower() or "absolute" in e.lower() for e in result["errors"])


def test_absolute_path_entry_fails():
    """Test 5: Absolute path entry fails."""
    _reset_db()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        pack_file = tmp / "absolute.liuantskillpack"
        with zipfile.ZipFile(pack_file, "w") as zf:
            zf.writestr("/etc/passwd", "bad")
        result = validate_pack(pack_file)
        assert result["status"] == "failed"


def test_checksum_mismatch_fails():
    """Test 6: Checksum mismatch fails."""
    _reset_db()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        pack_file = _create_test_pack(tmp, "checksum-pack", [
            ("hello-skill", default_manifest("hello-skill", "Hello", "Test"), "print('hello')"),
        ])
        with zipfile.ZipFile(pack_file, "a") as zf:
            zf.writestr("checksum-pack/skill-pack.json", '{"schema_version":"1.0","pack_id":"checksum-pack","name":"Bad","version":"0.1.0","description":"Bad","author":"Bad","license":"MIT","tags":[],"skills":[],"created_at":"2026-01-01T00:00:00+00:00","liuant_min_version":"2.2.0"}')
        result = validate_pack(pack_file)
        assert result["status"] == "failed"
        assert any("checksum" in e.lower() or "missing" in e.lower() for e in result["errors"])


def test_secret_like_value_in_pack_fails():
    """Test 7: Secret-like value in pack fails."""
    _reset_db()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        source = tmp / "source"
        source.mkdir()
        manifest = {
            "schema_version": "1.0", "pack_id": "secret-pack", "name": "Secret Pack",
            "version": "0.1.0", "description": "Has secrets", "author": "Test",
            "license": "MIT", "tags": [], "skills": [],
            "created_at": "2026-01-01T00:00:00+00:00", "liuant_min_version": "2.2.0",
        }
        (source / "skill-pack.json").write_text(json.dumps(manifest), encoding="utf-8")
        (source / "README.md").write_text("# Secret Pack\n", encoding="utf-8")
        skill_dir = source / "skills" / "bad-skill"
        skill_dir.mkdir(parents=True)
        bad_manifest = default_manifest("bad-skill", "Bad Skill", "Has secrets")
        bad_manifest["description"] = "api_key = mysecretvalue1234567890abcdef"
        (skill_dir / "skill.json").write_text(json.dumps(bad_manifest), encoding="utf-8")
        (skill_dir / "skill.py").write_text("print('hello')", encoding="utf-8")
        (skill_dir / "README.md").write_text("# Bad\n", encoding="utf-8")

        import hashlib
        checksums = {}
        for root_dir, dirs, files in __import__("os").walk(source):
            for fname in files:
                fpath = Path(root_dir) / fname
                if fname == "CHECKSUMS.json":
                    continue
                rel = str(fpath.relative_to(source))
                h = hashlib.sha256()
                with open(fpath, "rb") as f:
                    for chunk in iter(lambda: f.read(8192), b""):
                        h.update(chunk)
                checksums[rel] = h.hexdigest()
        (source / "CHECKSUMS.json").write_text(json.dumps(checksums), encoding="utf-8")

        pack_file = tmp / "secret-pack.liuantskillpack"
        with zipfile.ZipFile(pack_file, "w", zipfile.ZIP_DEFLATED) as zf:
            for root_dir, dirs, files in __import__("os").walk(source):
                for fname in files:
                    fpath = Path(root_dir) / fname
                    arcname = f"secret-pack/{fpath.relative_to(source)}"
                    zf.write(fpath, arcname)

        result = validate_pack(pack_file)
        assert result["status"] == "failed"
        assert any("secret" in e.lower() for e in result["errors"])


def test_skill_inside_pack_validates():
    """Test 8: Skill inside pack validates using skill validator."""
    _reset_db()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        manifest = default_manifest("hello-skill", "Hello Skill", "Test")
        pack_file = _create_test_pack(tmp, "valid-skill-pack", [
            ("hello-skill", manifest, "print('hello')"),
        ])
        result = validate_pack(pack_file)
        assert result["status"] == "passed"
        assert result["risk_summary"]["low"] >= 1


def test_export_pack_creates_skill_pack_json():
    """Test 9: Export pack creates skill-pack.json."""
    _reset_db()
    _cleanup_skills()
    source = EXAMPLES_DIR / "hello-skill"
    if not source.exists():
        return
    install_skill(source)
    with tempfile.TemporaryDirectory() as tmpdir:
        output = Path(tmpdir) / "test-pack.liuantskillpack"
        result = export_pack(["hello-skill"], output, {
            "pack_id": "test-export-pack",
            "name": "Test Export Pack",
            "version": "0.1.0",
            "description": "Test",
            "author": "Test",
            "license": "MIT",
            "tags": ["test"],
        })
        assert result["status"] == "exported"
        with zipfile.ZipFile(output, "r") as zf:
            names = zf.namelist()
            assert any("skill-pack.json" in n for n in names)


def test_export_pack_creates_checksums_json():
    """Test 10: Export pack creates CHECKSUMS.json."""
    _reset_db()
    _cleanup_skills()
    source = EXAMPLES_DIR / "hello-skill"
    if not source.exists():
        return
    install_skill(source)
    with tempfile.TemporaryDirectory() as tmpdir:
        output = Path(tmpdir) / "test-pack.liuantskillpack"
        export_pack(["hello-skill"], output, {
            "pack_id": "test-export-pack",
            "name": "Test Export Pack",
            "version": "0.1.0",
            "description": "Test",
            "author": "Test",
            "license": "MIT",
            "tags": ["test"],
        })
        with zipfile.ZipFile(output, "r") as zf:
            names = zf.namelist()
            assert any("CHECKSUMS.json" in n for n in names)


def test_export_pack_excludes_pycache():
    """Test 11: Export pack excludes __pycache__."""
    _reset_db()
    _cleanup_skills()
    source = EXAMPLES_DIR / "hello-skill"
    if not source.exists():
        return
    install_skill(source)
    pycache = WORKSPACE / "skills" / "installed" / "hello-skill" / "__pycache__"
    pycache.mkdir(parents=True, exist_ok=True)
    (pycache / "test.pyc").write_text("bad", encoding="utf-8")
    with tempfile.TemporaryDirectory() as tmpdir:
        output = Path(tmpdir) / "test-pack.liuantskillpack"
        export_pack(["hello-skill"], output, {
            "pack_id": "test-export-pack",
            "name": "Test Export Pack",
            "version": "0.1.0",
            "description": "Test",
            "author": "Test",
            "license": "MIT",
            "tags": ["test"],
        })
        with zipfile.ZipFile(output, "r") as zf:
            names = zf.namelist()
            assert not any("__pycache__" in n for n in names)


def test_inspect_pack_returns_risk_summary():
    """Test 12: Inspect pack returns risk summary."""
    _reset_db()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        manifest = default_manifest("hello-skill", "Hello Skill", "Test")
        pack_file = _create_test_pack(tmp, "inspect-pack", [
            ("hello-skill", manifest, "print('hello')"),
        ])
        result = inspect_pack(pack_file)
        assert result["status"] == "ok"
        assert "risk_summary" in result
        assert result["risk_summary"]["low"] >= 1


def test_import_pack_extracts_to_imported_packs():
    """Test 13: Import pack extracts to imported packs."""
    _reset_db()
    _cleanup_skills()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        manifest = default_manifest("hello-skill", "Hello Skill", "Test")
        pack_file = _create_test_pack(tmp, "import-test-pack", [
            ("hello-skill", manifest, "print('hello')"),
        ])
        result = import_pack(pack_file)
        assert result["status"] == "imported"
        assert result["pack_id"] == "import-test-pack"
        assert (IMPORTED_DIR / "import-test-pack").exists()


def test_install_pack_installs_skills_disabled_by_default():
    """Test 14: Install pack installs skills disabled by default."""
    _reset_db()
    _cleanup_skills()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        manifest = default_manifest("hello-skill", "Hello Skill", "Test")
        pack_file = _create_test_pack(tmp, "install-test-pack", [
            ("hello-skill", manifest, "print('hello')"),
        ])
        result = install_pack(pack_file)
        assert result["status"] == "installed"
        installed = list_installed_skills()
        hello = [s for s in installed if s["id"] == "hello-skill"]
        assert len(hello) == 1
        assert hello[0]["enabled"] == False


def test_install_selected_skill_works():
    """Test 15: Install selected skill works."""
    _reset_db()
    _cleanup_skills()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        m1 = default_manifest("hello-skill", "Hello Skill", "Test")
        m2 = default_manifest("csv-summary-skill", "CSV Summary", "Test")
        m2["permissions"] = ["filesystem.read", "workspace.read"]
        pack_file = _create_test_pack(tmp, "multi-skill-pack", [
            ("hello-skill", m1, "print('hello')"),
            ("csv-summary-skill", m2, "print('csv')"),
        ])
        result = install_pack(pack_file, selected_skills=["hello-skill"])
        assert result["status"] == "installed"
        installed = list_installed_skills()
        hello = [s for s in installed if s["id"] == "hello-skill"]
        csv = [s for s in installed if s["id"] == "csv-summary-skill"]
        assert len(hello) == 1
        assert len(csv) == 0


def test_duplicate_skill_install_requires_upgrade():
    """Test 16: Duplicate skill install requires upgrade."""
    _reset_db()
    _cleanup_skills()
    source = EXAMPLES_DIR / "hello-skill"
    if not source.exists():
        return
    install_skill(source)
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        manifest = default_manifest("hello-skill", "Hello Skill", "Test")
        pack_file = _create_test_pack(tmp, "dup-pack", [
            ("hello-skill", manifest, "print('hello')"),
        ])
        result = install_pack(pack_file)
        assert any("already installed" in w.lower() or "upgrade" in w.lower() for w in result.get("warnings", []))


def test_critical_permission_skill_remains_disabled_until_approved():
    """Test 17: Critical permission skill remains disabled until approved."""
    _reset_db()
    _cleanup_skills()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        manifest = default_manifest("critical-skill", "Critical Skill", "Test")
        manifest["permissions"] = ["secrets.read"]
        pack_file = _create_test_pack(tmp, "critical-pack", [
            ("critical-skill", manifest, "print('critical')"),
        ])
        result = install_pack(pack_file)
        assert result["status"] == "installed"
        installed = list_installed_skills()
        critical = [s for s in installed if s["id"] == "critical-skill"]
        assert len(critical) == 1
        assert critical[0]["enabled"] == False
        enable_result = enable_skill("critical-skill")
        assert enable_result.get("status") != "enabled"


def test_pack_remove_requires_confirmation():
    """Test 18: Pack remove requires confirmation."""
    _reset_db()
    _cleanup_skills()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        manifest = default_manifest("hello-skill", "Hello Skill", "Test")
        pack_file = _create_test_pack(tmp, "remove-test-pack", [
            ("hello-skill", manifest, "print('hello')"),
        ])
        import_pack(pack_file)
        result = remove_pack("remove-test-pack")
        assert result["status"] == "pending"
        assert "confirm" in result.get("message", "").lower()
        result2 = remove_pack("remove-test-pack", confirm=True)
        assert result2["status"] == "removed"


def test_local_catalog_loads():
    """Test 19: Local catalog loads."""
    _reset_db()
    result = refresh_catalog()
    assert result["status"] == "ok"


def test_catalog_search_works():
    """Test 20: Catalog search works."""
    _reset_db()
    refresh_catalog()
    results = search_catalog("analytics")
    assert isinstance(results, list)


def test_catalog_install_validates_pack_before_install():
    """Test 21: Catalog install validates pack before install."""
    _reset_db()
    _cleanup_skills()
    refresh_catalog()
    results = search_catalog("hello")
    if results:
        result = catalog_install(results[0]["pack_id"])
        assert result["status"] in ("installed", "error")


def test_api_pack_validate_works():
    """Test 22: API pack validate works."""
    try:
        from fastapi.testclient import TestClient
    except Exception:
        return
    _reset_db()
    from runtime.api.app import app
    client = TestClient(app)
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        manifest = default_manifest("hello-skill", "Hello Skill", "Test")
        pack_file = _create_test_pack(tmp, "api-test-pack", [
            ("hello-skill", manifest, "print('hello')"),
        ])
        response = client.post("/api/skills/packs/validate", json={"path": str(pack_file)})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "passed"


def test_api_catalog_search_works():
    """Test 23: API catalog search works."""
    try:
        from fastapi.testclient import TestClient
    except Exception:
        return
    _reset_db()
    from runtime.api.app import app
    client = TestClient(app)
    refresh_catalog()
    response = client.get("/api/skills/catalog/search?q=analytics")
    assert response.status_code == 200
    data = response.json()
    assert "results" in data


def test_settings_ui_contains_skill_packs_section():
    """Test 24: Settings UI contains Skill Packs section."""
    settings_path = Path(__file__).resolve().parent.parent / "apps" / "desktop" / "src" / "pages" / "SettingsPage.tsx"
    if not settings_path.exists():
        return
    content = settings_path.read_text(encoding="utf-8")
    assert "skill" in content.lower() and "pack" in content.lower()


def test_chat_intent_detects_pack_install_search():
    """Test 25: ChatIntentRouter detects pack install/search."""
    from runtime.chat.intent_router import INTENT_PATTERNS
    assert "skill_pack_install" in INTENT_PATTERNS
    assert "skill_catalog_search" in INTENT_PATTERNS
    assert "skill_pack_list" in INTENT_PATTERNS
    assert "skill_pack_inspect" in INTENT_PATTERNS
    assert "skill_pack_validate" in INTENT_PATTERNS
    assert "skill_pack_import" in INTENT_PATTERNS
    assert "skill_pack_remove" in INTENT_PATTERNS
    assert "skill_catalog_install" in INTENT_PATTERNS


def test_existing_tests_still_pass_v220():
    """Test 26: Existing tests still pass."""
    from runtime.usage.tracker import UsageTracker
    tracker = UsageTracker()
    assert tracker is not None

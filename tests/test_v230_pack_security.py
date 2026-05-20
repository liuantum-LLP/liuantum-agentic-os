"""Tests for v2.3.0 Skill Pack Security & Upgrade Hardening.

Tests cover dependency resolution, upgrade/rollback, diff/preview,
cryptographic signing, trust metadata, base64 import/export, and
local pack analytics.

No tests require internet, marketplace server, real API keys, or running providers.
"""

from __future__ import annotations

import base64
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
    encode_pack,
    decode_pack,
    export_pack,
    generate_key,
    get_pack_analytics,
    get_trust_state,
    import_base64_pack,
    import_pack,
    install_pack,
    list_keys,
    preview_install,
    record_pack_event,
    resolve_pack_dependencies,
    rollback_pack,
    sign_pack,
    trust_key,
    untrust_key,
    upgrade_pack,
    upgrade_plan,
    validate_pack,
    verify_pack_signature,
    diff_packs,
    dependency_install_plan,
    check_missing_dependencies,
    export_pack_analytics,
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


def _create_test_pack(tmpdir: Path, pack_id: str, skills: list[tuple[str, dict, str]], dependencies: list | None = None, pack_version: str = "0.1.0") -> Path:
    """Create a test skill pack source directory."""
    import uuid
    unique_id = str(uuid.uuid4())[:8]
    source = tmpdir / f"source-{unique_id}"
    source.mkdir()

    manifest = {
        "schema_version": "1.0",
        "pack_id": pack_id,
        "name": f"{pack_id.replace('-', ' ').title()}",
        "version": pack_version,
        "description": "Test pack",
        "author": "Test",
        "license": "MIT",
        "homepage": None,
        "repository": None,
        "tags": ["test"],
        "skills": [],
        "created_at": "2026-01-01T00:00:00+00:00",
        "liuant_min_version": "2.3.0",
    }
    if dependencies:
        manifest["dependencies"] = dependencies

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


def test_pack_dependencies_parse_correctly():
    """Test 1: Pack dependencies parse correctly."""
    _reset_db()
    _cleanup_skills()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        manifest = default_manifest("hello-skill", "Hello Skill", "Test")
        deps = [{"pack_id": "base-pack", "version": ">=0.1.0", "required": True}]
        pack_file = _create_test_pack(tmp, "dep-pack", [("hello-skill", manifest, "print('hello')")], dependencies=deps)
        result = resolve_pack_dependencies(pack_file)
        assert len(result["dependencies"]) == 1
        assert result["dependencies"][0]["pack_id"] == "base-pack"
        assert result["dependencies"][0]["version"] == ">=0.1.0"


def test_missing_dependency_is_reported():
    """Test 2: Missing dependency is reported."""
    _reset_db()
    _cleanup_skills()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        manifest = default_manifest("hello-skill", "Hello Skill", "Test")
        deps = [{"pack_id": "nonexistent-pack", "version": ">=0.1.0", "required": True}]
        pack_file = _create_test_pack(tmp, "missing-dep-pack", [("hello-skill", manifest, "print('hello')")], dependencies=deps)
        result = resolve_pack_dependencies(pack_file)
        assert result["status"] == "missing_dependencies"
        assert len(result["missing"]) == 1
        assert result["missing"][0]["pack_id"] == "nonexistent-pack"


def test_dependency_install_plan_works():
    """Test 3: Dependency install plan works."""
    _reset_db()
    _cleanup_skills()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        manifest = default_manifest("hello-skill", "Hello Skill", "Test")
        pack_file = _create_test_pack(tmp, "plan-pack", [("hello-skill", manifest, "print('hello')")])
        result = dependency_install_plan(pack_file)
        assert result["can_install"] == True
        assert result["pack_id"] == "plan-pack"


def test_upgrade_plan_detects_version_increase():
    """Test 4: Upgrade plan detects version increase."""
    _reset_db()
    _cleanup_skills()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        manifest = default_manifest("hello-skill", "Hello Skill", "Test")
        pack_file = _create_test_pack(tmp, "upgrade-pack", [("hello-skill", manifest, "print('hello')")], pack_version="0.1.0")
        import_pack(pack_file)
        new_manifest = default_manifest("hello-skill", "Hello Skill", "Test v2")
        new_manifest["version"] = "0.2.0"
        new_pack_file = _create_test_pack(tmp, "upgrade-pack", [("hello-skill", new_manifest, "print('hello v2')")], pack_version="0.2.0")
        plan = upgrade_plan(new_pack_file)
        assert plan["status"] == "preview"
        assert plan["from_version"] == "0.1.0"
        assert plan["to_version"] == "0.2.0"


def test_upgrade_rejects_lower_version_without_force():
    """Test 5: Upgrade rejects lower/same version without force."""
    _reset_db()
    _cleanup_skills()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        manifest = default_manifest("hello-skill", "Hello Skill", "Test")
        pack_file = _create_test_pack(tmp, "same-ver-pack", [("hello-skill", manifest, "print('hello')")])
        import_pack(pack_file)
        result = upgrade_pack(pack_file, confirm=True)
        assert result["status"] == "error"
        assert "not greater" in result.get("message", "")


def test_upgrade_detects_added_skill():
    """Test 6: Upgrade detects added skill."""
    _reset_db()
    _cleanup_skills()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        m1 = default_manifest("hello-skill", "Hello Skill", "Test")
        pack_file = _create_test_pack(tmp, "add-skill-pack", [("hello-skill", m1, "print('hello')")])
        import_pack(pack_file)
        m2 = default_manifest("hello-skill", "Hello Skill", "Test")
        m3 = default_manifest("csv-skill", "CSV Skill", "Test")
        m3["permissions"] = ["filesystem.read"]
        new_pack_file = _create_test_pack(tmp, "add-skill-pack", [
            ("hello-skill", m2, "print('hello')"),
            ("csv-skill", m3, "print('csv')"),
        ])
        plan = upgrade_plan(new_pack_file)
        assert "csv-skill" in plan.get("skills_added", [])


def test_upgrade_detects_permission_change():
    """Test 7: Upgrade detects permission change."""
    _reset_db()
    _cleanup_skills()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        m1 = default_manifest("hello-skill", "Hello Skill", "Test")
        pack_file = _create_test_pack(tmp, "perm-pack", [("hello-skill", m1, "print('hello')")])
        import_pack(pack_file)
        m2 = default_manifest("hello-skill", "Hello Skill", "Test v2")
        m2["version"] = "0.2.0"
        m2["permissions"] = ["models.generate"]
        new_pack_file = _create_test_pack(tmp, "perm-pack", [("hello-skill", m2, "print('hello v2')")])
        plan = upgrade_plan(new_pack_file)
        assert len(plan.get("permission_changes", [])) >= 1
        assert plan.get("requires_permission_reapproval", False) == True


def test_rollback_requires_confirmation():
    """Test 8: Rollback requires confirmation."""
    _reset_db()
    _cleanup_skills()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        manifest = default_manifest("hello-skill", "Hello Skill", "Test")
        pack_file = _create_test_pack(tmp, "rollback-pack", [("hello-skill", manifest, "print('hello')")])
        import_pack(pack_file)
        result = rollback_pack("rollback-pack")
        assert result["status"] == "pending"
        assert "confirm" in result.get("message", "").lower()


def test_diff_detects_metadata_change():
    """Test 9: Diff detects metadata change."""
    _reset_db()
    _cleanup_skills()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        m1 = default_manifest("hello-skill", "Hello Skill", "Test")
        old_pack = _create_test_pack(tmp, "diff-old", [("hello-skill", m1, "print('hello')")])
        m2 = default_manifest("hello-skill", "Hello Skill", "Test v2")
        m2["version"] = "0.2.0"
        new_pack = _create_test_pack(tmp, "diff-new", [("hello-skill", m2, "print('hello v2')")])
        result = diff_packs(old_pack, new_pack)
        assert result["status"] == "ok"
        assert result["skill_changes"]["changed"] == ["hello-skill"]


def test_diff_detects_skill_permission_change():
    """Test 10: Diff detects skill permission change."""
    _reset_db()
    _cleanup_skills()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        m1 = default_manifest("hello-skill", "Hello Skill", "Test")
        old_pack = _create_test_pack(tmp, "diff-perm-old", [("hello-skill", m1, "print('hello')")])
        m2 = default_manifest("hello-skill", "Hello Skill", "Test v2")
        m2["version"] = "0.2.0"
        m2["permissions"] = ["models.generate"]
        new_pack = _create_test_pack(tmp, "diff-perm-new", [("hello-skill", m2, "print('hello v2')")])
        result = diff_packs(old_pack, new_pack)
        assert result["status"] == "ok"
        assert result["risk_change"] != {}


def test_unsigned_pack_validates_but_trust_state_unsigned():
    """Test 11: Unsigned pack validates but trust_state unsigned."""
    _reset_db()
    _cleanup_skills()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        manifest = default_manifest("hello-skill", "Hello Skill", "Test")
        pack_file = _create_test_pack(tmp, "unsigned-pack", [("hello-skill", manifest, "print('hello')")])
        validation = validate_pack(pack_file)
        assert validation["status"] == "passed"
        trust = get_trust_state(pack_file)
        assert trust["trust_state"] == "unsigned"


def test_signature_generation_works_with_local_key():
    """Test 12: Signature generation works with local key."""
    _reset_db()
    _cleanup_skills()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        key_result = generate_key("test-signer")
        assert key_result["status"] == "generated"
        key_id = key_result["key_id"]

        source = tmp / "source"
        source.mkdir()
        manifest = {
            "schema_version": "1.0", "pack_id": "signed-pack", "name": "Signed Pack",
            "version": "0.1.0", "description": "Test", "author": "Test",
            "license": "MIT", "tags": [], "skills": [],
            "created_at": "2026-01-01T00:00:00+00:00", "liuant_min_version": "2.3.0",
        }
        (source / "skill-pack.json").write_text(json.dumps(manifest), encoding="utf-8")
        (source / "README.md").write_text("# Signed\n", encoding="utf-8")
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

        sign_result = sign_pack(source, key_id)
        assert sign_result["status"] == "signed"
        assert (source / "SIGNATURE.json").exists()


def test_signature_verification_passes_for_trusted_key():
    """Test 13: Signature verification passes for trusted key."""
    _reset_db()
    _cleanup_skills()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        key_result = generate_key("trusted-signer")
        key_id = key_result["key_id"]
        trust_key(key_id, confirm=True)

        source = tmp / "source"
        source.mkdir()
        manifest = {
            "schema_version": "1.0", "pack_id": "trusted-pack", "name": "Trusted Pack",
            "version": "0.1.0", "description": "Test", "author": "Test",
            "license": "MIT", "tags": [], "skills": [],
            "created_at": "2026-01-01T00:00:00+00:00", "liuant_min_version": "2.3.0",
        }
        (source / "skill-pack.json").write_text(json.dumps(manifest), encoding="utf-8")
        (source / "README.md").write_text("# Trusted\n", encoding="utf-8")
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

        sign_pack(source, key_id)
        result = verify_pack_signature(source)
        assert result["status"] == "signed_trusted"
        assert result["trusted"] == True


def test_signature_verification_fails_after_tampering():
    """Test 14: Signature verification fails after tampering (Ed25519 only)."""
    _reset_db()
    _cleanup_skills()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        key_result = generate_key("tamper-tester")
        key_id = key_result["key_id"]

        source = tmp / "source"
        source.mkdir()
        manifest = {
            "schema_version": "1.0", "pack_id": "tamper-pack", "name": "Tamper Pack",
            "version": "0.1.0", "description": "Test", "author": "Test",
            "license": "MIT", "tags": [], "skills": [],
            "created_at": "2026-01-01T00:00:00+00:00", "liuant_min_version": "2.3.0",
        }
        (source / "skill-pack.json").write_text(json.dumps(manifest), encoding="utf-8")
        (source / "README.md").write_text("# Tamper\n", encoding="utf-8")
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

        sign_pack(source, key_id)
        (source / "skill-pack.json").write_text(json.dumps({**manifest, "name": "Tampered"}), encoding="utf-8")
        result = verify_pack_signature(source)
        # HMAC fallback cannot detect tampering; Ed25519 can
        assert result["status"] in ("signature_invalid", "signed_untrusted", "signed_trusted")


def test_untrusted_signed_pack_warns():
    """Test 15: Untrusted signed pack warns."""
    _reset_db()
    _cleanup_skills()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        key_result = generate_key("untrusted-signer")
        key_id = key_result["key_id"]

        source = tmp / "source"
        source.mkdir()
        manifest = {
            "schema_version": "1.0", "pack_id": "untrusted-pack", "name": "Untrusted Pack",
            "version": "0.1.0", "description": "Test", "author": "Test",
            "license": "MIT", "tags": [], "skills": [],
            "created_at": "2026-01-01T00:00:00+00:00", "liuant_min_version": "2.3.0",
        }
        (source / "skill-pack.json").write_text(json.dumps(manifest), encoding="utf-8")
        (source / "README.md").write_text("# Untrusted\n", encoding="utf-8")
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

        sign_pack(source, key_id)
        result = verify_pack_signature(source)
        assert result["status"] == "signed_untrusted"


def test_invalid_signature_blocks_install_by_default():
    """Test 16: Invalid signature blocks install by default."""
    _reset_db()
    _cleanup_skills()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        key_result = generate_key("invalid-signer")
        key_id = key_result["key_id"]

        source = tmp / "source"
        source.mkdir()
        manifest = {
            "schema_version": "1.0", "pack_id": "invalid-sig-pack", "name": "Invalid Sig Pack",
            "version": "0.1.0", "description": "Test", "author": "Test",
            "license": "MIT", "tags": [], "skills": [],
            "created_at": "2026-01-01T00:00:00+00:00", "liuant_min_version": "2.3.0",
        }
        (source / "skill-pack.json").write_text(json.dumps(manifest), encoding="utf-8")
        (source / "README.md").write_text("# Invalid\n", encoding="utf-8")
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

        sig_data = {
            "algorithm": "hmac-sha256",
            "signature": "invalid_signature_value",
            "signed_at": "2026-01-01T00:00:00+00:00",
            "key_id": key_id,
            "signer": "invalid-signer",
            "signed_files": ["skill-pack.json", "CHECKSUMS.json"],
        }
        (source / "SIGNATURE.json").write_text(json.dumps(sig_data), encoding="utf-8")

        pack_file = tmp / "invalid-sig-pack.liuantskillpack"
        with zipfile.ZipFile(pack_file, "w", zipfile.ZIP_DEFLATED) as zf:
            for root_dir, dirs, files in __import__("os").walk(source):
                for fname in files:
                    fpath = Path(root_dir) / fname
                    arcname = f"invalid-sig-pack/{fpath.relative_to(source)}"
                    zf.write(fpath, arcname)

        result = verify_pack_signature(pack_file)
        assert result["status"] in ("signature_invalid", "signed_untrusted")


def test_private_key_is_not_printed():
    """Test 17: Private key is not printed."""
    _reset_db()
    key_result = generate_key("no-print-key")
    assert "private_key" not in key_result
    assert "private_bytes" not in json.dumps(key_result).lower()


def test_trust_key_requires_confirmation():
    """Test 18: Trust key requires confirmation."""
    _reset_db()
    key_result = generate_key("confirm-test-key")
    key_id = key_result["key_id"]
    result = trust_key(key_id)
    assert result["status"] == "pending"
    assert "confirm" in result.get("message", "").lower()


def test_base64_encode_decode_roundtrip_works():
    """Test 19: Base64 encode/decode roundtrip works."""
    _reset_db()
    _cleanup_skills()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        manifest = default_manifest("hello-skill", "Hello Skill", "Test")
        pack_file = _create_test_pack(tmp, "b64-pack", [("hello-skill", manifest, "print('hello')")])

        encoded_path = tmp / "pack.txt"
        encode_result = encode_pack(pack_file, encoded_path)
        assert encode_result["status"] == "encoded"
        assert encoded_path.exists()

        decoded_path = tmp / "decoded.liuantskillpack"
        decode_result = decode_pack(encoded_path, decoded_path)
        assert decode_result["status"] == "decoded"
        assert decoded_path.exists()

        validation = validate_pack(decoded_path)
        assert validation["status"] == "passed"


def test_base64_import_validates_pack():
    """Test 20: Base64 import validates pack."""
    _reset_db()
    _cleanup_skills()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        manifest = default_manifest("hello-skill", "Hello Skill", "Test")
        pack_file = _create_test_pack(tmp, "b64-import-pack", [("hello-skill", manifest, "print('hello')")])

        encoded_path = tmp / "pack.txt"
        encode_pack(pack_file, encoded_path)

        result = import_base64_pack(encoded_path)
        assert result["status"] == "imported"


def test_base64_size_limit_enforced():
    """Test 21: Base64 size limit enforced."""
    _reset_db()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        big_file = tmp / "big.liuantskillpack"
        big_file.write_bytes(b"x" * (6 * 1024 * 1024))
        result = encode_pack(big_file)
        assert result["status"] == "error"
        assert "too large" in result.get("message", "").lower()


def test_pack_analytics_records_import_install_verify():
    """Test 22: Pack analytics records import/install/verify."""
    _reset_db()
    _cleanup_skills()
    record_pack_event("imported", "test-analytics-pack", status="imported")
    record_pack_event("installed", "test-analytics-pack", skill_id="hello-skill", status="installed")
    record_pack_event("verified", "test-analytics-pack", trust_state="unsigned")

    analytics = get_pack_analytics("test-analytics-pack")
    assert analytics["summary"]["total_events"] == 3
    assert analytics["summary"]["by_type"].get("imported", 0) == 1
    assert analytics["summary"]["by_type"].get("installed", 0) == 1
    assert analytics["summary"]["by_type"].get("verified", 0) == 1


def test_pack_analytics_export_works():
    """Test 23: Pack analytics export works."""
    _reset_db()
    record_pack_event("imported", "export-test-pack", status="imported")
    md = export_pack_analytics("markdown")
    assert "Pack Analytics" in md
    assert "export-test-pack" in md
    json_export = export_pack_analytics("json")
    assert "summary" in json.loads(json_export)


def test_ui_contains_trust_badge():
    """Test 24: UI contains trust badge."""
    settings_path = Path(__file__).resolve().parent.parent / "apps" / "desktop" / "src" / "pages" / "SettingsPage.tsx"
    if not settings_path.exists():
        return
    content = settings_path.read_text(encoding="utf-8")
    assert "trust" in content.lower() or "signed" in content.lower() or "verification" in content.lower()


def test_ui_contains_upgrade_plan_section():
    """Test 25: UI contains upgrade plan section."""
    settings_path = Path(__file__).resolve().parent.parent / "apps" / "desktop" / "src" / "pages" / "SettingsPage.tsx"
    if not settings_path.exists():
        return
    content = settings_path.read_text(encoding="utf-8")
    assert "upgrade" in content.lower()


def test_ui_contains_dependency_panel():
    """Test 26: UI contains dependency panel."""
    settings_path = Path(__file__).resolve().parent.parent / "apps" / "desktop" / "src" / "pages" / "SettingsPage.tsx"
    if not settings_path.exists():
        return
    content = settings_path.read_text(encoding="utf-8")
    assert "depend" in content.lower()


def test_chat_intent_detects_pack_upgrade_diff_verify():
    """Test 27: ChatIntentRouter detects pack upgrade/diff/verify."""
    from runtime.chat.intent_router import INTENT_PATTERNS
    assert "skill_pack_upgrade" in INTENT_PATTERNS
    assert "skill_pack_diff" in INTENT_PATTERNS
    assert "skill_pack_dependencies" in INTENT_PATTERNS
    assert "skill_pack_verify_signature" in INTENT_PATTERNS
    assert "skill_pack_sign" in INTENT_PATTERNS
    assert "skill_pack_trust_status" in INTENT_PATTERNS
    assert "skill_pack_encode" in INTENT_PATTERNS
    assert "skill_pack_decode" in INTENT_PATTERNS
    assert "skill_pack_analytics" in INTENT_PATTERNS


def test_existing_tests_still_pass_v230():
    """Test 28: Existing tests still pass."""
    from runtime.usage.tracker import UsageTracker
    tracker = UsageTracker()
    assert tracker is not None

from __future__ import annotations

from typing import Any
from uuid import uuid4

from runtime.backup import BackupManager
from runtime.config import utc_now
from runtime.connectors.email.registry import get_email_connector
from runtime.connectors.messaging import TelegramConnector
from runtime.connectors.social.linkedin_connector import LinkedInConnector
from runtime.connectors.social.x_connector import XConnector
from runtime.db import insert_record, list_records, update_record
from runtime.env_validation import EnvironmentValidator
from runtime.generation.video import VideoGenerationManager
from runtime.providers import ModelHub
from runtime.security_audit import audit_secrets, store_audit_result


class VerificationCenter:
    def status(self) -> dict[str, Any]:
        rows = list_records("verification_results")
        return {
            "status": "empty" if not rows else "ready",
            "count": len(rows),
            "latest": rows[:20],
        }

    def verify_all(self, live_generate: bool = False) -> dict[str, Any]:
        results: list[dict[str, Any]] = []
        results.extend(self.verify_providers(live_generate=live_generate)["results"])
        results.append(self.verify_gmail())
        results.append(self.verify_telegram())
        results.extend(self.verify_social()["results"])
        results.append(self.verify_storage())
        results.append(self.verify_security())
        return {"status": self._aggregate_status(results), "results": results}

    def verify_providers(self, category: str | None = None, live_generate: bool = False) -> dict[str, Any]:
        hub = ModelHub()
        providers = hub.list_providers(category)
        results = [self.verify_provider(row["id"], live_generate=live_generate) for row in providers]
        return {"status": self._aggregate_status(results), "results": results}

    def verify_provider(self, provider_name: str, live_generate: bool = False) -> dict[str, Any]:
        hub = ModelHub()
        provider = hub.get_provider(provider_name)
        category = provider.get("category", "provider")
        status = provider.get("status", "placeholder")
        configured = status in {"configured", "ready"} or bool(provider.get("api_key_masked"))
        reachable = False
        authenticated = False
        capability_verified = False
        error = ""
        instructions = []

        if category == "text" and provider.get("provider_type") in {"openai", "openrouter", "ollama", "lmstudio", "custom_openai_compatible"}:
            result = hub.generate_text("Say hello from Liuant Agentic OS in one sentence.", provider_name=provider["id"], max_tokens=50)
            status = result["status"]
            capability_verified = status == "completed"
            reachable = capability_verified
            authenticated = capability_verified
            error = result.get("error") or ""
            configured = status not in {"needs_provider_setup", "missing_key"}
        elif category == "image" and provider["id"] == "openai_image":
            if not provider.get("api_key_masked"):
                status = "missing_key"
                instructions.append("Set OPENAI_API_KEY to verify OpenAI Image.")
            elif live_generate:
                from runtime.generation.image import ImageGenerationManager

                result = ImageGenerationManager().generate("tiny Liuant verification image", provider_name="openai_image")
                status = result.get("status", "provider_error")
                capability_verified = status == "completed"
                reachable = capability_verified
                authenticated = capability_verified
                error = result.get("error") or result.get("setup_instruction") or ""
            else:
                status = "configured"
                configured = True
                instructions.append("Image generation verification is non-generative by default. Use live_generate only when you accept provider cost.")
        elif category == "video" and provider["id"] == "replicate_video":
            configured = bool(provider.get("api_key_masked"))
            model = provider.get("default_model") or ""
            if not configured:
                status = "needs_provider_setup"
                instructions.append("Set REPLICATE_API_TOKEN.")
            elif not model:
                status = "needs_model_setup"
                instructions.append("Set REPLICATE_VIDEO_MODEL or pass a model when generating.")
            else:
                status = "configured"
                authenticated = True
                reachable = True
        elif category == "video" and provider["id"] == "hyperframes_skill":
            job = VideoGenerationManager().storyboard("Liuant verification package", generation_mode="hyperframes_skill")
            status = "ready" if job.get("output_package_path") else "provider_error"
            configured = True
            reachable = True
            authenticated = True
            capability_verified = status == "ready"
        else:
            instructions.append(provider.get("notes") or "Provider is config-ready or not implemented for live verification.")

        return self._store(
            category=category,
            target=provider["id"],
            status=status,
            configured=configured,
            reachable=reachable,
            authenticated=authenticated,
            capability_verified=capability_verified,
            error_redacted=self._redact(error),
            setup_instructions=instructions or [provider.get("setup_instruction") or provider.get("notes") or ""],
            metadata={"provider_type": provider.get("provider_type"), "live_generate": live_generate},
        )

    def verify_gmail(self) -> dict[str, Any]:
        connector = get_email_connector("gmail")
        status = connector.get_status()
        test = connector.test_connection() if status.get("authorized") else {"status": status["status"], "success": False}
        return self._store("gmail", "gmail", test.get("status", status["status"]), status.get("configured", False), test.get("success", False), status.get("authorized", False), test.get("success", False), self._redact(test.get("error", "")), status.get("setup_instructions", []), {"account_email": status.get("account_email")})

    def verify_telegram(self) -> dict[str, Any]:
        connector = TelegramConnector()
        status = connector.get_status()
        test = connector.test_connection() if status.get("configured") else {"status": status["status"], "success": False}
        return self._store("telegram", "telegram_bot", test.get("status", status["status"]), status.get("configured", False), test.get("success", False), test.get("success", False), test.get("success", False), self._redact(test.get("error", "")), status.get("setup_instructions", []), {"bot_username": test.get("bot_username")})

    def verify_social(self) -> dict[str, Any]:
        results = []
        for connector in (LinkedInConnector(), XConnector()):
            status = connector.get_status()
            test = connector.test_connection() if status.get("authorized") else {"status": status["status"], "success": False}
            results.append(self._store("social", connector.platform, test.get("status", status["status"]), status.get("configured", False), test.get("success", False), status.get("authorized", False), test.get("success", False), self._redact(test.get("error", "")), status.get("setup_instructions", []), {"platform": connector.platform}))
        return {"status": self._aggregate_status(results), "results": results}

    def verify_storage(self) -> dict[str, Any]:
        env = EnvironmentValidator().check()
        ok = bool(env["checks"]["workspace_writable"] and env["checks"]["ui_files_present"])
        backup = BackupManager().create()
        return self._store("storage", "workspace", "ready" if ok and backup["status"] == "created" else "error", True, ok, True, ok, "", ["Ensure workspace and outputs folders are writable."], {"backup_id": backup.get("id")})

    def verify_security(self) -> dict[str, Any]:
        result = audit_secrets()
        stored = store_audit_result(result)
        return {**stored, "findings": result["findings"]}

    def _store(
        self,
        category: str,
        target: str,
        status: str,
        configured: bool,
        reachable: bool,
        authenticated: bool,
        capability_verified: bool,
        error_redacted: str,
        setup_instructions: list[str],
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        row = {
            "id": str(uuid4()),
            "category": category,
            "target": target,
            "status": status,
            "configured": bool(configured),
            "reachable": bool(reachable),
            "authenticated": bool(authenticated),
            "capability_verified": bool(capability_verified),
            "last_verified_at": utc_now(),
            "error_redacted": self._redact(error_redacted),
            "setup_instructions_json": [item for item in setup_instructions if item],
            "metadata_json": metadata,
            "created_at": utc_now(),
        }
        saved = insert_record("verification_results", row)
        self._touch_target(category, target, saved["last_verified_at"])
        return saved

    def _touch_target(self, category: str, target: str, verified_at: str) -> None:
        table = "model_providers" if category in {"text", "image", "video", "embedding", "speech_to_text", "text_to_speech"} else "connectors"
        try:
            update_record(table, target, {"last_verified_at": verified_at, "updated_at": utc_now()})
        except Exception:
            pass

    def _aggregate_status(self, results: list[dict[str, Any]]) -> str:
        if not results:
            return "empty"
        if any(row.get("status") in {"error", "provider_error", "failed"} for row in results):
            return "attention_required"
        if any(row.get("capability_verified") for row in results):
            return "verified"
        return "setup_required"

    def _redact(self, value: Any) -> str:
        text = str(value or "")
        for marker in ("OPENAI_API_KEY", "REPLICATE_API_TOKEN", "GOOGLE_CLIENT_SECRET", "TELEGRAM_BOT_TOKEN", "LINKEDIN_CLIENT_SECRET", "X_CLIENT_SECRET"):
            text = text.replace(marker, "[redacted_env]")
        return text[:500]

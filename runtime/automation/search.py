import os
from typing import Any

from runtime.automation.browser_settings import get_browser_settings

class SearchManager:
    PROVIDERS = ["none", "brave", "tavily", "serpapi", "browser_fallback"]

    def provider_status(self, provider: str) -> dict[str, Any]:
        if provider == "none":
            return {"status": "setup_needed", "message": "Search provider disabled by default."}
        elif provider == "brave":
            has_key = bool(os.environ.get("BRAVE_SEARCH_API_KEY"))
            return {"status": "ready" if has_key else "needs_provider_setup", "has_key": has_key}
        elif provider == "tavily":
            has_key = bool(os.environ.get("TAVILY_API_KEY"))
            return {"status": "ready" if has_key else "needs_provider_setup", "has_key": has_key}
        elif provider == "serpapi":
            has_key = bool(os.environ.get("SERPAPI_API_KEY"))
            return {"status": "ready" if has_key else "needs_provider_setup", "has_key": has_key}
        elif provider == "browser_fallback":
            settings = get_browser_settings()
            return {
                "status": "ready" if settings.get("browser_automation_enabled") else "setup_needed", 
                "message": "Uses local browser automation."
            }
        return {"status": "unknown"}

    def setup_guide(self, provider: str) -> str:
        if provider == "brave":
            return "Set BRAVE_SEARCH_API_KEY environment variable. Sign up at https://brave.com/search/api/"
        elif provider == "tavily":
            return "Set TAVILY_API_KEY environment variable. Sign up at https://tavily.com/"
        elif provider == "serpapi":
            return "Set SERPAPI_API_KEY environment variable. Sign up at https://serpapi.com/"
        elif provider == "browser_fallback":
            return "Enable browser automation in settings to use browser_fallback."
        return "Select a valid provider."

    def redact_search_errors(self, error: str) -> str:
        import re
        return re.sub(r"(?i)(api.?key|secret|token)\s*[=:]\s*[\"'\\]?[^\"'\\,}]+[\"'\\]?", "[REDACTED_KEY]", error)

    def search(self, query: str, provider: str | None = None, confirm: bool = False) -> dict[str, Any]:
        settings = get_browser_settings()
        if provider is None:
            provider = settings.get("search_provider", "none")
            
        if provider == "none":
            return {"status": "setup_needed", "message": "Search provider is not configured. Set one in Settings."}
            
        status = self.provider_status(provider)
        if status["status"] != "ready":
            return {"status": status["status"], "message": self.setup_guide(provider)}

        if settings.get("search_requires_confirmation", True) and not confirm:
            return {
                "status": "approval_required",
                "action": "search_web",
                "query": query,
                "approval_required": True,
                "warnings": ["Search requires approval."]
            }

        # Mock results for v3.0.0 since we don't have real implementation APIs configured locally
        # or we could make requests if we had keys.
        return {
            "status": "completed",
            "action": "search_web",
            "query": query,
            "provider": provider,
            "results": [
                {
                    "title": f"Mock result for {query}",
                    "url": "https://example.com/mock",
                    "snippet": f"This is a mocked snippet for {query} using {provider}.",
                    "source": provider
                }
            ],
            "approval_required": False,
            "warnings": []
        }

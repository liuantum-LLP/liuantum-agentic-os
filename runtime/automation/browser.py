import re
from typing import Any
from urllib.parse import urlparse

from runtime.automation.browser_settings import get_browser_settings

try:
    from playwright.sync_api import sync_playwright, Page, BrowserContext
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

class BrowserAutomationManager:
    def __init__(self):
        self._playwright = None
        self._browser = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    def status(self) -> dict[str, Any]:
        settings = get_browser_settings()
        return {
            "enabled": settings.get("browser_automation_enabled", False),
            "playwright_installed": HAS_PLAYWRIGHT,
            "browser_active": self._browser is not None,
        }

    def dependency_check(self) -> dict[str, Any]:
        if not HAS_PLAYWRIGHT:
            return {
                "status": "dependency_missing",
                "message": "Playwright is not installed. Install with `pip install -e .[browser]` and run `python -m playwright install chromium`."
            }
        return {"status": "installed", "message": "Playwright is installed and ready."}

    def _ensure_browser(self):
        if not HAS_PLAYWRIGHT:
            return False
        if self._browser is None:
            settings = get_browser_settings()
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(headless=settings.get("headless", False))
            self._context = self._browser.new_context()
            self._page = self._context.new_page()
        return True

    def close_browser(self):
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()
        self._browser = None
        self._playwright = None
        self._context = None
        self._page = None

    def _is_url_allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        return True

    def _redact_secrets(self, text: str) -> str:
        # Simple redaction for page text
        text = re.sub(r"sk-[A-Za-z0-9]{20,}", "[REDACTED_API_KEY]", text)
        return text

    def open_url(self, url: str, confirm: bool = False) -> dict[str, Any]:
        settings = get_browser_settings()
        if not settings.get("browser_automation_enabled", False):
            return {"status": "blocked", "action": "open_url", "message": "Browser automation is disabled."}
        
        if not self._is_url_allowed(url):
            return {"status": "blocked", "action": "open_url", "message": "Invalid or blocked URL scheme."}

        if settings.get("require_confirmation_for_navigation", True) and not confirm:
            return {
                "status": "approval_required",
                "action": "open_url",
                "url": url,
                "title": "",
                "text_preview": "",
                "screenshot_path": None,
                "approval_required": True,
                "warnings": ["Navigating to URL requires approval."]
            }

        if not HAS_PLAYWRIGHT:
            return self.dependency_check()

        self._ensure_browser()
        try:
            self._page.goto(url)
            self._page.wait_for_load_state("networkidle")
            title = self._page.title()
            text = self._page.inner_text("body")[:500]
            return {
                "status": "completed",
                "action": "open_url",
                "url": url,
                "title": title,
                "text_preview": self._redact_secrets(text),
                "screenshot_path": None,
                "approval_required": False,
                "warnings": []
            }
        except Exception as e:
            return {"status": "failed", "action": "open_url", "message": str(e)}

    def search_web(self, query: str, provider: str = "configured", confirm: bool = False) -> dict[str, Any]:
        # This will delegate or wrap around search.py
        # For now, implemented properly in search.py
        pass

    def read_page(self, url: str | None = None, current_page: bool = False, confirm: bool = False) -> dict[str, Any]:
        settings = get_browser_settings()
        if not settings.get("browser_automation_enabled", False):
            return {"status": "blocked", "action": "read_page", "message": "Browser automation disabled."}
            
        if not HAS_PLAYWRIGHT:
            return self.dependency_check()
            
        if not current_page and url:
            if not confirm and settings.get("require_confirmation_for_navigation", True):
                return {"status": "approval_required", "action": "read_page", "url": url, "approval_required": True, "warnings": []}
            self._ensure_browser()
            try:
                self._page.goto(url)
                self._page.wait_for_load_state("networkidle")
            except Exception as e:
                return {"status": "failed", "action": "read_page", "message": str(e)}

        if not self._page:
            return {"status": "failed", "action": "read_page", "message": "No active page."}

        text = self._page.inner_text("body")
        if settings.get("redact_page_text", True):
            text = self._redact_secrets(text)
        max_chars = settings.get("max_page_text_chars", 20000)
        
        return {
            "status": "completed",
            "action": "read_page",
            "url": self._page.url,
            "title": self._page.title(),
            "text": text[:max_chars],
            "approval_required": False,
            "warnings": []
        }

    def summarize_page(self, url: str | None = None, model_role: str = "default") -> dict[str, Any]:
        res = self.read_page(url=url, confirm=True)
        if res.get("status") != "completed":
            return res
        
        # Here we would normally call the agent generation
        # For this skeleton, we just mock the summary format
        return {
            "status": "completed",
            "action": "summarize_page",
            "url": res["url"],
            "summary": f"Mock summary of {res['title']}",
            "approval_required": False,
            "warnings": []
        }

    def screenshot_page(self, url: str | None = None, output_path: str | None = None, confirm: bool = False) -> dict[str, Any]:
        settings = get_browser_settings()
        if not settings.get("allow_screenshots", False):
            return {"status": "blocked", "action": "screenshot_page", "message": "Screenshots disabled in settings."}
            
        if not confirm:
            return {"status": "approval_required", "action": "screenshot_page", "url": url, "approval_required": True, "warnings": ["Screenshot requires approval."]}

        if not HAS_PLAYWRIGHT:
            return self.dependency_check()

        if url:
            self._ensure_browser()
            self._page.goto(url)
        elif not self._page:
            return {"status": "failed", "action": "screenshot_page", "message": "No active page."}

        if output_path:
            self._page.screenshot(path=output_path)

        return {
            "status": "completed",
            "action": "screenshot_page",
            "url": self._page.url,
            "screenshot_path": output_path,
            "approval_required": False,
            "warnings": []
        }

    def click(self, selector_or_text: str, confirm: bool = False) -> dict[str, Any]:
        if not confirm:
            return {"status": "approval_required", "action": "click", "approval_required": True, "warnings": ["Click requires approval."]}

        if not HAS_PLAYWRIGHT:
            return self.dependency_check()
            
        if not self._page:
            return {"status": "failed", "action": "click", "message": "No active page."}

        try:
            self._page.click(selector_or_text)
            return {"status": "completed", "action": "click"}
        except Exception as e:
            return {"status": "failed", "action": "click", "message": str(e)}

    def fill_form(self, fields: dict[str, str], confirm: bool = False) -> dict[str, Any]:
        if not confirm:
            return {"status": "approval_required", "action": "fill_form", "approval_required": True, "warnings": ["Form fill requires approval."]}

        if not HAS_PLAYWRIGHT:
            return self.dependency_check()

        if not self._page:
            return {"status": "failed", "action": "fill_form", "message": "No active page."}

        try:
            for selector, value in fields.items():
                self._page.fill(selector, value)
            return {"status": "completed", "action": "fill_form"}
        except Exception as e:
            return {"status": "failed", "action": "fill_form", "message": str(e)}

    def download_file(self, url: str, output_path: str | None = None, confirm: bool = False) -> dict[str, Any]:
        if not confirm:
            return {"status": "approval_required", "action": "download_file", "approval_required": True, "warnings": ["Download requires approval."]}
        return {"status": "failed", "action": "download_file", "message": "Not implemented completely in v3.0.0"}

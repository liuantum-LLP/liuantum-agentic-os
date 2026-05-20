import os
import pytest
from pathlib import Path

from runtime.automation.browser import BrowserAutomationManager
from runtime.automation.search import SearchManager
from runtime.automation.desktop import DesktopAutomationManager
from runtime.automation.browser_settings import get_browser_settings, update_browser_settings
from runtime.approvals.queue import ActionApprovalQueue

def test_browser_disabled_by_default(tmp_path):
    # Setup test workspace
    os.environ["LIUANT_WORKSPACE"] = str(tmp_path)
    
    settings = get_browser_settings()
    assert settings.get("browser_automation_enabled") is False
    
    browser = BrowserAutomationManager()
    status = browser.status()
    assert status["enabled"] is False

def test_browser_enable_requires_confirmation(tmp_path):
    os.environ["LIUANT_WORKSPACE"] = str(tmp_path)
    update_browser_settings({"browser_automation_enabled": True})
    
    settings = get_browser_settings()
    assert settings.get("browser_automation_enabled") is True
    
    browser = BrowserAutomationManager()
    # Mocking disabled, but if called it needs confirmation.
    res = browser.open_url("https://example.com", confirm=False)
    assert res["status"] == "approval_required"
    assert "approval_required" in res

def test_desktop_open_app_requires_confirmation():
    desktop = DesktopAutomationManager()
    res = desktop.open_app("Terminal", confirm=False)
    assert res["status"] == "approval_required"

def test_desktop_safe_apps_list():
    desktop = DesktopAutomationManager()
    safe = desktop.list_safe_apps()
    assert "Terminal" in safe
    assert "Google Chrome" in safe

def test_search_provider_fallback(tmp_path):
    os.environ["LIUANT_WORKSPACE"] = str(tmp_path)
    search = SearchManager()
    res = search.search("test query", provider="none")
    assert res["status"] == "setup_needed"

def test_approval_queue_creates_and_approves(tmp_path):
    os.environ["LIUANT_WORKSPACE"] = str(tmp_path)
    queue = ActionApprovalQueue()
    
    item = queue.create(
        action_type="open_url",
        title="Open Example",
        description="Navigate to example.com",
        risk_level="low",
        payload={"url": "https://example.com", "secret_key": "api_key=my-fake-test-key-123"}
    )
    
    assert item["status"] == "pending"
    assert "my-fake-test-key" not in item["payload"]["secret_key"] # Redacted
    assert "[REDACTED_KEY]" in item["payload"]["secret_key"]
    
    pending = queue.list_pending()
    assert len(pending) == 1
    
    res = queue.approve(item["id"])
    assert res["status"] == "completed"
    assert res["mocked_execution"] is True
    
    pending_after = queue.list_pending()
    assert len(pending_after) == 0

def test_desktop_validates_app_name():
    desktop = DesktopAutomationManager()
    val = desktop.validate_app_name("Terminal")
    assert val["valid"] is True
    assert val["warning"] is None
    
    val2 = desktop.validate_app_name("MaliciousApp")
    assert val2["valid"] is True # Still allows trying to open it, but throws a warning
    assert val2["warning"] is not None

def test_desktop_open_file_hidden(tmp_path):
    desktop = DesktopAutomationManager()
    hidden_file = tmp_path / ".secret"
    hidden_file.write_text("secret")
    
    res = desktop.open_file(str(hidden_file), confirm=True)
    assert res["status"] == "blocked"
    assert "hidden paths" in res["message"]

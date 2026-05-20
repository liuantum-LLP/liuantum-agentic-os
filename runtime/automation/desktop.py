import os
import platform
import subprocess
from pathlib import Path
from typing import Any

SAFE_APPS = {
    "Google Chrome",
    "Safari",
    "Firefox",
    "Visual Studio Code",
    "Terminal",
    "Finder",
    "PyCharm",
    "Cursor",
    "Antigravity",
}

class DesktopAutomationManager:
    def status(self) -> dict[str, Any]:
        return {
            "status": "active",
            "os": platform.system(),
        }

    def list_safe_apps(self) -> list[str]:
        return sorted(list(SAFE_APPS))

    def validate_app_name(self, app_name: str) -> dict[str, Any]:
        if app_name in SAFE_APPS:
            return {"valid": True, "warning": None}
        return {"valid": True, "warning": f"'{app_name}' is not in the safe allowlist."}

    def validate_path(self, path: str) -> dict[str, Any]:
        p = Path(path).resolve()
        if p.name.startswith("."):
            return {"valid": False, "warning": "Cannot open hidden paths."}
        return {"valid": True, "warning": None}

    def open_app(self, app_name: str, confirm: bool = False) -> dict[str, Any]:
        val = self.validate_app_name(app_name)
        if not confirm:
            warnings = ["Opening app requires approval."]
            if val["warning"]:
                warnings.append(val["warning"])
            return {
                "status": "approval_required",
                "action": "open_app",
                "target": app_name,
                "approval_required": True,
                "warnings": warnings,
            }

        sys_os = platform.system()
        try:
            if sys_os == "Darwin":
                subprocess.run(["open", "-a", app_name], check=True)
            elif sys_os == "Windows":
                # Assuming app_name is an executable path or registered alias in Windows if it's not a path
                subprocess.run(["start", "", app_name], shell=True, check=True)
            elif sys_os == "Linux":
                subprocess.run(["xdg-open", app_name], check=True)
            else:
                return {"status": "failed", "action": "open_app", "message": "Unsupported OS."}
            return {"status": "completed", "action": "open_app", "target": app_name, "approval_required": False, "warnings": []}
        except Exception as e:
            return {"status": "failed", "action": "open_app", "target": app_name, "message": str(e)}

    def open_url_system(self, url: str, confirm: bool = False) -> dict[str, Any]:
        if not confirm:
            return {"status": "approval_required", "action": "open_url_system", "target": url, "approval_required": True, "warnings": ["Requires confirmation."]}
        
        sys_os = platform.system()
        try:
            if sys_os == "Darwin":
                subprocess.run(["open", url], check=True)
            elif sys_os == "Windows":
                subprocess.run(["start", "", url], shell=True, check=True)
            elif sys_os == "Linux":
                subprocess.run(["xdg-open", url], check=True)
            return {"status": "completed", "action": "open_url_system", "target": url}
        except Exception as e:
            return {"status": "failed", "action": "open_url_system", "message": str(e)}

    def open_file(self, path: str, confirm: bool = False) -> dict[str, Any]:
        val = self.validate_path(path)
        if not val["valid"]:
            return {"status": "blocked", "action": "open_file", "message": val["warning"]}

        if not confirm:
            return {"status": "approval_required", "action": "open_file", "target": path, "approval_required": True, "warnings": ["Opening file requires approval."]}

        sys_os = platform.system()
        try:
            if sys_os == "Darwin":
                subprocess.run(["open", path], check=True)
            elif sys_os == "Windows":
                subprocess.run(["start", "", path], shell=True, check=True)
            elif sys_os == "Linux":
                subprocess.run(["xdg-open", path], check=True)
            return {"status": "completed", "action": "open_file", "target": path}
        except Exception as e:
            return {"status": "failed", "action": "open_file", "message": str(e)}

    def open_folder(self, path: str, confirm: bool = False) -> dict[str, Any]:
        return self.open_file(path, confirm)

    def reveal_file(self, path: str, confirm: bool = False) -> dict[str, Any]:
        val = self.validate_path(path)
        if not val["valid"]:
            return {"status": "blocked", "action": "reveal_file", "message": val["warning"]}
        
        if not confirm:
            return {"status": "approval_required", "action": "reveal_file", "target": path, "approval_required": True, "warnings": ["Revealing file requires approval."]}

        sys_os = platform.system()
        try:
            if sys_os == "Darwin":
                subprocess.run(["open", "-R", path], check=True)
            elif sys_os == "Windows":
                subprocess.run(["explorer", f"/select,{path}"], check=True)
            elif sys_os == "Linux":
                subprocess.run(["xdg-open", str(Path(path).parent)], check=True)
            return {"status": "completed", "action": "reveal_file", "target": path}
        except Exception as e:
            return {"status": "failed", "action": "reveal_file", "message": str(e)}

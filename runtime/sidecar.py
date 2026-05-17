from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from runtime.config import SettingsManager
from runtime.storage import ROOT, WORKSPACE

SIDECAR_NAME = "liuant-backend"
SIDECAR_DIR = ROOT / "sidecar"
SIDECAR_STATUS_PATH = WORKSPACE / "sidecar.json"


def _required_packaging_tools() -> dict[str, bool]:
    return {
        "pyinstaller": shutil.which("pyinstaller") is not None,
        "nuitka": shutil.which("nuitka") is not None,
        "zipapp": True,
    }


def _sidecar_executable_path() -> Path | None:
    if sys.platform == "win32":
        exe = SIDECAR_DIR / f"{SIDECAR_NAME}.exe"
    else:
        exe = SIDECAR_DIR / SIDECAR_NAME
    if exe.exists() and os.access(str(exe), os.X_OK):
        return exe

    alt = shutil.which(SIDECAR_NAME)
    if alt:
        p = Path(alt)
        if p.exists() and os.access(str(p), os.X_OK):
            return p

    return None


def _read_status() -> dict[str, Any] | None:
    if not SIDECAR_STATUS_PATH.exists():
        return None
    try:
        import json
        return json.loads(SIDECAR_STATUS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_status(data: dict[str, Any]) -> None:
    import json
    SIDECAR_STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SIDECAR_STATUS_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _clear_status() -> None:
    if SIDECAR_STATUS_PATH.exists():
        SIDECAR_STATUS_PATH.unlink()


def sidecar_status() -> dict[str, Any]:
    available = _sidecar_executable_path() is not None
    status_data = _read_status() or {}
    running = False
    pid = status_data.get("pid")
    if pid:
        try:
            os.kill(int(pid), 0)
            running = True
        except (ProcessLookupError, OSError):
            running = False

    tools = _required_packaging_tools()

    return {
        "status": "available" if available else "unavailable",
        "executable": str(_sidecar_executable_path()) if available else None,
        "running": running,
        "pid": pid if running else None,
        "started_at": status_data.get("started_at") if running else None,
        "port": status_data.get("port", 8765),
        "host": status_data.get("host", "127.0.0.1"),
        "packaging_tools": tools,
        "build_instructions": _build_instructions(),
        "message": "Sidecar executable is available." if available else "Sidecar executable not found. Run `./liuant sidecar build` to create one, or use external_backend / managed_backend mode.",
    }


def sidecar_build(confirm: bool = False) -> dict[str, Any]:
    if not confirm:
        return {
            "status": "blocked",
            "message": "Sidecar build requires --confirm.",
            "build_instructions": _build_instructions(),
        }

    tools = _required_packaging_tools()

    if tools["pyinstaller"]:
        return _build_with_pyinstaller()
    elif tools["nuitka"]:
        return _build_with_nuitka()
    else:
        return {
            "status": "dependency_missing",
            "message": "No packaging tool found. Install PyInstaller (`pip install pyinstaller`) or Nuitka (`pip install nuitka`) to build a sidecar executable.",
            "packaging_tools": tools,
            "build_instructions": _build_instructions(),
        }


def _build_with_pyinstaller() -> dict[str, Any]:
    SIDECAR_DIR.mkdir(parents=True, exist_ok=True)
    entry = str(ROOT / "cli" / "liuant.py")
    output_dir = str(SIDECAR_DIR)
    try:
        result = subprocess.run(
            [
                "pyinstaller",
                "--onefile",
                "--name", SIDECAR_NAME,
                "--distpath", output_dir,
                "--workpath", str(SIDECAR_DIR / "build"),
                "--specpath", str(SIDECAR_DIR),
                "--add-data", f"{ROOT / 'ui'}{os.pathsep}ui",
                entry,
            ],
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode != 0:
            return {
                "status": "build_failed",
                "tool": "pyinstaller",
                "returncode": result.returncode,
                "stdout": result.stdout[-2000:] if result.stdout else "",
                "stderr": result.stderr[-2000:] if result.stderr else "",
                "message": "PyInstaller build failed. Check output above for details.",
            }
        exe = _sidecar_executable_path()
        if exe and exe.exists():
            size_kb = exe.stat().st_size / 1024
            return {
                "status": "completed",
                "tool": "pyinstaller",
                "executable": str(exe),
                "size_kb": round(size_kb, 1),
                "message": f"Sidecar executable built at {exe} ({size_kb:.0f} KB).",
            }
        return {
            "status": "completed",
            "tool": "pyinstaller",
            "executable": str(SIDECAR_DIR / SIDECAR_NAME),
            "message": "PyInstaller build completed but executable not found at expected path.",
        }
    except FileNotFoundError:
        return {
            "status": "dependency_missing",
            "tool": "pyinstaller",
            "message": "PyInstaller not found. Install with: pip install pyinstaller",
        }
    except subprocess.TimeoutExpired:
        return {
            "status": "build_timeout",
            "tool": "pyinstaller",
            "message": "PyInstaller build timed out after 300 seconds.",
        }


def _build_with_nuitka() -> dict[str, Any]:
    SIDECAR_DIR.mkdir(parents=True, exist_ok=True)
    entry = str(ROOT / "cli" / "liuant.py")
    output_dir = str(SIDECAR_DIR)
    try:
        result = subprocess.run(
            [
                "nuitka",
                "--onefile",
                "--output-dir", output_dir,
                "--output-filename", SIDECAR_NAME,
                entry,
            ],
            capture_output=True, text=True, timeout=600,
        )
        if result.returncode != 0:
            return {
                "status": "build_failed",
                "tool": "nuitka",
                "returncode": result.returncode,
                "stdout": result.stdout[-2000:] if result.stdout else "",
                "stderr": result.stderr[-2000:] if result.stderr else "",
                "message": "Nuitka build failed. Check output above for details.",
            }
        exe = _sidecar_executable_path()
        if exe and exe.exists():
            size_kb = exe.stat().st_size / 1024
            return {
                "status": "completed",
                "tool": "nuitka",
                "executable": str(exe),
                "size_kb": round(size_kb, 1),
                "message": f"Sidecar executable built at {exe} ({size_kb:.0f} KB).",
            }
        return {
            "status": "completed",
            "tool": "nuitka",
            "executable": str(SIDECAR_DIR / SIDECAR_NAME),
            "message": "Nuitka build completed but executable not found at expected path.",
        }
    except FileNotFoundError:
        return {
            "status": "dependency_missing",
            "tool": "nuitka",
            "message": "Nuitka not found. Install with: pip install nuitka",
        }
    except subprocess.TimeoutExpired:
        return {
            "status": "build_timeout",
            "tool": "nuitka",
            "message": "Nuitka build timed out after 600 seconds.",
        }


def sidecar_check() -> dict[str, Any]:
    exe = _sidecar_executable_path()
    if not exe:
        return {
            "status": "unavailable",
            "executable": None,
            "message": "No sidecar executable found. Build with: ./liuant sidecar build",
            "build_instructions": _build_instructions(),
        }

    try:
        result = subprocess.run(
            [str(exe), "--version"],
            capture_output=True, text=True, timeout=15,
        )
        version_output = (result.stdout or result.stderr or "").strip()
        # Also try a quick help
        help_result = subprocess.run(
            [str(exe), "--help"],
            capture_output=True, text=True, timeout=15,
        )
        help_output = (help_result.stdout or help_result.stderr or "").strip()

        return {
            "status": "available",
            "executable": str(exe),
            "version_output": version_output[:500] if version_output else None,
            "help_output": help_output[:500] if help_output else None,
            "message": "Sidecar executable found and responds.",
        }
    except subprocess.TimeoutExpired:
        return {
            "status": "timeout",
            "executable": str(exe),
            "message": "Sidecar executable found but did not respond within 15 seconds. It may be starting slowly or corrupted.",
        }
    except Exception as e:
        return {
            "status": "error",
            "executable": str(exe),
            "message": f"Sidecar executable found but could not be launched: {e}",
        }


def sidecar_run(host: str = "127.0.0.1", port: int = 8765) -> dict[str, Any]:
    if host not in {"127.0.0.1", "localhost"}:
        return {
            "status": "blocked",
            "message": "Sidecar backend may only bind to localhost.",
            "host": host,
        }

    exe = _sidecar_executable_path()
    if not exe:
        return {
            "status": "unavailable",
            "message": "No sidecar executable found. Build with: ./liuant sidecar build",
            "build_instructions": _build_instructions(),
        }

    status = _read_status()
    if status and status.get("pid"):
        try:
            os.kill(int(status["pid"]), 0)
            return {
                "status": "already_running",
                "pid": status["pid"],
                "url": f"http://{host}:{port}",
                "message": "Sidecar backend is already running.",
            }
        except (ProcessLookupError, OSError):
            pass

    try:
        process = subprocess.Popen(
            [str(exe), "serve", str(port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=str(ROOT),
        )
        pid = process.pid
        data = {
            "pid": pid,
            "host": host,
            "port": port,
            "url": f"http://{host}:{port}",
            "status": "started",
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
        _write_status(data)
        return {
            "status": "started",
            "pid": pid,
            "url": data["url"],
            "host": host,
            "port": port,
            "message": f"Sidecar backend started (PID {pid}).",
        }
    except Exception as e:
        return {
            "status": "failed",
            "message": f"Failed to start sidecar backend: {e}",
        }


def sidecar_stop(confirm: bool = False) -> dict[str, Any]:
    if not confirm:
        return {
            "status": "blocked",
            "message": "Sidecar stop requires --confirm.",
        }

    status = _read_status()
    if not status or not status.get("pid"):
        return {
            "status": "not_running",
            "message": "Sidecar backend is not running (no PID file).",
        }

    pid = int(status["pid"])
    try:
        os.kill(pid, signal.SIGTERM)
        _clear_status()
        return {
            "status": "stopped",
            "pid": pid,
            "message": f"Sidecar backend stopped (PID {pid}).",
        }
    except ProcessLookupError:
        _clear_status()
        return {
            "status": "stopped",
            "pid": pid,
            "message": f"Sidecar backend was not running (PID {pid} not found). Status cleared.",
        }
    except Exception as e:
        return {
            "status": "error",
            "pid": pid,
            "message": f"Failed to stop sidecar backend: {e}",
        }


def _build_instructions() -> list[str]:
    return [
        "To build the sidecar backend executable:",
        "  1. pip install pyinstaller",
        "  2. ./liuant sidecar build --confirm",
        "Alternatively use Nuitka:",
        "  1. pip install nuitka",
        "  2. ./liuant sidecar build --confirm",
        "The executable will be placed in sidecar/liuant-backend.",
    ]

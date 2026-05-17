from __future__ import annotations

import importlib.util
import inspect
import os
import tempfile
import traceback
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable


def fixture(*_args: Any, **_kwargs: Any) -> Callable:
    def decorator(func: Callable) -> Callable:
        return func

    return decorator


class MonkeyPatch:
    def __init__(self) -> None:
        self._env: list[tuple[str, str | None]] = []

    def setenv(self, key: str, value: str) -> None:
        self._env.append((key, os.environ.get(key)))
        os.environ[key] = value

    def delenv(self, key: str, raising: bool = True) -> None:
        if key not in os.environ:
            if raising:
                raise KeyError(key)
            return
        self._env.append((key, os.environ.get(key)))
        os.environ.pop(key, None)

    def setattr(self, target: Any, name: str | None = None, value: Any = None) -> None:
        if name is None:
            raise TypeError("setattr requires target, name, and value")
        original = getattr(target, name)
        self._env.append((f"__attr__:{id(target)}:{name}", (target, name, original)))  # type: ignore[arg-type]
        setattr(target, name, value)

    def undo(self) -> None:
        for key, value in reversed(self._env):
            if key.startswith("__attr__"):
                target, name, original = value  # type: ignore[misc]
                setattr(target, name, original)
            elif value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self._env.clear()


def main() -> int:
    quiet = "-q" in os.sys.argv
    test_files = sorted(Path("tests").glob("test_*.py"))
    passed = 0
    failed: list[tuple[str, BaseException, str]] = []
    for file_path in test_files:
        module = _load_module(file_path)
        for name, func in inspect.getmembers(module, inspect.isfunction):
            if not name.startswith("test_"):
                continue
            label = f"{file_path}::{name}"
            monkeypatch = MonkeyPatch()
            with tempfile.TemporaryDirectory() as temp_dir:
                tmp_path = Path(temp_dir)
                monkeypatch.setenv("LIUANT_DB_PATH", str(tmp_path / "liuant-test.db"))
                kwargs = {}
                signature = inspect.signature(func)
                if "tmp_path" in signature.parameters:
                    kwargs["tmp_path"] = tmp_path
                if "monkeypatch" in signature.parameters:
                    kwargs["monkeypatch"] = monkeypatch
                try:
                    func(**kwargs)
                    passed += 1
                    if not quiet:
                        print(f"PASSED {label}")
                except BaseException as exc:
                    failed.append((label, exc, traceback.format_exc()))
                finally:
                    monkeypatch.undo()
    if failed:
        for label, exc, tb in failed:
            print(f"FAILED {label}: {exc}")
            print(tb)
        print(f"{len(failed)} failed, {passed} passed")
        return 1
    print(f"{passed} passed")
    return 0


def console_main() -> int:
    return main()


def _load_module(path: Path) -> Any:
    name = path.with_suffix("").as_posix().replace("/", ".")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


if __name__ == "__main__":
    raise SystemExit(main())

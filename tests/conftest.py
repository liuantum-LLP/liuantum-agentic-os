import os

import pytest


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setenv("LIUANT_DB_PATH", str(tmp_path / "liuant-test.db"))
    monkeypatch.setenv("LIUANT_SECRET_STORE_PATH", str(tmp_path / "secrets.enc.json"))
    monkeypatch.setenv("LIUANT_LOCAL_SECRET_KEY_PATH", str(tmp_path / "local-secret.key"))
    yield

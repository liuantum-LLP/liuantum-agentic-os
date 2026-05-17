from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any


def get_json(url: str, access_token: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"authorization": f"Bearer {access_token}"})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def post_json(url: str, payload: dict[str, Any], access_token: str, headers: dict[str, str] | None = None) -> dict[str, Any]:
    request_headers = {"authorization": f"Bearer {access_token}", "content-type": "application/json"}
    request_headers.update(headers or {})
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=request_headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def exchange_code(token_url: str, code: str, client_id: str, client_secret: str, redirect_uri: str, code_verifier: str | None = None) -> dict[str, Any]:
    payload = {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    if code_verifier:
        payload["code_verifier"] = code_verifier
    body = urllib.parse.urlencode(payload).encode("utf-8")
    request = urllib.request.Request(token_url, data=body, headers={"content-type": "application/x-www-form-urlencoded"}, method="POST")
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


"""Tiny JSON GET with a browser-like UA. Stdlib only."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

import certifi

os.environ.setdefault("SSL_CERT_FILE", certifi.where())
os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())

UA = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
}


def get_json(url: str, timeout: float = 12) -> Any:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def try_json(url: str, timeout: float = 12) -> tuple[Any | None, str | None]:
    try:
        return get_json(url, timeout=timeout), None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
        return None, str(exc)

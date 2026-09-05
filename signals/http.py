"""Tiny JSON GET with a browser-like UA. Stdlib only."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

UA = {"User-Agent": "smart-money-floor/1.0", "Accept": "application/json"}


def get_json(url: str, timeout: float = 12) -> Any:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def try_json(url: str, timeout: float = 12) -> tuple[Any | None, str | None]:
    try:
        return get_json(url, timeout=timeout), None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
        return None, str(exc)

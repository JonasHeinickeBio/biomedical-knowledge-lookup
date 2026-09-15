"""
Keep API keys out of log messages and error strings.

HTTP client errors embed the request URL (aiohttp, httpx), so a key sent as a
query parameter ends up in any log line that formats the exception. Adapters
send keys in headers where the upstream API allows it; :func:`redact` is the
second line of defence for everything that is still logged.
"""

from __future__ import annotations

import re

MASK = "***"

# `apikey=…`, `apiKey=…`, `api_key=…`, `token=…` query parameters (URL-encoded or not)
_SECRET_PARAM = re.compile(r"(?i)\b(api[_-]?key|access[_-]?token|token)=([^&\s'\"<>]+)")
# `Authorization: apikey token=…`, `Bearer …`, `Basic …` header values
_AUTH_VALUE = re.compile(r"(?i)\b(apikey token=|bearer\s+|basic\s+)([^\s'\",}>]+)")


def redact(text: object, *secrets: str | None) -> str:
    """Return ``str(text)`` with the given secret values and key-like parameters masked."""
    message = str(text)
    for secret in secrets:
        if secret:
            message = message.replace(secret, MASK)
    message = _SECRET_PARAM.sub(lambda m: f"{m.group(1)}={MASK}", message)
    return _AUTH_VALUE.sub(lambda m: f"{m.group(1)}{MASK}", message)

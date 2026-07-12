"""Redacción de secretos / patrones sensibles en logs y resúmenes."""

from __future__ import annotations

import re

_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*[=:]\s*\S+"), r"\1=***REDACTED***"),
    (re.compile(r"(?i)authorization:\s*\S+"), "Authorization: ***REDACTED***"),
    (re.compile(r"(?i)bearer\s+[A-Za-z0-9\-._~+/]+=*"), "Bearer ***REDACTED***"),
    (re.compile(r"(?i)openai-api-key\s*[:=]\s*\S+"), "openai-api-key=***REDACTED***"),
]


def redact(text: str, max_chars: int | None = None) -> str:
    if not text:
        return text
    out = text
    for pattern, repl in _PATTERNS:
        out = pattern.sub(repl, out)
    if max_chars is not None and len(out) > max_chars:
        out = out[: max_chars - 20] + "\n...[truncated]..."
    return out

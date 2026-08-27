from __future__ import annotations

from launcher.logging_config import redact


def test_redact_removes_common_secrets() -> None:
    text = "api_key=sk-123456789012345 authorization: Bearer abc123"
    result = redact(text)
    assert "sk-123456789012345" not in result
    assert "Bearer abc123" not in result
    assert "[REDACTED]" in result

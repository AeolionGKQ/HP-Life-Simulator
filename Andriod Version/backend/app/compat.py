from __future__ import annotations


class HTTPException(Exception):
    """Minimal FastAPI-compatible exception for the Android service layer."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)

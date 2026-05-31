"""Structured sensor error — carried inside a signal, not raised to the client."""
from __future__ import annotations


class SensorError(Exception):
    """Raised internally by a sensor; callers convert it to an error_signal.

    Attributes:
        code: short machine-readable code (e.g. "missing_token", "fetch_failed").
        message: human-readable detail.
    """

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")

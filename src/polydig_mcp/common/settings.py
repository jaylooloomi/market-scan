"""Load configuration from environment / .env.

Secrets (FinMind token, etc.) live in .env (gitignored) and NEVER in code.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


def _find_dotenv() -> Path | None:
    """Walk up from CWD looking for a .env so the servers work regardless of
    which directory Claude Code launches them from."""
    here = Path.cwd()
    for parent in [here, *here.parents]:
        candidate = parent / ".env"
        if candidate.exists():
            return candidate
    return None


@dataclass
class Settings:
    finmind_token: str | None
    http_timeout: float
    user_agent: str
    telegram_bot_token: str | None
    telegram_chat_id: str | None

    @property
    def has_finmind(self) -> bool:
        return bool(self.finmind_token)

    @property
    def has_telegram(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_chat_id)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    dotenv_path = _find_dotenv()
    if dotenv_path is not None:
        load_dotenv(dotenv_path)
    return Settings(
        finmind_token=os.getenv("FINMIND_TOKEN") or os.getenv("FINMIND_API_TOKEN"),
        http_timeout=float(os.getenv("POLYDIG_HTTP_TIMEOUT", "15")),
        user_agent=os.getenv(
            "POLYDIG_USER_AGENT",
            "Market-Scan/0.1 (+https://github.com/jaylooloomi/market-scan) research-assistant",
        ),
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID"),
    )

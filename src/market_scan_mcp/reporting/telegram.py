"""Push a report to Telegram via the Bot API.

Credentials come from .env (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID) — never
hardcoded, never logged. Sends plain text (no parse_mode) so unescaped Markdown
in the report can't trigger Telegram 400 errors; long reports are split into
<=4096-char chunks. Failure is returned as a structured result, never raised.
"""
from __future__ import annotations

from typing import Any

import requests

from market_scan_mcp.common.settings import get_settings

API_BASE = "https://api.telegram.org"
MAX_LEN = 4000  # Telegram hard limit is 4096; leave headroom


def _split(text: str, limit: int = MAX_LEN) -> list[str]:
    """Split text into <=limit chunks, preferring paragraph/line boundaries."""
    chunks: list[str] = []
    remaining = text
    while len(remaining) > limit:
        cut = remaining.rfind("\n", 0, limit)
        if cut <= 0:
            cut = limit
        chunks.append(remaining[:cut])
        remaining = remaining[cut:].lstrip("\n")
    if remaining:
        chunks.append(remaining)
    return chunks


def send_message(text: str, *, token: str | None = None, chat_id: str | None = None) -> dict[str, Any]:
    """Send `text` to Telegram. Returns {ok, sent, chunks, error?}.

    Uses .env credentials unless token/chat_id are passed explicitly.
    """
    settings = get_settings()
    token = token or settings.telegram_bot_token
    chat_id = chat_id or settings.telegram_chat_id
    if not token or not chat_id:
        return {"ok": False, "sent": 0, "chunks": 0,
                "error": "missing TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID in .env"}

    url = f"{API_BASE}/bot{token}/sendMessage"
    parts = _split(text)
    sent = 0
    for part in parts:
        try:
            resp = requests.post(
                url,
                json={"chat_id": chat_id, "text": part, "disable_web_page_preview": True},
                timeout=settings.http_timeout,
            )
            payload = resp.json()
            if not payload.get("ok"):
                # Telegram errors (e.g. chat not found if user hasn't /start'd the bot)
                return {"ok": False, "sent": sent, "chunks": len(parts),
                        "error": f"telegram api: {payload.get('description', resp.text[:120])}"}
            sent += 1
        except requests.RequestException as e:
            return {"ok": False, "sent": sent, "chunks": len(parts), "error": f"network: {e}"}
    return {"ok": True, "sent": sent, "chunks": len(parts)}


def main(argv: list[str] | None = None) -> int:
    """`python -m market_scan_mcp.reporting.telegram <file>` — send a file's contents
    (or stdin if no file) to Telegram. Used by the daily routine to push a
    Claude-polished summary."""
    import sys

    args = argv if argv is not None else sys.argv[1:]
    if args:
        text = open(args[0], encoding="utf-8").read()
    else:
        text = sys.stdin.read()
    if not text.strip():
        print("telegram: nothing to send (empty input)", file=sys.stderr)
        return 1
    res = send_message(text)
    print(f"telegram: {res}")
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

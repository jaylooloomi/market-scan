"""Unit tests for the Telegram push helper — _split + send_message paths, no real network."""
from __future__ import annotations

import sys

sys.path.insert(0, "src")
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import polydig_mcp.reporting.telegram as tg


def main() -> int:
    # _split keeps every chunk <= limit and splits a long body into many parts
    chunks = tg._split("line\n" * 5000, limit=100)
    assert len(chunks) > 1 and all(len(c) <= 100 for c in chunks), [len(c) for c in chunks[:3]]
    assert tg._split("hello", limit=100) == ["hello"]
    print(f"_split: PASS ({len(chunks)} chunks)")

    # missing credentials -> ok False, no network call attempted
    res = tg.send_message("hi", token=None, chat_id=None)
    assert res["ok"] is False and "missing" in res["error"].lower(), res
    print("send_message missing-creds: PASS")

    # mocked success by swapping the module-level `requests` (restored in finally)
    class _Resp:
        text = ""
        def json(self):
            return {"ok": True}

    class _FakeRequests:
        RequestException = Exception
        def post(self, url, json=None, timeout=None):
            return _Resp()

    orig = tg.requests
    try:
        tg.requests = _FakeRequests()
        ok = tg.send_message("hi", token="t", chat_id="c")
        assert ok["ok"] is True and ok["sent"] == 1 and ok["chunks"] == 1, ok
    finally:
        tg.requests = orig
    print("send_message mocked-success: PASS")

    print("\n=== PASS ===")
    return 0


def test_telegram():
    assert main() == 0


if __name__ == "__main__":
    raise SystemExit(main())

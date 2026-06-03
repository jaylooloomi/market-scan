"""End-to-end integration test for the Phase 1 MCP servers.

Launches each server as a real subprocess over stdio (exactly how Claude Code
will), lists its tools, and invokes one cheap tool to prove the round trip.

Run:  python tests/test_mcp_integration.py
"""
from __future__ import annotations

import asyncio
import json
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Each (tool, args) exercises the network path (requests-based now — yfinance was
# removed from the server path because curl_cffi corrupts the stdio transport).
SERVERS = {
    "market-scan-news": (["-m", "market_scan_mcp.news.server"], "fetch_news", {"source": "udn-money", "limit": 3}),
    "market-scan-data": (["-m", "market_scan_mcp.data.server"], "get_commodity_price", {"commodity": "crude"}),
    "market-scan-price": (["-m", "market_scan_mcp.price.server"], "get_quote", {"symbol": "2330"}),
    "market-scan-policy": (["-m", "market_scan_mcp.policy.server"], "list_policy_sources", {}),
    "market-scan-roadmap": (["-m", "market_scan_mcp.roadmap.server"], "parse_earnings_call",
                        {"text": "我們看到 HBM4 供不應求,CoWoS 擴產,800G 升級到 1.6T", "company": "TSMC"}),
}


async def check_server(name: str, args: list[str], tool: str, tool_args: dict) -> bool:
    params = StdioServerParameters(command=sys.executable, args=args)
    # errlog MUST be utf-8: stdio_client forwards the server's stderr here, and a
    # cp950 console (Windows default) raises UnicodeEncodeError on CJK log lines,
    # which crashes the anyio TaskGroup as BrokenResourceError. Real Claude Code
    # captures stderr safely; we replicate that here.
    errlog = open(os.devnull, "w", encoding="utf-8")
    async with stdio_client(params, errlog=errlog) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            tool_names = [t.name for t in tools.tools]
            print(f"[{name}] tools: {tool_names}")
            assert tool in tool_names, f"{tool} missing from {name}"

            result = await session.call_tool(tool, tool_args)
            payload = result.content[0].text if result.content else "<empty>"
            print(f"[{name}] {tool}({tool_args}) -> {payload[:160]}")
            assert not result.isError, f"{name}.{tool} returned error"
            return True


async def main() -> int:
    ok = True
    for name, (args, tool, tool_args) in SERVERS.items():
        print(f"[{name}] starting…", flush=True)
        try:
            await asyncio.wait_for(check_server(name, args, tool, tool_args), timeout=60)
            print(f"[{name}] PASS\n", flush=True)
        except asyncio.TimeoutError:
            ok = False
            print(f"[{name}] FAIL: timed out after 60s\n", flush=True)
        except Exception as e:  # noqa: BLE001
            ok = False
            print(f"[{name}] FAIL: {e!r}\n", flush=True)
    print("=== ALL PASS ===" if ok else "=== SOME FAILED ===", flush=True)
    return 0 if ok else 1


def test_mcp_servers():
    assert asyncio.run(main()) == 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

"""stdout guarding for MCP stdio servers.

CRITICAL: an MCP stdio server speaks JSON-RPC over stdout (fd 1). Any non-protocol
write to stdout corrupts the framing. We redirect Python-level stdout writes to
stderr around noisy third-party calls.

NOTE: we deliberately do NOT manipulate fd 1 with os.dup2 — fd 1 is a pipe to the
client, and dup2 on it breaks the protocol stream (BrokenResourceError). Only the
Python-level sys.stdout object is swapped, which leaves the pipe intact.
"""
from __future__ import annotations

import contextlib
import sys
from typing import Iterator


@contextlib.contextmanager
def quiet_stdout() -> Iterator[None]:
    """Redirect Python-level stdout writes (print/logging-to-stdout) to stderr.

    Utility for wrapping any future stdout-noisy library inside an MCP stdio
    server. (Not currently needed: yfinance was removed from the server path
    because curl_cffi corrupts the transport regardless of stdout — see macro.py.)
    """
    with contextlib.redirect_stdout(sys.stderr):
        yield

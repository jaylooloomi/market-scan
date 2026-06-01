"""PolyDig MCP sensor servers (Phase 1+).

Each sensor is an independent MCP server exposing detection/fetch tools.
Sensors do raw anomaly detection + data fetch only — semantic reasoning lives
in the Reviewer agent (Phase 2), never here.
"""

# Single-source the version from installed package metadata (pyproject) to avoid
# drift; fall back to a literal when running from an uninstalled source tree.
try:
    from importlib.metadata import version as _version

    __version__ = _version("polydig")
except Exception:
    __version__ = "0.1.0"

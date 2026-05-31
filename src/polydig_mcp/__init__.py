"""PolyDig MCP sensor servers (Phase 1+).

Each sensor is an independent MCP server exposing detection/fetch tools.
Sensors do raw anomaly detection + data fetch only — semantic reasoning lives
in the Reviewer agent (Phase 2), never here.
"""

__version__ = "0.1.0"

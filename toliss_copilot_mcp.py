#!/usr/bin/env python3
"""Compatibility entrypoint for the ToLiss A321 co-pilot MCP server."""

from toliss_copilot.server import mcp, run_server, smoke_test


if __name__ == "__main__":
    run_server()

#!/usr/bin/env python
"""MCP OriginPro Server — Entry Point.

Run with: uv run mcp dev server.py
Install to Claude Desktop with: uv run mcp install server.py
"""

from mcp_origin.server import main

if __name__ == "__main__":
    main()

#!/bin/sh
# Start MCP server on PORT (Lambda Web Adapter forwards traffic). :contentReference[oaicite:6]{index=6}
export PORT=${PORT:-8000}
python mcp_server.py

from __future__ import annotations

import os

import uvicorn

from dg_governance_mcp.server import mcp


def build_app():
    """Build the Streamable HTTP ASGI app with deployment-safe host validation.

    Uvicorn must bind to 0.0.0.0 inside Render, but MCP host validation must
    accept the public hostname, such as dg-governance-mcp.onrender.com. Mixing
    those two values causes 421 Invalid Host header. Ask me how we know.
    """
    public_host = os.getenv("DG_MCP_PUBLIC_HOST")

    if public_host:
        try:
            return mcp.streamable_http_app(host=public_host)
        except TypeError:
            pass

    return mcp.streamable_http_app()


app = build_app()


def main() -> None:
    bind_host = os.getenv("DG_MCP_BIND_HOST", os.getenv("DG_MCP_HOST", "0.0.0.0"))
    port = int(os.getenv("DG_MCP_PORT", os.getenv("PORT", "8000")))
    uvicorn.run(app, host=bind_host, port=port, log_level="info")


if __name__ == "__main__":
    main()

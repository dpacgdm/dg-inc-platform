FROM python:3.12-slim

WORKDIR /app

COPY mcp/dg-governance-mcp/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY mcp/dg-governance-mcp/dg_governance_mcp ./dg_governance_mcp
COPY governance ./governance

ENV DG_DATA_DIR=/app/governance
ENV DG_MCP_BIND_HOST=0.0.0.0
ENV DG_MCP_PUBLIC_HOST=dg-governance-mcp.onrender.com
ENV DG_MCP_TRANSPORT=streamable-http

EXPOSE 8000

CMD ["python", "-m", "dg_governance_mcp.http_server"]

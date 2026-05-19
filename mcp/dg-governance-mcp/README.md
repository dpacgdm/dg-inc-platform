# D&G Governance MCP

A working MCP server for D&G Inc platform governance.

This server provides governance tools for SRE workflows:

- service catalog lookup
- incident creation and status updates
- change request creation and approval simulation
- problem record creation
- postmortem generation
- runbook search
- platform risk checks
- deployment readiness review

The first version stores records as JSON/Markdown files under `governance/records/`. This is deliberate: it gives us auditable artifacts that are easy to review in GitHub, then later we can add Jira, Slack, ServiceNow, and Google Workspace adapters without changing the governance model.

## Why this matters

This is not a chatbot toy. It is an SRE control plane pattern:

1. Receive an operational request.
2. Validate required metadata.
3. Apply governance policy.
4. Create an auditable record.
5. Return clear next actions.

## Local setup

```bash
cd mcp/dg-governance-mcp
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m dg_governance_mcp.server
```

By default the server runs in Streamable HTTP mode on `127.0.0.1:8000`.

```bash
curl http://127.0.0.1:8000/health
```

## Environment variables

```bash
DG_DATA_DIR=../../governance
DG_MCP_HOST=127.0.0.1
DG_MCP_PORT=8000
DG_MCP_TRANSPORT=streamable-http
```

## ChatGPT custom MCP app

ChatGPT custom MCP apps require a remotely reachable HTTPS endpoint. For local testing, use this server locally with MCP Inspector. For ChatGPT Business developer mode, deploy this server to a remote HTTPS host, then register the MCP endpoint in the ChatGPT workspace app settings.

## Safety model

- Tools produce records, not destructive infra actions.
- Approvals are simulated in v0.1.
- Deployment rollback and CI triggers are intentionally not implemented until we add authentication and confirmation gates.

That is not cowardice. That is governance with a seatbelt.

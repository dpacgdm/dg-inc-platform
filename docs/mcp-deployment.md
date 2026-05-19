# Deploy D&G Governance MCP to Remote HTTPS

## Goal

Deploy the D&G Inc governance MCP server to a public HTTPS endpoint so it can be registered as a ChatGPT Business developer-mode custom MCP app.

## Current target

Use Render Free with Docker.

Why Render first:

- simple GitHub-based deployment
- automatic HTTPS endpoint
- Docker support
- free plan suitable for early validation

## Important limitation

Render Free filesystem is not a durable production database.

The current server writes records to the container filesystem under `governance/records/`. That is good for local development and short-lived smoke tests, but remote records can disappear after redeploy/restart.

For durable remote governance records, add one of these next:

1. GitHub-backed record store
2. SQLite on persistent disk if plan supports it
3. PostgreSQL
4. Object storage

The next best step for this portfolio is GitHub-backed records because governance artifacts should live in the repo.

## Files involved

```text
render.yaml
mcp/dg-governance-mcp/Dockerfile
mcp/dg-governance-mcp/dg_governance_mcp/server.py
```

## Deployment steps

### 1. Push latest changes

```bash
git pull
git push
```

### 2. Create Render service

In Render:

```text
New +
Blueprint
Connect GitHub repository: dpacgdm/dg-inc-platform
Use render.yaml
Create service
```

Expected service name:

```text
dg-governance-mcp
```

### 3. Confirm environment

Expected environment variables:

```text
DG_DATA_DIR=/app/governance
DG_MCP_HOST=0.0.0.0
DG_MCP_TRANSPORT=streamable-http
```

Do not set `DG_MCP_PORT` on Render unless needed. Render provides `PORT` automatically and the server reads it.

### 4. Verify health

After deploy, open:

```text
https://<render-service-url>/health
```

Expected:

```json
{"status":"ok","service":"dg-governance-mcp"}
```

CLI test:

```bash
curl -i https://<render-service-url>/health
```

### 5. Register in ChatGPT Business developer mode

In ChatGPT Business workspace settings:

```text
Workspace Settings
Apps
Create
Custom MCP app
```

Use:

```text
Name: D&G Inc Control Plane
Description: Governance MCP for D&G Inc platform operations, incident/change/problem records, deployment readiness and runbook search.
Endpoint: https://<render-service-url>/mcp
Authentication: none for first private test, then add auth before serious use
```

## First ChatGPT validation prompts

```text
List D&G Inc services using the D&G Inc Control Plane app.
```

```text
Create a SEV2 incident for checkout-service: synthetic checkout latency above SLO, no real customers impacted.
```

```text
Review production deployment readiness for checkout-service:v0.1.0 with tests and rollback ready but observability missing.
```

Expected behavior: production readiness should return `no-go` because observability is missing.

## Rollback

If deployment breaks:

1. Revert the bad commit.
2. Push to `main`.
3. Render redeploys from the reverted commit.

Manual rollback:

```bash
git log --oneline -5
git revert <bad-commit-sha>
git push
```

## Production hardening backlog

- Add authentication for remote MCP endpoint.
- Add GitHub-backed record store.
- Add request logging and correlation IDs.
- Add structured audit logs.
- Add rate limiting.
- Add read-only mode toggle.
- Add tool-level policy checks for external writes.
- Add GitHub issue/PR adapter.
- Add Slack/Jira/ServiceNow adapters later.

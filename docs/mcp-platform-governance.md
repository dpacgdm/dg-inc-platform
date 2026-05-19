# D&G Inc MCP Platform Governance Model

## Purpose

The D&G Inc governance MCP server is the control plane for production-style SRE work.

It gives ChatGPT and compatible MCP clients controlled tools for:

- service catalog lookup
- incident creation and updates
- change request creation
- deployment readiness review
- problem record creation
- postmortem skeleton generation
- runbook search

## Governance philosophy

The server is intentionally record-first.

Every operational action should leave an auditable artifact under `governance/records/`.

This mirrors real production process:

1. Define service ownership.
2. Create incident/change/problem records.
3. Validate risk and readiness.
4. Generate postmortems.
5. Improve runbooks and automation.

## MCP tools

### list_services

Lists all services from `governance/catalog/services.json`.

### get_service

Returns one service with tier, owner, critical-user-journey flag, SLIs, and dependencies.

### search_runbooks

Searches runbooks under `governance/runbooks/`.

### create_incident

Creates an incident JSON record.

Required fields:

- service
- severity
- summary
- customer_impact

### update_incident_status

Appends timeline/status updates to an existing incident.

### list_incidents

Lists incidents, optionally by status.

### create_change_request

Creates a change request and runs policy checks.

### create_problem_record

Creates a problem record linked to an incident.

### review_deployment_readiness

Evaluates deployment readiness, especially for production.

### generate_postmortem_skeleton

Generates a Markdown RCA skeleton from an incident.

## Safety boundaries

Current v0.1 does not trigger real deployments, rollbacks, cloud changes, or external writes.

That is intentional. Governance comes before power tools. A junior engineer with unaudited rollback access is not DevOps. That is a slot machine with root access.

## Next integrations

Future adapters can write to:

- GitHub Issues
- Slack
- Jira Service Management
- ServiceNow PDI
- Google Workspace or Outlook

The governance model should remain stable while adapters change.

# D&G Inc Platform

Production-grade SRE platform lab for D&G Inc.

This repository is the operating home for D&G Inc platform governance, incident/change/problem management, reliability automation, Kubernetes operations, observability, and interview-grade SRE artifacts.

## Current focus

The first deliverable is a working MCP-based platform governance control plane:

- `mcp/dg-governance-mcp/` - local and remote-capable MCP server using the official Python MCP SDK.
- `governance/` - service catalog, policy documents, templates, sample records, and runbooks.
- `.github/workflows/` - CI validation for MCP server and governance data.

## Operating principle

Every meaningful action should create an artifact: code, configuration, runbook, ticket, incident record, change record, postmortem, test result, or automation script.

No invisible learning. No certificate confetti. Build the machine.

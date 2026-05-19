#!/usr/bin/env python3
"""Smoke-test the D&G Inc governance MCP tools through a real MCP client session.

This script starts the governance MCP server over stdio, initializes an MCP
client session, discovers tools, and calls representative governance tools.

It intentionally creates local governance records under governance/records/.
That is the point: production-style operations should leave an audit trail.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


REQUIRED_TOOLS = {
    "list_services",
    "get_service",
    "search_runbooks",
    "create_incident",
    "update_incident_status",
    "list_incidents",
    "create_change_request",
    "create_problem_record",
    "review_deployment_readiness",
    "generate_postmortem_skeleton",
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def unwrap_tool_result(result: Any) -> Any:
    """Extract structured data from an MCP CallToolResult.

    Different SDK/spec revisions expose structured output slightly differently,
    so this parser uses a small compatibility ladder. Boring compatibility code
    saves lives and weekends.
    """
    for attr in ("structuredContent", "structured_content"):
        data = getattr(result, attr, None)
        if data:
            return data.get("result", data) if isinstance(data, dict) else data

    content = getattr(result, "content", None) or []
    if not content:
        return None

    first = content[0]
    text = getattr(first, "text", None)
    if text is None:
        return first

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict) and set(parsed.keys()) == {"result"}:
            return parsed["result"]
        return parsed
    except json.JSONDecodeError:
        return text


async def call(session: ClientSession, name: str, arguments: dict[str, Any]) -> Any:
    result = await session.call_tool(name, arguments=arguments)
    if getattr(result, "isError", False):
        raise RuntimeError(f"Tool {name} failed: {result}")
    return unwrap_tool_result(result)


async def main() -> int:
    root = repo_root()
    data_dir = root / "governance"
    server_env = {
        **os.environ,
        "DG_DATA_DIR": str(data_dir),
        "DG_MCP_TRANSPORT": "stdio",
    }

    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "dg_governance_mcp.server"],
        env=server_env,
    )

    print("[smoke] starting governance MCP server over stdio")
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("[smoke] MCP session initialized")

            tools_response = await session.list_tools()
            discovered = {tool.name for tool in tools_response.tools}
            missing = REQUIRED_TOOLS - discovered
            if missing:
                raise AssertionError(f"Missing required tools: {sorted(missing)}")
            print(f"[smoke] discovered {len(discovered)} tools")

            services = await call(session, "list_services", {})
            if not isinstance(services, list) or not services:
                raise AssertionError("list_services returned no services")
            print(f"[smoke] service catalog contains {len(services)} services")

            incident = await call(
                session,
                "create_incident",
                {
                    "service": "checkout-service",
                    "severity": "SEV2",
                    "summary": "Checkout latency above SLO during synthetic validation",
                    "customer_impact": "Synthetic users observe slow checkout responses; no real customers impacted.",
                    "symptoms": [
                        "p95 checkout latency above 2 seconds",
                        "synthetic transaction duration breached warning threshold",
                    ],
                    "detected_by": "dg-governance-smoke-test",
                },
            )
            incident_id = incident["record"]["id"]
            print(f"[smoke] created incident {incident_id}")

            updated_incident = await call(
                session,
                "update_incident_status",
                {
                    "incident_id": incident_id,
                    "status": "identified",
                    "update": "Synthetic smoke test identified simulated checkout latency as planned scenario.",
                    "next_actions": ["Generate postmortem skeleton", "Create problem record if recurrence is observed"],
                },
            )
            if updated_incident["record"]["status"] != "identified":
                raise AssertionError("Incident status update did not persist")
            print(f"[smoke] updated incident {incident_id} status")

            change = await call(
                session,
                "create_change_request",
                {
                    "service": "checkout-service",
                    "title": "Deploy checkout-service v0.1.0 to staging",
                    "risk": "medium",
                    "reason": "Validate governance flow and deployment-readiness policy.",
                    "implementation_plan": [
                        "Build image checkout-service:v0.1.0",
                        "Deploy to staging namespace",
                        "Watch rollout until all replicas are available",
                    ],
                    "validation_plan": [
                        "Run synthetic checkout request",
                        "Verify p95 latency and error-rate dashboards",
                        "Check application logs for exceptions",
                    ],
                    "rollback_plan": [
                        "Rollback deployment to previous ReplicaSet",
                        "Validate checkout health endpoint and synthetic transaction",
                    ],
                    "planned_window_utc": "2026-05-19T18:00:00Z",
                },
            )
            change_id = change["record"]["id"]
            print(f"[smoke] created change {change_id}")

            review = await call(
                session,
                "review_deployment_readiness",
                {
                    "service": "checkout-service",
                    "image_tag": "checkout-service:v0.1.0",
                    "environment": "prod",
                    "change_id": change_id,
                    "checks": {
                        "tests_passed": True,
                        "rollback_verified": True,
                        "observability_ready": False,
                        "change_record_exists": True,
                    },
                },
            )
            if review["decision"] != "no-go":
                raise AssertionError("Production readiness should be no-go when observability is missing")
            print("[smoke] deployment readiness correctly returned no-go")

            problem = await call(
                session,
                "create_problem_record",
                {
                    "related_incident_id": incident_id,
                    "service": "checkout-service",
                    "problem_statement": "Synthetic checkout latency scenario needs prevention and detection improvements.",
                    "suspected_causes": ["simulated dependency latency", "missing dashboard readiness gate"],
                },
            )
            print(f"[smoke] created problem {problem['record']['id']}")

            postmortem = await call(
                session,
                "generate_postmortem_skeleton",
                {"incident_id": incident_id},
            )
            if "Executive summary" not in postmortem["content"]:
                raise AssertionError("Postmortem skeleton does not look valid")
            print(f"[smoke] generated postmortem at {postmortem['path']}")

            print("[smoke] governance MCP smoke test passed")
            return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from dg_governance_mcp.models import (
    ChangeCreateRequest,
    ChangeRecord,
    DeploymentReview,
    IncidentCreateRequest,
    IncidentRecord,
    IncidentStatus,
    IncidentUpdateRequest,
    ProblemCreateRequest,
    ProblemRecord,
)
from dg_governance_mcp.policy import evaluate_change_policy, evaluate_deployment_review
from dg_governance_mcp.store import GovernanceStore

PROTOCOL_VERSION = "2025-03-26"
SERVER_INFO = {"name": "dg-governance-mcp", "version": "0.2.0"}


def _default_data_dir() -> Path:
    explicit = os.getenv("DG_DATA_DIR")
    if explicit:
        return Path(explicit).resolve()
    current = Path(__file__).resolve()
    candidates = [
        current.parents[1] / "governance",
        current.parents[3] / "governance" if len(current.parents) > 3 else None,
        Path.cwd() / "governance",
    ]
    for candidate in candidates:
        if candidate and candidate.exists():
            return candidate.resolve()
    return (Path.cwd() / "governance").resolve()


DATA_DIR = _default_data_dir()
store = GovernanceStore(DATA_DIR)


def _jsonrpc_result(request_id: Any, result: Any) -> JSONResponse:
    return JSONResponse({"jsonrpc": "2.0", "id": request_id, "result": result})


def _jsonrpc_error(request_id: Any, code: int, message: str, data: Any | None = None) -> JSONResponse:
    payload: dict[str, Any] = {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }
    if data is not None:
        payload["error"]["data"] = data
    return JSONResponse(payload, status_code=200)


def _tool_schema(name: str, description: str, properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "inputSchema": {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        },
    }


def _tools() -> list[dict[str, Any]]:
    string = {"type": "string"}
    string_array = {"type": "array", "items": {"type": "string"}}
    bool_map = {"type": "object", "additionalProperties": {"type": "boolean"}}

    return [
        _tool_schema("server_info", "Return server runtime information.", {}, []),
        _tool_schema("list_services", "List D&G Inc service catalog entries.", {}, []),
        _tool_schema("get_service", "Get one service from the service catalog.", {"service_name": string}, ["service_name"]),
        _tool_schema("search_runbooks", "Search local runbooks by keyword.", {"query": string}, ["query"]),
        _tool_schema(
            "create_incident",
            "Create an incident record.",
            {
                "service": string,
                "severity": {"type": "string", "enum": ["SEV1", "SEV2", "SEV3", "SEV4"]},
                "summary": string,
                "customer_impact": string,
                "symptoms": string_array,
                "detected_by": string,
            },
            ["service", "severity", "summary", "customer_impact"],
        ),
        _tool_schema(
            "update_incident_status",
            "Update incident status and timeline.",
            {
                "incident_id": string,
                "status": {"type": "string", "enum": ["investigating", "identified", "monitoring", "resolved"]},
                "update": string,
                "next_actions": string_array,
            },
            ["incident_id", "status", "update"],
        ),
        _tool_schema("list_incidents", "List incident records.", {"status": string}, []),
        _tool_schema(
            "create_change_request",
            "Create a change request and run policy checks.",
            {
                "service": string,
                "title": string,
                "risk": {"type": "string", "enum": ["low", "medium", "high", "critical"]},
                "reason": string,
                "implementation_plan": string_array,
                "validation_plan": string_array,
                "rollback_plan": string_array,
                "planned_window_utc": string,
            },
            ["service", "title", "risk", "reason", "implementation_plan", "validation_plan", "rollback_plan", "planned_window_utc"],
        ),
        _tool_schema(
            "create_problem_record",
            "Create a problem record linked to an incident.",
            {
                "related_incident_id": string,
                "service": string,
                "problem_statement": string,
                "suspected_causes": string_array,
            },
            ["related_incident_id", "service", "problem_statement"],
        ),
        _tool_schema(
            "review_deployment_readiness",
            "Review deployment readiness for an environment.",
            {
                "service": string,
                "image_tag": string,
                "environment": {"type": "string", "enum": ["dev", "staging", "prod"]},
                "checks": bool_map,
                "change_id": string,
            },
            ["service", "image_tag", "environment", "checks"],
        ),
        _tool_schema("generate_postmortem_skeleton", "Generate an RCA skeleton from an incident.", {"incident_id": string}, ["incident_id"]),
    ]


def _record_uri(record_type: str, record_id: str) -> str:
    return f"governance://records/{record_type}/{record_id}"


def _call_tool(name: str, args: dict[str, Any]) -> Any:
    if name == "server_info":
        return {"name": SERVER_INFO["name"], "version": SERVER_INFO["version"], "data_dir": str(DATA_DIR), "tools": len(_tools())}

    if name == "list_services":
        return [service.model_dump(mode="json") for service in store.list_services()]

    if name == "get_service":
        service = store.get_service(args["service_name"])
        if service is None:
            return {"found": False, "message": f"Service not found: {args['service_name']}"}
        return {"found": True, "service": service.model_dump(mode="json")}

    if name == "search_runbooks":
        return store.search_runbooks(args["query"])

    if name == "create_incident":
        request = IncidentCreateRequest.model_validate({**args, "symptoms": args.get("symptoms", []), "detected_by": args.get("detected_by", "manual")})
        record = IncidentRecord(
            service=request.service,
            severity=request.severity,
            summary=request.summary,
            symptoms=request.symptoms,
            customer_impact=request.customer_impact,
            detected_by=request.detected_by,
            timeline=["Incident created. Initial triage required."],
            next_actions=[
                "Assign incident commander.",
                "Confirm customer impact and blast radius.",
                "Check service dashboard, logs, saturation, recent deploys, and dependencies.",
            ],
        )
        path = store.write_incident(record)
        return {"record_uri": _record_uri("incidents", record.id), "path": str(path), "record": record.model_dump(mode="json")}

    if name == "update_incident_status":
        request = IncidentUpdateRequest.model_validate({**args, "next_actions": args.get("next_actions", [])})
        current = store.read_record("incidents", request.incident_id)
        timeline = list(current.get("timeline", []))
        timeline.append(f"{request.status.value}: {request.update}")
        record = store.update_incident(request.incident_id, {"status": request.status, "timeline": timeline, "next_actions": request.next_actions})
        return {"record_uri": _record_uri("incidents", record.id), "record": record.model_dump(mode="json")}

    if name == "list_incidents":
        records = store.list_records("incidents")
        status = args.get("status")
        if status:
            wanted = IncidentStatus(status)
            records = [record for record in records if record.get("status") == wanted.value]
        return records

    if name == "create_change_request":
        request = ChangeCreateRequest.model_validate(args)
        findings = evaluate_change_policy(request, store)
        record = ChangeRecord(**request.model_dump(mode="json"), policy_findings=findings)
        path = store.write_change(record)
        return {"record_uri": _record_uri("changes", record.id), "path": str(path), "approval_required": bool(findings), "policy_findings": findings, "record": record.model_dump(mode="json")}

    if name == "create_problem_record":
        request = ProblemCreateRequest.model_validate({**args, "suspected_causes": args.get("suspected_causes", [])})
        record = ProblemRecord(**request.model_dump(mode="json"))
        path = store.write_problem(record)
        return {"record_uri": _record_uri("problems", record.id), "path": str(path), "record": record.model_dump(mode="json")}

    if name == "review_deployment_readiness":
        request_data = {**args, "change_id": args.get("change_id")}
        from dg_governance_mcp.models import DeploymentReviewRequest

        request = DeploymentReviewRequest.model_validate(request_data)
        decision, findings, required_actions = evaluate_deployment_review(request, store)
        review = DeploymentReview(service=request.service, environment=request.environment, decision=decision, findings=findings, required_actions=required_actions)
        return review.model_dump(mode="json")

    if name == "generate_postmortem_skeleton":
        incident = store.read_record("incidents", args["incident_id"])
        lines = [
            f"# RCA-{args['incident_id']}: {incident['summary']}",
            "",
            "## Executive summary",
            "TBD",
            "",
            "## Impact",
            incident.get("customer_impact", "TBD"),
            "",
            "## Timeline",
            *[f"- {entry}" for entry in incident.get("timeline", [])],
            "",
            "## Root cause",
            "TBD",
            "",
            "## Action items",
            "- [ ] Add prevention action with owner and due date.",
            "- [ ] Add detection improvement with owner and due date.",
        ]
        target = store.data_dir / "records" / "postmortems"
        target.mkdir(parents=True, exist_ok=True)
        path = target / f"RCA-{args['incident_id']}.md"
        content = "\n".join(lines) + "\n"
        path.write_text(content, encoding="utf-8")
        return {"path": str(path), "content": content}

    raise ValueError(f"Unknown tool: {name}")


async def health(_: Request) -> Response:
    return JSONResponse({"status": "ok", "service": "dg-governance-mcp", "mode": "adapter"})


async def mcp_endpoint(request: Request) -> Response:
    if request.method == "GET":
        return JSONResponse({"status": "ok", "service": "dg-governance-mcp", "mcp_path": "/mcp"})

    try:
        payload = await request.json()
    except json.JSONDecodeError:
        return _jsonrpc_error(None, -32700, "Parse error")

    request_id = payload.get("id")
    method = payload.get("method")
    params = payload.get("params") or {}

    if method == "initialize":
        return _jsonrpc_result(
            request_id,
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": SERVER_INFO,
            },
        )

    if method == "notifications/initialized":
        return Response(status_code=202)

    if method == "tools/list":
        return _jsonrpc_result(request_id, {"tools": _tools()})

    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments") or {}
        try:
            result = _call_tool(name, arguments)
            return _jsonrpc_result(request_id, {"content": [{"type": "text", "text": json.dumps(result)}], "isError": False})
        except Exception as exc:
            return _jsonrpc_result(request_id, {"content": [{"type": "text", "text": str(exc)}], "isError": True})

    return _jsonrpc_error(request_id, -32601, f"Method not found: {method}")


app = Starlette(
    debug=False,
    routes=[
        Route("/health", health, methods=["GET", "HEAD"]),
        Route("/mcp", mcp_endpoint, methods=["GET", "POST"]),
        Route("/mcp/", mcp_endpoint, methods=["GET", "POST"]),
    ],
)


def main() -> None:
    host = os.getenv("DG_MCP_BIND_HOST", os.getenv("DG_MCP_HOST", "0.0.0.0"))
    port = int(os.getenv("DG_MCP_PORT", os.getenv("PORT", "8000")))
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()

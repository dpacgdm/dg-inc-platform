from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from dg_governance_mcp.models import (
    ChangeCreateRequest,
    ChangeRecord,
    DeploymentReview,
    DeploymentReviewRequest,
    IncidentCreateRequest,
    IncidentRecord,
    IncidentStatus,
    IncidentUpdateRequest,
    ProblemCreateRequest,
    ProblemRecord,
)
from dg_governance_mcp.policy import evaluate_change_policy, evaluate_deployment_review
from dg_governance_mcp.store import GovernanceStore


def _create_mcp() -> FastMCP:
    """Create FastMCP with production HTTP settings when supported."""
    try:
        return FastMCP(
            "D&G Inc Platform Governance",
            stateless_http=True,
            json_response=True,
            streamable_http_path="/mcp",
        )
    except TypeError:
        server = FastMCP("D&G Inc Platform Governance")
        settings = getattr(server, "settings", None)
        if settings is not None:
            for key, value in {
                "stateless_http": True,
                "json_response": True,
                "streamable_http_path": "/mcp",
            }.items():
                if hasattr(settings, key):
                    setattr(settings, key, value)
        return server


def _default_data_dir() -> Path:
    """Return a data directory that works in both repo and container layouts.

    Local repo layout:
      <repo>/mcp/dg-governance-mcp/dg_governance_mcp/server.py
      <repo>/governance

    Docker layout:
      /app/dg_governance_mcp/server.py
      /app/governance
    """
    explicit = os.getenv("DG_DATA_DIR")
    if explicit:
        return Path(explicit).resolve()

    current = Path(__file__).resolve()
    candidates = [
        current.parents[1] / "governance",  # Docker: /app/governance
        current.parents[3] / "governance" if len(current.parents) > 3 else None,  # repo layout
        Path.cwd() / "governance",
    ]
    for candidate in candidates:
        if candidate and candidate.exists():
            return candidate.resolve()

    return (Path.cwd() / "governance").resolve()


DATA_DIR = _default_data_dir()

mcp = _create_mcp()
store = GovernanceStore(DATA_DIR)


def _record_uri(record_type: str, record_id: str) -> str:
    return f"governance://records/{record_type}/{record_id}"


@mcp.tool()
def list_services() -> list[dict[str, Any]]:
    """List D&G Inc services from the governance service catalog."""
    return [service.model_dump(mode="json") for service in store.list_services()]


@mcp.tool()
def get_service(service_name: str) -> dict[str, Any]:
    """Return governance metadata for one service."""
    service = store.get_service(service_name)
    if service is None:
        return {"found": False, "message": f"Service not found: {service_name}"}
    return {"found": True, "service": service.model_dump(mode="json")}


@mcp.tool()
def search_runbooks(query: str) -> list[dict[str, str]]:
    """Search local SRE runbooks by keyword."""
    return store.search_runbooks(query)


@mcp.tool()
def create_incident(
    service: str,
    severity: str,
    summary: str,
    customer_impact: str,
    symptoms: list[str] | None = None,
    detected_by: str = "manual",
) -> dict[str, Any]:
    """Create an incident record and return operational next steps."""
    request = IncidentCreateRequest.model_validate(
        {
            "service": service,
            "severity": severity,
            "summary": summary,
            "customer_impact": customer_impact,
            "symptoms": symptoms or [],
            "detected_by": detected_by,
        }
    )
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
            "Post first stakeholder update within 10 minutes for SEV1/SEV2.",
        ],
    )
    path = store.write_incident(record)
    return {
        "record_uri": _record_uri("incidents", record.id),
        "path": str(path),
        "record": record.model_dump(mode="json"),
    }


@mcp.tool()
def update_incident_status(
    incident_id: str,
    status: str,
    update: str,
    next_actions: list[str] | None = None,
) -> dict[str, Any]:
    """Append a status update to an existing incident."""
    request = IncidentUpdateRequest.model_validate(
        {
            "incident_id": incident_id,
            "status": status,
            "update": update,
            "next_actions": next_actions or [],
        }
    )
    current = store.read_record("incidents", request.incident_id)
    timeline = list(current.get("timeline", []))
    timeline.append(f"{request.status.value}: {request.update}")
    record = store.update_incident(
        request.incident_id,
        {
            "status": request.status,
            "timeline": timeline,
            "next_actions": request.next_actions,
        },
    )
    return {
        "record_uri": _record_uri("incidents", record.id),
        "record": record.model_dump(mode="json"),
    }


@mcp.tool()
def list_incidents(status: str | None = None) -> list[dict[str, Any]]:
    """List incident records, optionally filtering by status."""
    records = store.list_records("incidents")
    if status:
        wanted = IncidentStatus(status)
        records = [record for record in records if record.get("status") == wanted.value]
    return records


@mcp.tool()
def create_change_request(
    service: str,
    title: str,
    risk: str,
    reason: str,
    implementation_plan: list[str],
    validation_plan: list[str],
    rollback_plan: list[str],
    planned_window_utc: str,
) -> dict[str, Any]:
    """Create a change request and run policy checks."""
    request = ChangeCreateRequest.model_validate(
        {
            "service": service,
            "title": title,
            "risk": risk,
            "reason": reason,
            "implementation_plan": implementation_plan,
            "validation_plan": validation_plan,
            "rollback_plan": rollback_plan,
            "planned_window_utc": planned_window_utc,
        }
    )
    findings = evaluate_change_policy(request, store)
    record = ChangeRecord(**request.model_dump(mode="json"), policy_findings=findings)
    path = store.write_change(record)
    return {
        "record_uri": _record_uri("changes", record.id),
        "path": str(path),
        "approval_required": bool(findings),
        "policy_findings": findings,
        "record": record.model_dump(mode="json"),
    }


@mcp.tool()
def create_problem_record(
    related_incident_id: str,
    service: str,
    problem_statement: str,
    suspected_causes: list[str] | None = None,
) -> dict[str, Any]:
    """Create a problem record after an incident or recurring defect."""
    request = ProblemCreateRequest.model_validate(
        {
            "related_incident_id": related_incident_id,
            "service": service,
            "problem_statement": problem_statement,
            "suspected_causes": suspected_causes or [],
        }
    )
    record = ProblemRecord(**request.model_dump(mode="json"))
    path = store.write_problem(record)
    return {
        "record_uri": _record_uri("problems", record.id),
        "path": str(path),
        "record": record.model_dump(mode="json"),
    }


@mcp.tool()
def review_deployment_readiness(
    service: str,
    image_tag: str,
    environment: str,
    checks: dict[str, bool],
    change_id: str | None = None,
) -> dict[str, Any]:
    """Review whether a deployment is ready for an environment, especially production."""
    request = DeploymentReviewRequest.model_validate(
        {
            "service": service,
            "image_tag": image_tag,
            "environment": environment,
            "checks": checks,
            "change_id": change_id,
        }
    )
    decision, findings, required_actions = evaluate_deployment_review(request, store)
    review = DeploymentReview(
        service=request.service,
        environment=request.environment,
        decision=decision,
        findings=findings,
        required_actions=required_actions,
    )
    return review.model_dump(mode="json")


@mcp.tool()
def generate_postmortem_skeleton(incident_id: str) -> dict[str, str]:
    """Generate a postmortem skeleton from an incident record."""
    incident = store.read_record("incidents", incident_id)
    lines = [
        f"# RCA-{incident_id}: {incident['summary']}",
        "",
        "## Executive summary",
        "TBD",
        "",
        "## Impact",
        incident.get("customer_impact", "TBD"),
        "",
        "## Severity",
        incident.get("severity", "TBD"),
        "",
        "## Timeline",
        *[f"- {entry}" for entry in incident.get("timeline", [])],
        "",
        "## Root cause",
        "TBD",
        "",
        "## Trigger",
        "TBD",
        "",
        "## Detection",
        incident.get("detected_by", "TBD"),
        "",
        "## What went well",
        "- TBD",
        "",
        "## What went poorly",
        "- TBD",
        "",
        "## Action items",
        "- [ ] Add one prevention action with owner and due date.",
        "- [ ] Add one detection improvement with owner and due date.",
        "- [ ] Add one runbook or automation improvement with owner and due date.",
    ]
    target = store.data_dir / "records" / "postmortems"
    target.mkdir(parents=True, exist_ok=True)
    path = target / f"RCA-{incident_id}.md"
    content = "\n".join(lines) + "\n"
    path.write_text(content, encoding="utf-8")
    return {"path": str(path), "content": content}


@mcp.tool()
def server_info() -> dict[str, Any]:
    """Return MCP server runtime and transport configuration."""
    settings = getattr(mcp, "settings", None)
    return {
        "name": "D&G Inc Platform Governance",
        "data_dir": str(DATA_DIR),
        "tools_expected": 11,
        "streamable_http_path": getattr(settings, "streamable_http_path", None),
        "stateless_http": getattr(settings, "stateless_http", None),
        "json_response": getattr(settings, "json_response", None),
    }


@mcp.custom_route("/health", methods=["GET"])
async def health(_: Request) -> Response:
    return JSONResponse({"status": "ok", "service": "dg-governance-mcp"})


def _run_streamable_http(host: str, port: int) -> None:
    """Run Streamable HTTP across multiple MCP SDK versions."""
    try:
        mcp.run(transport="streamable-http", host=host, port=port)
        return
    except TypeError as exc:
        if "unexpected keyword argument" not in str(exc):
            raise

    import uvicorn

    app = mcp.streamable_http_app()
    uvicorn.run(app, host=host, port=port, log_level="info")


def main() -> None:
    transport = os.getenv("DG_MCP_TRANSPORT", "streamable-http")
    host = os.getenv("DG_MCP_HOST", "127.0.0.1")
    port = int(os.getenv("DG_MCP_PORT", os.getenv("PORT", "8000")))

    if transport == "streamable-http":
        _run_streamable_http(host=host, port=port)
    elif transport == "stdio":
        mcp.run(transport="stdio")
    else:
        raise ValueError(f"Unsupported transport for D&G governance server: {transport}")


if __name__ == "__main__":
    main()

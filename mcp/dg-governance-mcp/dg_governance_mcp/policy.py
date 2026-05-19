from __future__ import annotations

from dg_governance_mcp.models import ChangeCreateRequest, ChangeRisk, DeploymentReviewRequest
from dg_governance_mcp.store import GovernanceStore


REQUIRED_PROD_CHECKS = {
    "tests_passed": "Automated tests must pass before production deployment.",
    "rollback_verified": "Rollback procedure must be documented and verified.",
    "observability_ready": "Dashboards and alerts must exist before production deployment.",
    "change_record_exists": "Production deployments require a change record.",
}


def evaluate_change_policy(change: ChangeCreateRequest, store: GovernanceStore) -> list[str]:
    findings: list[str] = []
    service = store.get_service(change.service)

    if service is None:
        findings.append(f"Unknown service '{change.service}'. Add it to the service catalog first.")
        return findings

    if service.tier in {"tier-0", "tier-1"} and change.risk in {ChangeRisk.high, ChangeRisk.critical}:
        findings.append("High/critical risk change on tier-0/tier-1 service requires explicit approval.")

    if service.critical_user_journey and change.risk != ChangeRisk.low:
        findings.append("Critical user journey change requires customer-impact validation and rollback rehearsal.")

    if len(change.rollback_plan) < 2:
        findings.append("Rollback plan is too thin. A production rollback needs decision criteria and exact commands.")

    if len(change.validation_plan) < 2:
        findings.append("Validation plan is too thin. Include service health, metrics, logs, and user-journey checks.")

    return findings


def evaluate_deployment_review(request: DeploymentReviewRequest, store: GovernanceStore) -> tuple[str, list[str], list[str]]:
    findings: list[str] = []
    required_actions: list[str] = []

    service = store.get_service(request.service)
    if service is None:
        findings.append(f"Unknown service '{request.service}'.")
        required_actions.append("Add service to governance/catalog/services.json.")

    if request.environment == "prod":
        for check, message in REQUIRED_PROD_CHECKS.items():
            if not request.checks.get(check, False):
                findings.append(message)
                required_actions.append(f"Complete prod readiness check: {check}.")

        if not request.change_id:
            findings.append("Production deployment does not reference a change record.")
            required_actions.append("Create or attach a change record before production deployment.")

    decision = "go" if not required_actions else "no-go"
    return decision, findings, required_actions

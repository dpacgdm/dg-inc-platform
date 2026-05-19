from dg_governance_mcp.models import ChangeCreateRequest, DeploymentReviewRequest
from dg_governance_mcp.policy import evaluate_change_policy, evaluate_deployment_review
from dg_governance_mcp.store import GovernanceStore


def test_high_risk_tier_zero_change_requires_approval(tmp_path):
    catalog = tmp_path / "catalog"
    catalog.mkdir()
    (catalog / "services.json").write_text(
        '[{"name":"checkout-service","tier":"tier-0","owner":"sre","critical_user_journey":true,"sli":[],"dependencies":[]}]',
        encoding="utf-8",
    )
    store = GovernanceStore(tmp_path)
    change = ChangeCreateRequest(
        service="checkout-service",
        title="Deploy checkout v2",
        risk="high",
        reason="release",
        implementation_plan=["deploy image"],
        validation_plan=["check /health"],
        rollback_plan=["rollback"],
        planned_window_utc="2026-05-19T18:00:00Z",
    )

    findings = evaluate_change_policy(change, store)

    assert any("requires explicit approval" in finding for finding in findings)
    assert any("Rollback plan is too thin" in finding for finding in findings)


def test_prod_deployment_without_checks_is_no_go(tmp_path):
    catalog = tmp_path / "catalog"
    catalog.mkdir()
    (catalog / "services.json").write_text(
        '[{"name":"payment-gateway-sim","tier":"tier-0","owner":"sre","critical_user_journey":true,"sli":[],"dependencies":[]}]',
        encoding="utf-8",
    )
    store = GovernanceStore(tmp_path)
    request = DeploymentReviewRequest(
        service="payment-gateway-sim",
        image_tag="v1.2.3",
        environment="prod",
        checks={"tests_passed": True},
    )

    decision, findings, required_actions = evaluate_deployment_review(request, store)

    assert decision == "no-go"
    assert findings
    assert required_actions


def test_staging_deployment_is_go_with_known_service(tmp_path):
    catalog = tmp_path / "catalog"
    catalog.mkdir()
    (catalog / "services.json").write_text(
        '[{"name":"catalog-service","tier":"tier-1","owner":"sre","critical_user_journey":true,"sli":[],"dependencies":[]}]',
        encoding="utf-8",
    )
    store = GovernanceStore(tmp_path)
    request = DeploymentReviewRequest(
        service="catalog-service",
        image_tag="v0.1.0",
        environment="staging",
        checks={},
    )

    decision, findings, required_actions = evaluate_deployment_review(request, store)

    assert decision == "go"
    assert findings == []
    assert required_actions == []

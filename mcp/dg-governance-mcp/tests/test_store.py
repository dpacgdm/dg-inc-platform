from dg_governance_mcp.models import IncidentRecord
from dg_governance_mcp.store import GovernanceStore


def test_write_and_read_incident(tmp_path):
    store = GovernanceStore(tmp_path)
    incident = IncidentRecord(
        service="checkout-service",
        severity="SEV2",
        summary="Checkout latency above SLO",
        symptoms=["p95 latency > 2s"],
        customer_impact="Some customers see slow checkout",
        detected_by="synthetic-monitor",
    )

    store.write_incident(incident)
    loaded = store.read_record("incidents", incident.id)

    assert loaded["service"] == "checkout-service"
    assert loaded["severity"] == "SEV2"


def test_search_runbooks(tmp_path):
    runbooks = tmp_path / "runbooks"
    runbooks.mkdir()
    (runbooks / "disk-full.md").write_text("# Disk Full\nUse df -h and du -sh.", encoding="utf-8")
    store = GovernanceStore(tmp_path)

    results = store.search_runbooks("disk")

    assert len(results) == 1
    assert results[0]["path"] == "runbooks/disk-full.md"

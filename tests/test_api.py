"""API integration tests for AEGIS NEXUS FastAPI portal."""

from fastapi.testclient import TestClient
from backend.app.main import app


client = TestClient(app)


def test_health_and_portal_root():
    res = client.get("/api/health")
    assert res.status_code == 200
    body = res.json()
    assert body["institutions_core"] == 23
    assert body["mode"] == "simulation"

    html = client.get("/")
    assert html.status_code == 200
    assert "AEGIS NEXUS" in html.text
    assert "SIMULATION-BASED PROTOTYPE" in html.text


def test_end_to_end_hospital_demo_and_workflow():
    # 1. Trigger Section 12 demo scenario
    demo_res = client.post("/api/demo/scenario/hospital-failure")
    assert demo_res.status_code == 200
    dash = demo_res.json()

    assert dash["kpis"]["institutions_monitored"] == 23
    assert dash["kpis"]["critical_alerts"] >= 1
    top_alert = dash["alerts"][0]
    assert top_alert["institution"]["institution_id"] == "HOSP-01"
    assert top_alert["level"] == "Critical"
    assert top_alert["playbook"]["triggered"] is True
    assert top_alert["cause_probabilities"] is not None

    # 2. Official acknowledges and restores
    ack_res = client.post(
        "/api/alerts/ALT-HOSP-01/workflow",
        json={"status": "Acknowledged", "official_name": "District Nodal Officer", "notes": "Playbook active"},
    )
    assert ack_res.status_code == 200
    assert ack_res.json()["dashboard"]["kpis"]["incidents_investigated"] >= 1

    rest_res = client.post(
        "/api/alerts/ALT-HOSP-01/workflow",
        json={"status": "Restored", "official_name": "District Nodal Officer", "notes": "Service stabilized"},
    )
    assert rest_res.status_code == 200

    # Reset back to baseline for clean state
    reset_res = client.post("/api/demo/reset")
    assert reset_res.status_code == 200


def test_governance_and_evaluation_endpoints():
    gov = client.get("/api/governance")
    assert gov.status_code == 200
    assert "CERT-In" in " ".join(gov.json()["positioning"]["existing_national_systems"])

    ev = client.get("/api/evaluation")
    assert ev.status_code == 200
    assert "detection" in ev.json()

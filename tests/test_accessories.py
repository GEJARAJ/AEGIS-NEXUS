"""Unit and API tests for the modular Synthetic Fault-Injector Accessory."""

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.nexa_engine import DriftSentinel, TelemetrySimulator
from backend.nexa_engine.accessories import (
    CampaignTarget,
    FaultCampaignRequest,
    SyntheticFaultInjectorAccessory,
)
from backend.nexa_engine.models import CauseCategory, FaultType


client = TestClient(app)


def test_accessory_deterministic_seeded_campaigns():
    sim_a = TelemetrySimulator(seed=42, history_ticks=30)
    sim_b = TelemetrySimulator(seed=42, history_ticks=30)
    acc_a = SyntheticFaultInjectorAccessory()
    acc_b = SyntheticFaultInjectorAccessory()

    req = FaultCampaignRequest(
        preset_id="coord_pds_auth_storm",
        duration_ticks=4,
        seed=1042,
        reset_before_run=True,
        step_immediately=2,
    )
    rec_a = acc_a.launch_campaign(sim_a, req)
    rec_b = acc_b.launch_campaign(sim_b, req)

    assert rec_a.ground_truth == rec_b.ground_truth
    assert sim_a.series["PDS-01"][-1] == sim_b.series["PDS-01"][-1]
    assert sim_a.series["PDS-03"][-1] == sim_b.series["PDS-03"][-1]
    assert sim_a.series["PDS-08"][-1] == sim_b.series["PDS-08"][-1]


def test_multi_target_time_bounded_expiry_and_staggered_offsets():
    sim = TelemetrySimulator(seed=42, history_ticks=30)
    acc = SyntheticFaultInjectorAccessory()

    req = FaultCampaignRequest(
        name="Staggered Resilience Drill",
        targets=[
            CampaignTarget(institution_id="HOSP-01", fault_type=FaultType.REQUEST_SPIKE, intensity=1.2, start_offset_ticks=0),
            CampaignTarget(institution_id="PDS-05", fault_type=FaultType.LINK_DROP, intensity=1.1, start_offset_ticks=1),
        ],
        duration_ticks=3,
        seed=777,
        step_immediately=0,
    )
    record = acc.launch_campaign(sim, req)
    assert len(record.ground_truth) == 2
    assert acc.status().active is True

    # Tick 1 (tick 31): HOSP-01 active, PDS-05 not started yet
    acc.step_with_simulator(sim, 1)
    assert sim.series["HOSP-01"][-1].injected_fault == FaultType.REQUEST_SPIKE
    assert sim.series["PDS-05"][-1].injected_fault == FaultType.NONE

    # Ticks 2 & 3 (ticks 32, 33): both active
    acc.step_with_simulator(sim, 2)
    assert sim.series["HOSP-01"][-1].injected_fault == FaultType.REQUEST_SPIKE
    assert sim.series["PDS-05"][-1].injected_fault == FaultType.LINK_DROP

    # Tick 4 (tick 34): HOSP-01 auto-expired, PDS-05 on its 3rd and final tick
    acc.step_with_simulator(sim, 1)
    assert sim.series["HOSP-01"][-1].injected_fault == FaultType.NONE
    assert sim.series["PDS-05"][-1].injected_fault == FaultType.LINK_DROP

    # Tick 5 (tick 35): both auto-expired and accessory is idle
    acc.step_with_simulator(sim, 1)
    assert sim.series["HOSP-01"][-1].injected_fault == FaultType.NONE
    assert sim.series["PDS-05"][-1].injected_fault == FaultType.NONE
    assert acc.status().active is False


def test_coordinated_preset_ground_truth_and_drift_detection():
    sim = TelemetrySimulator(seed=42, history_ticks=35)
    acc = SyntheticFaultInjectorAccessory()
    sentinel = DriftSentinel(baseline_window=30)

    record = acc.launch_campaign(
        sim,
        FaultCampaignRequest(
            preset_id="hospital_ddos_backhaul_cascade",
            duration_ticks=5,
            seed=2042,
            reset_before_run=True,
            step_immediately=2,
        ),
    )

    gt_by_inst = {gt.institution_id: gt for gt in record.ground_truth}
    assert gt_by_inst["HOSP-01"].expected_cause == CauseCategory.CYBERATTACK_LIKE
    assert gt_by_inst["HOSP-02"].expected_cause == CauseCategory.CONNECTIVITY_FAILURE
    assert gt_by_inst["PDS-11"].expected_cause == CauseCategory.CONNECTIVITY_FAILURE

    assert sentinel.evaluate(sim.institutions["HOSP-01"], sim.series["HOSP-01"]).is_anomalous
    assert sentinel.evaluate(sim.institutions["HOSP-02"], sim.series["HOSP-02"]).is_anomalous
    assert sentinel.evaluate(sim.institutions["PDS-11"], sim.series["PDS-11"]).is_anomalous


def test_accessory_api_endpoints_and_portal_tab():
    html = client.get("/")
    assert html.status_code == 200
    assert 'data-tab="accessories"' in html.text
    assert "Resilience Accessories" in html.text

    acc_list = client.get("/api/accessories")
    assert acc_list.status_code == 200
    items = acc_list.json()
    assert len(items) == 1
    assert items[0]["metadata"]["accessory_id"] == "synthetic_fault_injector"
    assert items[0]["metadata"]["is_simulation_only"] is True
    assert items[0]["metadata"]["zero_pii"] is True

    state_res = client.get("/api/accessories/fault-injector")
    assert state_res.status_code == 200
    assert len(state_res.json()["presets"]) == 4

    run_res = client.post(
        "/api/accessories/fault-injector/campaigns",
        json={
            "preset_id": "coord_pds_auth_storm",
            "duration_ticks": 4,
            "seed": 1042,
            "reset_before_run": True,
            "step_immediately": 2,
        },
    )
    assert run_res.status_code == 200
    body = run_res.json()
    assert len(body["campaign"]["ground_truth"]) == 3
    assert body["dashboard"]["kpis"]["services_at_risk"] >= 3
    assert len(body["state"]["active_injections"]) == 3

    bad_res = client.post(
        "/api/accessories/fault-injector/campaigns",
        json={
            "targets": [{"institution_id": "NOPE-99", "fault_type": "request_spike", "intensity": 1.0}],
            "duration_ticks": 2,
        },
    )
    assert bad_res.status_code == 400

    clear_res = client.post("/api/accessories/fault-injector/clear")
    assert clear_res.status_code == 200
    assert clear_res.json()["state"]["active_injections"] == []

    reset_res = client.post("/api/demo/reset")
    assert reset_res.status_code == 200


def test_telecom_subsea_5g_storm_preset():
    state_res = client.get("/api/accessories/fault-injector")
    assert state_res.status_code == 200
    telecom_presets = state_res.json()["telecom_presets"]
    assert len(telecom_presets) >= 1
    assert telecom_presets[0]["preset_id"] == "telecom_subsea_5g_storm"

    run_res = client.post(
        "/api/accessories/fault-injector/campaigns",
        json={
            "preset_id": "telecom_subsea_5g_storm",
            "duration_ticks": 5,
            "seed": 5042,
            "reset_before_run": True,
            "step_immediately": 2,
        },
    )
    assert run_res.status_code == 200
    body = run_res.json()
    assert body["campaign"]["ground_truth"]
    gt_by_inst = {gt["institution_id"]: gt for gt in body["campaign"]["ground_truth"]}
    assert gt_by_inst["HOSP-01"]["expected_cause"] == "cyberattack_like"
    assert gt_by_inst["HOSP-02"]["expected_cause"] == "cyberattack_like"
    assert gt_by_inst["PDS-03"]["expected_cause"] == "cyberattack_like"
    assert gt_by_inst["PDS-11"]["expected_cause"] == "connectivity_failure"
    assert body["dashboard"]["kpis"]["services_at_risk"] >= 4

    clear_res = client.post("/api/accessories/fault-injector/clear")
    assert clear_res.status_code == 200
    assert client.post("/api/demo/reset").status_code == 200

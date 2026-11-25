"""Unit tests for the 5-layer NEXA ENGINE core."""

from backend.nexa_engine import (
    CORE_INSTITUTIONS,
    CauseClassifier,
    CitizenImpactEngine,
    DriftSentinel,
    PlaybookEngine,
    TelemetrySimulator,
)
from backend.nexa_engine.evaluation import run_full_evaluation
from backend.nexa_engine.models import AlertLevel, FaultType, ServiceType, WorkflowStatus


def test_core_scope_is_hard_frozen_to_23_institutions():
    hospitals = [i for i in CORE_INSTITUTIONS if i.service_type == ServiceType.HOSPITAL_REGISTRATION]
    rations = [i for i in CORE_INSTITUTIONS if i.service_type == ServiceType.RATION_DISTRIBUTION]
    assert len(hospitals) == 3
    assert len(rations) == 20
    assert len(CORE_INSTITUTIONS) == 23


def test_simulator_is_deterministic_with_fixed_seed():
    sim_a = TelemetrySimulator(seed=42, history_ticks=25)
    sim_b = TelemetrySimulator(seed=42, history_ticks=25)
    assert sim_a.series["HOSP-01"][-1] == sim_b.series["HOSP-01"][-1]


def test_drift_sentinel_detects_injected_fault_and_explains_signals():
    sim = TelemetrySimulator(seed=42, history_ticks=35)
    sentinel = DriftSentinel(baseline_window=30)

    normal_res = sentinel.evaluate(sim.institutions["HOSP-01"], sim.series["HOSP-01"])
    assert not normal_res.is_anomalous

    sim.inject_fault("HOSP-01", FaultType.REQUEST_SPIKE, intensity=1.2)
    sim.step(2)
    fault_res = sentinel.evaluate(sim.institutions["HOSP-01"], sim.series["HOSP-01"])
    assert fault_res.is_anomalous
    assert fault_res.severity >= 0.4
    assert len(fault_res.top_contributing_signals) > 0


def test_cause_classifier_outputs_valid_probabilities():
    sim = TelemetrySimulator(seed=99, history_ticks=35)
    sim.inject_fault("PDS-03", FaultType.LINK_DROP, intensity=1.2)
    sim.step(1)
    clf = CauseClassifier(seed=101)
    probs = clf.predict_proba(sim.institutions["PDS-03"], sim.series["PDS-03"][-1])
    total = (
        probs.cyberattack_like
        + probs.overload
        + probs.connectivity_failure
        + probs.hardware_or_human_error
    )
    assert 0.99 <= total <= 1.01
    assert "never a deterministic verdict" in probs.note.lower()


def test_impact_engine_produces_range_assumptions_and_ranking():
    sim = TelemetrySimulator(seed=42, history_ticks=35)
    sentinel = DriftSentinel()
    impact = CitizenImpactEngine()

    sim.inject_fault("HOSP-01", FaultType.SERVER_CRASH, intensity=1.2)
    sim.inject_fault("PDS-20", FaultType.SUSTAINED_OVERLOAD, intensity=0.6)
    sim.step(2)

    items = [(inst, sentinel.evaluate(inst, sim.series[inst.institution_id])) for inst in CORE_INSTITUTIONS]
    ranked = impact.assess_and_rank(items)

    top_inst, _, top_assess, top_level = ranked[0]
    assert top_inst.institution_id == "HOSP-01"
    assert top_level == AlertLevel.CRITICAL
    assert top_assess.priority_rank == 1
    assert 0 < top_assess.affected_citizens_low <= top_assess.affected_citizens_high
    assert len(top_assess.assumptions) >= 3


def test_playbook_and_workflow_state():
    pb_engine = PlaybookEngine()
    hosp = CORE_INSTITUTIONS[0]
    pb = pb_engine.build_playbook(hosp, AlertLevel.CRITICAL)
    assert pb is not None
    assert pb.triggered is True
    assert pb.requires_official_approval is True

    wf = pb_engine.update_workflow("ALT-HOSP-01", WorkflowStatus.ACKNOWLEDGED, "Collectorate Officer", "Verified")
    assert wf.status == WorkflowStatus.ACKNOWLEDGED
    assert wf.acknowledged_by == "Collectorate Officer"


def test_evaluation_suite_runs_cleanly():
    report = run_full_evaluation()
    assert report["detection"]["recall"] >= 0.85
    assert report["impact_ranking"]["exact_match"] is True

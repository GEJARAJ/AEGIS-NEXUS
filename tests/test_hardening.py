"""Phase 1 Production Hardening tests: zero-PII boundary, staleness, cooldowns, and <50ms benchmark."""

from datetime import datetime, timedelta, timezone
import time
from fastapi.testclient import TestClient
import numpy as np
import pytest
from pydantic import ValidationError

from backend.app.main import app
from backend.nexa_engine import (
    CORE_INSTITUTIONS,
    CitizenImpactEngine,
    DriftSentinel,
    LiveTelemetryCollector,
    PlaybookEngine,
    TelemetrySimulator,
    TelemetrySource,
)
from backend.nexa_engine.models import (
    AlertLevel,
    FaultType,
    HeartbeatStatus,
    InstitutionProfile,
    ServiceType,
    TelemetryIngestBatch,
    TelemetryPoint,
    WorkflowStatus,
)


def _make_point(
    inst_id: str,
    tick: int,
    ts: datetime,
    uptime: float = 99.8,
    latency: float = 150.0,
    error_rate: float = 0.012,
    auth_failures: int = 4,
    queue_len: int = 16,
    fault: FaultType = FaultType.NONE,
) -> TelemetryPoint:
    return TelemetryPoint(
        institution_id=inst_id,
        tick=tick,
        timestamp=ts.isoformat(),
        uptime_pct=uptime,
        latency_ms=latency,
        error_rate=error_rate,
        auth_failure_count=auth_failures,
        queue_length=queue_len,
        injected_fault=fault,
    )


def test_zero_pii_extra_forbid_validation():
    base_payload = {
        "institution_id": "HOSP-01",
        "tick": 1,
        "timestamp": "2026-11-25T10:00:00+00:00",
        "uptime_pct": 99.9,
        "latency_ms": 140.0,
        "error_rate": 0.01,
        "auth_failure_count": 3,
        "queue_length": 14,
    }
    # Reject undeclared PII fields on TelemetryPoint
    with pytest.raises(ValidationError):
        TelemetryPoint.model_validate({**base_payload, "citizen_name": "Ravi Kumar"})

    with pytest.raises(ValidationError):
        TelemetryPoint.model_validate({**base_payload, "aadhaar_id": "1234-5678-9012"})

    # Reject undeclared fields at batch level and collector ingest boundary
    with pytest.raises(ValidationError):
        TelemetryIngestBatch.model_validate(
            {"source_id": "collector-1", "points": [base_payload], "operator_ip": "10.0.0.1"}
        )

    collector = LiveTelemetryCollector(CORE_INSTITUTIONS)
    with pytest.raises(ValidationError):
        collector.ingest({"points": [{**base_payload, "imsi": "404010123456789"}]})

    assert collector.ingest({"points": [base_payload]}) == 1


def test_telemetry_source_interface_separation():
    sim = TelemetrySimulator(seed=42, history_ticks=15)
    collector = LiveTelemetryCollector(CORE_INSTITUTIONS)

    assert isinstance(sim, TelemetrySource)
    assert isinstance(collector, TelemetrySource)
    assert len(sim.collect_batch()) == 23
    assert len(collector.collect_batch()) == 23


def test_stale_heartbeat_detection_distinct_from_server_crash():
    t0 = datetime(2026, 11, 25, 9, 0, 0, tzinfo=timezone.utc)
    collector = LiveTelemetryCollector(CORE_INSTITUTIONS, initial_time=t0)
    sentinel = DriftSentinel(baseline_window=20, stale_after_ticks=3, stale_after_seconds=900.0)

    # Feed 10 healthy ticks for HOSP-01 and HOSP-02
    for tick in range(1, 11):
        ts = t0 + timedelta(minutes=5 * tick)
        collector.ingest(
            {
                "points": [
                    _make_point("HOSP-01", tick, ts),
                    _make_point("HOSP-02", tick, ts),
                ]
            }
        )

    # HOSP-01 goes silent while HOSP-02 continues reporting and experiences an active SERVER_CRASH
    for tick in range(11, 15):
        ts = t0 + timedelta(minutes=5 * tick)
        is_crash = tick == 14
        collector.ingest(
            {
                "points": [
                    _make_point(
                        "HOSP-02",
                        tick,
                        ts,
                        uptime=32.0 if is_crash else 99.8,
                        latency=680.0 if is_crash else 155.0,
                        error_rate=0.68 if is_crash else 0.013,
                        queue_len=70 if is_crash else 14,
                        fault=FaultType.SERVER_CRASH if is_crash else FaultType.NONE,
                    )
                ]
            }
        )

    hosp1_res = sentinel.evaluate(
        collector.institutions["HOSP-01"],
        collector.get_history("HOSP-01"),
        reference_tick=collector.current_tick,
        reference_time=collector.reference_time,
    )
    hosp2_res = sentinel.evaluate(
        collector.institutions["HOSP-02"],
        collector.get_history("HOSP-02"),
        reference_tick=collector.current_tick,
        reference_time=collector.reference_time,
    )

    assert hosp1_res.is_stale is True
    assert hosp1_res.heartbeat_status == HeartbeatStatus.STALE
    assert hosp1_res.missed_ticks == 4
    assert hosp1_res.is_anomalous is True
    assert hosp1_res.z_score_max == 0.0
    assert "stale" in hosp1_res.summary.lower()

    assert hosp2_res.is_stale is False
    assert hosp2_res.heartbeat_status == HeartbeatStatus.HEALTHY
    assert hosp2_res.is_anomalous is True
    assert hosp2_res.z_score_max >= 5.0


def test_playbook_cooldown_deduplication_and_escalation():
    pb = PlaybookEngine(cooldown_ticks=5, escalation_delta=0.15)
    hosp = CORE_INSTITUTIONS[0]

    # Initial Critical alert before acknowledgement triggers playbook
    initial_pb = pb.build_playbook(hosp, AlertLevel.CRITICAL, alert_id="ALT-HOSP-01", severity=0.58, current_tick=10)
    assert initial_pb is not None
    assert initial_pb.triggered is True

    # Official acknowledges at tick 10 (Warning, severity 0.45)
    pb.update_workflow(
        "ALT-HOSP-01",
        WorkflowStatus.ACKNOWLEDGED,
        "DoT Nodal Officer",
        notes="Containment active",
        current_tick=10,
        severity=0.45,
        level=AlertLevel.WARNING,
    )

    # Repeated ticks within cooldown without escalation are suppressed
    notify_11, reason_11 = pb.evaluate_dispatch("ALT-HOSP-01", AlertLevel.WARNING, severity=0.48, current_tick=11)
    notify_12, reason_12 = pb.evaluate_dispatch("ALT-HOSP-01", AlertLevel.WARNING, severity=0.50, current_tick=12)
    assert notify_11 is False and reason_11 == "cooldown_suppressed"
    assert notify_12 is False and reason_12 == "cooldown_suppressed"
    wf = pb.get_workflow("ALT-HOSP-01")
    assert wf.cooldown_active is True
    assert wf.suppressed_duplicates == 2

    # Severity escalation (WARNING -> CRITICAL and +0.25 severity) breaks cooldown
    pb_esc = pb.build_playbook(hosp, AlertLevel.CRITICAL, alert_id="ALT-HOSP-01", severity=0.70, current_tick=13)
    assert pb_esc is not None
    assert pb_esc.triggered is True
    assert pb.get_workflow("ALT-HOSP-01").last_dispatch_reason == "severity_escalated"

    # Marking Restored clears cooldown state
    restored_wf = pb.update_workflow("ALT-HOSP-01", WorkflowStatus.RESTORED, "DoT Nodal Officer", current_tick=14)
    assert restored_wf.cooldown_active is False
    assert restored_wf.suppressed_duplicates == 0


def test_100_institution_cycle_latency_under_50ms():
    rng = np.random.default_rng(123)
    t0 = datetime(2026, 11, 25, 9, 0, 0, tzinfo=timezone.utc)
    institutions = []
    histories = []

    for i in range(100):
        base = CORE_INSTITUTIONS[i % len(CORE_INSTITUTIONS)]
        inst = InstitutionProfile(
            institution_id=f"NODE-{i + 1:03d}",
            name=f"{base.name} #{i + 1}",
            service_type=ServiceType.HOSPITAL_REGISTRATION if i < 15 else ServiceType.RATION_DISTRIBUTION,
            zone=base.zone,
            service_capacity=base.service_capacity,
            daily_footfall=base.daily_footfall,
            vulnerability_weight=base.vulnerability_weight,
            vulnerability_proxy_reason=base.vulnerability_proxy_reason,
            responsible_department=base.responsible_department,
            alternate_centre=base.alternate_centre,
            baseline_latency_ms=base.baseline_latency_ms,
            baseline_error_rate=base.baseline_error_rate,
            baseline_auth_failures=base.baseline_auth_failures,
            baseline_queue_length=base.baseline_queue_length,
        )
        pts = []
        for tick in range(1, 36):
            ts = t0 + timedelta(minutes=5 * tick)
            is_fault = tick == 35 and i in (0, 25, 75)
            pts.append(
                _make_point(
                    inst.institution_id,
                    tick,
                    ts,
                    uptime=78.0 if is_fault else float(min(100.0, max(0.0, 99.8 + rng.normal(0.0, 0.1)))),
                    latency=880.0 if is_fault else float(max(10.0, inst.baseline_latency_ms + rng.normal(0.0, 10.0))),
                    error_rate=0.35 if is_fault else float(inst.baseline_error_rate),
                    auth_failures=95 if is_fault else int(inst.baseline_auth_failures),
                    queue_len=90 if is_fault else int(inst.baseline_queue_length),
                    fault=FaultType.REQUEST_SPIKE if is_fault else FaultType.NONE,
                )
            )
        institutions.append(inst)
        histories.append(pts)

    batch = list(zip(institutions, histories))
    sentinel = DriftSentinel(baseline_window=30)
    impact_engine = CitizenImpactEngine()
    pb_engine = PlaybookEngine()
    ref_time = t0 + timedelta(minutes=5 * 35)

    # Warm-up cycle
    sentinel.evaluate_batch(batch, reference_tick=35, reference_time=ref_time)

    elapsed_ms = []
    for _ in range(5):
        start = time.perf_counter()
        drift_results = sentinel.evaluate_batch(batch, reference_tick=35, reference_time=ref_time)
        ranked = impact_engine.assess_and_rank(list(zip(institutions, drift_results)))
        for inst, drift, _, level in ranked:
            pb_engine.build_playbook(
                inst,
                level,
                alert_id=f"ALT-{inst.institution_id}",
                severity=drift.severity,
                current_tick=35,
            )
        elapsed_ms.append((time.perf_counter() - start) * 1000.0)

    avg_ms = sum(elapsed_ms) / len(elapsed_ms)
    print(f"[100-institution cycle benchmark] avg={avg_ms:.2f}ms, max={max(elapsed_ms):.2f}ms", flush=True)
    assert avg_ms < 50.0, f"100-institution cycle avg latency {avg_ms:.2f}ms exceeded 50ms budget"


def test_api_telemetry_ingest_rejects_pii():
    client = TestClient(app)
    res = client.post(
        "/api/telemetry/ingest",
        json={
            "source_id": "term-cell-collector",
            "points": [
                {
                    "institution_id": "HOSP-01",
                    "tick": 41,
                    "timestamp": "2026-11-25T12:25:00+00:00",
                    "uptime_pct": 99.7,
                    "latency_ms": 145.0,
                    "error_rate": 0.012,
                    "auth_failure_count": 4,
                    "queue_length": 18,
                    "subscriber_msisdn": "+919800000000",
                }
            ],
        },
    )
    assert res.status_code == 422

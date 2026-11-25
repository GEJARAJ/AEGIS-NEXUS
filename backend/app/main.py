"""FastAPI Server for AEGIS NEXUS — Civic Sentinel (Powered by NEXA ENGINE)."""

from pathlib import Path
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.nexa_engine import (
    CauseClassifier,
    CitizenImpactEngine,
    DriftSentinel,
    EXTENSION_SECTORS,
    PlaybookEngine,
    TelemetrySimulator,
    VULNERABILITY_PROXY_TABLE,
)
from backend.nexa_engine.evaluation import run_full_evaluation
from backend.nexa_engine.models import (
    AlertLevel,
    CivicAlert,
    DashboardSummary,
    FaultType,
    TelemetryPoint,
    WorkflowStatus,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIR = PROJECT_ROOT / "frontend"


class FaultInjectionRequest(BaseModel):
    institution_id: str
    fault_type: FaultType
    intensity: float = Field(default=1.0, ge=0.3, le=2.0)


class WorkflowUpdateRequest(BaseModel):
    status: WorkflowStatus
    official_name: str = Field(..., min_length=2, max_length=100)
    notes: Optional[str] = Field(default=None, max_length=400)


class CivicSentinelService:
    """Orchestrates the 5-layer NEXA ENGINE pipeline over the active simulation."""

    def __init__(self, seed: int = 42):
        self.simulator = TelemetrySimulator(seed=seed, history_ticks=40)
        self.drift_sentinel = DriftSentinel(baseline_window=30, z_threshold=2.6)
        self.cause_classifier = CauseClassifier(seed=101)
        self.impact_engine = CitizenImpactEngine()
        self.playbook_engine = PlaybookEngine()
        self._cached_evaluation: Optional[Dict[str, object]] = None

    def build_dashboard(self) -> DashboardSummary:
        drift_items = []
        for inst_id, inst in self.simulator.institutions.items():
            history = self.simulator.series[inst_id]
            drift = self.drift_sentinel.evaluate(inst, history)
            drift_items.append((inst, drift))

        ranked = self.impact_engine.assess_and_rank(drift_items)

        alerts: List[CivicAlert] = []
        critical_count = 0
        at_risk_count = 0
        investigated_count = 0

        for inst, drift, impact, level in ranked:
            latest_pt = self.simulator.series[inst.institution_id][-1]
            alert_id = f"ALT-{inst.institution_id}"
            cause_probs = (
                self.cause_classifier.predict_proba(inst, latest_pt)
                if drift.is_anomalous
                else None
            )
            playbook = self.playbook_engine.build_playbook(inst, level)
            workflow = self.playbook_engine.get_workflow(alert_id)

            if level == AlertLevel.CRITICAL:
                critical_count += 1
            if level in (AlertLevel.CRITICAL, AlertLevel.WARNING):
                at_risk_count += 1
            if workflow.status != WorkflowStatus.OPEN:
                investigated_count += 1

            alerts.append(
                CivicAlert(
                    alert_id=alert_id,
                    institution=inst,
                    level=level,
                    drift=drift,
                    cause_probabilities=cause_probs,
                    impact=impact,
                    playbook=playbook,
                    workflow=workflow,
                    latest_telemetry=latest_pt,
                    is_simulation_based=True,
                    is_illustrative=True,
                )
            )

        return DashboardSummary(
            district_name="Model Civic District (Simulation Prototype)",
            scope_note="Core Scope (Hard-Frozen): 3 Government Hospitals + 20 Ration Distribution Centres (23 institutions).",
            simulation_disclaimer=(
                "SIMULATION-BASED PROTOTYPE: All telemetry, cause probabilities, and citizen-impact ranges "
                "are synthetic and illustrative. Real deployment requires government authorization and a data-sharing agreement."
            ),
            kpis={
                "critical_alerts": critical_count,
                "services_at_risk": at_risk_count,
                "institutions_monitored": len(self.simulator.institutions),
                "incidents_investigated": investigated_count,
            },
            alerts=alerts,
            extension_sectors=EXTENSION_SECTORS,
        )

    def run_hospital_demo_scenario(self) -> DashboardSummary:
        """Section 12 scripted demo: normal -> hospital registration failure -> warning ration centre -> playbook."""
        self.simulator.reset(seed=42)
        self.playbook_engine.reset()
        self.simulator.inject_fault("HOSP-01", FaultType.REQUEST_SPIKE, intensity=1.15)
        self.simulator.inject_fault("PDS-03", FaultType.AUTH_FAILURE_STORM, intensity=0.65)
        self.simulator.step(2)
        return self.build_dashboard()

    def get_evaluation(self) -> Dict[str, object]:
        if self._cached_evaluation is None:
            self._cached_evaluation = run_full_evaluation()
        return self._cached_evaluation


service = CivicSentinelService(seed=42)

app = FastAPI(
    title="AEGIS NEXUS — Civic Sentinel (NEXA ENGINE)",
    description=(
        "AI-Powered Public Infrastructure Intelligence and Citizen Impact Early Warning System. "
        "Simulation-based prototype operating strictly on aggregate operational telemetry."
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health_check() -> Dict[str, object]:
    return {
        "status": "operational",
        "engine": "NEXA ENGINE v0.1",
        "mode": "simulation",
        "institutions_core": len(service.simulator.institutions),
        "current_tick": service.simulator.current_tick,
    }


@app.get("/api/dashboard", response_model=DashboardSummary)
def get_dashboard() -> DashboardSummary:
    return service.build_dashboard()


@app.get("/api/institutions/{institution_id}/telemetry", response_model=List[TelemetryPoint])
def get_institution_telemetry(institution_id: str, limit: int = 35) -> List[TelemetryPoint]:
    if institution_id not in service.simulator.series:
        raise HTTPException(status_code=404, detail="Institution not found in core district scope.")
    return service.simulator.series[institution_id][-limit:]


@app.post("/api/demo/scenario/hospital-failure", response_model=DashboardSummary)
def trigger_hospital_demo() -> DashboardSummary:
    return service.run_hospital_demo_scenario()


@app.post("/api/demo/inject", response_model=DashboardSummary)
def inject_fault(req: FaultInjectionRequest) -> DashboardSummary:
    if req.institution_id not in service.simulator.institutions:
        raise HTTPException(status_code=404, detail="Institution not found in core district scope.")
    service.simulator.inject_fault(req.institution_id, req.fault_type, req.intensity)
    service.simulator.step(2)
    return service.build_dashboard()


@app.post("/api/demo/step", response_model=DashboardSummary)
def advance_simulation(steps: int = 1) -> DashboardSummary:
    service.simulator.step(max(1, min(steps, 10)))
    return service.build_dashboard()


@app.post("/api/demo/reset", response_model=DashboardSummary)
def reset_simulation() -> DashboardSummary:
    service.simulator.reset(seed=42)
    service.playbook_engine.reset()
    return service.build_dashboard()


@app.post("/api/alerts/{alert_id}/workflow")
def update_alert_workflow(alert_id: str, req: WorkflowUpdateRequest) -> Dict[str, object]:
    valid_ids = {f"ALT-{inst_id}" for inst_id in service.simulator.institutions}
    if alert_id not in valid_ids:
        raise HTTPException(status_code=404, detail="Alert ID not found.")

    state = service.playbook_engine.update_workflow(
        alert_id=alert_id,
        status=req.status,
        official_name=req.official_name,
        notes=req.notes,
    )
    # If marked Restored, clear active simulated fault on that institution to reflect restoration
    if req.status == WorkflowStatus.RESTORED:
        inst_id = alert_id.replace("ALT-", "", 1)
        service.simulator.clear_fault(inst_id)
        service.simulator.step(2)

    return {"alert_id": alert_id, "workflow": state, "dashboard": service.build_dashboard()}


@app.get("/api/evaluation")
def get_evaluation() -> Dict[str, object]:
    return service.get_evaluation()


@app.get("/api/governance")
def get_governance_info() -> Dict[str, object]:
    return {
        "positioning": {
            "existing_national_systems": [
                "CERT-In (National incident response)",
                "NCCC (Threat monitoring and coordination)",
                "NCIIPC (Critical information infrastructure protection)",
                "I4C (Cybercrime coordination)",
                "Cyber Swachhta Kendra (Botnet and malware detection assistance)",
            ],
            "civic_sentinel_role": (
                "Complementary citizen-impact and service-continuity layer sitting on top of existing cybersecurity "
                "and operational monitoring systems."
            ),
        },
        "privacy_and_ethics": [
            "Aggregate and anonymized operational signals only (uptime, latency, error rate, auth failures, queue length).",
            "Zero personally identifiable information (PII) ingested or stored.",
            "Vulnerability weighting uses service-level institutional proxies only — never individual profiling.",
            "Human-in-the-loop: NEXA ENGINE recommends; authorized government officials decide and execute.",
            "Real deployment requires formal government authorization and a signed data-sharing agreement.",
        ],
        "vulnerability_proxy_table": VULNERABILITY_PROXY_TABLE,
        "claims_guardrails": [
            {
                "say": "Adds a citizen-impact layer on top of existing systems",
                "do_not_say": "India has no cyber monitoring",
            },
            {
                "say": "Cause classifier gives probabilities, validated on simulation",
                "do_not_say": "Detects cyberattacks with X% accuracy in the real world",
            },
            {
                "say": "Estimated impact range under stated assumptions",
                "do_not_say": "Exact number of citizens affected",
            },
            {
                "say": "Dashboard figures are illustrative and simulation-based",
                "do_not_say": "Dashboard figures as if they were live government data",
            },
            {
                "say": "Deployment requires government authorization",
                "do_not_say": "Ready for immediate government rollout",
            },
        ],
    }


if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/", include_in_schema=False)
    def serve_portal() -> FileResponse:
        return FileResponse(str(FRONTEND_DIR / "index.html"))

"""Data contracts for NEXA ENGINE (strictly aggregate, zero-PII telemetry)."""

from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class ServiceType(str, Enum):
    HOSPITAL_REGISTRATION = "hospital_registration"
    RATION_DISTRIBUTION = "ration_distribution"


class FaultType(str, Enum):
    NONE = "none"
    REQUEST_SPIKE = "request_spike"
    AUTH_FAILURE_STORM = "auth_failure_storm"
    LINK_DROP = "link_drop"
    SERVER_CRASH = "server_crash"
    SUSTAINED_OVERLOAD = "sustained_overload"


class CauseCategory(str, Enum):
    CYBERATTACK_LIKE = "cyberattack_like"
    OVERLOAD = "overload"
    CONNECTIVITY_FAILURE = "connectivity_failure"
    HARDWARE_OR_HUMAN_ERROR = "hardware_or_human_error"


class AlertLevel(str, Enum):
    CRITICAL = "Critical"
    WARNING = "Warning"
    NORMAL = "Normal"


class WorkflowStatus(str, Enum):
    OPEN = "Open"
    ACKNOWLEDGED = "Acknowledged"
    MITIGATING = "Mitigating"
    RESTORED = "Restored"


class InstitutionProfile(BaseModel):
    institution_id: str
    name: str
    service_type: ServiceType
    zone: str  # Urban | Semi-Urban | Rural (service-level proxy only)
    service_capacity: int = Field(..., description="Max citizens served per day")
    daily_footfall: int = Field(..., description="Typical anonymized aggregate daily footfall")
    vulnerability_weight: float = Field(..., ge=1.0, le=2.0)
    vulnerability_proxy_reason: str
    responsible_department: str
    alternate_centre: str
    baseline_latency_ms: float
    baseline_error_rate: float
    baseline_auth_failures: float
    baseline_queue_length: float


class TelemetryPoint(BaseModel):
    """Authorized, privacy-preserving aggregate operational telemetry (no PII)."""

    institution_id: str
    tick: int
    timestamp: str
    uptime_pct: float = Field(..., ge=0.0, le=100.0)
    latency_ms: float = Field(..., ge=0.0)
    error_rate: float = Field(..., ge=0.0, le=1.0)
    auth_failure_count: int = Field(..., ge=0)
    queue_length: int = Field(..., ge=0)
    injected_fault: FaultType = FaultType.NONE


class SignalContribution(BaseModel):
    signal: str
    z_score: float
    current_value: float
    baseline_mean: float
    description: str


class DriftResult(BaseModel):
    institution_id: str
    severity: float = Field(..., ge=0.0, le=1.0)
    is_anomalous: bool
    z_score_max: float
    isolation_score: float
    top_contributing_signals: List[SignalContribution]
    summary: str


class CauseProbabilities(BaseModel):
    cyberattack_like: float = Field(..., ge=0.0, le=1.0)
    overload: float = Field(..., ge=0.0, le=1.0)
    connectivity_failure: float = Field(..., ge=0.0, le=1.0)
    hardware_or_human_error: float = Field(..., ge=0.0, le=1.0)
    dominant_cause: CauseCategory
    method: str = "ml_calibrated"
    note: str = "Probabilistic estimate across operational causes; never a deterministic verdict."


class ImpactAssessment(BaseModel):
    impact_score: float
    affected_citizens_low: int
    affected_citizens_high: int
    priority_rank: int
    assumptions: List[str]


class PlaybookAction(BaseModel):
    playbook_id: str
    title: str
    triggered: bool
    department: str
    alternate_centre: str
    immediate_steps: List[str]
    requires_official_approval: bool = True


class AlertWorkflowState(BaseModel):
    status: WorkflowStatus = WorkflowStatus.OPEN
    acknowledged_by: Optional[str] = None
    updated_at: Optional[str] = None
    notes: Optional[str] = None


class CivicAlert(BaseModel):
    alert_id: str
    institution: InstitutionProfile
    level: AlertLevel
    drift: DriftResult
    cause_probabilities: Optional[CauseProbabilities] = None
    impact: ImpactAssessment
    playbook: Optional[PlaybookAction] = None
    workflow: AlertWorkflowState = Field(default_factory=AlertWorkflowState)
    latest_telemetry: TelemetryPoint
    is_simulation_based: bool = True
    is_illustrative: bool = True


class DashboardSummary(BaseModel):
    district_name: str
    scope_note: str
    simulation_disclaimer: str
    kpis: Dict[str, int]
    alerts: List[CivicAlert]
    extension_sectors: List[Dict[str, str]]

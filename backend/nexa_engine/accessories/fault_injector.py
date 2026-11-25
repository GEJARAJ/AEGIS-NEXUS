"""Synthetic Fault-Injector Accessory for deterministic, multi-target, time-bounded campaigns."""

from typing import Dict, List, Optional, Set
import numpy as np
from pydantic import BaseModel, Field

from ..cause_classifier import FAULT_TO_CAUSE
from ..models import CauseCategory, FaultType
from ..simulator import TelemetrySimulator
from .base import AccessoryMetadata, AccessoryStatus, ResilienceAccessory


class CampaignTarget(BaseModel):
    """Single institution fault specification within a synthetic campaign."""

    institution_id: str
    fault_type: FaultType
    intensity: float = Field(default=1.0, ge=0.3, le=2.0)
    start_offset_ticks: int = Field(default=0, ge=0, le=50)


class FaultCampaignRequest(BaseModel):
    """Request to launch either a coordinated preset or a custom multi-target campaign."""

    name: Optional[str] = Field(default=None, max_length=120)
    preset_id: Optional[str] = None
    targets: List[CampaignTarget] = Field(default_factory=list)
    duration_ticks: int = Field(default=4, ge=1, le=50)
    seed: int = Field(default=42, ge=0, le=2_147_483_647)
    intensity_jitter: float = Field(default=0.0, ge=0.0, le=0.25)
    reset_before_run: bool = False
    step_immediately: int = Field(default=2, ge=0, le=10)


class GroundTruthLabel(BaseModel):
    """Labeled ground-truth metadata for validating detection and cause classification."""

    institution_id: str
    fault_type: FaultType
    expected_cause: Optional[CauseCategory] = None
    intensity: float
    start_tick: int
    end_tick: int
    preset_id: Optional[str] = None


class ActiveInjection(BaseModel):
    """Live view of a scheduled or active time-bounded fault injection."""

    campaign_id: str
    campaign_name: str
    preset_id: Optional[str] = None
    institution_id: str
    fault_type: FaultType
    expected_cause: Optional[CauseCategory] = None
    intensity: float
    starts_at_tick: int
    ends_at_tick: int
    remaining_ticks: int
    active_now: bool


class FaultPreset(BaseModel):
    """Pre-configured multi-institution cybersecurity or resilience test scenario."""

    preset_id: str
    title: str
    category: str
    description: str
    recommended_duration_ticks: int
    default_seed: int
    targets: List[CampaignTarget]
    ground_truth_summary: str


class CampaignExecutionRecord(BaseModel):
    """Audit and ground-truth record of an executed fault campaign."""

    campaign_id: str
    name: str
    preset_id: Optional[str] = None
    seed: int
    duration_ticks: int
    started_at_tick: int
    ends_at_tick: int
    ground_truth: List[GroundTruthLabel]


class FaultInjectorState(BaseModel):
    """Complete serializable state for the Synthetic Fault-Injector Accessory."""

    status: AccessoryStatus
    current_tick: int
    presets: List[FaultPreset]
    telecom_presets: List[FaultPreset] = Field(default_factory=list)
    active_injections: List[ActiveInjection]
    campaign_history: List[CampaignExecutionRecord]


TELECOM_PRESETS: List[FaultPreset] = [
    FaultPreset(
        preset_id="telecom_subsea_5g_storm",
        title="Signaling / Control-Plane Flood + Backhaul Degradation",
        category="Cyber-Resilience & Threat Containment Drill (DoT / CERT-In)",
        description=(
            "Simulates a coordinated control-plane request flood at HOSP-01 (Chennai CLS & IXP Gateway) "
            "and 5G Core / AAA signaling storm at HOSP-02 & PDS-03, coupled with backhaul link "
            "degradation at coastal BharatNet PoP PDS-11."
        ),
        recommended_duration_ticks=5,
        default_seed=5042,
        targets=[
            CampaignTarget(institution_id="HOSP-01", fault_type=FaultType.REQUEST_SPIKE, intensity=1.30, start_offset_ticks=0),
            CampaignTarget(institution_id="HOSP-02", fault_type=FaultType.AUTH_FAILURE_STORM, intensity=1.15, start_offset_ticks=1),
            CampaignTarget(institution_id="PDS-03", fault_type=FaultType.AUTH_FAILURE_STORM, intensity=1.10, start_offset_ticks=1),
            CampaignTarget(institution_id="PDS-11", fault_type=FaultType.LINK_DROP, intensity=1.05, start_offset_ticks=1),
        ],
        ground_truth_summary="Expected causes: cyberattack_like control-plane & signaling storm (HOSP-01, HOSP-02, PDS-03) + connectivity_failure backhaul degradation (PDS-11)",
    ),
]


COORDINATED_PRESETS: List[FaultPreset] = [
    FaultPreset(
        preset_id="coord_pds_auth_storm",
        title="Coordinated PDS Credential & Biometric Storm",
        category="Cyberattack-Like Simulation",
        description=(
            "Simulates simultaneous biometric/portal authentication failure storms across three "
            "high-need rural and peri-urban ration centres."
        ),
        recommended_duration_ticks=5,
        default_seed=1042,
        targets=[
            CampaignTarget(institution_id="PDS-01", fault_type=FaultType.AUTH_FAILURE_STORM, intensity=1.15),
            CampaignTarget(institution_id="PDS-03", fault_type=FaultType.AUTH_FAILURE_STORM, intensity=1.05),
            CampaignTarget(institution_id="PDS-08", fault_type=FaultType.AUTH_FAILURE_STORM, intensity=0.95),
        ],
        ground_truth_summary="Expected cause: cyberattack_like across PDS-01, PDS-03, PDS-08",
    ),
    FaultPreset(
        preset_id="hospital_ddos_backhaul_cascade",
        title="Hospital DDoS + Backhaul Link Cascade",
        category="Multi-Layer Cascading Failure",
        description=(
            "Starts with a request spike at District General Hospital (HOSP-01), followed 1 tick later "
            "by connectivity link drops at HOSP-02 and coastal ration depot PDS-11."
        ),
        recommended_duration_ticks=5,
        default_seed=2042,
        targets=[
            CampaignTarget(institution_id="HOSP-01", fault_type=FaultType.REQUEST_SPIKE, intensity=1.25, start_offset_ticks=0),
            CampaignTarget(institution_id="HOSP-02", fault_type=FaultType.LINK_DROP, intensity=1.10, start_offset_ticks=1),
            CampaignTarget(institution_id="PDS-11", fault_type=FaultType.LINK_DROP, intensity=1.00, start_offset_ticks=1),
        ],
        ground_truth_summary="Expected causes: cyberattack_like (HOSP-01) -> connectivity_failure (HOSP-02, PDS-11)",
    ),
    FaultPreset(
        preset_id="peak_ration_overload_wave",
        title="Peak-Hour District Ration Rush Overload",
        category="Capacity & Resilience Stress",
        description=(
            "Models sustained peak-hour queue saturation across four high-footfall urban and "
            "semi-urban Fair Price Shops."
        ),
        recommended_duration_ticks=6,
        default_seed=3042,
        targets=[
            CampaignTarget(institution_id="PDS-10", fault_type=FaultType.SUSTAINED_OVERLOAD, intensity=1.10),
            CampaignTarget(institution_id="PDS-16", fault_type=FaultType.SUSTAINED_OVERLOAD, intensity=1.05),
            CampaignTarget(institution_id="PDS-18", fault_type=FaultType.SUSTAINED_OVERLOAD, intensity=1.15),
            CampaignTarget(institution_id="PDS-20", fault_type=FaultType.SUSTAINED_OVERLOAD, intensity=1.20),
        ],
        ground_truth_summary="Expected cause: overload across PDS-10, PDS-16, PDS-18, PDS-20",
    ),
    FaultPreset(
        preset_id="maternal_crash_diversion",
        title="Maternal Wing Crash & Overflow Diversion",
        category="Service Continuity Drill",
        description=(
            "Triggers an application outage at Maternal & Child Hospital (HOSP-03) and a staggered "
            "diversion overload at District General Hospital (HOSP-01) 1 tick later."
        ),
        recommended_duration_ticks=4,
        default_seed=4042,
        targets=[
            CampaignTarget(institution_id="HOSP-03", fault_type=FaultType.SERVER_CRASH, intensity=1.30, start_offset_ticks=0),
            CampaignTarget(institution_id="HOSP-01", fault_type=FaultType.SUSTAINED_OVERLOAD, intensity=1.05, start_offset_ticks=1),
        ],
        ground_truth_summary="Expected causes: hardware_or_human_error (HOSP-03) + overload (HOSP-01)",
    ),
]


class _ScheduledSlot:
    """Internal mutable slot for tracking a time-bounded institution injection."""

    def __init__(
        self,
        campaign_id: str,
        campaign_name: str,
        preset_id: Optional[str],
        institution_id: str,
        fault_type: FaultType,
        intensity: float,
        starts_at_tick: int,
        ends_at_tick: int,
    ) -> None:
        self.campaign_id = campaign_id
        self.campaign_name = campaign_name
        self.preset_id = preset_id
        self.institution_id = institution_id
        self.fault_type = fault_type
        self.intensity = intensity
        self.starts_at_tick = starts_at_tick
        self.ends_at_tick = ends_at_tick

    def is_active_for_tick(self, tick: int) -> bool:
        return self.starts_at_tick <= tick <= self.ends_at_tick

    def to_model(self, current_tick: int) -> ActiveInjection:
        remaining = max(0, self.ends_at_tick - max(current_tick, self.starts_at_tick - 1))
        return ActiveInjection(
            campaign_id=self.campaign_id,
            campaign_name=self.campaign_name,
            preset_id=self.preset_id,
            institution_id=self.institution_id,
            fault_type=self.fault_type,
            expected_cause=FAULT_TO_CAUSE.get(self.fault_type),
            intensity=self.intensity,
            starts_at_tick=self.starts_at_tick,
            ends_at_tick=self.ends_at_tick,
            remaining_ticks=remaining,
            active_now=self.is_active_for_tick(current_tick),
        )


class SyntheticFaultInjectorAccessory(ResilienceAccessory):
    """Modular accessory that orchestrates deterministic, time-bounded fault campaigns."""

    _METADATA = AccessoryMetadata(
        accessory_id="synthetic_fault_injector",
        name="Synthetic Fault-Injector Accessory",
        category="Cybersecurity & Resilience Simulation",
        version="0.1.0",
        description=(
            "Runs deterministic, multi-target, time-bounded fault campaigns and coordinated "
            "cyber-resilience drills on top of TelemetrySimulator with ground-truth labels."
        ),
        is_simulation_only=True,
        zero_pii=True,
    )

    def __init__(self) -> None:
        self._presets: Dict[str, FaultPreset] = {
            p.preset_id: p for p in (*COORDINATED_PRESETS, *TELECOM_PRESETS)
        }
        self._slots: Dict[str, _ScheduledSlot] = {}
        self._managed_institutions: Set[str] = set()
        self._history: List[CampaignExecutionRecord] = []
        self._sequence: int = 0

    @property
    def metadata(self) -> AccessoryMetadata:
        return self._METADATA

    def status(self) -> AccessoryStatus:
        return AccessoryStatus(
            metadata=self._METADATA,
            active=len(self._slots) > 0,
            active_items=len(self._slots),
            total_runs=len(self._history),
        )

    def reset(self) -> None:
        self._slots.clear()
        self._managed_institutions.clear()
        self._history.clear()
        self._sequence = 0

    def list_presets(self) -> List[FaultPreset]:
        return list(COORDINATED_PRESETS)

    def list_telecom_presets(self) -> List[FaultPreset]:
        return list(TELECOM_PRESETS)

    def get_preset(self, preset_id: str) -> FaultPreset:
        if preset_id not in self._presets:
            raise ValueError(f"Unknown preset_id: {preset_id}")
        return self._presets[preset_id]

    def launch_campaign(
        self,
        simulator: TelemetrySimulator,
        request: FaultCampaignRequest,
    ) -> CampaignExecutionRecord:
        """Schedule a deterministic, time-bounded campaign and optionally advance the simulator."""
        preset: Optional[FaultPreset] = None
        targets = list(request.targets)
        duration = request.duration_ticks
        seed = request.seed
        campaign_name = (request.name or "").strip()

        if request.preset_id:
            preset = self.get_preset(request.preset_id)
            if not targets:
                targets = list(preset.targets)
            if not campaign_name:
                campaign_name = preset.title

        if not targets:
            raise ValueError("Campaign must specify at least one target institution or a valid preset_id.")

        if not campaign_name:
            campaign_name = f"Custom Multi-Target Campaign ({len(targets)} targets)"

        for t in targets:
            if t.institution_id not in simulator.institutions:
                raise ValueError(f"Unknown institution_id in campaign: {t.institution_id}")

        if request.reset_before_run:
            self.clear_all(simulator)
            simulator.reset(seed=seed)

        self._sequence += 1
        campaign_id = f"CMP-{seed}-{self._sequence:02d}"
        rng = np.random.default_rng(seed)
        base_tick = simulator.current_tick

        ground_truth: List[GroundTruthLabel] = []
        max_end_tick = base_tick + duration

        for t in targets:
            jitter = float(rng.uniform(-request.intensity_jitter, request.intensity_jitter)) if request.intensity_jitter > 0 else 0.0
            resolved_intensity = round(float(max(0.3, min(2.0, t.intensity + jitter))), 3)
            starts_at = base_tick + 1 + t.start_offset_ticks
            ends_at = base_tick + t.start_offset_ticks + duration
            max_end_tick = max(max_end_tick, ends_at)

            if t.fault_type == FaultType.NONE:
                self._slots.pop(t.institution_id, None)
                self._managed_institutions.discard(t.institution_id)
                simulator.clear_fault(t.institution_id)
                continue

            slot = _ScheduledSlot(
                campaign_id=campaign_id,
                campaign_name=campaign_name,
                preset_id=preset.preset_id if preset else None,
                institution_id=t.institution_id,
                fault_type=t.fault_type,
                intensity=resolved_intensity,
                starts_at_tick=starts_at,
                ends_at_tick=ends_at,
            )
            self._slots[t.institution_id] = slot
            self._managed_institutions.add(t.institution_id)
            ground_truth.append(
                GroundTruthLabel(
                    institution_id=t.institution_id,
                    fault_type=t.fault_type,
                    expected_cause=FAULT_TO_CAUSE.get(t.fault_type),
                    intensity=resolved_intensity,
                    start_tick=starts_at,
                    end_tick=ends_at,
                    preset_id=preset.preset_id if preset else None,
                )
            )

        record = CampaignExecutionRecord(
            campaign_id=campaign_id,
            name=campaign_name,
            preset_id=preset.preset_id if preset else None,
            seed=seed,
            duration_ticks=duration,
            started_at_tick=base_tick + 1,
            ends_at_tick=max_end_tick,
            ground_truth=ground_truth,
        )
        self._history.insert(0, record)
        if len(self._history) > 25:
            self._history = self._history[:25]

        if request.step_immediately > 0:
            self.step_with_simulator(simulator, request.step_immediately)

        return record

    def step_with_simulator(self, simulator: TelemetrySimulator, steps: int = 1) -> None:
        """Advance the simulator tick-by-tick while activating and expiring bounded faults."""
        for _ in range(steps):
            next_tick = simulator.current_tick + 1
            self._sync_for_next_tick(simulator, next_tick)
            simulator.step(1)
            self._expire_finished_slots(simulator, simulator.current_tick)

    def _sync_for_next_tick(self, simulator: TelemetrySimulator, next_tick: int) -> None:
        for inst_id, slot in list(self._slots.items()):
            if slot.is_active_for_tick(next_tick):
                simulator.inject_fault(inst_id, slot.fault_type, slot.intensity)
            elif next_tick > slot.ends_at_tick:
                simulator.clear_fault(inst_id)
                self._slots.pop(inst_id, None)
                self._managed_institutions.discard(inst_id)

    def _expire_finished_slots(self, simulator: TelemetrySimulator, completed_tick: int) -> None:
        for inst_id, slot in list(self._slots.items()):
            if completed_tick >= slot.ends_at_tick:
                simulator.clear_fault(inst_id)
                self._slots.pop(inst_id, None)
                self._managed_institutions.discard(inst_id)

    def clear_institution(self, institution_id: str, simulator: Optional[TelemetrySimulator] = None) -> None:
        """Abort any active accessory fault on a specific institution."""
        self._slots.pop(institution_id, None)
        if institution_id in self._managed_institutions:
            self._managed_institutions.discard(institution_id)
            if simulator is not None:
                simulator.clear_fault(institution_id)

    def clear_all(self, simulator: TelemetrySimulator) -> None:
        """Clear all accessory-managed faults from the simulator without disturbing core state."""
        for inst_id in list(self._managed_institutions):
            simulator.clear_fault(inst_id)
        self._slots.clear()
        self._managed_institutions.clear()

    def get_state(self, simulator: TelemetrySimulator) -> FaultInjectorState:
        active = [
            slot.to_model(simulator.current_tick)
            for slot in sorted(self._slots.values(), key=lambda s: (s.starts_at_tick, s.institution_id))
        ]
        return FaultInjectorState(
            status=self.status(),
            current_tick=simulator.current_tick,
            presets=self.list_presets(),
            telecom_presets=self.list_telecom_presets(),
            active_injections=active,
            campaign_history=list(self._history),
        )

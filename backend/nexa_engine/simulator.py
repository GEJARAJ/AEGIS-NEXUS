"""Layer 1 Input: Deterministic, Fixed-Seed Civic Infrastructure Telemetry Simulator.

Generates authorized, privacy-preserving aggregate-only signals:
- uptime_pct
- latency_ms
- error_rate
- auth_failure_count
- queue_length

All outputs are simulation-based and labelled with ground-truth fault tags for validation.
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
import numpy as np

from .ingestion import TelemetrySource
from .institutions import CORE_INSTITUTIONS
from .models import FaultType, InstitutionProfile, TelemetryPoint


class TelemetrySimulator(TelemetrySource):
    def __init__(self, seed: int = 42, history_ticks: int = 40):
        self.seed = seed
        self.rng = np.random.default_rng(seed)
        self.history_ticks = history_ticks
        self._institutions: Dict[str, InstitutionProfile] = {
            inst.institution_id: inst for inst in CORE_INSTITUTIONS
        }
        self.active_faults: Dict[str, Tuple[FaultType, float]] = {}
        self.series: Dict[str, List[TelemetryPoint]] = {}
        self._current_tick = 0
        self.base_time = datetime(2026, 11, 25, 9, 0, 0, tzinfo=timezone.utc)
        self.reset(seed=seed)

    @property
    def institutions(self) -> Dict[str, InstitutionProfile]:
        return self._institutions

    @property
    def current_tick(self) -> int:
        return self._current_tick

    @current_tick.setter
    def current_tick(self, value: int) -> None:
        self._current_tick = value

    @property
    def reference_time(self) -> datetime:
        return self.base_time + timedelta(minutes=5 * self._current_tick)

    def get_history(self, institution_id: str, limit: Optional[int] = None) -> List[TelemetryPoint]:
        pts = self.series[institution_id]
        return pts[-limit:] if limit is not None else pts

    def get_latest(self, institution_id: str) -> Optional[TelemetryPoint]:
        pts = self.series.get(institution_id, [])
        return pts[-1] if pts else None

    def reset(self, seed: Optional[int] = None) -> None:
        if seed is not None:
            self.seed = seed
        self.rng = np.random.default_rng(self.seed)
        self.active_faults.clear()
        self.series = {inst_id: [] for inst_id in self.institutions}
        self.current_tick = 0
        for _ in range(self.history_ticks):
            self.step()

    def inject_fault(
        self,
        institution_id: str,
        fault_type: FaultType,
        intensity: float = 1.0,
    ) -> None:
        if institution_id not in self.institutions:
            raise ValueError(f"Unknown institution_id: {institution_id}")
        if fault_type == FaultType.NONE:
            self.active_faults.pop(institution_id, None)
        else:
            self.active_faults[institution_id] = (fault_type, max(0.3, min(2.0, intensity)))

    def clear_fault(self, institution_id: str) -> None:
        self.active_faults.pop(institution_id, None)

    def _generate_point(
        self,
        inst: InstitutionProfile,
        tick: int,
        fault: FaultType,
        intensity: float,
        rng: np.random.Generator,
        regime_scale: float = 1.0,
    ) -> TelemetryPoint:
        # Normal diurnal-like smooth civic load wave + mild Gaussian noise
        wave = 1.0 + 0.08 * np.sin(tick / 6.0)
        uptime = float(np.clip(99.85 + rng.normal(0.0, 0.12), 97.5, 100.0))
        latency = float(max(35.0, inst.baseline_latency_ms * wave + rng.normal(0.0, 12.0)))
        error_rate = float(np.clip(inst.baseline_error_rate * wave + rng.normal(0.0, 0.004), 0.001, 0.06))
        auth_failures = int(max(0, round(inst.baseline_auth_failures * wave + rng.normal(0.0, 1.5))))
        queue_len = int(max(0, round(inst.baseline_queue_length * wave + rng.normal(0.0, 2.5))))

        s = intensity * regime_scale

        if fault == FaultType.REQUEST_SPIKE:
            # Cyberattack-like / DDoS request surge: sharp latency, errors, auth spikes, queue burst
            uptime = float(np.clip(uptime - rng.uniform(3.0, 10.0) * s, 55.0, 99.0))
            latency += float(rng.uniform(480.0, 950.0) * s)
            error_rate = float(np.clip(error_rate + rng.uniform(0.18, 0.42) * s, 0.0, 0.98))
            auth_failures += int(rng.uniform(30, 85) * s)
            queue_len += int(rng.uniform(45, 110) * s)

        elif fault == FaultType.AUTH_FAILURE_STORM:
            # Credential/biometric storm (often cyberattack-like or auth subsystem failure)
            uptime = float(np.clip(uptime - rng.uniform(1.0, 4.0) * s, 75.0, 99.5))
            latency += float(rng.uniform(140.0, 320.0) * s)
            error_rate = float(np.clip(error_rate + rng.uniform(0.10, 0.28) * s, 0.0, 0.90))
            auth_failures += int(rng.uniform(65, 150) * s)
            queue_len += int(rng.uniform(22, 55) * s)

        elif fault == FaultType.LINK_DROP:
            # Connectivity deterioration: severe latency & uptime drop, moderate errors, low auth storm
            uptime = float(np.clip(uptime - rng.uniform(12.0, 35.0) * s, 20.0, 95.0))
            latency += float(rng.uniform(750.0, 1750.0) * s)
            error_rate = float(np.clip(error_rate + rng.uniform(0.14, 0.35) * s, 0.0, 0.95))
            auth_failures += int(rng.uniform(4, 14) * s)
            queue_len += int(rng.uniform(18, 45) * s)

        elif fault == FaultType.SERVER_CRASH:
            # Hardware/software crash or human misconfiguration: abrupt uptime loss & 5xx error spike
            uptime = float(np.clip(uptime - rng.uniform(38.0, 85.0) * s, 0.0, 72.0))
            latency += float(rng.uniform(320.0, 820.0) * s)
            error_rate = float(np.clip(error_rate + rng.uniform(0.42, 0.78) * s, 0.0, 1.0))
            auth_failures += int(rng.uniform(2, 10) * s)
            queue_len += int(rng.uniform(35, 85) * s)

        elif fault == FaultType.SUSTAINED_OVERLOAD:
            # Peak-hour civic overload: very high queue & latency, modest error growth, healthy uptime
            uptime = float(np.clip(uptime - rng.uniform(0.5, 3.0) * s, 88.0, 99.8))
            latency += float(rng.uniform(360.0, 740.0) * s)
            error_rate = float(np.clip(error_rate + rng.uniform(0.06, 0.18) * s, 0.0, 0.65))
            auth_failures += int(rng.uniform(5, 18) * s)
            queue_len += int(rng.uniform(65, 145) * s)

        ts = (self.base_time + timedelta(minutes=5 * tick)).isoformat()
        return TelemetryPoint(
            institution_id=inst.institution_id,
            tick=tick,
            timestamp=ts,
            uptime_pct=round(uptime, 2),
            latency_ms=round(latency, 1),
            error_rate=round(error_rate, 4),
            auth_failure_count=auth_failures,
            queue_length=queue_len,
            injected_fault=fault,
        )

    def step(self, steps: int = 1) -> None:
        for _ in range(steps):
            self.current_tick += 1
            for inst_id, inst in self.institutions.items():
                fault, intensity = self.active_faults.get(inst_id, (FaultType.NONE, 1.0))
                pt = self._generate_point(
                    inst=inst,
                    tick=self.current_tick,
                    fault=fault,
                    intensity=intensity,
                    rng=self.rng,
                )
                self.series[inst_id].append(pt)
                if len(self.series[inst_id]) > 120:
                    self.series[inst_id] = self.series[inst_id][-120:]

    def sample_synthetic_fault(
        self,
        inst: InstitutionProfile,
        fault: FaultType,
        intensity: float,
        rng: np.random.Generator,
        regime_scale: float = 1.0,
    ) -> TelemetryPoint:
        """Generate an isolated labeled telemetry sample (used for training/evaluation)."""
        return self._generate_point(
            inst=inst,
            tick=int(rng.integers(1, 200)),
            fault=fault,
            intensity=intensity,
            rng=rng,
            regime_scale=regime_scale,
        )

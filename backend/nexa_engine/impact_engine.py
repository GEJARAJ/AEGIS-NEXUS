"""Layer 4: Citizen Impact Engine.

Implements:
    Impact score = service_capacity * daily_footfall * severity * vulnerability_weight

Outputs a low-to-high affected-citizen range with explicit stated assumptions
and ranks institutions by priority ("which one first?").
"""

from typing import List, Tuple
from .models import AlertLevel, DriftResult, ImpactAssessment, InstitutionProfile, ServiceType


class CitizenImpactEngine:
    """Computes impact scores, low-high citizen ranges, alert levels, and priority ranks."""

    # Normalization factor so raw score stays readable while preserving exact multiplicative proportionality
    SCORE_SCALE = 1000.0

    def compute_raw_impact(self, inst: InstitutionProfile, severity: float) -> float:
        raw = (
            float(inst.service_capacity)
            * float(inst.daily_footfall)
            * float(severity)
            * float(inst.vulnerability_weight)
        )
        return round(raw / self.SCORE_SCALE, 2)

    def estimate_citizen_range(
        self,
        inst: InstitutionProfile,
        severity: float,
        is_anomalous: bool,
    ) -> Tuple[int, int, List[str]]:
        if not is_anomalous or severity <= 0.05:
            return (
                0,
                0,
                [
                    "Service operating within normal baseline; no citizen disruption projected.",
                    f"Aggregate baseline footfall: ~{inst.daily_footfall} citizens/day (illustrative).",
                ],
            )

        # Conservative-to-peak disruption window assumption (4 to 10 operational hours)
        # Bounded by daily_footfall and service_capacity
        effective_load = min(inst.service_capacity, inst.daily_footfall)
        low_factor = max(0.18, 0.35 * severity)
        high_factor = min(1.0, 0.65 * severity + 0.20)

        low_est = int(round(effective_load * low_factor))
        high_est = int(round(max(low_est + 10, inst.service_capacity * high_factor * min(1.15, inst.vulnerability_weight / 1.35))))
        high_est = min(high_est, int(inst.service_capacity * 1.1))

        service_label = (
            "digital patient-registration intake"
            if inst.service_type == ServiceType.HOSPITAL_REGISTRATION
            else "biometric PDS ration authentication & distribution"
        )

        assumptions = [
            f"Assumes disruption impacts {service_label} for a 4-hour (low) to full-shift (high) window.",
            f"Institution profile: capacity={inst.service_capacity}/day, typical anonymized footfall={inst.daily_footfall}/day.",
            f"Service-level vulnerability proxy weight={inst.vulnerability_weight} ({inst.vulnerability_proxy_reason}).",
            "Estimate represents an aggregate simulation range, not an exact citizen headcount.",
        ]
        return low_est, high_est, assumptions

    def classify_alert_level(self, drift: DriftResult, impact_score: float) -> AlertLevel:
        if not drift.is_anomalous:
            return AlertLevel.NORMAL
        if drift.severity >= 0.55 or (drift.severity >= 0.38 and impact_score >= 350.0):
            return AlertLevel.CRITICAL
        return AlertLevel.WARNING

    def assess_and_rank(
        self,
        items: List[Tuple[InstitutionProfile, DriftResult]],
    ) -> List[Tuple[InstitutionProfile, DriftResult, ImpactAssessment, AlertLevel]]:
        preliminary = []
        for inst, drift in items:
            effective_sev = drift.severity if drift.is_anomalous else 0.0
            score = self.compute_raw_impact(inst, effective_sev)
            low, high, assumptions = self.estimate_citizen_range(inst, effective_sev, drift.is_anomalous)
            level = self.classify_alert_level(drift, score)
            preliminary.append((inst, drift, score, low, high, assumptions, level))

        # Sort: Critical first, then Warning, then Normal; within tier by impact_score descending
        tier_order = {AlertLevel.CRITICAL: 0, AlertLevel.WARNING: 1, AlertLevel.NORMAL: 2}
        preliminary.sort(
            key=lambda x: (tier_order[x[6]], -x[2], -x[0].daily_footfall)
        )

        ranked = []
        for rank_idx, (inst, drift, score, low, high, assumptions, level) in enumerate(preliminary, start=1):
            assessment = ImpactAssessment(
                impact_score=score,
                affected_citizens_low=low,
                affected_citizens_high=high,
                priority_rank=rank_idx,
                assumptions=assumptions,
            )
            ranked.append((inst, drift, assessment, level))
        return ranked

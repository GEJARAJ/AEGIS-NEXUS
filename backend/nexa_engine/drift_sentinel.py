"""Layer 2: DriftSentinel — Per-institution baseline drift and anomaly detection."""

from typing import Dict, List
import numpy as np
from sklearn.ensemble import IsolationForest

from .models import DriftResult, InstitutionProfile, SignalContribution, TelemetryPoint


SIGNAL_SPECS = [
    ("uptime_pct", "Service Uptime (%)", -1.0),  # lower uptime = worse
    ("latency_ms", "Response Latency (ms)", 1.0),
    ("error_rate", "Request Error Rate", 1.0),
    ("auth_failure_count", "Authentication Failures", 1.0),
    ("queue_length", "Citizen Service Queue Length", 1.0),
]


class DriftSentinel:
    """Combines per-institution rolling baseline Z-scores with Isolation Forest."""

    def __init__(self, baseline_window: int = 30, z_threshold: float = 2.6):
        self.baseline_window = baseline_window
        self.z_threshold = z_threshold

    @staticmethod
    def _to_vector(pt: TelemetryPoint) -> List[float]:
        return [
            100.0 - pt.uptime_pct,  # convert uptime drop into positive anomaly direction
            pt.latency_ms,
            pt.error_rate,
            float(pt.auth_failure_count),
            float(pt.queue_length),
        ]

    def evaluate(
        self,
        institution: InstitutionProfile,
        history: List[TelemetryPoint],
    ) -> DriftResult:
        if len(history) < 6:
            return DriftResult(
                institution_id=institution.institution_id,
                severity=0.0,
                is_anomalous=False,
                z_score_max=0.0,
                isolation_score=0.0,
                top_contributing_signals=[],
                summary="Insufficient telemetry history to establish baseline.",
            )

        latest = history[-1]
        baseline_pts = history[-(self.baseline_window + 1) : -1]
        if len(baseline_pts) < 5:
            baseline_pts = history[:-1]

        contributions: List[SignalContribution] = []
        directed_z_scores: List[float] = []

        for field_name, label, direction in SIGNAL_SPECS:
            vals = np.array([float(getattr(p, field_name)) for p in baseline_pts], dtype=float)
            curr = float(getattr(latest, field_name))
            mean = float(np.mean(vals))
            # Floor std so ultra-stable baselines do not explode on tiny jitter
            floor_std = {
                "uptime_pct": 0.25,
                "latency_ms": 18.0,
                "error_rate": 0.008,
                "auth_failure_count": 2.2,
                "queue_length": 3.5,
            }[field_name]
            std = max(float(np.std(vals)), floor_std)
            raw_z = (curr - mean) / std
            adverse_z = max(0.0, raw_z * direction)
            directed_z_scores.append(adverse_z)

            if adverse_z >= 1.5:
                pct_delta = ((curr - mean) / max(abs(mean), 1e-3)) * 100.0
                direction_word = "dropped" if direction < 0 else "elevated"
                contributions.append(
                    SignalContribution(
                        signal=label,
                        z_score=round(adverse_z, 2),
                        current_value=round(curr, 3),
                        baseline_mean=round(mean, 3),
                        description=f"{label} {direction_word} ({pct_delta:+.1f}% vs. rolling baseline)",
                    )
                )

        contributions.sort(key=lambda c: c.z_score, reverse=True)
        z_max = float(max(directed_z_scores)) if directed_z_scores else 0.0
        z_mean_top2 = float(np.mean(sorted(directed_z_scores, reverse=True)[:2]))

        # Fit lightweight Isolation Forest on the institution's rolling baseline window
        baseline_matrix = np.array([self._to_vector(p) for p in baseline_pts], dtype=float)
        latest_vec = np.array([self._to_vector(latest)], dtype=float)
        iso = IsolationForest(
            n_estimators=40,
            contamination=0.05,
            random_state=42,
        )
        iso.fit(baseline_matrix)
        raw_iso = float(-iso.decision_function(latest_vec)[0])  # higher = more anomalous
        iso_norm = float(np.clip((raw_iso + 0.05) / 0.35, 0.0, 1.0))

        # Combine statistical z-score severity and isolation score into bounded [0, 1] severity
        z_severity = float(np.clip((z_mean_top2 - 1.4) / 8.5, 0.0, 1.0))
        severity = round(float(np.clip(0.72 * z_severity + 0.28 * iso_norm, 0.0, 1.0)), 3)
        if z_max < self.z_threshold and severity < 0.25:
            severity = round(min(severity, 0.14), 3)

        is_anomalous = z_max >= self.z_threshold or severity >= 0.32

        if not is_anomalous:
            summary = "Operating within expected institutional baseline parameters."
        else:
            top_names = ", ".join(c.signal for c in contributions[:2]) or "multi-signal drift"
            summary = f"Abnormal drift detected driven primarily by {top_names} (max z={z_max:.1f})."

        return DriftResult(
            institution_id=institution.institution_id,
            severity=severity,
            is_anomalous=is_anomalous,
            z_score_max=round(z_max, 2),
            isolation_score=round(iso_norm, 3),
            top_contributing_signals=contributions[:4],
            summary=summary,
        )

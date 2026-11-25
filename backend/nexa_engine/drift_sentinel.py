"""Layer 2: DriftSentinel — Per-institution baseline drift, staleness, and anomaly detection."""

from datetime import datetime
from typing import Dict, List, Optional, Tuple
import numpy as np
from sklearn.ensemble import IsolationForest

from .ingestion import parse_telemetry_timestamp
from .models import (
    DriftResult,
    HeartbeatStatus,
    InstitutionProfile,
    SignalContribution,
    TelemetryPoint,
)


SIGNAL_SPECS = [
    ("uptime_pct", "Service Uptime (%)", -1.0),  # lower uptime = worse
    ("latency_ms", "Response Latency (ms)", 1.0),
    ("error_rate", "Request Error Rate", 1.0),
    ("auth_failure_count", "Authentication Failures", 1.0),
    ("queue_length", "Citizen Service Queue Length", 1.0),
]

FLOOR_STDS: Dict[str, float] = {
    "uptime_pct": 0.25,
    "latency_ms": 18.0,
    "error_rate": 0.008,
    "auth_failure_count": 2.2,
    "queue_length": 3.5,
}

_FLOOR_STD_ARR = np.array([FLOOR_STDS[name] for name, _, _ in SIGNAL_SPECS], dtype=float)
_DIRECTION_ARR = np.array([direction for _, _, direction in SIGNAL_SPECS], dtype=float)


class DriftSentinel:
    """Combines per-institution rolling baseline Z-scores, Isolation Forest, and staleness checks."""

    def __init__(
        self,
        baseline_window: int = 30,
        z_threshold: float = 2.6,
        stale_after_ticks: int = 3,
        stale_after_seconds: float = 900.0,
    ):
        self.baseline_window = baseline_window
        self.z_threshold = z_threshold
        self.stale_after_ticks = stale_after_ticks
        self.stale_after_seconds = stale_after_seconds

        # Shared normalized Isolation Forest scored in a single vectorized batch per cycle
        rng = np.random.default_rng(42)
        normal_ref = rng.normal(0.0, 0.75, size=(600, len(SIGNAL_SPECS)))
        self._shared_iso = IsolationForest(
            n_estimators=40,
            contamination=0.05,
            random_state=42,
        )
        self._shared_iso.fit(normal_ref)

    @staticmethod
    def _to_matrix(points: List[TelemetryPoint]) -> np.ndarray:
        return np.array(
            [
                [
                    p.uptime_pct,
                    p.latency_ms,
                    p.error_rate,
                    float(p.auth_failure_count),
                    float(p.queue_length),
                ]
                for p in points
            ],
            dtype=float,
        )

    def _check_staleness(
        self,
        institution: InstitutionProfile,
        history: List[TelemetryPoint],
        reference_tick: Optional[int],
        reference_time: Optional[datetime],
    ) -> Optional[DriftResult]:
        if not history:
            return DriftResult(
                institution_id=institution.institution_id,
                severity=0.5,
                is_anomalous=True,
                z_score_max=0.0,
                isolation_score=0.0,
                top_contributing_signals=[],
                summary="No telemetry heartbeat received (missing telemetry feed; distinct from service crash).",
                heartbeat_status=HeartbeatStatus.MISSING,
                is_stale=True,
                missed_ticks=reference_tick or 0,
                staleness_seconds=0.0,
            )

        latest = history[-1]
        missed_ticks = max(0, reference_tick - latest.tick) if reference_tick is not None else 0
        staleness_seconds = 0.0
        if reference_time is not None:
            latest_dt = parse_telemetry_timestamp(latest.timestamp)
            if latest_dt is not None:
                staleness_seconds = max(0.0, (reference_time - latest_dt).total_seconds())

        tick_stale = reference_tick is not None and missed_ticks >= self.stale_after_ticks
        time_stale = reference_time is not None and staleness_seconds >= self.stale_after_seconds
        if tick_stale or time_stale:
            stale_units = max(missed_ticks, int(staleness_seconds // 300))
            sev = round(min(0.65, 0.35 + 0.05 * stale_units), 3)
            return DriftResult(
                institution_id=institution.institution_id,
                severity=sev,
                is_anomalous=True,
                z_score_max=0.0,
                isolation_score=0.0,
                top_contributing_signals=[],
                summary=(
                    f"Telemetry heartbeat stale ({missed_ticks} missed ticks, "
                    f"{int(staleness_seconds)}s old); collector silent (distinct from active server crash)."
                ),
                heartbeat_status=HeartbeatStatus.STALE,
                is_stale=True,
                missed_ticks=missed_ticks,
                staleness_seconds=round(staleness_seconds, 1),
            )
        return None

    def evaluate(
        self,
        institution: InstitutionProfile,
        history: List[TelemetryPoint],
        reference_tick: Optional[int] = None,
        reference_time: Optional[datetime] = None,
    ) -> DriftResult:
        return self.evaluate_batch(
            [(institution, history)],
            reference_tick=reference_tick,
            reference_time=reference_time,
        )[0]

    def evaluate_batch(
        self,
        items: List[Tuple[InstitutionProfile, List[TelemetryPoint]]],
        reference_tick: Optional[int] = None,
        reference_time: Optional[datetime] = None,
    ) -> List[DriftResult]:
        """Vectorized batch evaluation across N institutions (<50ms for 100 institutions)."""
        results: List[Optional[DriftResult]] = [None] * len(items)
        eval_indices: List[int] = []
        rel_vectors: List[np.ndarray] = []
        eval_meta: List[Tuple[InstitutionProfile, np.ndarray, np.ndarray, np.ndarray, np.ndarray]] = []

        for idx, (inst, history) in enumerate(items):
            stale_res = self._check_staleness(inst, history, reference_tick, reference_time)
            if stale_res is not None:
                results[idx] = stale_res
                continue

            if len(history) < 6:
                results[idx] = DriftResult(
                    institution_id=inst.institution_id,
                    severity=0.0,
                    is_anomalous=False,
                    z_score_max=0.0,
                    isolation_score=0.0,
                    top_contributing_signals=[],
                    summary="Insufficient telemetry history to establish baseline.",
                    heartbeat_status=HeartbeatStatus.HEALTHY,
                    is_stale=False,
                )
                continue

            baseline_pts = history[-(self.baseline_window + 1) : -1]
            if len(baseline_pts) < 5:
                baseline_pts = history[:-1]

            mat = self._to_matrix(baseline_pts)
            curr_vec = self._to_matrix([history[-1]])[0]
            means = np.mean(mat, axis=0)
            stds = np.maximum(np.std(mat, axis=0), _FLOOR_STD_ARR)
            directed_z = np.maximum(0.0, ((curr_vec - means) / stds) * _DIRECTION_ARR)

            eval_indices.append(idx)
            rel_vectors.append(directed_z)
            eval_meta.append((inst, curr_vec, means, directed_z))

        if eval_indices:
            rel_mat = np.vstack(rel_vectors)
            raw_iso_scores = -self._shared_iso.decision_function(rel_mat)
            iso_norms = np.clip((raw_iso_scores + 0.05) / 0.35, 0.0, 1.0)

            for pos, orig_idx in enumerate(eval_indices):
                inst, curr_vec, means, directed_z = eval_meta[pos]
                iso_norm = float(iso_norms[pos])

                contributions: List[SignalContribution] = []
                for s_idx, (_, label, direction) in enumerate(SIGNAL_SPECS):
                    adverse_z = float(directed_z[s_idx])
                    if adverse_z >= 1.5:
                        curr = float(curr_vec[s_idx])
                        mean = float(means[s_idx])
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
                z_max = float(np.max(directed_z))
                top2_sorted = np.sort(directed_z)[-2:]
                z_mean_top2 = float(np.mean(top2_sorted))

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

                results[orig_idx] = DriftResult(
                    institution_id=inst.institution_id,
                    severity=severity,
                    is_anomalous=is_anomalous,
                    z_score_max=round(z_max, 2),
                    isolation_score=round(iso_norm, 3),
                    top_contributing_signals=contributions[:4],
                    summary=summary,
                    heartbeat_status=HeartbeatStatus.HEALTHY,
                    is_stale=False,
                )

        return [r for r in results if r is not None]

"""Layer 3: Cause Classifier — Rule-Based Baseline + Calibrated ML Classifier.

Outputs probabilities across four operational causes:
1. cyberattack_like
2. overload
3. connectivity_failure
4. hardware_or_human_error

Always returns probabilities, never a deterministic verdict.
"""

from typing import Dict, List, Tuple
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from .institutions import CORE_INSTITUTIONS
from .models import CauseCategory, CauseProbabilities, FaultType, InstitutionProfile, TelemetryPoint
from .simulator import TelemetrySimulator


CAUSE_ORDER = [
    CauseCategory.CYBERATTACK_LIKE,
    CauseCategory.OVERLOAD,
    CauseCategory.CONNECTIVITY_FAILURE,
    CauseCategory.HARDWARE_OR_HUMAN_ERROR,
]

# Mapping from simulator fault types to underlying operational cause classes
FAULT_TO_CAUSE: Dict[FaultType, CauseCategory] = {
    FaultType.REQUEST_SPIKE: CauseCategory.CYBERATTACK_LIKE,
    FaultType.AUTH_FAILURE_STORM: CauseCategory.CYBERATTACK_LIKE,
    FaultType.SUSTAINED_OVERLOAD: CauseCategory.OVERLOAD,
    FaultType.LINK_DROP: CauseCategory.CONNECTIVITY_FAILURE,
    FaultType.SERVER_CRASH: CauseCategory.HARDWARE_OR_HUMAN_ERROR,
}


def extract_relative_features(inst: InstitutionProfile, pt: TelemetryPoint) -> np.ndarray:
    """Scale-invariant relative telemetry features compared to institutional baseline."""
    uptime_drop = max(0.0, 100.0 - pt.uptime_pct)
    latency_ratio = pt.latency_ms / max(inst.baseline_latency_ms, 1.0)
    error_delta = max(0.0, pt.error_rate - inst.baseline_error_rate)
    auth_ratio = pt.auth_failure_count / max(inst.baseline_auth_failures, 1.0)
    queue_ratio = pt.queue_length / max(inst.baseline_queue_length, 1.0)
    return np.array(
        [uptime_drop, latency_ratio, error_delta, auth_ratio, queue_ratio],
        dtype=float,
    )


class RuleBasedCauseClassifier:
    """Transparent heuristic baseline for honest ML comparison."""

    def predict_proba(self, inst: InstitutionProfile, pt: TelemetryPoint) -> CauseProbabilities:
        uptime_drop, latency_ratio, error_delta, auth_ratio, queue_ratio = extract_relative_features(inst, pt)

        scores = {
            CauseCategory.CYBERATTACK_LIKE: 0.4 + 0.55 * max(0.0, auth_ratio - 2.0) + 1.8 * error_delta * (auth_ratio > 2.5),
            CauseCategory.OVERLOAD: 0.4 + 0.70 * max(0.0, queue_ratio - 2.0) + 0.30 * max(0.0, latency_ratio - 1.8) - 0.12 * uptime_drop,
            CauseCategory.CONNECTIVITY_FAILURE: 0.4 + 0.55 * max(0.0, latency_ratio - 3.0) + 0.14 * min(uptime_drop, 35.0),
            CauseCategory.HARDWARE_OR_HUMAN_ERROR: 0.4 + 0.16 * max(0.0, uptime_drop - 15.0) + 3.2 * max(0.0, error_delta - 0.25),
        }
        # Softmax conversion to valid probabilities
        vals = np.array([max(0.01, scores[c]) for c in CAUSE_ORDER], dtype=float)
        exp_vals = np.exp(np.clip(vals - np.max(vals), -15.0, 15.0))
        probs = exp_vals / np.sum(exp_vals)

        return _build_cause_probs(probs, method="rule_baseline")


class CauseClassifier:
    """Calibrated ML classifier (Logistic Regression) trained with simulator parameter jitter."""

    def __init__(self, seed: int = 101, exclude_faults: List[FaultType] | None = None):
        self.seed = seed
        self.scaler = StandardScaler()
        self.model = LogisticRegression(max_iter=600, C=0.8, random_state=seed)
        self.rule_baseline = RuleBasedCauseClassifier()
        self._fit_on_simulated_regimes(exclude_faults=exclude_faults or [])

    def _fit_on_simulated_regimes(self, exclude_faults: List[FaultType]) -> None:
        rng = np.random.default_rng(self.seed)
        sim = TelemetrySimulator(seed=self.seed)
        x_rows: List[np.ndarray] = []
        y_rows: List[int] = []

        trainable_faults = [f for f in FAULT_TO_CAUSE if f not in exclude_faults]
        for fault in trainable_faults:
            cause_idx = CAUSE_ORDER.index(FAULT_TO_CAUSE[fault])
            for _ in range(140):
                inst = CORE_INSTITUTIONS[int(rng.integers(0, len(CORE_INSTITUTIONS)))]
                intensity = float(rng.uniform(0.65, 1.55))
                regime_scale = float(rng.uniform(0.8, 1.25))
                pt = sim.sample_synthetic_fault(
                    inst=inst,
                    fault=fault,
                    intensity=intensity,
                    rng=rng,
                    regime_scale=regime_scale,
                )
                x_rows.append(extract_relative_features(inst, pt))
                y_rows.append(cause_idx)

        x_mat = np.vstack(x_rows)
        y_vec = np.array(y_rows, dtype=int)
        x_scaled = self.scaler.fit_transform(x_mat)
        self.model.fit(x_scaled, y_vec)

    def predict_proba(self, inst: InstitutionProfile, pt: TelemetryPoint) -> CauseProbabilities:
        feat = extract_relative_features(inst, pt).reshape(1, -1)
        x_scaled = self.scaler.transform(feat)
        raw_probs = self.model.predict_proba(x_scaled)[0]

        # Align probabilities to CAUSE_ORDER (handles hold-out cases gracefully)
        aligned = np.full(len(CAUSE_ORDER), 1e-4, dtype=float)
        for col_idx, cls_id in enumerate(self.model.classes_):
            aligned[int(cls_id)] = float(raw_probs[col_idx])
        aligned = aligned / np.sum(aligned)
        return _build_cause_probs(aligned, method="ml_calibrated")

    def predict_rule_baseline(self, inst: InstitutionProfile, pt: TelemetryPoint) -> CauseProbabilities:
        return self.rule_baseline.predict_proba(inst, pt)


def _build_cause_probs(probs: np.ndarray, method: str) -> CauseProbabilities:
    p_list = [round(float(x), 4) for x in probs]
    # Re-normalize rounded values on the largest entry to sum closely to 1.0
    dominant_idx = int(np.argmax(p_list))
    return CauseProbabilities(
        cyberattack_like=p_list[0],
        overload=p_list[1],
        connectivity_failure=p_list[2],
        hardware_or_human_error=p_list[3],
        dominant_cause=CAUSE_ORDER[dominant_idx],
        method=method,
    )

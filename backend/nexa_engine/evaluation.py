"""Honest Simulation Validation & Benchmark Suite (Section 9).

Reports:
1. DriftSentinel detection precision, recall, false alarm rate, and mean time to detect.
2. CauseClassifier accuracy and Brier probability calibration vs. rule-based baseline,
   including hold-out fault type testing (so ML does not memorize simulator constants).
3. CitizenImpactEngine ranking agreement (Spearman rank correlation) against hand-built ground truth.
"""

from typing import Dict, List
import numpy as np
from scipy.stats import spearmanr

from .cause_classifier import CAUSE_ORDER, CauseClassifier, FAULT_TO_CAUSE, RuleBasedCauseClassifier
from .drift_sentinel import DriftSentinel
from .impact_engine import CitizenImpactEngine
from .institutions import CORE_INSTITUTIONS
from .models import CauseCategory, FaultType
from .simulator import TelemetrySimulator


def evaluate_detection(seed: int = 77) -> Dict[str, float]:
    """Evaluate DriftSentinel precision, recall, false alarm rate, and time-to-detect."""
    sim = TelemetrySimulator(seed=seed, history_ticks=32)
    sentinel = DriftSentinel(baseline_window=28, z_threshold=2.6)

    tp = fp = tn = fn = 0
    detection_delays: List[int] = []

    # 1. Measure normal baseline false alarms over 15 ticks across all 23 institutions
    for _ in range(15):
        sim.step(1)
        for inst_id, inst in sim.institutions.items():
            res = sentinel.evaluate(inst, sim.series[inst_id])
            if res.is_anomalous:
                fp += 1
            else:
                tn += 1

    # 2. Inject faults into 10 distinct institution episodes and measure detection & time-to-detect
    test_episodes = [
        ("HOSP-01", FaultType.REQUEST_SPIKE),
        ("HOSP-02", FaultType.LINK_DROP),
        ("HOSP-03", FaultType.SERVER_CRASH),
        ("PDS-01", FaultType.AUTH_FAILURE_STORM),
        ("PDS-03", FaultType.SUSTAINED_OVERLOAD),
        ("PDS-05", FaultType.LINK_DROP),
        ("PDS-08", FaultType.REQUEST_SPIKE),
        ("PDS-11", FaultType.AUTH_FAILURE_STORM),
        ("PDS-14", FaultType.SERVER_CRASH),
        ("PDS-18", FaultType.SUSTAINED_OVERLOAD),
    ]

    for inst_id, fault in test_episodes:
        sim.reset(seed=seed + hash(inst_id) % 100)
        sim.inject_fault(inst_id, fault, intensity=1.0)
        detected_at = None
        for tick_offset in range(1, 6):
            sim.step(1)
            res = sentinel.evaluate(sim.institutions[inst_id], sim.series[inst_id])
            if res.is_anomalous:
                tp += 1
                if detected_at is None:
                    detected_at = tick_offset
            else:
                fn += 1
        if detected_at is not None:
            detection_delays.append(detected_at)

    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    false_alarm_rate = fp / max(fp + tn, 1)
    mean_ttd_ticks = float(np.mean(detection_delays)) if detection_delays else 0.0

    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "false_alarm_rate": round(false_alarm_rate, 4),
        "mean_time_to_detect_ticks": round(mean_ttd_ticks, 2),
        "episodes_detected": len(detection_delays),
        "episodes_total": len(test_episodes),
    }


def _brier_multiclass(probs_list: List[np.ndarray], true_indices: List[int]) -> float:
    total = 0.0
    for probs, t_idx in zip(probs_list, true_indices):
        one_hot = np.zeros_like(probs)
        one_hot[t_idx] = 1.0
        total += float(np.sum((probs - one_hot) ** 2))
    return total / max(len(true_indices), 1)


def evaluate_cause_classification(seed: int = 202) -> Dict[str, object]:
    """Compare ML classifier vs rule-based baseline, including hold-out fault type testing."""
    rng = np.random.default_rng(seed)
    sim = TelemetrySimulator(seed=seed)

    ml_clf = CauseClassifier(seed=101)
    rule_clf = RuleBasedCauseClassifier()

    ml_correct = rule_correct = 0
    ml_probs_all: List[np.ndarray] = []
    rule_probs_all: List[np.ndarray] = []
    true_indices: List[int] = []

    # Test on shifted simulator parameters (regime_scale != 1.0) so test differs from training
    for fault, cause in FAULT_TO_CAUSE.items():
        true_idx = CAUSE_ORDER.index(cause)
        for _ in range(40):
            inst = CORE_INSTITUTIONS[int(rng.integers(0, len(CORE_INSTITUTIONS)))]
            pt = sim.sample_synthetic_fault(
                inst=inst,
                fault=fault,
                intensity=float(rng.uniform(0.75, 1.45)),
                rng=rng,
                regime_scale=float(rng.uniform(0.85, 1.2)),
            )
            p_ml = ml_clf.predict_proba(inst, pt)
            p_rule = rule_clf.predict_proba(inst, pt)

            if p_ml.dominant_cause == cause:
                ml_correct += 1
            if p_rule.dominant_cause == cause:
                rule_correct += 1

            ml_probs_all.append(np.array([
                p_ml.cyberattack_like,
                p_ml.overload,
                p_ml.connectivity_failure,
                p_ml.hardware_or_human_error,
            ]))
            rule_probs_all.append(np.array([
                p_rule.cyberattack_like,
                p_rule.overload,
                p_rule.connectivity_failure,
                p_rule.hardware_or_human_error,
            ]))
            true_indices.append(true_idx)

    n_total = len(true_indices)

    # Hold-out fault type test: train WITHOUT AUTH_FAILURE_STORM, test ON AUTH_FAILURE_STORM
    # Both REQUEST_SPIKE and AUTH_FAILURE_STORM map to cyberattack_like, testing generalization across fault forms
    holdout_clf = CauseClassifier(seed=101, exclude_faults=[FaultType.AUTH_FAILURE_STORM])
    holdout_ml_hits = 0
    holdout_rule_hits = 0
    holdout_n = 50
    for _ in range(holdout_n):
        inst = CORE_INSTITUTIONS[int(rng.integers(0, len(CORE_INSTITUTIONS)))]
        pt = sim.sample_synthetic_fault(
            inst=inst,
            fault=FaultType.AUTH_FAILURE_STORM,
            intensity=float(rng.uniform(0.8, 1.35)),
            rng=rng,
            regime_scale=1.05,
        )
        if holdout_clf.predict_proba(inst, pt).dominant_cause == CauseCategory.CYBERATTACK_LIKE:
            holdout_ml_hits += 1
        if rule_clf.predict_proba(inst, pt).dominant_cause == CauseCategory.CYBERATTACK_LIKE:
            holdout_rule_hits += 1

    return {
        "ml_accuracy": round(ml_correct / n_total, 4),
        "rule_baseline_accuracy": round(rule_correct / n_total, 4),
        "ml_brier_score": round(_brier_multiclass(ml_probs_all, true_indices), 4),
        "rule_baseline_brier_score": round(_brier_multiclass(rule_probs_all, true_indices), 4),
        "holdout_fault_test": {
            "held_out_fault": FaultType.AUTH_FAILURE_STORM.value,
            "ml_accuracy_on_unseen_fault": round(holdout_ml_hits / holdout_n, 4),
            "rule_baseline_accuracy": round(holdout_rule_hits / holdout_n, 4),
        },
    }


def evaluate_impact_ranking() -> Dict[str, object]:
    """Verify CitizenImpactEngine ranking agreement against hand-built priority ground truth."""
    engine = CitizenImpactEngine()

    # Hand-built civic triage ordering across 5 representative scenarios (highest urgency first)
    scenarios = [
        # 1. Referral hospital critical outage (highest capacity + footfall + vulnerability weight + high severity)
        ("HOSP-01", 0.85, 1),
        # 2. Sub-district hospital severe disruption
        ("HOSP-02", 0.72, 2),
        # 3. Rural high-need ration depot severe disruption
        ("PDS-03", 0.78, 3),
        # 4. Urban ration shop moderate warning
        ("PDS-20", 0.42, 4),
        # 5. Rural ration shop minor warning
        ("PDS-07", 0.30, 5),
    ]

    inst_map = {inst.institution_id: inst for inst in CORE_INSTITUTIONS}
    scores = []
    expected_ranks = []
    for inst_id, sev, expected_rank in scenarios:
        scores.append(engine.compute_raw_impact(inst_map[inst_id], sev))
        expected_ranks.append(expected_rank)

    # Convert scores to predicted ranks (1 = highest score)
    order = np.argsort(-np.array(scores))
    predicted_ranks = [0] * len(scores)
    for r, idx in enumerate(order, start=1):
        predicted_ranks[idx] = r

    corr, _ = spearmanr(expected_ranks, predicted_ranks)
    return {
        "spearman_rank_correlation": round(float(corr), 4),
        "expected_ranks": expected_ranks,
        "predicted_ranks": predicted_ranks,
        "exact_match": expected_ranks == predicted_ranks,
    }


def run_full_evaluation() -> Dict[str, object]:
    return {
        "disclaimer": "All evaluation metrics are strictly simulation-based using fixed seeds and shifted test parameters.",
        "detection": evaluate_detection(),
        "cause_classification": evaluate_cause_classification(),
        "impact_ranking": evaluate_impact_ranking(),
    }


if __name__ == "__main__":
    import json
    print(json.dumps(run_full_evaluation(), indent=2))

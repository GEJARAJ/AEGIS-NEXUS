# NEXA ENGINE — Simulation & Evaluation Methodology

## 1. Honest Simulation Design
Because live government telemetry is not publicly available and requires formal authorization, all validation runs against a **deterministic, fixed-seed operational telemetry simulator**.

### Core District Scope (Hard-Frozen)
- **3 Government Hospitals** (digital patient-registration systems)
- **20 Ration Distribution Centres** (biometric authentication & PDS connectivity)

### Injected Fault Modes
1. `request_spike` — DDoS-like abnormal request surge and queue saturation
2. `auth_failure_storm` — Repeated biometric/portal authentication failures
3. `link_drop` — Connectivity deterioration, high latency, and intermittent drops
4. `server_crash` — Registration/application service unavailability & 5xx spike
5. `sustained_overload` — Gradual queue & latency buildup during peak civic hours

## 2. Evaluation Rules
1. **State plainly that all results are simulation-based.**
2. **Hold-out fault validation:** Entire fault scenarios/parameter regimes are held out between training and testing so the ML classifier does not memorize simulator constants.
3. **Rule-based baseline comparison:** Every ML classifier metric is reported alongside a transparent rule-based baseline.
4. **Metrics tracked:**
   - Detection Precision, Recall, F1, and False Alarm Rate
   - Mean Time to Detect (ticks)
   - Cause-Classification Accuracy & Brier Probability Calibration Score (ML vs. Rule Baseline)
   - Impact-Ranking Agreement (Spearman rank correlation against hand-built ground-truth priority)

## 3. Known Limitations
- Synthetic telemetry cannot capture all real-world institutional network topologies, seasonal civic spikes (e.g., monthly ration distribution rush days), or multi-vendor hardware quirks.
- Thresholds and calibration weights will require re-tuning on authorized, anonymized pilot telemetry prior to any district trial.

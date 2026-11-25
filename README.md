# AEGIS NEXUS — Civic Sentinel

**AI-Powered Public Infrastructure Intelligence and Citizen Impact Early Warning System**  
*Protecting services. Preventing disruption. Prioritizing people.*  
**Technical Engine:** `NEXA ENGINE` | **Status:** Simulation-Based Working Prototype

---

> **Governance & Simulation Notice:**  
> All telemetry, dashboard figures, cause probabilities, and citizen-impact ranges in this repository are **simulation-based and illustrative**. Real-world deployment requires formal **government authorization** and a signed **data-sharing agreement**. Civic Sentinel is designed as a **complementary citizen-impact and service-continuity layer** sitting on top of existing cybersecurity and operations monitoring systems (such as **CERT-In**, **NCCC**, **NCIIPC**, **I4C**, and **Cyber Swachhta Kendra**).

---

## 1. Overview: The Citizen-Impact Layer

Technical failures become social emergencies when essential public services stop functioning — whether caused by cyberattacks, infrastructure faults, connectivity drops, system overload, or human error.

**Civic Sentinel** answers four operational questions for a District Administration using **authorized, privacy-preserving, aggregate-only telemetry**:
1. **Which public service is degrading?**
2. **Does the disruption resemble a cyberattack or a technical/operational failure?** *(Probabilistic estimate, never a verdict)*
3. **Roughly how many citizens could be affected?** *(Low-to-high range with stated assumptions)*
4. **What action should happen first?** *(Impact-ranked priority + offline-continuity playbook)*

---

## 2. Scope & Architecture

### Committed Scope (Hard-Frozen Working Core)
- **Core Scope (Active):** One simulated district with two critical service types:
  - **3 Government Hospitals** (digital patient-registration systems)
  - **20 Ration Distribution Centres** (biometric authentication & PDS connectivity)
- **Extension Scope (Roadmap):** Government schools, municipal water/service-request offices, citizen digital portals.
- **Future Scope (Authorization-Gated):** Multi-district federation and integration with state/national CERT workflows.

### Five-Layer `NEXA ENGINE` Pipeline

```text
[1. Telemetry Ingestion]      Aggregate-only: uptime, latency, error_rate, auth_failures, queue_length (Zero PII)
           │
           ▼
[2. DriftSentinel (Layer 2)]  Per-institution rolling baseline + Z-score + Isolation Forest anomaly & drift scoring
           │
           ▼
[3. Cause Classifier]         Rule-based baseline + calibrated ML probabilities across 4 causes:
           │                  (cyberattack-like | overload | connectivity_failure | hardware_or_human_error)
           ▼
[4. Citizen Impact Engine]    Impact = service_capacity × daily_footfall × severity × vulnerability_weight
           │                  Outputs ranked priority + low-to-high affected-citizen range + stated assumptions
           ▼
[5. Action & Coordination]    Critical/Warning/Normal alerts, Offline-Continuity Playbook,
                              Department routing, Official Acknowledgement & Restoration Tracking
```

---

## 3. Repository Structure

```text
AEGIS-NEXUS/
├── backend/
│   ├── app/
│   │   └── main.py                 # FastAPI server & REST endpoints + static portal mount
│   └── nexa_engine/
│       ├── models.py               # Pydantic data contracts (zero-PII telemetry & alerts)
│       ├── institutions.py         # Core district registry (3 hospitals + 20 ration centres)
│       ├── simulator.py            # Deterministic, fixed-seed telemetry & fault-injection simulator
│       ├── drift_sentinel.py       # Layer 2: Per-institution baseline + Z-score & Isolation Forest
│       ├── cause_classifier.py     # Layer 3: Rule-based baseline + calibrated ML cause probabilities
│       ├── impact_engine.py        # Layer 4: Citizen Impact formula, range estimator & ranking
│       ├── playbook.py             # Layer 5: Offline-continuity playbooks & governance workflow
│       └── evaluation.py           # Honest hold-out fault evaluation & baseline comparison
├── frontend/                       # Government-themed Civic Command Portal (HTML/CSS/JS)
│   ├── index.html
│   ├── css/gov-theme.css
│   └── js/app.js
├── docs/
│   ├── PRIVACY_AND_GOVERNANCE.md
│   └── EVALUATION_METHODOLOGY.md
├── tests/                          # Pytest suite for NEXA ENGINE & FastAPI routes
├── run.py                          # One-command launcher for the portal & API
├── requirements.txt
└── pyproject.toml
```

---

## 4. Quickstart

### Prerequisites
- Python 3.10+

### Install & Run
```bash
pip install -r requirements.txt
python run.py
```
Then open **`http://127.0.0.1:8000`** in your browser to access the **AEGIS NEXUS — District Civic Resilience Portal**.

### Run the Demo Scenario (Section 12 Flow)
Inside the portal, click **"Run Hospital Failure Demo"** (or call `POST /api/demo/scenario/hospital-failure`) to observe:
1. Normal baseline operation across all 23 core institutions.
2. Injection of a registration-system degradation at a Government Hospital.
3. `DriftSentinel` flagging abnormal request failures and connectivity/queue deterioration.
4. `CauseClassifier` emitting probabilistic breakdown across overload, connectivity failure, and cyberattack-like patterns.
5. `CitizenImpactEngine` escalating the hospital to **Critical (Rank #1)** with an estimated affected-citizen range and assumptions.
6. Automatic triggering of the **Offline-Continuity Playbook** (manual registration & alternate service desk routing).
7. Human-in-the-loop **Acknowledgement** and **Restoration Tracking** by the responsible department official.

### Run Tests & Honest Simulation Evaluation
```bash
pytest
python -m backend.nexa_engine.evaluation
```

---

## 5. Claims & Governance Guardrails

| Appropriate Claim | Avoid Saying |
| :--- | :--- |
| Adds a citizen-impact layer on top of existing monitoring systems | *"India has no cyber monitoring"* |
| Cause classifier outputs probabilities validated on simulation | *"Detects cyberattacks with X% real-world accuracy"* |
| Estimated impact range under stated assumptions | *"Exact number of citizens affected"* |
| Dashboard figures are simulation-based and illustrative | Presenting dashboard metrics as live government data |
| Deployment requires government authorization & data-sharing agreements | *"Ready for immediate government rollout"* |

---

## 6. License
Released under the [MIT License](LICENSE).

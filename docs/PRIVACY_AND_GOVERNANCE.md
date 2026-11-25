# AEGIS NEXUS — Privacy, Ethics & Governance Policy

> **Prototype Status Notice:** AEGIS NEXUS (Civic Sentinel / NEXA ENGINE) is a **simulation-based research and demonstration prototype**. All operational telemetry and dashboard figures are synthetic/illustrative unless connected to an explicitly authorized government feed.

## 1. Deployment Prerequisite
Real-world operation requires:
1. Formal **government administrative authorization** (District Collectorate / State IT & Sectoral Departments).
2. Signed **data-sharing and telemetry-minimization agreements** specifying allowed aggregate endpoints.
3. Alignment with existing national cybersecurity institutions (**CERT-In, NCCC, NCIIPC, I4C, Cyber Swachhta Kendra**).

## 2. Data Minimization by Design
- **Permitted signals:** Service uptime percentage, API/endpoint response latency (ms), HTTP/system error rates, aggregate authentication failure counts, and aggregate queue lengths.
- **Prohibited signals:** Citizen names, Aadhaar/ration card IDs, patient health records, IP addresses of citizens, biometric templates, or any personally identifiable information (PII).

## 3. Non-Profiling Vulnerability Weighting
- Vulnerability weights use **service-level institutional proxies** only (e.g., whether an institution is a rural Fair Price Shop serving high beneficiary volume, or a district hospital emergency registration desk).
- No individual or household profiling is performed anywhere in the pipeline.

## 4. Human-in-the-Loop Authority
- The system **recommends** priority ranks, cause probabilities, and pre-approved offline-continuity playbooks.
- **Authorized government officials** verify alerts, acknowledge incidents, trigger manual/offline continuity protocols, and confirm service restoration.

## 5. Explainability & Honest Claims
- Every alert exposes top contributing telemetry signals, impact calculation assumptions, and probabilistic cause estimates (never a deterministic verdict).
- Impact outputs are always presented as a **low-to-high citizen range** with documented assumptions.

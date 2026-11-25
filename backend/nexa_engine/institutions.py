"""Core District Registry (Hard-Frozen Scope: 3 Government Hospitals + 20 Ration Centres)."""

from typing import Dict, List
from .models import InstitutionProfile, ServiceType

# Service-level proxy table for vulnerability weighting (never individual profiling)
VULNERABILITY_PROXY_TABLE: Dict[str, Dict[str, object]] = {
    "hospital_referral_emergency": {
        "weight": 1.65,
        "proxy_reason": "District referral hospital with high emergency & maternal registration load",
    },
    "hospital_subdistrict": {
        "weight": 1.45,
        "proxy_reason": "Sub-district hospital serving rural & semi-urban outpatient queues",
    },
    "ration_rural_high_need": {
        "weight": 1.50,
        "proxy_reason": "Rural Fair Price Shop (PDS) serving high proportion of priority household beneficiaries",
    },
    "ration_periurban": {
        "weight": 1.30,
        "proxy_reason": "Peri-urban ration centre with high daily migrant/worker footfall",
    },
    "ration_urban": {
        "weight": 1.15,
        "proxy_reason": "Urban ration distribution centre with nearby alternate PDS outlets",
    },
}

CORE_INSTITUTIONS: List[InstitutionProfile] = [
    # --- 3 Government Hospitals (Core Scope) ---
    InstitutionProfile(
        institution_id="HOSP-01",
        name="District General Hospital — Central Registration Wing",
        service_type=ServiceType.HOSPITAL_REGISTRATION,
        zone="Urban",
        service_capacity=1400,
        daily_footfall=1180,
        vulnerability_weight=1.65,
        vulnerability_proxy_reason=str(VULNERABILITY_PROXY_TABLE["hospital_referral_emergency"]["proxy_reason"]),
        responsible_department="District Health & Family Welfare / NIC e-Hospital Cell",
        alternate_centre="District Hospital Block-B Manual Triage Desk & CHC North Wing",
        baseline_latency_ms=145.0,
        baseline_error_rate=0.012,
        baseline_auth_failures=4.0,
        baseline_queue_length=18.0,
    ),
    InstitutionProfile(
        institution_id="HOSP-02",
        name="Sub-District Hospital (East Block) — OPD Registration",
        service_type=ServiceType.HOSPITAL_REGISTRATION,
        zone="Semi-Urban",
        service_capacity=850,
        daily_footfall=690,
        vulnerability_weight=1.45,
        vulnerability_proxy_reason=str(VULNERABILITY_PROXY_TABLE["hospital_subdistrict"]["proxy_reason"]),
        responsible_department="District Health & Family Welfare / Sub-Divisional Medical Officer",
        alternate_centre="East Block Paper Slip Counter & Primary Health Centre #4",
        baseline_latency_ms=160.0,
        baseline_error_rate=0.015,
        baseline_auth_failures=3.0,
        baseline_queue_length=14.0,
    ),
    InstitutionProfile(
        institution_id="HOSP-03",
        name="Maternal & Child Government Hospital — Patient Intake",
        service_type=ServiceType.HOSPITAL_REGISTRATION,
        zone="Urban",
        service_capacity=720,
        daily_footfall=580,
        vulnerability_weight=1.65,
        vulnerability_proxy_reason=str(VULNERABILITY_PROXY_TABLE["hospital_referral_emergency"]["proxy_reason"]),
        responsible_department="District Health & Family Welfare / Maternal Care Unit",
        alternate_centre="Maternal Emergency Paper Register & District General Hospital Wing",
        baseline_latency_ms=150.0,
        baseline_error_rate=0.014,
        baseline_auth_failures=3.0,
        baseline_queue_length=12.0,
    ),
]

# --- 20 Ration Distribution Centres (Core Scope) ---
_RATION_SPECS = [
    ("PDS-01", "FPS-01 Kaveri Nagar Ration Centre", "Rural", "ration_rural_high_need", 460, 390),
    ("PDS-02", "FPS-02 Palayam Fair Price Shop", "Rural", "ration_rural_high_need", 440, 375),
    ("PDS-03", "FPS-03 Melur Block Ration Depot", "Rural", "ration_rural_high_need", 500, 420),
    ("PDS-04", "FPS-04 Vallam Rural PDS Outlet", "Rural", "ration_rural_high_need", 410, 340),
    ("PDS-05", "FPS-05 Thiruvaiyaru Grama Ration Unit", "Rural", "ration_rural_high_need", 480, 405),
    ("PDS-06", "FPS-06 Orathanadu East Fair Price Shop", "Rural", "ration_rural_high_need", 430, 355),
    ("PDS-07", "FPS-07 Sengipatti Cooperative Ration Centre", "Rural", "ration_rural_high_need", 390, 325),
    ("PDS-08", "FPS-08 Budalur Junction Ration Depot", "Semi-Urban", "ration_periurban", 520, 430),
    ("PDS-09", "FPS-09 Peravurani Market PDS Centre", "Semi-Urban", "ration_periurban", 510, 415),
    ("PDS-10", "FPS-10 Pattukkottai West Ration Shop", "Semi-Urban", "ration_periurban", 560, 450),
    ("PDS-11", "FPS-11 Adirampattinam Coastal PDS Unit", "Rural", "ration_rural_high_need", 495, 425),
    ("PDS-12", "FPS-12 Madukkur Grama Fair Price Shop", "Rural", "ration_rural_high_need", 420, 350),
    ("PDS-13", "FPS-13 Nanjikottai Ward-4 Ration Centre", "Semi-Urban", "ration_periurban", 530, 440),
    ("PDS-14", "FPS-14 Gandarvakottai Border PDS Shop", "Rural", "ration_rural_high_need", 405, 335),
    ("PDS-15", "FPS-15 Ammapettai Cooperative Ration Depot", "Semi-Urban", "ration_periurban", 490, 400),
    ("PDS-16", "FPS-16 Papanasam Town Fair Price Shop", "Semi-Urban", "ration_periurban", 540, 445),
    ("PDS-17", "FPS-17 Kumbakonam South PDS Centre", "Urban", "ration_urban", 620, 480),
    ("PDS-18", "FPS-18 Medical College Road Ration Unit", "Urban", "ration_urban", 590, 455),
    ("PDS-19", "FPS-19 Railway Colony Urban PDS Shop", "Urban", "ration_urban", 610, 470),
    ("PDS-20", "FPS-20 Central Market Ward-12 Ration Centre", "Urban", "ration_urban", 650, 510),
]

for idx, (inst_id, name, zone, proxy_key, cap, footfall) in enumerate(_RATION_SPECS, start=1):
    proxy_info = VULNERABILITY_PROXY_TABLE[proxy_key]
    next_id = f"PDS-{(idx % 20) + 1:02d}"
    CORE_INSTITUTIONS.append(
        InstitutionProfile(
            institution_id=inst_id,
            name=name,
            service_type=ServiceType.RATION_DISTRIBUTION,
            zone=zone,
            service_capacity=cap,
            daily_footfall=footfall,
            vulnerability_weight=float(proxy_info["weight"]),
            vulnerability_proxy_reason=str(proxy_info["proxy_reason"]),
            responsible_department="District Civil Supplies & Consumer Protection (PDS Cell)",
            alternate_centre=f"Nearest Backup Outlet ({next_id}) & Manual Ration Register Ledger",
            baseline_latency_ms=190.0 + (idx % 4) * 15.0,
            baseline_error_rate=0.018,
            baseline_auth_failures=6.0 + (idx % 3),
            baseline_queue_length=10.0 + (idx % 5),
        )
    )

EXTENSION_SECTORS: List[Dict[str, str]] = [
    {
        "sector": "Government Schools",
        "scope_stage": "Extension Scope (Phase 2)",
        "example_signal": "Digital learning infrastructure & attendance sync uptime",
        "status": "Planned — excluded from hard-frozen core",
    },
    {
        "sector": "Municipal Services",
        "scope_stage": "Extension Scope (Phase 2)",
        "example_signal": "Water-management & civic grievance portal latency",
        "status": "Planned — excluded from hard-frozen core",
    },
    {
        "sector": "Government Digital Portals",
        "scope_stage": "Extension Scope (Phase 2)",
        "example_signal": "Certificate & welfare portal request failure rate",
        "status": "Planned — excluded from hard-frozen core",
    },
    {
        "sector": "State & National CERT Integration",
        "scope_stage": "Future Scope (Authorization-Gated)",
        "example_signal": "Multi-district escalation workflows with CERT-In / State SOC",
        "status": "Subject to formal government authorization",
    },
]

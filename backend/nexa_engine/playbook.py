"""Layer 5: Action & Coordination — Offline-Continuity Playbooks & Human-in-the-Loop Workflow."""

from datetime import datetime, timezone
from typing import Dict, Optional

from .models import (
    AlertLevel,
    AlertWorkflowState,
    InstitutionProfile,
    PlaybookAction,
    ServiceType,
    WorkflowStatus,
)


class PlaybookEngine:
    """Recommends pre-approved offline-continuity actions and tracks official acknowledgement."""

    def __init__(self) -> None:
        self._workflows: Dict[str, AlertWorkflowState] = {}

    def build_playbook(self, inst: InstitutionProfile, level: AlertLevel) -> Optional[PlaybookAction]:
        if level == AlertLevel.NORMAL:
            return None

        triggered = level == AlertLevel.CRITICAL
        if inst.service_type == ServiceType.HOSPITAL_REGISTRATION:
            steps = [
                "Activate pre-approved manual paper-token OPD registration ledger at intake desk.",
                "Prioritize emergency & maternal triage queue bypass independent of digital portal.",
                f"Route overflow non-emergency registrations to {inst.alternate_centre}.",
                "Notify NIC / e-Hospital district nodal officer for parallel technical triage (no PII shared).",
            ]
            title = "Hospital Digital Registration Offline-Continuity Protocol"
            pb_id = f"PB-HOSP-{inst.institution_id}"
        else:
            steps = [
                "Authorize offline ration distribution register with verified beneficiary card reconciliation.",
                "Issue timestamped offline disbursement slips for deferred biometric sync once link stabilizes.",
                f"Redirect walk-in overflow if needed to {inst.alternate_centre}.",
                "Dispatch PDS technical support alert to District Civil Supplies Cell.",
            ]
            title = "PDS Ration Centre Offline-Continuity Protocol"
            pb_id = f"PB-PDS-{inst.institution_id}"

        return PlaybookAction(
            playbook_id=pb_id,
            title=title,
            triggered=triggered,
            department=inst.responsible_department,
            alternate_centre=inst.alternate_centre,
            immediate_steps=steps,
            requires_official_approval=True,
        )

    def get_workflow(self, alert_id: str) -> AlertWorkflowState:
        return self._workflows.get(alert_id, AlertWorkflowState())

    def update_workflow(
        self,
        alert_id: str,
        status: WorkflowStatus,
        official_name: str,
        notes: Optional[str] = None,
    ) -> AlertWorkflowState:
        state = AlertWorkflowState(
            status=status,
            acknowledged_by=official_name.strip() or "District Duty Officer",
            updated_at=datetime.now(timezone.utc).isoformat(),
            notes=notes,
        )
        self._workflows[alert_id] = state
        return state

    def reset(self) -> None:
        self._workflows.clear()

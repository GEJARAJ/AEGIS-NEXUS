"""Layer 5: Action & Coordination — Offline-Continuity Playbooks, Deduplication & Cooldowns."""

from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

from .models import (
    AlertLevel,
    AlertWorkflowState,
    InstitutionProfile,
    PlaybookAction,
    ServiceType,
    WorkflowStatus,
)

_LEVEL_TIER = {
    AlertLevel.NORMAL: 0,
    AlertLevel.WARNING: 1,
    AlertLevel.CRITICAL: 2,
}


class _CooldownRecord:
    """Internal per-alert deduplication and severity-escalation tracking."""

    def __init__(
        self,
        last_level: AlertLevel,
        last_severity: float,
        cooldown_until_tick: int,
        last_evaluated_tick: int,
    ) -> None:
        self.last_level = last_level
        self.last_severity = last_severity
        self.cooldown_until_tick = cooldown_until_tick
        self.last_evaluated_tick = last_evaluated_tick
        self.suppressed_duplicates = 0


class PlaybookEngine:
    """Recommends pre-approved continuity actions and tracks acknowledgement & alert cooldowns."""

    def __init__(self, cooldown_ticks: int = 5, escalation_delta: float = 0.15) -> None:
        self.cooldown_ticks = cooldown_ticks
        self.escalation_delta = escalation_delta
        self._workflows: Dict[str, AlertWorkflowState] = {}
        self._cooldowns: Dict[str, _CooldownRecord] = {}

    def evaluate_dispatch(
        self,
        alert_id: str,
        level: AlertLevel,
        severity: float,
        current_tick: int,
    ) -> Tuple[bool, str]:
        """Return (should_notify, reason) enforcing cooldown suppression unless severity escalates."""
        if level == AlertLevel.NORMAL:
            return False, "normal_baseline"

        wf = self._workflows.get(alert_id)
        rec = self._cooldowns.get(alert_id)
        if wf is None or rec is None or wf.status not in (WorkflowStatus.ACKNOWLEDGED, WorkflowStatus.MITIGATING):
            return True, "new_alert"

        if current_tick < rec.cooldown_until_tick:
            tier_escalated = _LEVEL_TIER[level] > _LEVEL_TIER[rec.last_level]
            severity_escalated = severity >= rec.last_severity + self.escalation_delta
            if tier_escalated or severity_escalated:
                rec.last_level = level
                rec.last_severity = severity
                rec.cooldown_until_tick = current_tick + self.cooldown_ticks
                rec.last_evaluated_tick = current_tick
                wf.cooldown_active = True
                wf.last_dispatch_reason = "severity_escalated"
                return True, "severity_escalated"

            if current_tick > rec.last_evaluated_tick:
                rec.suppressed_duplicates += 1
                rec.last_evaluated_tick = current_tick
            wf.cooldown_active = True
            wf.suppressed_duplicates = rec.suppressed_duplicates
            wf.last_dispatch_reason = "cooldown_suppressed"
            return False, "cooldown_suppressed"

        # Cooldown window expired; permit re-notification and refresh window
        rec.last_level = level
        rec.last_severity = severity
        rec.cooldown_until_tick = current_tick + self.cooldown_ticks
        rec.last_evaluated_tick = current_tick
        wf.cooldown_active = True
        wf.last_dispatch_reason = "cooldown_expired"
        return True, "cooldown_expired"

    def build_playbook(
        self,
        inst: InstitutionProfile,
        level: AlertLevel,
        alert_id: Optional[str] = None,
        severity: float = 0.0,
        current_tick: int = 0,
    ) -> Optional[PlaybookAction]:
        if level == AlertLevel.NORMAL:
            return None

        triggered = level == AlertLevel.CRITICAL
        if alert_id is not None:
            should_notify, _ = self.evaluate_dispatch(
                alert_id=alert_id,
                level=level,
                severity=severity,
                current_tick=current_tick,
            )
            triggered = triggered and should_notify

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
        current_tick: int = 0,
        severity: float = 0.0,
        level: AlertLevel = AlertLevel.NORMAL,
    ) -> AlertWorkflowState:
        if status in (WorkflowStatus.ACKNOWLEDGED, WorkflowStatus.MITIGATING):
            existing = self._cooldowns.get(alert_id)
            rec = _CooldownRecord(
                last_level=level,
                last_severity=severity,
                cooldown_until_tick=current_tick + self.cooldown_ticks,
                last_evaluated_tick=current_tick,
            )
            if existing is not None:
                rec.suppressed_duplicates = existing.suppressed_duplicates
            self._cooldowns[alert_id] = rec
            cooldown_active = True
            suppressed = rec.suppressed_duplicates
            reason = "acknowledged_cooldown_started"
        elif status == WorkflowStatus.RESTORED:
            self._cooldowns.pop(alert_id, None)
            cooldown_active = False
            suppressed = 0
            reason = "restored"
        else:
            self._cooldowns.pop(alert_id, None)
            cooldown_active = False
            suppressed = 0
            reason = "reopened"

        state = AlertWorkflowState(
            status=status,
            acknowledged_by=official_name.strip() or "District Duty Officer",
            updated_at=datetime.now(timezone.utc).isoformat(),
            notes=notes,
            cooldown_active=cooldown_active,
            suppressed_duplicates=suppressed,
            last_dispatch_reason=reason,
        )
        self._workflows[alert_id] = state
        return state

    def reset(self) -> None:
        self._workflows.clear()
        self._cooldowns.clear()

"""Layer 1 Ingestion: TelemetrySource interface and LiveTelemetryCollector."""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional, Tuple

from .models import InstitutionProfile, TelemetryIngestBatch, TelemetryPoint


def parse_telemetry_timestamp(raw_ts: str) -> Optional[datetime]:
    """Parse an ISO-8601 telemetry timestamp into a UTC-aware datetime."""
    if not raw_ts:
        return None
    try:
        normalized = raw_ts.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


class TelemetrySource(ABC):
    """Abstract interface separating simulated feeds from live telemetry collectors."""

    @property
    @abstractmethod
    def institutions(self) -> Dict[str, InstitutionProfile]:
        """Mapping of institution_id to InstitutionProfile."""

    @property
    @abstractmethod
    def current_tick(self) -> int:
        """Current logical reference tick of the telemetry source."""

    @property
    @abstractmethod
    def reference_time(self) -> datetime:
        """Current UTC reference clock of the telemetry source."""

    @abstractmethod
    def get_history(self, institution_id: str, limit: Optional[int] = None) -> List[TelemetryPoint]:
        """Return ordered aggregate telemetry history for an institution."""

    @abstractmethod
    def get_latest(self, institution_id: str) -> Optional[TelemetryPoint]:
        """Return the latest aggregate telemetry point for an institution, if any."""

    def collect_batch(self) -> List[Tuple[InstitutionProfile, List[TelemetryPoint]]]:
        """Collect current (institution, history) pairs for all registered institutions."""
        return [
            (inst, self.get_history(inst_id))
            for inst_id, inst in self.institutions.items()
        ]


class LiveTelemetryCollector(TelemetrySource):
    """In-memory collector for live aggregate-only telemetry with strict zero-PII validation."""

    def __init__(
        self,
        institutions: Iterable[InstitutionProfile] | Dict[str, InstitutionProfile],
        max_history: int = 120,
        initial_time: Optional[datetime] = None,
    ) -> None:
        if isinstance(institutions, dict):
            self._institutions: Dict[str, InstitutionProfile] = dict(institutions)
        else:
            self._institutions = {inst.institution_id: inst for inst in institutions}
        self._max_history = max_history
        self._series: Dict[str, List[TelemetryPoint]] = {
            inst_id: [] for inst_id in self._institutions
        }
        self._current_tick = 0
        self._reference_time = initial_time or datetime.now(timezone.utc)

    @property
    def institutions(self) -> Dict[str, InstitutionProfile]:
        return self._institutions

    @property
    def current_tick(self) -> int:
        return self._current_tick

    @property
    def reference_time(self) -> datetime:
        return self._reference_time

    def get_history(self, institution_id: str, limit: Optional[int] = None) -> List[TelemetryPoint]:
        if institution_id not in self._series:
            raise KeyError(f"Unknown institution_id: {institution_id}")
        pts = self._series[institution_id]
        return pts[-limit:] if limit is not None else pts

    def get_latest(self, institution_id: str) -> Optional[TelemetryPoint]:
        pts = self.get_history(institution_id)
        return pts[-1] if pts else None

    def ingest(self, payload: TelemetryIngestBatch | Dict[str, object]) -> int:
        """Validate (rejecting extra/PII fields) and append aggregate telemetry points."""
        batch = (
            payload
            if isinstance(payload, TelemetryIngestBatch)
            else TelemetryIngestBatch.model_validate(payload)
        )
        accepted = 0
        for pt in batch.points:
            if pt.institution_id not in self._institutions:
                raise ValueError(f"Unknown institution_id: {pt.institution_id}")
            buf = self._series[pt.institution_id]
            buf.append(pt)
            if len(buf) > self._max_history:
                self._series[pt.institution_id] = buf[-self._max_history :]
            if pt.tick > self._current_tick:
                self._current_tick = pt.tick
            parsed_dt = parse_telemetry_timestamp(pt.timestamp)
            if parsed_dt is not None and parsed_dt > self._reference_time:
                self._reference_time = parsed_dt
            accepted += 1
        return accepted

    def advance_clock(self, ticks: int = 1, seconds: float = 300.0) -> None:
        """Advance reference tick and timestamp (allows heartbeat staleness detection)."""
        self._current_tick += max(0, ticks)
        self._reference_time = self._reference_time + timedelta(seconds=max(0.0, seconds))

    def reset(self) -> None:
        self._series = {inst_id: [] for inst_id in self._institutions}
        self._current_tick = 0

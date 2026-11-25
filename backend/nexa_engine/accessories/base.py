"""Base contracts and interface for modular NEXA ENGINE resilience accessories."""

from abc import ABC, abstractmethod
from pydantic import BaseModel, Field


class AccessoryMetadata(BaseModel):
    """Descriptive metadata for a pluggable cybersecurity or resilience accessory."""

    accessory_id: str
    name: str
    category: str
    version: str = "0.1.0"
    description: str
    is_simulation_only: bool = True
    zero_pii: bool = True


class AccessoryStatus(BaseModel):
    """Runtime status snapshot for an accessory."""

    metadata: AccessoryMetadata
    active: bool = False
    active_items: int = Field(default=0, ge=0)
    total_runs: int = Field(default=0, ge=0)


class ResilienceAccessory(ABC):
    """Abstract base class for modular, non-invasive NEXA ENGINE accessories."""

    @property
    @abstractmethod
    def metadata(self) -> AccessoryMetadata:
        """Return immutable metadata describing the accessory."""

    @abstractmethod
    def status(self) -> AccessoryStatus:
        """Return the current runtime status of the accessory."""

    @abstractmethod
    def reset(self) -> None:
        """Reset any accessory-local state back to baseline."""

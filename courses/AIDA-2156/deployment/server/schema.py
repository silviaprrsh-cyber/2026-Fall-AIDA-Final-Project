"""Common types and safe wire constants for the read-only Red Deer study service."""
from dataclasses import dataclass
from datetime import datetime, timezone
import math

UTC = timezone.utc
FLOWS = {
    "05CB007": "Dickson Dam Tunnel Outlet",
    "05CB001": "Little Red Deer River near the Mouth",
    "05CC007": "Medicine River near Eckville",
    "05CC002": "Red Deer River at Red Deer",
}
RAIN_ID = "3025484"
RAIN_NAME = "Red Deer Regional A"
WARNING = ("Academic research only. Do not use for real flood warnings, emergency response or safety decisions. "
           "Depths use a different, unvalidated live router; P01–P05 are unverified latent values "
           "and P06 is a gauge-derived terminal depth proxy, not a measured depth or a validated forecast.")

def aware(d: datetime) -> datetime:
    if not isinstance(d, datetime) or d.tzinfo is None or d.utcoffset() is None:
        raise ValueError("An aware timestamp is required")
    return d.astimezone(UTC)

def iso(d: datetime | None) -> str | None:
    return aware(d).isoformat(timespec="seconds").replace("+00:00", "Z") if d is not None else None

@dataclass(frozen=True, slots=True)
class Observation:
    station_id: str
    kind: str
    observed_at: datetime
    retrieved_at: datetime
    value: float
    source: str
    period_seconds: int | None = None
    available_at: datetime | None = None

    def __post_init__(self):
        allowed = self.station_id in FLOWS if self.kind == "flow" else self.station_id == RAIN_ID if self.kind == "rain" else False
        if not allowed or isinstance(self.value, bool) or not math.isfinite(self.value) or self.value < 0:
            raise ValueError("Invalid observation station/kind/value")
        if not isinstance(self.source, str) or not self.source or len(self.source) > 150:
            raise ValueError("Invalid source")
        if self.kind == "rain" and self.period_seconds != 3600:
            raise ValueError("The configured airport product must be hourly")
        if self.kind == "flow" and self.period_seconds is not None:
            raise ValueError("Flow is an instantaneous observation")
        a, b = aware(self.observed_at), aware(self.retrieved_at)
        if a > b:
            raise ValueError("Observed time must not follow its receipt")
        if self.available_at is not None:
            aware(self.available_at)

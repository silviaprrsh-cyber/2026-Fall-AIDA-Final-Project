"""Isolated observation stores for live routing; schema creation is opt-in."""

from datetime import datetime
from math import isfinite
import json
import os

from .schema import Observation


SCHEMA = "rdr_live_v1"
DSN_ENV = "RDR_DEPLOYMENT_DSN"

_CREATE = f"""
CREATE TABLE IF NOT EXISTS {SCHEMA}.observation_versions (
    version_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    station_id text NOT NULL CHECK (station_id <> ''),
    kind text NOT NULL CHECK (kind IN ('flow', 'rain')),
    observed_at timestamptz NOT NULL,
    retrieved_at timestamptz NOT NULL CHECK (retrieved_at >= observed_at),
    value double precision NOT NULL
        CHECK (value > '-Infinity'::double precision AND value < 'Infinity'::double precision),
    source text NOT NULL CHECK (source <> ''),
    period_seconds integer CHECK (period_seconds > 0),
    available_at timestamptz CHECK (available_at >= observed_at),
    UNIQUE NULLS NOT DISTINCT (
        kind, station_id, observed_at, retrieved_at, source, value, period_seconds, available_at
    )
);
"""

_CREATE_SNAPSHOT = f"""
CREATE TABLE IF NOT EXISTS {SCHEMA}.current_snapshot (
    singleton boolean PRIMARY KEY CHECK (singleton),
    generated_at timestamptz NOT NULL,
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object')
)
"""

_SAVE_SNAPSHOT = f"""
INSERT INTO {SCHEMA}.current_snapshot AS current (singleton, generated_at, payload)
VALUES (TRUE, %s, %s::jsonb)
ON CONFLICT (singleton) DO UPDATE
SET generated_at = EXCLUDED.generated_at, payload = EXCLUDED.payload
WHERE current.generated_at < EXCLUDED.generated_at
"""

_INSERT = f"""
WITH incoming(station_id, kind, observed_at, retrieved_at, value, source, period_seconds, available_at) AS (
    VALUES (%s::text, %s::text, %s::timestamptz, %s::timestamptz, %s::double precision, %s::text, %s::integer, %s::timestamptz)
), latest AS (
    SELECT old.retrieved_at, old.value, old.source, old.period_seconds, old.available_at
    FROM incoming i
    JOIN {SCHEMA}.observation_versions old
      ON (old.kind, old.station_id, old.observed_at) = (i.kind, i.station_id, i.observed_at)
    ORDER BY old.retrieved_at DESC, old.version_id DESC
    LIMIT 1
)
INSERT INTO {SCHEMA}.observation_versions (
    station_id, kind, observed_at, retrieved_at, value, source, period_seconds, available_at
)
SELECT i.* FROM incoming i
WHERE NOT EXISTS (
    SELECT 1 FROM latest l WHERE l.retrieved_at <= i.retrieved_at
      AND (l.value, l.source, l.period_seconds, l.available_at)
          IS NOT DISTINCT FROM (i.value, i.source, i.period_seconds, i.available_at)
)
ON CONFLICT DO NOTHING
"""

_READ = f"""
SELECT station_id, kind, observed_at, retrieved_at, value, source, period_seconds, available_at
FROM (
    SELECT DISTINCT ON (kind, station_id, observed_at)
           station_id, kind, observed_at, retrieved_at, value, source, period_seconds, available_at
    FROM {SCHEMA}.observation_versions
    WHERE observed_at >= %s AND observed_at <= %s AND retrieved_at <= %s
      AND (available_at IS NULL OR available_at <= %s)
    ORDER BY kind, station_id, observed_at, retrieved_at DESC, version_id DESC
) AS visible
ORDER BY observed_at, kind, station_id
"""


def _aware(value: datetime, name: str) -> None:
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError(f"{name} must be a timezone-aware datetime")


def _validated(row: Observation) -> tuple:
    _aware(row.observed_at, "observed_at")
    _aware(row.retrieved_at, "retrieved_at")
    if row.available_at is not None:
        _aware(row.available_at, "available_at")
    if row.retrieved_at < row.observed_at or (
        row.available_at is not None and row.available_at < row.observed_at
    ):
        raise ValueError("retrieval/release cannot precede the observation")
    if row.kind not in ("flow", "rain") or not row.station_id or not row.source:
        raise ValueError("invalid observation kind, station or source")
    if row.period_seconds is not None and (
        type(row.period_seconds) is not int or not 0 < row.period_seconds <= 2_147_483_647
    ):
        raise ValueError("period_seconds must be a positive PostgreSQL integer")
    value = float(row.value)
    if not isfinite(value):
        raise ValueError("observation value must be finite")
    return (
        row.station_id, row.kind, row.observed_at, row.retrieved_at, value,
        row.source, row.period_seconds, row.available_at,
    )


def _check_range(since: datetime, as_of: datetime) -> None:
    _aware(since, "since")
    _aware(as_of, "as_of")
    if as_of < since:
        raise ValueError("as_of cannot precede since")


def _snapshot_values(snapshot: dict) -> tuple[datetime, str]:
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("generated_at"), str):
        raise ValueError("snapshot requires an ISO-8601 generated_at string")
    at = datetime.fromisoformat(snapshot["generated_at"].replace("Z", "+00:00"))
    _aware(at, "generated_at")
    return at, json.dumps(snapshot, allow_nan=False)


class PgStore:
    """Psycopg 3 store. Import/construct/read/save never initialize the schema."""

    def __init__(self, dsn: str | None = None):
        self._dsn = dsn or os.environ.get(DSN_ENV)
        if not self._dsn:
            raise ValueError(f"{DSN_ENV} is required for PostgreSQL")

    def _connection(self):
        try:
            import psycopg
        except ImportError:
            raise RuntimeError("Deployment PostgreSQL requires psycopg 3") from None
        try:
            return psycopg.connect(self._dsn, connect_timeout=5)
        except psycopg.Error:
            raise RuntimeError("Cannot connect to the deployment PostgreSQL database") from None

    def initialize(self) -> None:
        """Call only in response to explicit --init-db. Requires PostgreSQL 15+."""
        with self._connection() as conn, conn.cursor() as cur:
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
            cur.execute(_CREATE)
            cur.execute(_CREATE_SNAPSHOT)
            cur.execute(
                f"CREATE INDEX IF NOT EXISTS observation_versions_latest_idx "
                f"ON {SCHEMA}.observation_versions "
                f"(kind, station_id, observed_at, retrieved_at DESC, version_id DESC)"
            )
            cur.execute(
                f"CREATE INDEX IF NOT EXISTS observation_versions_observed_idx "
                f"ON {SCHEMA}.observation_versions (observed_at)"
            )

    def save(self, rows: list[Observation]) -> None:
        # Compaction assumes receipts arrive chronologically for a given key.
        # Older distinct receipts are kept if visible, but a skipped duplicate
        # cannot later be recovered if a different historical value is backfilled.
        params = sorted((_validated(row) for row in rows), key=lambda row: row[3])
        if params:
            with self._connection() as conn, conn.cursor() as cur:
                # Fixed namespace + per-stream key, acquired in one sorted order.
                for stream in sorted({r[1] + ":" + r[0] for r in params}):
                    cur.execute("SELECT pg_advisory_xact_lock(519087221, hashtext(%s))", (stream,))
                cur.executemany(_INSERT, params)

    def read(self, since: datetime, as_of: datetime) -> list[Observation]:
        _check_range(since, as_of)
        with self._connection() as conn, conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute(_READ, (since, as_of, as_of, as_of))
            return [Observation(
                station_id=r[0], kind=r[1], observed_at=r[2], retrieved_at=r[3],
                value=r[4], source=r[5], period_seconds=r[6], available_at=r[7],
            ) for r in cur.fetchall()]

    def save_snapshot(self, snapshot: dict) -> None:
        with self._connection() as conn, conn.cursor() as cur:
            cur.execute(_SAVE_SNAPSHOT, _snapshot_values(snapshot))

    def load_snapshot(self) -> dict | None:
        with self._connection() as conn, conn.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
            cur.execute(f"SELECT payload FROM {SCHEMA}.current_snapshot WHERE singleton")
            row = cur.fetchone()
            return row[0] if row is not None else None


class MemoryStore:
    """In-memory demo implementing PostgreSQL visibility and tie rules."""

    def __init__(self):
        self._versions = {}
        self._latest = {}
        self._snapshot = None

    def initialize(self) -> None:
        pass

    def save(self, rows: list[Observation]) -> None:
        for record in sorted((_validated(row) for row in rows), key=lambda row: row[3]):
            key = record[:3]
            latest = self._latest.get(key)
            if latest is not None and latest[3] <= record[3] and latest[4:] == record[4:]:
                continue
            if record not in self._versions:
                self._versions[record] = None
                if latest is None or record[3] >= latest[3]:
                    self._latest[key] = record

    def read(self, since: datetime, as_of: datetime) -> list[Observation]:
        _check_range(since, as_of)
        visible = {}
        for row in self._versions:
            station, kind, observed, receipt, _, _, _, release = row
            if not since <= observed <= as_of or receipt > as_of or (
                release is not None and release > as_of
            ):
                continue
            key = (observed, kind, station)
            if key not in visible or receipt >= visible[key][3]:
                visible[key] = row
        return [Observation(
            station_id=r[0], kind=r[1], observed_at=r[2], retrieved_at=r[3],
            value=r[4], source=r[5], period_seconds=r[6], available_at=r[7],
        ) for r in (visible[key] for key in sorted(visible))]

    def save_snapshot(self, snapshot: dict) -> None:
        value = _snapshot_values(snapshot)
        if self._snapshot is None or value[0] > self._snapshot[0]:
            self._snapshot = value

    def load_snapshot(self) -> dict | None:
        return json.loads(self._snapshot[1]) if self._snapshot is not None else None

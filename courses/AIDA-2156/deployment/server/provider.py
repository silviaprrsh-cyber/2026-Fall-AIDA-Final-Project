"""Bounded, observation-only adapter for the fixed public ECCC GeoMet endpoints."""
import json
import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

if __package__:
    try:
        from .schema import Observation
    except ModuleNotFoundError as exc:
        if exc.name != __package__ + ".schema":
            raise
        Observation = None
else:
    try:
        from schema import Observation
    except ModuleNotFoundError as exc:
        if exc.name != "schema":
            raise
        Observation = None

if Observation is None:
    @dataclass(frozen=True)
    class Observation:
        station_id: str
        kind: str
        observed_at: datetime
        retrieved_at: datetime
        value: float
        source: str
        period_seconds: int | None = None
        available_at: datetime | None = None

UTC = timezone.utc
HYDRO_IDS = ("05CB007", "05CB001", "05CC007", "05CC002")
RAIN_ID = "3025484"
ROOT = "https://api.weather.gc.ca/collections/"
HYDRO = "hydrometric-realtime"
RAIN = "climate-hourly"
MAX_BYTES = 8 * 1024 * 1024
_LEVEL_LOCK = Lock()
_RECENT_LEVELS: dict[str, dict[datetime, float]] = {}


def get_recent_levels(as_of: datetime, hours: int = 48) -> dict[str, list[list]]:
    """Return cached ECCC real-time water level (m, assumed datum) series for the last `hours`."""
    end = as_of.astimezone(UTC)
    begin = end - timedelta(hours=hours)
    out: dict[str, list[list]] = {}
    with _LEVEL_LOCK:
        for sid, series in _RECENT_LEVELS.items():
            pts = [[at.strftime("%Y-%m-%dT%H:%M:%SZ"), round(val, 3)]
                   for at, val in sorted(series.items()) if begin <= at <= end]
            if pts:
                out[sid] = pts
    return out


def _time(value, *, explicit_utc=True):
    if not isinstance(value, str):
        raise ValueError("timestamp must be a string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        if explicit_utc:
            raise ValueError("observation requires explicit UTC offset")
        return parsed.replace(tzinfo=UTC)
    if parsed.utcoffset() != timedelta(0):
        raise ValueError("observation requires UTC")
    return parsed.astimezone(UTC)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def _request(collection, query, timeout):
    request = Request(ROOT + collection + "/items?" + urlencode(query),
                      headers={"Accept": "application/geo+json, application/json",
                               "User-Agent": "RDP-Red-Deer-Hydro-Prototype/1.0"})
    with build_opener(_NoRedirect()).open(request, timeout=timeout) as response:
        body = response.read(MAX_BYTES + 1)
    received = datetime.now(UTC)
    if len(body) > MAX_BYTES:
        raise ValueError("response exceeds byte budget")
    return json.loads(body), received


def parse_page(obj, collection, station, start, end, received):
    """Pure parser, useful for archived or synthetic fixtures."""
    if not isinstance(obj, dict) or obj.get("type") != "FeatureCollection":
        raise ValueError("not a feature collection")
    features = obj.get("features")
    if not isinstance(features, list):
        raise ValueError("invalid feature list")
    if any(link.get("rel") == "next" for link in obj.get("links", [])):
        raise ValueError("page truncated; do not report it as complete")
    matched = obj.get("numberMatched")
    if isinstance(matched, int) and matched > len(features):
        raise ValueError("page truncated")
    rain = collection == RAIN
    if not rain and collection != HYDRO:
        raise ValueError("unknown weather collection")
    out, conflicts = {}, set()
    for feature in features:
        p = feature["properties"]
        field, tf, vf = (("CLIMATE_IDENTIFIER", "UTC_DATE", "PRECIP_AMOUNT") if rain
                         else ("STATION_NUMBER", "DATETIME", "DISCHARGE"))
        if p.get(field) != station:
            raise ValueError("provider did not honor fixed station filter")
        at = _time(p[tf], explicit_utc=not rain)
        if not start <= at <= end:
            continue
        if not rain:
            lv = p.get("LEVEL")
            if not isinstance(lv, bool) and isinstance(lv, (int, float)) and math.isfinite(lv):
                with _LEVEL_LOCK:
                    bucket = _RECENT_LEVELS.setdefault(station, {})
                    bucket[at] = float(lv)
                    if len(bucket) > 1200:
                        cutoff = sorted(bucket.keys())[-1000]
                        for old_k in [k for k in bucket if k < cutoff]:
                            del bucket[old_k]
        if rain and (at.minute or at.second or at.microsecond):
            raise ValueError("rain has non-hourly clock")
        v = p.get(vf)
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0:
            continue  # Missing is absence, never an invented zero.
        if rain and p.get("PRECIP_AMOUNT_FLAG") not in (None, ""):
            continue
        # Processing timestamps are not retrieval; preserve as provenance if explicitly
        # supplied with this observation. Do not assume DATETIME_LST is processing time.
        processing = p.get("PROCESSED_DATE_TM") or p.get("processed_date_tm")
        processed_at = None
        if isinstance(processing, str):
            try:
                processed_at = _time(processing)
            except ValueError:
                pass
        # Retrieval is enforced independently at issue time. Release signals stay
        # stable across overlapping polls so unchanged rows deduplicate honestly.
        available = max(at + timedelta(hours=1) if rain else at, processed_at or at)
        source = ROOT + collection + "/items"
        if processed_at is not None:
            source += "#provider_processed_at=" + processed_at.isoformat()
        row = Observation(station_id=station, kind="rain" if rain else "flow",
                          observed_at=at, retrieved_at=received, value=float(v),
                          source=source, period_seconds=3600 if rain else None,
                          available_at=available)
        previous = out.get(at)
        if previous is not None and previous.value != row.value:
            conflicts.add(at)
        if previous is None or previous.available_at < row.available_at:
            out[at] = row
    if conflicts:
        raise ValueError("conflicting provider values at identical source clock")
    return sorted(out.values(), key=lambda row: row.observed_at)


def _flow(station, begin, end, timeout):
    rows = []
    start = begin
    while start <= end:
        stop = min(start + timedelta(hours=72), end)
        query = {"f": "json", "limit": 1000, "STATION_NUMBER": station,
                 "sortby": "-DATETIME", "datetime": start.isoformat() + "/" + stop.isoformat()}
        page, received = _request(HYDRO, query, timeout)
        rows.extend(parse_page(page, HYDRO, station, start, stop, received))
        start = stop + timedelta(microseconds=1)
    return rows


def _rain(begin, end, timeout):
    # Provider LOCAL_YEAR/MONTH is Alberta standard time, UTC-07:00.
    month_keys = {(p.year, p.month) for p in (begin - timedelta(hours=7), end - timedelta(hours=7))}
    rows = []
    for year, month in sorted(month_keys):
        page, received = _request(RAIN, {"f":"json", "limit":1000,
                                 "CLIMATE_IDENTIFIER":RAIN_ID, "LOCAL_YEAR":year,
                                 "LOCAL_MONTH":month}, timeout)
        rows.extend(parse_page(page, RAIN, RAIN_ID, begin, end, received))
    return rows


def poll(now: datetime, history_hours: int = 80, timeout: float = 10) -> tuple[list[Observation], list[str]]:
    """Fetch 5 fixed public sources. Returned safe errors may denote partial coverage.

    Transport timeout is per request. The history and request count are bounded.
    At a pre-fetch issuance clock, observations retrieved later are not yet available.
    """
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now requires timezone")
    if not isinstance(history_hours, int) or isinstance(history_hours, bool) or not 1 <= history_hours <= 96:
        raise ValueError("history_hours must be between 1 and 96")
    if not isinstance(timeout, (float, int)) or isinstance(timeout, bool) or not math.isfinite(timeout) or not 0 < timeout <= 30:
        raise ValueError("timeout must be in (0, 30] seconds")
    end = now.astimezone(UTC)
    begin = end - timedelta(hours=history_hours)
    data, errors = {}, []
    with ThreadPoolExecutor(max_workers=5) as pool:
        jobs = {pool.submit(_flow, s, begin, end, timeout): f"flow:{s}" for s in HYDRO_IDS}
        jobs[pool.submit(_rain, begin, end, timeout)] = f"rain:{RAIN_ID}"
        for job in as_completed(jobs):
            label = jobs[job]
            try:
                rows = job.result()
                if not rows:
                    errors.append(label)
                for row in rows:
                    key = (row.station_id, row.kind, row.observed_at)
                    if key not in data or row.retrieved_at > data[key].retrieved_at:
                        data[key] = row
            except (OSError, ValueError, TypeError, KeyError, AttributeError, OverflowError):
                errors.append(label)
    return sorted(data.values(), key=lambda x: (x.kind, x.station_id, x.observed_at)), sorted(errors)

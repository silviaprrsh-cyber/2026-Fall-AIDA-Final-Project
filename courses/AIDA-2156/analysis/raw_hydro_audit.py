"""Audit untouched Water Office unit-value CSV and GeoMet hourly GeoJSON."""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from math import isfinite
from pathlib import Path

COURSE = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = COURSE / "output" / "raw_data_eda"
HYDRO_SNAPSHOTS = ("20261103T070414Z", "20261111T030808Z")
WEATHER_SNAPSHOTS = (
    "20200601_20230531_3025484_monthly",
    "20230601_20260531_3025484_monthly",
    "20250501_20261104_3025484_monthly",
    "20260601_20261111_3025484_monthly",
)
STATIONS = {
    ("05CB007", "47"): ("Dickson Dam Tunnel Outlet", "discharge", "m3/s"),
    ("05CB001", "47"): ("Little Red Deer River near the Mouth", "discharge", "m3/s"),
    ("05CC007", "47"): ("Medicine River near Eckville", "discharge", "m3/s"),
    ("05CC002", "47"): ("Red Deer River at Red Deer", "discharge", "m3/s"),
    ("05CC002", "46"): ("Red Deer River at Red Deer", "gauge stage", "m"),
    ("05CC003", "46"): ("Sylvan Lake", "gauge stage", "m"),
}
WEATHER = {"PRECIP_AMOUNT": ("precipitation", "mm"), "TEMP": ("air temperature", "deg C"),
           "RELATIVE_HUMIDITY": ("relative humidity", "%")}


def parse_time(value: str) -> datetime:
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return result.replace(tzinfo=timezone.utc) if result.tzinfo is None else result.astimezone(timezone.utc)


def number(value: str | float | None) -> float | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    result = float(value)
    if not isfinite(result):
        raise ValueError(f"Non-finite source value: {value!r}")
    return result


@dataclass
class Series:
    station: str
    name: str
    variable: str
    unit: str
    group: str
    cadence: int
    points: dict[datetime, tuple[float | None, str, str]] = field(default_factory=dict)
    counters: Counter = field(default_factory=Counter)
    files: set[str] = field(default_factory=set)
    max_revision: float = 0.0
    revision_months: Counter = field(default_factory=Counter)

    def add(self, time, value, flag, status, source):
        self.files.add(source)
        self.counters["raw_rows"] += 1
        if time in self.points:
            self.counters["overlap_rows"] += 1
            old_value, old_flag, old_status = self.points[time]
            if old_value != value:
                self.counters["changed_value_rows"] += 1
                self.revision_months[time.strftime("%Y-%m")] += 1
                if old_value is not None and value is not None:
                    self.max_revision = max(self.max_revision, abs(old_value - value))
            if (old_flag, old_status) != (flag, status):
                self.counters["changed_flag_rows"] += 1
        self.points[time] = value, flag, status

    @property
    def key(self):
        return dict(group=self.group, station=self.station, name=self.name,
                    variable=self.variable, unit=self.unit)


def collect():
    source = COURSE / "data" / "sources"
    hydro = source / "eccc_wateroffice" / "raw" / "unit_values"
    climate = source / "eccc_climate_hourly" / "raw"
    series = {key: Series(key[0], *spec, "hydrometric", 5) for key, spec in STATIONS.items()}
    for snapshot in HYDRO_SNAPSHOTS:
        for station in sorted({key[0] for key in series}):
            files = sorted((hydro / snapshot / station).glob("*.csv"))
            if not files:
                raise FileNotFoundError(f"No Water Office CSV files: {hydro / snapshot / station}")
            for file in files:
                with file.open(encoding="utf-8-sig", newline="") as handle:
                    reader = csv.reader(handle)
                    header = next(reader)
                    if list(map(str.strip, header[:2])) != ["ID", "Date"] or len(header) != 9:
                        raise ValueError(f"Unexpected Water Office schema: {file}")
                    for row in reader:
                        if not row:
                            continue
                        if len(row) != len(header) or row[0].strip() != station:
                            raise ValueError(f"Invalid station or source row: {file} line {reader.line_num}")
                        item = series.get((station, row[2]))
                        if item:
                            flags = "|".join(row[i] for i in (4, 5, 7, 8)).strip("|")
                            item.add(parse_time(row[1]), number(row[3]), flags, row[6], str(file))
    wx = {(group, field_name): Series("3025484", "Red Deer Regional A", *spec, group, 60)
          for group in ("weather_full_archive", "weather_project_snapshots") for field_name, spec in WEATHER.items()}
    for index, snapshot in enumerate(WEATHER_SNAPSHOTS):
        files = sorted(file for file in (climate / snapshot).glob("20??_??.json"))
        if not files:
            raise FileNotFoundError(f"No climate-hourly GeoJSON files: {climate / snapshot}")
        for file in files:
            page = json.loads(file.read_text(encoding="utf-8-sig"))
            features = page["features"]
            if page.get("numberMatched", len(features)) != len(features):
                raise ValueError(f"Truncated climate archive page: {file}")
            for feature in features:
                p = feature["properties"]
                if str(p["CLIMATE_IDENTIFIER"]) != "3025484":
                    raise ValueError(f"Unexpected climate station: {file}")
                moment = parse_time(p["UTC_DATE"])
                for field_name in WEATHER:
                    value, flag = number(p[field_name]), p.get(field_name + "_FLAG") or ""
                    wx["weather_full_archive", field_name].add(moment, value, flag, "", str(file))
                    if index >= 2:
                        wx["weather_project_snapshots", field_name].add(moment, value, flag, "", str(file))
    return [*series.values(), *wx.values()]


def gap_rows(series, known, step):
    if not known:
        raise ValueError(f"No numeric observations in {series.key}")
    first, last = min(series.points), max(series.points)
    anchors = [first - step, *known, last + step]
    for a, b in zip(anchors, anchors[1:]):
        missing_slots = (b - a) // step - 1
        if missing_slots > 0:
            yield series.key | dict(first_missing_utc=(a + step).isoformat(),
                                    last_missing_utc=(b - step).isoformat(),
                                    missing_slots=missing_slots, missing_minutes=missing_slots * series.cadence)


def summarize(series):
    stamps = sorted(series.points)
    if not stamps:
        raise ValueError(f"Empty series: {series.key}")
    step = timedelta(minutes=series.cadence)
    start, end = stamps[0], stamps[-1]
    if any((stamp - start) % step for stamp in stamps):
        raise ValueError(f"Off nominal grid: {series.key}")
    known = [time for time in stamps if series.points[time][0] is not None]
    gaps = list(gap_rows(series, known, step))
    monthly = {}
    for slot in range((end - start) // step + 1):
        time = start + slot * step
        count = monthly.setdefault(time.strftime("%Y-%m"), Counter())
        count["inferred_slots"] += 1
        if time in series.points:
            value = series.points[time][0]
            count["timestamp_present"] += 1
            count["numeric_observations"] += value is not None
            count["recorded_zero"] += value == 0
    months = [series.key | dict(month=month, inferred_slots=c["inferred_slots"],
                              numeric_observations=c["numeric_observations"],
                              absent_timestamps=c["inferred_slots"] - c["timestamp_present"],
                              timestamp_with_blank=c["timestamp_present"] - c["numeric_observations"],
                              recorded_zero=c["recorded_zero"],
                              missing_pct=round(100 * (1 - c["numeric_observations"] / c["inferred_slots"]), 4))
              for month, c in monthly.items()]
    expected = sum(row["inferred_slots"] for row in months)
    missing = expected - len(known)
    if missing != sum(row["missing_slots"] for row in gaps):
        raise RuntimeError(f"Missing-slot check failed: {series.key}")
    if len(stamps) != series.counters["raw_rows"] - series.counters["overlap_rows"]:
        raise RuntimeError(f"Source overlap check failed: {series.key}")
    intervals = Counter((b - a) // timedelta(minutes=1) for a, b in zip(stamps, stamps[1:]))
    longest = max(gaps, key=lambda r: r["missing_slots"], default={})
    values = sorted(series.points[stamp][0] for stamp in known)
    row = series.key | dict(
        start_utc=start.isoformat(), end_utc=end.isoformat(), source_file_count=len(series.files),
        nominal_minutes=series.cadence, modal_minutes=intervals.most_common(1)[0][0] if intervals else "",
        raw_rows=series.counters["raw_rows"], overlap_rows=series.counters["overlap_rows"],
        changed_value_rows=series.counters["changed_value_rows"], changed_flag_rows=series.counters["changed_flag_rows"],
        max_abs_numeric_revision=round(series.max_revision, 9), distinct_timestamps=len(stamps),
        numeric_observations=len(known), inferred_slots=expected, absent_timestamps=expected-len(stamps),
        timestamp_with_blank=len(stamps)-len(known), recorded_zero=values.count(0.0),
        missing_pct=round(100 * missing / expected, 4), longest_missing_minutes=longest.get("missing_minutes", 0),
        longest_gap_start_utc=longest.get("first_missing_utc", ""), longest_gap_end_utc=longest.get("last_missing_utc", ""),
        minimum=values[0], median=(values[(len(values)-1)//2]+values[len(values)//2])/2,
        p99_nearest_lower=values[(len(values)-1)*99//100], maximum=values[-1])
    flags = [series.key | dict(quality_flag=flag, approval=status, observations=count)
             for (flag, status), count in sorted(Counter((flag, status) for _, flag, status in series.points.values()).items())]
    revisions = [series.key | dict(month=month, changed_value_rows=count)
                 for month, count in sorted(series.revision_months.items())]
    return row, months, gaps, flags, revisions


def write_csv(path, records):
    if not records:
        raise RuntimeError(f"Empty results: {path.name}")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=records[0].keys())
        writer.writeheader()
        writer.writerows(records)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    fields = ("series_summary", "monthly_coverage", "gap_inventory", "provider_flags", "value_revisions")
    tables = [[] for _ in fields]
    for series in collect():
        row, *details = summarize(series)
        tables[0].append(row)
        for target, rows in zip(tables[1:], details):
            target.extend(rows)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, records in zip(fields, tables):
        if name == "value_revisions" and not records:
            path = args.output_dir / "hydro_value_revisions.csv"
            path.write_text("group,station,name,variable,unit,month,changed_value_rows\n", encoding="utf-8")
        else:
            write_csv(args.output_dir / f"hydro_{name}.csv", records)
    print(f"Hydrometric and climate raw audit: {len(tables[0])} series; coverage reconciled.")


if __name__ == "__main__":
    main()


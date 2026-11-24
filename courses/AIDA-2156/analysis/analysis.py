"""Decision-led historical hydrometry EDA; no database, model, or network access."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

COURSE = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = COURSE / "data/processed/model_unit_history/20261103T070414Z"
DEFAULT_OUTPUT = COURSE / "output/final_eda"
RIVERS = ("05CB007", "05CB001", "05CC007", "05CC002")
LAKE = "05CC003"
ENDPOINT = "05CC002"
PARAMETERS = {"level": ("level_m", "m"), "discharge": ("discharge_m3_s", "m3/s")}
FLAGS = ("approval", "grade", "symbol", "qualifiers")
FINAL_APPROVAL = "Final/Finales"
START = datetime.fromisoformat("2025-05-03T07:04:14+00:00")
END = datetime.fromisoformat("2026-11-03T07:04:14+00:00")
CADENCE = 300
DAY = 86_400
BLOCK = 7 * DAY
ANCHOR = int(START.replace(hour=0, minute=0, second=0).timestamp())
LAGS = (0, 6, 12, 24, 30, 48)
BOOTSTRAP_DRAWS = 1_000
BOOTSTRAP_SEED = 20261120
MIN_BLOCKS = 8
DECLARED_DISPOSITION = "Experimental descriptive study only; operational use withheld."


def require(condition, message):
    if not condition:
        raise ValueError(message)


def parse_value(raw):
    if not raw.strip():
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    return value if math.isfinite(value) else None


def screen(value, symbol, qualifiers):
    return value is not None and value > 0 and symbol == "" and qualifiers == ""


def percentile(values, probability):
    if not values:
        return None
    index = probability * (len(values) - 1)
    i = int(index)
    return values[i] + (values[min(i + 1, len(values) - 1)] - values[i]) * (index - i)


def round_or_none(value, decimals=6):
    return None if value is None else round(value, decimals)


def distribution(values):
    ordered = sorted(values)
    result = {"n": len(ordered), "mean": round_or_none(math.fsum(ordered) / len(ordered) if ordered else None)}
    for key, q in (("min", 0), ("p10", .1), ("p25", .25), ("median", .5), ("p75", .75), ("p90", .9), ("max", 1)):
        result[key] = round_or_none(percentile(ordered, q))
    return result


def expected_by_month():
    counts = Counter()
    t = ((int(START.timestamp()) + CADENCE - 1) // CADENCE) * CADENCE
    while t <= END.timestamp():
        counts[datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m")] += 1
        t += CADENCE
    return counts


def sha256(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def read_station(path, station, months):
    parameters = ("level",) if station == LAKE else ("level", "discharge")
    counts = {p: defaultdict(Counter) for p in parameters}
    flags = {p: {flag: Counter() for flag in FLAGS} for p in parameters}
    baseline = {p: {} for p in parameters}
    strict = {p: {} for p in parameters}
    row_count = 0
    previous = int(START.timestamp()) - 1
    observed_steps = Counter()
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"station_id", "observed_at"} | {
            key for p in parameters for key in (PARAMETERS[p][0], *(f"{p}_{flag}" for flag in FLAGS))
        }
        require(required <= set(reader.fieldnames or []), f"{path.name}: missing fields {sorted(required - set(reader.fieldnames or []))}")
        for row in reader:
            row_count += 1
            require(row["station_id"] == station, f"{path.name}: station ID mismatch at row {row_count + 1}")
            observed = datetime.fromisoformat(row["observed_at"])
            require(observed.utcoffset() == timedelta(0) and observed.microsecond == 0,
                    f"{path.name}: invalid UTC timestamp at row {row_count + 1}")
            t = int(observed.timestamp())
            require(t > previous and START <= observed <= END,
                    f"{path.name}: out-of-window, unsorted, or duplicate key at row {row_count + 1}")
            if row_count > 1:
                observed_steps[t - previous] += 1
            previous = t
            month = row["observed_at"][:7]
            on_grid = t % CADENCE == 0
            for parameter in parameters:
                value_raw = row[PARAMETERS[parameter][0]]
                val = parse_value(value_raw)
                metric = counts[parameter][month]
                metric["station_rows"] += 1
                if val is None:
                    metric["blank_value_rows" if not value_raw.strip() else "invalid_value_rows"] += 1
                    continue
                metric["numeric_rows"] += 1
                metric["on_grid_numeric_rows" if on_grid else "off_grid_numeric_rows"] += 1
                metric["zero_rows"] += int(val == 0)
                qual = {flag: row[f"{parameter}_{flag}"] for flag in FLAGS}
                for flag in FLAGS:
                    flags[parameter][flag][(month, qual[flag] or "<blank>")] += 1
                if screen(val, qual["symbol"], qual["qualifiers"]):
                    if not on_grid:
                        metric["baseline_screen_off_grid_rows"] += 1
                        continue
                    baseline[parameter][t] = val
                    metric["baseline_eligible"] += 1
                    if qual["approval"] == FINAL_APPROVAL:
                        strict[parameter][t] = val
                        metric["strict_final_eligible"] += 1
    require(row_count > 1 and observed_steps.most_common(1)[0][0] == CADENCE,
            f"{path.name}: expected five-minute modal station cadence")
    coverage = []
    quality = []
    distributions = []
    metrics = ("station_rows", "numeric_rows", "on_grid_numeric_rows", "off_grid_numeric_rows",
               "blank_value_rows", "invalid_value_rows", "zero_rows", "baseline_eligible",
               "baseline_screen_off_grid_rows", "strict_final_eligible")
    for parameter in parameters:
        unit = PARAMETERS[parameter][1]
        for month, slots in months.items():
            c = counts[parameter][month]
            require(c["on_grid_numeric_rows"] <= slots, "Observed grid count exceeds denominator")
            require(c["strict_final_eligible"] <= c["baseline_eligible"] <= c["on_grid_numeric_rows"],
                    "Filter hierarchy violated")
            coverage.append({
                "station": station, "parameter": parameter, "unit": unit, "month_utc": month,
                "expected_5min_slots": slots, **{k: c[k] for k in metrics},
                "inferred_unobserved_grid_slots": slots - c["on_grid_numeric_rows"],
                "numeric_grid_coverage_fraction": round(c["on_grid_numeric_rows"] / slots, 6),
                "on_grid_numeric_excluded_by_baseline": c["on_grid_numeric_rows"] - c["baseline_eligible"],
                "baseline_excluded_by_strict": c["baseline_eligible"] - c["strict_final_eligible"],
            })
        for flag, tally in flags[parameter].items():
            quality.extend({"station": station, "parameter": parameter, "month_utc": month,
                            "flag": flag, "value": value, "finite_observations": n}
                           for (month, value), n in sorted(tally.items()))
        for name, groups in (("historical_screen", baseline), ("historical_screen_plus_Final_approval", strict)):
            distributions.append({"station": station, "parameter": parameter, "unit": unit,
                                  "cohort": name, **distribution(groups[parameter].values())})
    input_meta = {"station": station, "input_file": path.name, "rows": row_count, "sha256": sha256(path)}
    return baseline, strict, coverage, quality, distributions, input_meta


def joint_times(by_station, stations):
    series = [values for station in stations for values in by_station[station].values()]
    smallest = min(series, key=len)
    return {t for t in smallest if all(t in values for values in series)}


def block_index(timestamp):
    return (timestamp - ANCHOR) // BLOCK


def date_utc(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc).date().isoformat()


def block_date(index):
    return date_utc(ANCHOR + index * BLOCK)


def block_sums(times, endpoint):
    grouped = defaultdict(list)
    for t in sorted(times):
        grouped[block_index(t)].append(endpoint[t])
    return {i: (len(values), math.fsum(values)) for i, values in grouped.items()}


def interval(samples):
    samples.sort()
    if len(samples) < .9 * BOOTSTRAP_DRAWS:
        return None, None
    return round_or_none(percentile(samples, .025)), round_or_none(percentile(samples, .975))


def paired_mean_delta_interval(reference, alternative):
    if min(len(reference), len(alternative)) < MIN_BLOCKS:
        return None, None
    rng = random.Random(BOOTSTRAP_SEED)
    ids = sorted(set(reference) | set(alternative))
    draws = []
    for _ in range(BOOTSTRAP_DRAWS):
        nr = na = sr = sa = 0
        for i in rng.choices(ids, k=len(ids)):
            n, total = reference.get(i, (0, 0.0))
            nr += n
            sr += total
            n, total = alternative.get(i, (0, 0.0))
            na += n
            sa += total
        if na and nr:
            draws.append(sa / na - sr / nr)
    return interval(draws)


def sensitivity_row(spec_id, description, reference, alternative, endpoint, implication):
    rb, ab = block_sums(reference, endpoint), block_sums(alternative, endpoint)
    rd, ad = distribution(endpoint[t] for t in reference), distribution(endpoint[t] for t in alternative)
    rmean, amean = rd["mean"], ad["mean"]
    exact_delta = (
        math.fsum(total for _, total in ab.values()) / len(alternative)
        - math.fsum(total for _, total in rb.values()) / len(reference)
        if alternative and reference else None
    )
    low, high = paired_mean_delta_interval(rb, ab)
    return {
        "id": spec_id, "comparison": description, "reference_timestamps": len(reference),
        "alternative_timestamps": len(alternative), "alternative_retention_fraction": round(len(alternative) / len(reference), 6) if reference else None,
        "reference_utc_days": len({t // DAY for t in reference}),
        "alternative_utc_days": len({t // DAY for t in alternative}),
        "reference_7day_blocks": len(rb), "alternative_7day_blocks": len(ab),
        "reference_endpoint_q_mean_m3_s": rmean, "alternative_endpoint_q_mean_m3_s": amean,
        "changed_minus_reference_mean_m3_s": round_or_none(exact_delta),
        "changed_minus_reference_mean_ci_2_5": low, "changed_minus_reference_mean_ci_97_5": high,
        "reference_endpoint_q_median_m3_s": rd["median"], "alternative_endpoint_q_median_m3_s": ad["median"],
        "reference_endpoint_q_p90_m3_s": rd["p90"], "alternative_endpoint_q_p90_m3_s": ad["p90"],
        "decision_impact": implication,
    }


def add_moments(stats, x, y):
    stats[0] += 1
    stats[1] += x
    stats[2] += y
    stats[3] += x * x
    stats[4] += y * y
    stats[5] += x * y


def correlation(blocks):
    if not blocks:
        return None
    n, x, y, x2, y2, xy = (math.fsum(column) for column in zip(*blocks))
    varx, vary = n * x2 - x * x, n * y2 - y * y
    if n < 2 or varx <= 0 or vary <= 0:
        return None
    return max(-1.0, min(1.0, (n * xy - x * y) / math.sqrt(varx * vary)))


def block_correlation_ci(table):
    if len(table) < MIN_BLOCKS:
        return None, None
    rng = random.Random(BOOTSTRAP_SEED)
    blocks = [table[k] for k in sorted(table)]
    samples = [correlation(rng.choices(blocks, k=len(blocks))) for _ in range(BOOTSTRAP_DRAWS)]
    return interval([r for r in samples if r is not None])


def lag_analysis(baseline):
    result = []
    endpoint = baseline[ENDPOINT]["discharge"]
    for upstream in RIVERS[:-1]:
        source = baseline[upstream]["discharge"]
        pairs = {
            lag: {t for t in endpoint if t - lag * 3600 in source} for lag in LAGS
        }
        common = sorted(set.intersection(*pairs.values()))
        require(common and all(len(common) <= len(pairs[lag]) for lag in LAGS),
                f"{upstream}: no exact common timestamp support")
        for lag in LAGS:
            accum = defaultdict(lambda: [0, 0., 0., 0., 0., 0.])
            for t in common:
                add_moments(accum[block_index(t)], source[t - lag * 3600], endpoint[t])
            rate = correlation(list(accum.values()))
            low, high = block_correlation_ci(accum)
            result.append({
                "upstream_station": upstream, "endpoint_station": ENDPOINT,
                "lag_h": lag, "eligible_pair_timestamps_at_this_lag": len(pairs[lag]),
                "common_timestamps_across_lags": len(common), "utc_7day_blocks": len(accum),
                "first_target_day_utc": date_utc(common[0]), "last_target_day_utc": date_utc(common[-1]),
                "pearson_r": round_or_none(rate), "block_ci_2_5": low, "block_ci_97_5": high,
            })
    return result


def write_csv(path, rows):
    require(bool(rows), f"No rows to write: {path.name}")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def run(input_dir, output_dir):
    expected = expected_by_month()
    baseline, strict, coverage, quality, distributions, inputs = {}, {}, [], [], [], []
    for station in (*RIVERS, LAKE):
        path = input_dir / f"{station}_observations.csv"
        require(path.is_file(), f"Missing normalized station input: {path.name}")
        base, final, cov, flags, dist, metadata = read_station(path, station, expected)
        baseline[station] = base
        strict[station] = final
        coverage.extend(cov)
        quality.extend(flags)
        distributions.extend(dist)
        inputs.append(metadata)

    river = joint_times(baseline, RIVERS)
    lake = joint_times(baseline, (*RIVERS, LAKE))
    final = joint_times(strict, (*RIVERS, LAKE))
    lake_days = {t // DAY for t in lake}
    comparable_river = {t for t in river if t // DAY in lake_days}
    require(final <= lake <= comparable_river <= river and bool(lake), "Invalid overlapping cohort")
    endpoint = baseline[ENDPOINT]["discharge"]
    sensitivities = [
        sensitivity_row(
            "P-S1", "Historical lake-complete screen versus same screen requiring explicit Final/Finales for all nine values.",
            lake, final, endpoint,
            "No joint all-final estimate available; retain flagged historical observations only for exploratory use."
            if not final else "Final-only comparison is exploratory; operational use stays withheld.",
        ),
        sensitivity_row(
            "P-S2", "River-only versus lake-complete using the historical screen on the same UTC dates that have at least one lake-complete candidate.",
            comparable_river, lake, endpoint,
            "Show lake-complete estimates as conditional on lake availability; do not impute or require lake data for a river-only descriptive analysis.",
        ),
    ]
    approval_coverage = [
        {"station": station, "parameter": parameter, "baseline_n": len(values),
         "explicit_final_n": len(strict[station][parameter])}
        for station, parameters in baseline.items() for parameter, values in parameters.items()
    ]
    strict_endpoint = set(strict[ENDPOINT]["discharge"])
    endpoint_final_dates = {t // DAY for t in strict_endpoint}
    endpoint_on_shared_dates = {t for t in endpoint if t // DAY in endpoint_final_dates}
    require(strict_endpoint <= endpoint_on_shared_dates, "Invalid endpoint approval cohort")
    endpoint_check = sensitivity_row(
        "secondary_endpoint_approval",
        "Endpoint discharge only, screened versus explicitly Final/Finales within UTC dates with any Final discharge.",
        endpoint_on_shared_dates, strict_endpoint, endpoint,
        "Describes endpoint approval availability and cannot substitute for an all-final joint river/lake comparison.",
    )
    cohorts = {"river_only_all_dates": river, "river_only_shared_dates": comparable_river,
               "lake_complete": lake, "all_final_lake_complete": final}
    by_block = {name: block_sums(times, endpoint) for name, times in cohorts.items()}
    time_blocks = []
    for i in range(block_index(int(END.timestamp())) + 1):
        row = {"block_start_utc": block_date(i), "span_days": 7}
        for name, sums in by_block.items():
            n, total = sums.get(i, (0, 0.0))
            row[f"{name}_n"] = n
            row[f"{name}_endpoint_q_mean_m3_s"] = round_or_none(total / n if n else None)
        time_blocks.append(row)
    lagged = lag_analysis(baseline)
    checks = {
        "five_station_inputs_with_unique_in_window_sorted_keys": len(inputs) == 5,
        "nine_parameter_series_reconciled": len(coverage) == 9 * len(expected),
        "filter_hierarchy_and_no_imputation": final <= lake <= comparable_river <= river,
        "shared_date_comparison_uses_identical_dates": lake_days == {t // DAY for t in comparable_river},
        "lagged_outputs_use_exact_past_or_same_time_support": len(lagged) == len(LAGS) * (len(RIVERS) - 1),
        "cohort_counts_equal_block_sums": all(len(ts) == sum(n for n, _ in by_block[k].values()) for k, ts in cohorts.items()),
    }
    require(all(checks.values()), "Internal decision EDA validation failed")
    summary = {
        "study": "Dickson to Red Deer 05CC002 historical observation adequacy",
        "request_window_utc": [START.isoformat(), END.isoformat()],
        "grid": "UTC-aligned 300 s slots within the requested window; expected slots are an inferred denominator, not a claim of nominal station uptime.",
        "inputs": inputs,
        "joint_screen": "Positive finite level and flow at all four river stations; a positive finite level at 05CC003 when required. Blank Symbol and Qualifiers fields, exact UTC five-minute keys, no imputation. Grade and approval retained.",
        "strict_policy": "Also require an explicit Final/Finales label on each value; other status and missing status excluded. No quality ordering of numeric grades assumed.",
        "approval_coverage_by_station_parameter": approval_coverage,
        "station_parameters_without_explicit_final_after_screen": [
            {"station": row["station"], "parameter": row["parameter"]}
            for row in approval_coverage if row["explicit_final_n"] == 0
        ],
        "secondary_endpoint_only_approval_check": endpoint_check,
        "cohort_timestamps": {key: len(times) for key, times in cohorts.items()},
        "cohort_utc_dates": {key: len({t // DAY for t in times}) for key, times in cohorts.items()},
        "river_only_timestamps_on_other_dates": len(river - comparable_river),
        "lag_method": "Pearson upstream Q(t-lag) versus endpoint Q(t); exact matches; common target support across tested lags within each upstream station; supports can differ between stations. Tested lags are illustrative, not a selected or verified transit time.",
        "uncertainty": f"Percentile 95% intervals from {BOOTSTRAP_DRAWS} resamples of fixed nonoverlapping 7-day UTC blocks (seed {BOOTSTRAP_SEED}); at least {MIN_BLOCKS} contributing blocks per cohort. P-S2 resamples paired calendar blocks and compares record-weighted means. Intervals describe historical sample variability, not independent-event, causal or forecast uncertainty.",
        "limitations": [
            "Season, shared drivers, persistence and station-specific availability affect contemporaneous and lagged flow associations.",
            "Receipt time does not prove availability at a historical forecast issue time.",
            "Avoid interpreting a change in sample composition as a hydraulic effect of the lake.",
            "Reported stage/elevation is not river-bed depth; common vertical datum and bank elevation not verified.",
            "Rare highs cannot validate flood warnings. No CV inference, rainfall imputation, model performance, or site-level hazard is estimated.",
        ],
        "sensitivity": sensitivities,
        "checks": checks,
        "disposition": DECLARED_DISPOSITION,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    for n, rows in (("coverage", coverage), ("quality_counts", quality), ("distributions", distributions),
                    ("lagged_relationships", lagged), ("sensitivity-results", sensitivities), ("time_blocks", time_blocks)):
        write_csv(output_dir / f"{n}.csv", rows)
    (output_dir / "summary.json").write_text(
        json.dumps(summary, allow_nan=False, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("Historical observation analysis completed; all internal checks passed.")
    print(f"River-only {len(river):,}; shared-date river-only {len(comparable_river):,}; "
          f"lake-complete {len(lake):,}; joint all-final {len(final):,}.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    inp, out = args.input_dir.resolve(), args.output_dir.resolve()
    if out.is_relative_to(inp):
        parser.error("Output must be outside the normalized input directory.")
    try:
        run(inp, out)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Analysis failed: {exc}\n")


if __name__ == "__main__":
    main()

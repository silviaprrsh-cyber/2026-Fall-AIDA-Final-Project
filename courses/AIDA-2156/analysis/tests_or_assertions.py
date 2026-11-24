"""Validate the frozen observation analysis inputs and final evidence tables."""

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from analysis import DEFAULT_INPUT, DEFAULT_OUTPUT, LAGS, RIVERS, LAKE, parse_value, require, screen, sha256


def read_csv(directory, name):
    with (directory / f"{name}.csv").open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def run(input_dir, output_dir):
    require(parse_value("0") == 0 and parse_value("nan") is None and parse_value("") is None,
            "Missing, nonfinite and numeric zero must differ")
    require(screen(1, "", "") and not screen(1, "E", "") and not screen(1, "", "tag")
            and not screen(None, "", "") and not screen(0, "", ""),
            "Historical screen must retain only positive, unflagged values")
    summary = json.loads((output_dir / "summary.json").read_text(encoding="utf-8"))
    require(all(summary["checks"].values()), "Internal analysis checks did not pass")
    require([v["station"] for v in summary["inputs"]] == [*RIVERS, LAKE], "Unexpected station selection")
    for meta in summary["inputs"]:
        path = input_dir / f'{meta["station"]}_observations.csv'
        require(meta["input_file"] == path.name and sha256(path) == meta["sha256"], "Input SHA-256 mismatch")
    coverage = read_csv(output_dir, "coverage")
    weights = Counter()
    for row in coverage:
        counts = {k: int(row[k]) for k in ("expected_5min_slots", "station_rows", "numeric_rows",
                  "blank_value_rows", "invalid_value_rows", "on_grid_numeric_rows", "off_grid_numeric_rows",
                  "inferred_unobserved_grid_slots", "baseline_eligible", "strict_final_eligible")}
        require(counts["numeric_rows"] + counts["blank_value_rows"] + counts["invalid_value_rows"] == counts["station_rows"],
                "Numeric/invalid/missing coverage does not reconcile")
        require(counts["on_grid_numeric_rows"] + counts["off_grid_numeric_rows"] == counts["numeric_rows"]
                and counts["on_grid_numeric_rows"] + counts["inferred_unobserved_grid_slots"] == counts["expected_5min_slots"],
                "Grid coverage does not reconcile")
        require(0 <= counts["strict_final_eligible"] <= counts["baseline_eligible"] <= counts["on_grid_numeric_rows"],
                "Source screen hierarchy changed")
        weights[(row["station"], row["parameter"], "historical_screen")] += counts["baseline_eligible"]
        weights[(row["station"], row["parameter"], "historical_screen_plus_Final_approval")] += counts["strict_final_eligible"]
    require(len(coverage) == 9 * 19 and len(weights) == 18, "Unexpected coverage grain")
    dists = read_csv(output_dir, "distributions")
    require(len(dists) == len(weights), "Missing distribution cohort")
    for row in dists:
        require(int(row["n"]) == weights[(row["station"], row["parameter"], row["cohort"])],
                "Distribution denominator differs from coverage")
        require(bool(row["mean"]) == (int(row["n"]) > 0), "Empty distribution must not have an estimate")
    require(read_csv(output_dir, "quality_counts"), "No provider flags retained")
    cohorts = summary["cohort_timestamps"]
    require(cohorts["lake_complete"] == 95_053 and cohorts["all_final_lake_complete"] == 0,
            "Legacy cohort reconstruction or all-final finding changed")
    require({(r["station"], r["parameter"]) for r in summary["station_parameters_without_explicit_final_after_screen"]}
            == {(s, p) for s in ("05CB001", "05CC007") for p in ("level", "discharge")},
            "Joint strict-approval blockers are inconsistent")
    secondary = summary["secondary_endpoint_only_approval_check"]
    require(0 < secondary["alternative_timestamps"] <= secondary["reference_timestamps"]
            and secondary["reference_utc_days"] == secondary["alternative_utc_days"],
            "Endpoint-only approval check must have shared dates and cannot be the joint strict result")
    require(cohorts["lake_complete"] <= cohorts["river_only_shared_dates"] <= cohorts["river_only_all_dates"],
            "Shared-date cohort selection invalid")
    blocks = read_csv(output_dir, "time_blocks")
    require(all(sum(int(r[f"{key}_n"]) for r in blocks) == count for key, count in cohorts.items()),
            "Block and cohort counts differ")
    strict, lake = read_csv(output_dir, "sensitivity-results")
    require(strict["id"] == "P-S1" and strict["alternative_timestamps"] == "0"
            and not strict["alternative_endpoint_q_mean_m3_s"] and not strict["changed_minus_reference_mean_ci_2_5"],
            "Empty strict cohort must not report a numeric estimate")
    require(lake["id"] == "P-S2" and lake["reference_utc_days"] == lake["alternative_utc_days"]
            and int(lake["reference_timestamps"]) == cohorts["river_only_shared_dates"],
            "Lake sensitivity did not use the comparable target dates")
    changed = float(lake["alternative_endpoint_q_mean_m3_s"]) - float(lake["reference_endpoint_q_mean_m3_s"])
    require(math.isclose(changed, float(lake["changed_minus_reference_mean_m3_s"]), abs_tol=2e-6),
            "Lake sensitivity estimate does not reconcile")
    ranks = defaultdict(list)
    for row in read_csv(output_dir, "lagged_relationships"):
        ranks[row["upstream_station"]].append(row)
        require(int(row["eligible_pair_timestamps_at_this_lag"]) >= int(row["common_timestamps_across_lags"]),
                "Lag-specific cohort must contain the common cohort")
        require(-1 <= float(row["pearson_r"]) <= 1 and row["endpoint_station"] == RIVERS[-1],
                "Bad association estimate")
    require(list(ranks) == list(RIVERS[:-1]), "Unexpected lag partners")
    for rows in ranks.values():
        require(tuple(int(r["lag_h"]) for r in rows) == LAGS
                and len({r["common_timestamps_across_lags"] for r in rows}) == 1,
                "Candidate lags must share support within each source station")
    print("EDA assertions passed: frozen input checksums, coverage accounting, cohort reconstruction, sensitivity, and lag support.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    run(args.input_dir, args.output_dir)


if __name__ == "__main__":
    main()

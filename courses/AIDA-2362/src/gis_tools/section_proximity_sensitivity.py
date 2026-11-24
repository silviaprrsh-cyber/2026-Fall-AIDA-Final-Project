"""Screen the five fixed GIS targets using their archived along-mainstem offsets."""
import csv
import json
import math
from pathlib import Path

COURSE = Path(__file__).resolve().parents[2]
PROJECT = COURSE / "project"
POINTS = PROJECT / "derived_prediction_targets" / "prediction_points.geojson"
SURVEYS = PROJECT / "alberta_flood_surveys"
OUTPUT = COURSE / "outputs" / "section-proximity-sensitivity.csv"
BASELINE_M, ALTERNATIVE_M = 25, 50


def features(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("type") != "FeatureCollection":
        raise ValueError(f"Not a FeatureCollection: {path.name}")
    return [feature["properties"] for feature in data["features"]]


def analyze():
    statuses = {}
    for source in ("county_markerville", "red_deer"):
        for section in features(SURVEYS / source / "cross_section_lines.geojson"):
            section_id = section["section_id"]
            if section_id in statuses:
                raise ValueError(f"Duplicate section: {section_id}")
            statuses[section_id] = section["line_status"]

    targets = sorted(features(POINTS), key=lambda row: row["target_id"])
    if [t["target_id"] for t in targets] != [f"P{i:02}" for i in range(1, 6)]:
        raise ValueError("Expected one feature for each active point P01 to P05")
    rows = []
    for t in targets:
        section_id = t["nearest_section_id"]
        status = statuses[section_id]
        signed = t["nearest_section_along_river_offset_m"]
        if t["distance_crs"] != "EPSG:3400" or not math.isfinite(signed):
            raise ValueError(f"Invalid distance CRS or offset for {t['target_id']}")
        if status not in {"planned", "surveyed"}:
            raise ValueError(f"Unexpected section status: {status}")
        distance = abs(signed)
        baseline = distance <= BASELINE_M
        alternative = distance <= ALTERNATIVE_M
        rows.append({
            "target_id": t["target_id"], "section_id": section_id,
            "section_status": status, "distance_crs": t["distance_crs"],
            "signed_offset_m": signed, "absolute_offset_m": distance,
            "passes_25m": "yes" if baseline else "no",
            "passes_50m": "yes" if alternative else "no",
            "changed": "added" if alternative and not baseline else "unchanged",
            "vertical_datum_verified": "yes" if t["vertical_datum_verified"] else "no",
            "hydraulic_transfer_verified": "yes" if t["hydraulic_transfer_verified"] else "no",
        })
    return rows


def main():
    rows = analyze()
    with OUTPUT.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=rows[0], lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    for limit in (BASELINE_M, ALTERNATIVE_M):
        eligible = [r for r in rows if r[f"passes_{limit}m"] == "yes"]
        print(f"{limit} m: {len(eligible)}/{len(rows)} ({', '.join(r['target_id'] for r in eligible)})")
    print("Added:", ", ".join(r["target_id"] for r in rows if r["changed"] == "added"))


if __name__ == "__main__":
    main()

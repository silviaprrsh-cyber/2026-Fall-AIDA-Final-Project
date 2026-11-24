"""Build reviewable prediction locations from archived river, survey and OSM geometry.

This offline tool creates cartographic targets only; it does not estimate flows.
"""

from project_paths import resolve_runtime_path, archive_relative
import hashlib
import json
from pathlib import Path

from pyproj import Transformer
from shapely.geometry import LineString, Point, shape, mapping
from shapely.ops import nearest_points, transform, unary_union

from project_paths import ROOT
def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


def first_downstream(sections, chainage):
    candidates = [s for s in sections if s["chainage_m"] > chainage + 0.01]
    if not candidates:
        raise ValueError("No surveyed section downstream within the selected mainstem")
    return min(candidates, key=lambda s: s["chainage_m"])


def bridge_position(main, bridges, ids, metric):
    positions, offsets = [], []
    for key in ids:
        element = bridges[key]
        if element.get("tags", {}).get("highway") == "proposed":
            raise ValueError("A proposed bridge cannot establish an existing crossing")
        line = transform(metric, LineString([(v["lon"], v["lat"]) for v in element["geometry"]]))
        distance = main.distance(line)
        if distance > 5:
            raise ValueError(f"Bridge {key} does not cross the selected mainstem: {distance} m")
        positions.append(main.project(nearest_points(main, line)[0]))
        offsets.append(distance)
    if max(positions) - min(positions) > 100:
        raise ValueError("Bridge carriageways are too far apart to combine")
    return sum(positions) / len(positions), offsets


def build():
    config_path = resolve_runtime_path(ROOT / "config/prediction_points.json")
    config = read(config_path)
    folder = resolve_runtime_path(ROOT / config["map_folder"])
    metric = Transformer.from_crs(4326, 3400, always_xy=True).transform
    inverse = Transformer.from_crs(3400, 4326, always_xy=True).transform
    rivers_path = folder / "nrcan_nhn/selected_rivers.geojson"
    rivers = read(rivers_path)["features"]
    main = transform(metric, shape(next(f for f in rivers if f["properties"]["role"] == "selected_mainstem")["geometry"]))
    tributaries = {f["properties"]["river"]: f for f in rivers if f["properties"]["role"] != "selected_mainstem"}
    bridges = {e["id"]: e for e in read(resolve_runtime_path(ROOT / config["bridges_source"]))["elements"]}
    details = read(resolve_runtime_path(ROOT / config["details_source"]))["elements"]
    sources = [config_path, rivers_path, resolve_runtime_path(ROOT / config["bridges_source"]), resolve_runtime_path(ROOT / config["details_source"])]
    sections = []
    for path in sorted(folder.glob("alberta_flood_surveys/*/cross_section_lines.geojson")):
        sources.append(path)
        for f in read(path)["features"]:
            if f["properties"]["river"] != "RED DEER RIVER":
                continue
            crossing = main.intersection(transform(metric, shape(f["geometry"])))
            points = [crossing] if crossing.geom_type == "Point" else list(getattr(crossing, "geoms", []))
            for point in points:
                if point.geom_type != "Point" or point.is_empty:
                    continue
                sections.append({"section_id": f["properties"]["section_id"],
                                 "chainage_m": main.project(point), "point": point,
                                 "source": archive_relative(path, ROOT).as_posix()})
    features = []
    for target in config["targets"]:
        evidence = {"selection": target}
        on_section = None
        method = target["method"]
        if method == "bridge":
            chainage, offsets = bridge_position(main, bridges, target["osm_ids"], metric)
            point = main.interpolate(chainage)
            evidence["bridge_to_mainstem_offsets_m"] = offsets
        elif method == "section":
            matches = [s for s in sections if s["section_id"] == target["section_id"]]
            if len(matches) != 1:
                raise ValueError("The selected section must have exactly one mainstem crossing")
            on_section = matches[0]
            chainage, point = on_section["chainage_m"], on_section["point"]
            if "between_bridge_ids" in target:
                limits = sorted(bridge_position(main, bridges, [i], metric)[0] for i in target["between_bridge_ids"])
                assert limits[0] < chainage < limits[1]
                evidence["bounding_bridge_chainages_m"] = limits
            if "adjacent_bridge_id" in target:
                bridge_chainage = bridge_position(main, bridges, [target["adjacent_bridge_id"]], metric)[0]
                evidence["section_to_bridge_along_river_m"] = bridge_chainage - chainage
        elif method == "after_confluences":
            mouths = {}
            for name in target["rivers"]:
                mouth = Point(metric(*tributaries[name]["properties"]["actual_mouth_lon_lat"]))
                assert main.distance(mouth) < 1
                mouths[name] = main.project(mouth)
            on_section = first_downstream(sections, max(mouths.values()))
            chainage, point = on_section["chainage_m"], on_section["point"]
            evidence["confluence_chainages_m"] = mouths
            evidence["distance_after_last_confluence_m"] = chainage - max(mouths.values())
        elif method == "osm_confluence":
            shared = []
            for name in target["rivers"]:
                candidates = [e for e in details if e.get("tags", {}).get("name") == name and target["osm_node_id"] in e.get("nodes", [])]
                assert candidates
                way = candidates[0]
                shared.append(way["geometry"][way["nodes"].index(target["osm_node_id"])])
            assert shared[0] == shared[1]
            coord = [shared[0]["lon"], shared[0]["lat"]]
            original = Point(metric(*coord))
            chainage = main.project(original)
            point = main.interpolate(chainage)
            evidence.update(osm_confluence_lon_lat=coord, cartographic_offset_m=original.distance(point))
        else:
            raise ValueError(method)
        if "landmark_name" in target:
            landmarks = [e for e in details if e.get("tags", {}).get("name") == target["landmark_name"]]
            geometry = unary_union([transform(metric, LineString([(v["lon"], v["lat"]) for v in e["geometry"]])) for e in landmarks])
            evidence["landmark_distance_m"] = point.distance(geometry)
            evidence["landmark_osm_ids"] = [e["id"] for e in landmarks]
        nearest = min(sections, key=lambda s: abs(s["chainage_m"] - chainage))
        assert main.distance(point) < 0.01
        p = {"target_id": target["id"], "map_label": target["id"], "name": target["name"],
             "role": "prediction_target", "map_color": "red", "prediction_status": "not_computed",
             "discharge_m3_s": None, "water_level_m": None, "risk": None,
             "river": "RED DEER RIVER", "chainage_from_dickson_m": chainage,
             "coordinate_crs": "EPSG:4326", "distance_crs": "EPSG:3400",
             "selection_method": method, "on_section_id": on_section["section_id"] if on_section else None,
             "nearest_section_id": nearest["section_id"],
             "nearest_section_along_river_offset_m": nearest["chainage_m"] - chainage,
             "section_source": (on_section or nearest)["source"],
             "hydraulic_transfer_verified": False, "vertical_datum_verified": False,
             "position_note": target.get("note", "Mapped location; hydraulic use requires separate validation."),
             "selection_evidence": json.dumps(evidence, sort_keys=True)}
        features.append({"type": "Feature", "id": target["id"], "geometry": mapping(transform(inverse, point)), "properties": p})
    features.sort(key=lambda f: f["properties"]["chainage_from_dickson_m"])
    expected_ids = [target["id"] for target in config["targets"]]
    assert expected_ids and len(set(expected_ids)) == len(expected_ids)
    assert [f["id"] for f in features] == expected_ids
    assert len({tuple(f["geometry"]["coordinates"]) for f in features}) == len(expected_ids)
    output = folder / "derived_prediction_targets/prediction_points.geojson"
    write(output, {"type": "FeatureCollection", "features": features})
    provenance = [{"path": archive_relative(p, ROOT).as_posix(), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in sources]
    write(folder / "prediction_points_review.json", {"target_count": len(features), "ordered_upstream_to_downstream": True,
          "all_points_on_selected_mainstem": True, "all_prediction_values_null": True,
          "inputs": provenance, "targets": [{**f["properties"], "coordinates": f["geometry"]["coordinates"]} for f in features]})
    manifest = read(folder / "manifest.json")
    relative = output.relative_to(folder).as_posix()
    manifest["layers"] = [e for e in manifest["layers"] if e["path"] != relative]
    manifest["layers"].append({"path": relative, "count": len(features),
          "sha256": hashlib.sha256(output.read_bytes()).hexdigest(), "source": "derived_prediction_targets",
          "style": "prediction", "title": f"Prediction targets - {expected_ids[0]} to {expected_ids[-1]} (red)"})
    manifest["prediction_targets_review"] = "prediction_points_review.json"
    write(folder / "manifest.json", manifest)
    for f in features:
        p = f["properties"]
        print(p["target_id"], p["name"], p["on_section_id"], round(p["chainage_from_dickson_m"], 1))


if __name__ == "__main__":
    build()

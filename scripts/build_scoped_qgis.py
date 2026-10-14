"""Build a Dickson outlet to the selected bridge map from saved data.

Routing uses connected NHN geometry with named-river constraints. Its orientation
is set by the verified endpoints, not an assertion of hydraulic calibration.
"""

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import heapq
import io
import json
import math
from pathlib import Path
import zipfile

import shapefile
from pyproj import Transformer
from shapely import voronoi_polygons
from shapely.geometry import LineString, MultiPoint, Point, mapping, shape
from shapely.ops import transform, substring, unary_union
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT / "data/processed/qgis_layers_20261011"
TO_M = Transformer.from_crs(4326, 3400, always_xy=True, allow_ballpark=False).transform
FROM_NHN = Transformer.from_crs(4617, 3400, always_xy=True, allow_ballpark=False).transform
TO_WGS = Transformer.from_crs(3400, 4326, always_xy=True, allow_ballpark=False).transform


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metric(lon, lat):
    return Point(TO_M(lon, lat))


class Network:
    def __init__(self):
        self.edges = []
        self.inputs = []
        seen = set()
        for path in sorted((ROOT / "data/sources/nrcan_nhn/static/nhn").glob("*.zip")):
            self.inputs.append({"path": path.relative_to(ROOT).as_posix(), "sha256": sha(path)})
            with zipfile.ZipFile(path) as z:
                for name in z.namelist():
                    if not name.endswith("NLFLOW_1.shp"):
                        continue
                    base = name[:-4]
                    reader = shapefile.Reader(shp=io.BytesIO(z.read(name)),
                        dbf=io.BytesIO(z.read(base + ".dbf")), shx=io.BytesIO(z.read(base + ".shx")),
                        encoding="utf-8", encodingErrors="replace")
                    for record in reader.iterShapeRecords():
                        p = record.record.as_dict()
                        coords = list(record.shape.points)
                        if p["NID"] in seen or len(coords) < 2:
                            continue
                        if not any(-114.8 < x < -113.4 and 51.85 < y < 52.4 for x, y in coords):
                            continue
                        seen.add(p["NID"])
                        self.edges.append({"id": p["NID"], "name": (p.get("NAME_1") or p.get("NAME_2") or "").upper(),
                            "line": transform(FROM_NHN, LineString(coords)), "direction": p["DIRECTION"],
                            "a": str(tuple(round(v, 6) for v in coords[0])),
                            "b": str(tuple(round(v, 6) for v in coords[-1]))})

    def route(self, start, end, river, include_receiving_mainstem=False):
        allowed = {"", river}
        if include_receiving_mainstem:
            allowed.add("RED DEER RIVER")
        edges = [e for e in self.edges if e["name"] in allowed]
        tree = STRtree([e["line"] for e in edges])
        si, ei = (int(tree.nearest(p)) for p in (start, end))
        marks = defaultdict(list)
        marks[si].append((edges[si]["line"].project(start), "START"))
        marks[ei].append((edges[ei]["line"].project(end), "END"))
        adj = defaultdict(list)
        for i, e in enumerate(edges):
            cuts = [(0, e["a"]), *marks[i], (e["line"].length, e["b"])]
            cuts.sort()
            for (d0, a), (d1, b) in zip(cuts, cuts[1:]):
                line = substring(e["line"], d0, d1)
                adj[a].append((b, d1-d0, line, e, True))
                adj[b].append((a, d1-d0, line, e, False))
        queue, distances, previous = [(0, "START")], {"START": 0}, {}
        while queue:
            distance, node = heapq.heappop(queue)
            if distance != distances[node]:
                continue
            if node == "END":
                break
            for neighbor, length, line, edge, forward in adj[node]:
                new = distance + length
                if new < distances.get(neighbor, math.inf):
                    distances[neighbor] = new
                    previous[neighbor] = (node, line, edge, forward)
                    heapq.heappush(queue, (new, neighbor))
        if "END" not in distances:
            raise ValueError(f"No connected same-river route: {river}")
        segments, node = [], "END"
        while node != "START":
            prior, line, edge, forward = previous[node]
            if line.geom_type == "LineString":
                segments.append((line if forward else LineString(list(line.coords)[::-1]), edge, forward))
            node = prior
        segments.reverse()
        coords, conflicts, gaps = [], [], []
        for line, edge, forward in segments:
            if coords:
                gaps.append(Point(coords[-1]).distance(Point(line.coords[0])))
            coords.extend(list(line.coords))
            expected = 1 if forward else 2
            if edge["direction"] in (1, 2) and edge["direction"] != expected:
                conflicts.append(edge["id"])
        if max(gaps, default=0) > 0.3:
            raise ValueError("Route has a discontinuity larger than endpoint rounding")
        return LineString(coords), {"length_m": distances["END"],
            "start_snap_m": edges[si]["line"].distance(start), "end_snap_m": edges[ei]["line"].distance(end),
            "edge_ids": list(dict.fromkeys(e["id"] for _, e, _ in segments)),
            "source_direction_conflict_ids": list(dict.fromkeys(conflicts)),
            "method": "connected_geometry_shortest_path_constrained_to_same_river_or_unnamed_edges",
            "orientation": "specified upstream input to downstream endpoint; hydraulic transfer unvalidated"}


def feature(geometry, **properties):
    return {"type": "Feature", "properties": properties, "geometry": mapping(transform(TO_WGS, geometry))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--bridge", required=True)
    parser.add_argument("--endpoint", choices=["joffre"], default="joffre")
    parser.add_argument("--folder", default="data/processed/qgis_dickson_joffre_20261012")
    args = parser.parse_args()
    output = (ROOT / args.folder).resolve()
    if not output.is_relative_to((ROOT / "data/processed").resolve()) or output.exists():
        raise ValueError("Choose a new folder under data/processed")
    report = read(ROOT / args.snapshot)
    fresh = {(r["kind"], r["station_id"]): r for r in report["results"]}
    master = {s["station_id"]: s for s in read(ROOT / "data/processed/station_master.json")}
    network = Network()
    start = metric(master["05CB007"]["longitude"], master["05CB007"]["latitude"])
    endpoint_label = "Joffre Bridge / Highway 11"
    rough_end = metric(-113.588, 52.268)
    rough, _ = network.route(start, rough_end, "RED DEER RIVER")
    bridge = read(ROOT / args.bridge)
    crossings = []
    for item in bridge["elements"]:
        if item.get("tags", {}).get("ref") != "11":
            continue
        road = transform(TO_M, LineString([(p["lon"], p["lat"]) for p in item["geometry"]]))
        hit = rough.intersection(road)
        if hit.geom_type == "Point" and not hit.is_empty:
            crossings.append((rough.project(hit), hit, item["id"]))
    if not crossings:
        raise ValueError("OSM Highway 11 bridge does not intersect the routed mainstem")
    _, endpoint, bridge_id = max(crossings, key=lambda row: row[0])
    mainstem, main_audit = network.route(start, endpoint, "RED DEER RIVER")
    routes = {"RED DEER RIVER": mainstem}
    audits = {"RED DEER RIVER": main_audit}
    river_features = [feature(mainstem, river="RED DEER RIVER", role="selected_mainstem", **main_audit)]
    keep = {"05CB007", "05CC002"}
    outlets = []
    gaps = []
    for outlet in read(ROOT / "data/processed/tributary_outlets.json"):
        if not outlet.get("direct_to_mainstem"):
            continue
        mouth = metric(outlet["longitude"], outlet["latitude"])
        distance = mainstem.project(mouth)
        if mainstem.distance(mouth) > 1000 or not 1 < distance < mainstem.length - 1:
            continue
        name = outlet["watercourse"]
        outlets.append({**outlet, "mainstem_chainage_m": distance, "mainstem_offset_m": mainstem.distance(mouth)})
        candidates = []
        for c in outlet.get("candidates", []):
            sid = c["station_id"]
            r = fresh.get(("water", sid), {})
            if r.get("status") != "numeric_observations" or c.get("along_river_distance_m") is None:
                continue
            age = (datetime.fromisoformat(report["run"].replace("Z", "+00:00")) -
                   datetime.fromisoformat(r["latest_observation"].replace("Z", "+00:00"))).total_seconds()
            if 0 <= age <= 48 * 3600:
                candidates.append((c["along_river_distance_m"], sid))
        if candidates:
            _, sid = min(candidates)
            s = master[sid]
            target = mainstem.interpolate(distance)
            line, audit = network.route(metric(s["longitude"], s["latitude"]), target, name,
                                        include_receiving_mainstem=True)
            contact = line.intersection(mainstem)
            def contact_points(geometry):
                if geometry.is_empty:
                    return []
                if geometry.geom_type == "Point":
                    return [geometry]
                if geometry.geom_type == "LineString":
                    return [Point(geometry.coords[0]), Point(geometry.coords[-1])]
                return [p for g in geometry.geoms for p in contact_points(g)]
            contacts = contact_points(contact)
            if not contacts:
                if Point(line.coords[-1]).distance(mainstem) > 0.3:
                    raise ValueError("Tributary does not meet selected mainstem")
            else:
                first = min(line.project(p) for p in contacts)
                line = substring(line, 0, first)
            audit["length_m"] = line.length
            audit["mouth_connection"] = "First contact with selected mainstem, including receiving side-channel connectors where needed"
            audit["actual_mouth_lon_lat"] = list(transform(TO_WGS, Point(line.coords[-1])).coords)[0]
            if audit["start_snap_m"] > 200 or audit["end_snap_m"] > 100:
                raise ValueError(f"Tributary endpoints not verified: {name}")
            routes[name], audits[name] = line, audit
            river_features.append(feature(line, river=name, role="tributary_input_to_mouth", station_id=sid, **audit))
            keep.add(sid)
        else:
            parts = [e["line"] for e in network.edges if e["name"] == name]
            if parts:
                line = unary_union(parts)
                routes[name] = line
                river_features.append(feature(line, river=name, role="ungauged_mapped_tributary",
                    note="Available named geometry only; no numeric current station or proven complete upstream geometry."))
            gaps.append({"river": name, "reason": "No current numeric same-river mouth candidate; no empty station displayed."})
    for sid in keep:
        if fresh.get(("water", sid), {}).get("status") != "numeric_observations":
            raise ValueError(f"Selected station lacks fresh snapshot numbers: {sid}")
    output.mkdir(parents=True)
    manifest = {"created_at_utc": datetime.now(timezone.utc).isoformat(), "output_crs": "EPSG:4326",
        "project_title": "Dickson outlet to " + endpoint_label,
        "map_subtitle": "Dickson outlet to Joffre Bridge",
        "project_filename": f"dickson_to_{args.endpoint}.qgz", "layers": [],
        "source_inputs": network.inputs + [{"path": args.snapshot, "sha256": sha(ROOT / args.snapshot)},
                                           {"path": args.bridge, "sha256": sha(ROOT / args.bridge)}]}
    input_paths = [ROOT / "data/processed" / name for name in
                   ("station_master.json", "weather_links.json", "tributary_outlets.json")]
    input_paths += [OLD / "manifest.json", OLD / "eccc_weather_geomet/linked_weather_stations.geojson"]
    input_paths += [OLD / entry["path"] for entry in read(OLD / "manifest.json")["layers"]
                    if entry["style"] == "sections"]
    manifest["source_inputs"] += [{"path": p.relative_to(ROOT).as_posix(), "sha256": sha(p)} for p in input_paths]

    def save(relative, features, source, style, title):
        if not features:
            return
        path = output / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        for f in features:
            g = shape(f["geometry"])
            if g.is_empty or not g.is_valid:
                raise ValueError(f"Invalid exported geometry: {relative}")
        path.write_text(json.dumps({"type": "FeatureCollection", "features": features}), encoding="utf-8")
        manifest["layers"].append({"path": relative, "sha256": sha(path), "count": len(features),
            "source": source, "style": style, "title": title})

    save("nrcan_nhn/selected_rivers.geojson", river_features, "nrcan_nhn", "network", "Selected mainstem and tributaries")
    stations = []
    for sid in sorted(keep):
        s, r = master[sid], fresh[("water", sid)]
        p = r["latest_properties"]
        river = "RED DEER RIVER" if sid == "05CB007" else s["watercourse"]
        stations.append(feature(metric(s["longitude"], s["latitude"]), station_id=sid, name=s["name"], river=river,
            has_data="Y", latest_observation_utc=r["latest_observation"], level_m=p.get("LEVEL"),
            discharge_m3_s=p.get("DISCHARGE"), raw_path=r["raw_path"], coordinate_source="ECCC station catalogue",
            role="dam_tunnel_outlet_not_verified_total_dam_release" if sid == "05CB007" else "water_observation",
            distance_to_selected_river_m=routes[river].distance(metric(s["longitude"], s["latitude"]))))
    save("eccc_hydrometric_geomet/stations.geojson", stations, "eccc_hydrometric_geomet", "hydro", "Water stations - numeric observations")
    retained_sections, excluded_sections = [], []
    for entry in read(OLD / "manifest.json")["layers"]:
        if entry["style"] != "sections":
            continue
        features = []
        for f in read(OLD / entry["path"])["features"]:
            p = f["properties"]
            river = p["river"]
            if river not in routes:
                continue
            line = transform(TO_M, shape(f["geometry"]))
            route = routes[river]
            point = metric(p["longitude"], p["latitude"])
            chainage = route.project(point)
            if line.distance(route) > 100 or not 0.1 < chainage < route.length - 0.1:
                continue
            if p.get("has_data") != "Y" or p.get("profile_point_count", 0) < 2:
                excluded_sections.append(p["section_id"])
                continue
            f["properties"].update(selected_river_chainage_m=chainage, selected_river_offset_m=line.distance(route),
                selection_method="same_named_river_section_within_100m_of_selected_route_and_inside_endpoint_chainages")
            features.append(f)
            retained_sections.append(p["section_id"])
        save(entry["path"], features, entry["source"], "sections", entry["title"])
    links = {x["station_id"]: x for x in read(ROOT / "data/processed/weather_links.json")}
    weather_ids = {links[s]["weather_id"] for s in keep}
    weather_features = []
    for f in read(OLD / "eccc_weather_geomet/linked_weather_stations.geojson")["features"]:
        sid = str(f.get("id") or f["properties"].get("weather_id"))
        if sid not in weather_ids:
            continue
        r = fresh[("weather", sid)]
        if r["status"] != "numeric_observations":
            raise ValueError("Linked weather station lacks numeric precipitation")
        f["properties"].update(latest_observation_utc=r["latest_observation"], raw_path=r["raw_path"],
            linked_water_stations=sorted(s for s in keep if links[s]["weather_id"] == sid))
        weather_features.append(f)
    if len(weather_features) != len(weather_ids):
        raise ValueError("Missing weather geometry")
    save("eccc_weather_geomet/stations.geojson", weather_features, "eccc_weather_geomet", "weather", "Linked precipitation station")
    schematic = unary_union(list(routes.values())).buffer(2000)
    ordered_ids = sorted(keep)
    seeds = MultiPoint([metric(master[s]["longitude"], master[s]["latitude"]) for s in ordered_ids])
    cells = voronoi_polygons(seeds, extend_to=schematic.envelope, ordered=True)
    groups = defaultdict(list)
    for sid, cell in zip(ordered_ids, cells.geoms):
        groups[links[sid]["weather_id"]].append(cell.intersection(schematic))
    areas = [feature(unary_union(parts), weather_id=wid,
        linked_water_stations=sorted(s for s in keep if links[s]["weather_id"] == wid),
        meaning="Existing water-to-weather links assigned through water-site Voronoi cells, clipped to a 2 km river corridor",
        not_official_coverage=True, not_a_catchment=True, cartographic_buffer_m=2000) for wid, parts in groups.items()]
    save("derived_weather_associations/areas.geojson", areas,
        "derived_weather_associations", "weather_areas", "Weather association - schematic river corridor")
    audit = {"snapshot": args.snapshot, "start": "Dickson Dam tunnel outlet downstream of Gleniffer Lake",
        "end": endpoint_label, "osm_bridge_way_id": bridge_id,
        "start_lon_lat": list(transform(TO_WGS, Point(mainstem.coords[0])).coords)[0],
        "end_lon_lat": list(transform(TO_WGS, endpoint).coords)[0], "routes": audits,
        "station_ids": sorted(keep), "weather_ids": sorted(weather_ids), "tributary_outlets": outlets,
        "gaps": gaps, "section_count": len(retained_sections), "section_ids": retained_sections,
        "sections_excluded_no_profile": excluded_sections,
        "excluded_snapshot_stations": [{"station_id": r["station_id"], "status": r["status"],
            "reason": "Outside selected reach/tributary input segment, or no numeric records"}
            for r in report["results"] if r["kind"] == "water" and r["station_id"] not in keep],
        "limitations": ["Network flow-direction conflicts remain explicit; route geometry is not hydraulic validation.",
            "Section horizontal screening uses a 100 m cartographic tolerance and same river names; gauge transfers and vertical datums remain unvalidated.",
            "Dickson tunnel outlet discharge is not confirmed to represent all dam release paths.",
            "Ungauged Sylvan Creek is displayed from available named geometry; no missing observations are invented."]}
    (output / "scope_validation.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({k: audit[k] for k in ("station_ids", "weather_ids", "section_count", "start_lon_lat", "end_lon_lat", "gaps")}, indent=2))
    print("Mainstem length km:", mainstem.length / 1000)


if __name__ == "__main__":
    main()

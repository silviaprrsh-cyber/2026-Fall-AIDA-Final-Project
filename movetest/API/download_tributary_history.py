"""Archive HYDAT station metadata and complete paged daily records once."""

from project_paths import resolve_runtime_path, archive_relative
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from urllib.parse import urlsplit

from API.client import fetch

from project_paths import ROOT
BASE = "https://api.weather.gc.ca/collections"


def acquire(url, relative, params=None):
    for attempt in range(3):
        try:
            target = Path(relative)
            target = target.with_name(f"{target.stem}_attempt{attempt+1}{target.suffix}")
            return fetch(url, target.as_posix(),
                         params, reuse=False, timeout=60)
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 ** (attempt + 1))


def station_history(sid, run):
    result = {"station_id": sid, "pages": [], "complete": False}
    url = BASE + "/hydrometric-daily-mean/items"
    params = {"STATION_NUMBER": sid, "sortby": "DATE", "limit": 10000, "f": "json"}
    seen, total, expected, previous = set(), 0, None, None
    try:
        for page in range(100):
            path = acquire(url, f"raw/tributary_history/{run}/{sid}/page_{page:03}.json", params)
            obj = json.loads(path.read_text(encoding="utf-8-sig"))
            if "features" not in obj:
                raise ValueError("Response has no features")
            features = obj["features"]
            if expected is None:
                expected = obj.get("numberMatched")
            elif obj.get("numberMatched", expected) != expected:
                raise ValueError("Matched count changed during pagination")
            for f in features:
                p = f["properties"]
                if p.get("STATION_NUMBER") != sid:
                    raise ValueError("Station filter mismatch")
                key = f.get("id") or p.get("id") or f"{sid}.{p['DATE']}"
                if key in seen:
                    raise ValueError("Duplicate record across pages")
                if previous is not None and p["DATE"] < previous:
                    raise ValueError("Chronological paging order changed")
                seen.add(key)
                previous = p["DATE"]
            total += len(features)
            result["pages"].append(archive_relative(path, ROOT).as_posix())
            next_links = [x["href"] for x in obj.get("links", []) if x.get("rel") == "next"]
            if not next_links:
                if isinstance(expected, int) and total != expected:
                    raise ValueError(f"Incomplete count {total}/{expected}")
                result.update(complete=True, record_count=total, number_matched=expected,
                              status="downloaded" if total else "no_records")
                break
            if not features:
                raise ValueError("Empty page with a next link")
            url = next_links[0]
            parsed = urlsplit(url)
            if parsed.scheme != "https" or parsed.hostname != "api.weather.gc.ca" or parsed.path != "/collections/hydrometric-daily-mean/items":
                raise ValueError("Unexpected pagination target")
            params = None
        else:
            raise ValueError("Exceeded finite pagination bound")
    except Exception as exc:
        result.update(status="failed_or_incomplete", record_count=total, error=str(exc))
    print(sid, result["status"], total, flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--discover", action="store_true")
    parser.add_argument("--candidates", help="JSON candidate station list with station_id fields")
    args = parser.parse_args()
    run = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if args.discover:
        jobs = [
            (BASE + "/hydrometric-stations/items", f"raw/tributary_history/{run}/station_metadata.json",
             {"bbox": "-115.7,51,-113.3,53.5", "limit": 10000, "f": "json"}),
            (BASE + "/hydrometric-daily-mean", f"raw/tributary_history/{run}/collection.json", {"f": "json"}),
            ("https://wateroffice.ec.gc.ca/station_metadata/reference_index_download_e.html",
             f"raw/tributary_history/{run}/station_index.csv", None),
        ]
        with ThreadPoolExecutor(max_workers=3) as pool:
            for path in pool.map(lambda job: acquire(*job), jobs):
                print(path, flush=True)
        return
    if not args.candidates:
        parser.error("Use --discover or --candidates")
    candidates = json.loads((resolve_runtime_path(ROOT / args.candidates)).read_text(encoding="utf-8"))
    ids = sorted({x["station_id"] for x in candidates})
    report = {"run": run, "candidate_file": args.candidates,
              "historical_resolution": "daily mean", "requested_period": "all available dates",
              "results": []}
    directory = resolve_runtime_path(ROOT / "data/reports/tributary_history" / run)
    directory.mkdir(parents=True, exist_ok=False)
    with ThreadPoolExecutor(max_workers=3) as pool:
        for result in pool.map(lambda sid: station_history(sid, run), ids):
            report["results"].append(result)
            (directory / "download_manifest.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(directory / "download_manifest.json", flush=True)


if __name__ == "__main__":
    main()

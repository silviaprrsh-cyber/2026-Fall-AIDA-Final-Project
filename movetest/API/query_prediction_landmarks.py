"""Archive road and footbridge geometry for the selected prediction reach once."""

from datetime import datetime, timezone
import argparse
from API.client import fetch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--details-only", action="store_true")
    args = parser.parse_args()
    run = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if args.details_only:
        query = ('[out:json][timeout:45];('
                 'way["highway"]["name"="76 Street"](52.29,-113.84,52.33,-113.75);'
                 'nwr["name"="Discovery Canyon"](52.29,-113.82,52.36,-113.70);'
                 'way["waterway"]["name"~"^(Sylvan Creek|Red Deer River)$"](52.245,-113.92,52.265,-113.86);'
                 ');out geom;')
    else:
        query = '[out:json][timeout:45];way["bridge"]["highway"](52.03,-114.25,52.40,-113.56);out geom;'
    path = fetch("https://overpass-api.de/api/interpreter",
                 f"raw/prediction_landmarks/{run}/{'details' if args.details_only else 'bridges'}.json",
                 {"data": query}, reuse=False, timeout=55)
    print(path)


if __name__ == "__main__":
    main()

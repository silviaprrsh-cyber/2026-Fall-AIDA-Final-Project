"""Retrieve OSM bridge geometry once to verify the requested downstream cut."""

from datetime import datetime, timezone
import argparse
from API.client import fetch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--endpoint', choices=['joffre'], default='joffre')
    args = parser.parse_args()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    bbox = '52.265,-113.602,52.275,-113.582'
    query = f'[out:json][timeout:25];way["bridge"]["highway"]({bbox});out geom;'
    path = fetch("https://overpass-api.de/api/interpreter",
                 f"raw/scope_boundary/{stamp}/{args.endpoint}_bridges.json",
                 {"data": query}, reuse=False, timeout=35)
    print(path)


if __name__ == "__main__":
    main()

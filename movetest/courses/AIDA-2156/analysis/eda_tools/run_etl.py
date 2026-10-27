"""Build stages 1-4 from local archives; no network or continuous collection."""
import argparse
from pathlib import Path
import sys

from rdr_eda.etl import run_pipeline

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--reuse-spatial',action='store_true',help='Reuse previously normalized surveys and spatial links')
    args=parser.parse_args()
    run_pipeline(rebuild_spatial=not args.reuse_spatial)

"""Build scoped project ETL, or explicitly select the legacy full-basin rebuild."""
import argparse
from pathlib import Path

from rdr_eda.etl import run_pipeline
from rdr_eda.project_etl import run_project_pipeline

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--reuse-spatial',action='store_true',help='Reuse previously normalized surveys and spatial links')
    parser.add_argument('--legacy-full-basin', action='store_true', help='Explicitly rebuild the older full-basin ETL instead of the current project dataset')
    parser.add_argument('--segment-states', type=Path, help='Optional CSV of prior submodel outputs within movetest; no observed downstream labels allowed as states')
    args=parser.parse_args()
    if args.legacy_full_basin:
        if args.segment_states:
            parser.error('--segment-states is not used by the legacy pipeline')
        run_pipeline(rebuild_spatial=not args.reuse_spatial)
    else:
        run_project_pipeline(segment_state_path=args.segment_states)

import argparse
import json
from API.collector import load_config, run

def main():
    parser=argparse.ArgumentParser(description='Red Deer River data collector (no API keys)')
    sub=parser.add_subparsers(dest='command',required=True)
    status=sub.add_parser('status',help='Show per-station configuration without network access')
    watch=sub.add_parser('watch',help='Continuous acquisition until terminal stop / Ctrl+C')
    watch.add_argument('--dry-run',action='store_true',help='Exercise scheduler and stop without network calls')
    watch.add_argument('--wait-first',action='store_true',help='Wait each source interval before first acquisition')
    watch.add_argument('--station',action='append',help='Limit to a configured station; may repeat')
    args=parser.parse_args();config=load_config()
    if args.command=='status':
        for s in config['stations']:
            print(json.dumps({'station_id':s['station_id'],'enabled':s['enabled'],
                'calculation_interval_seconds':s.get('calculation_interval_seconds'),
                'mode':s.get('mode'),'sources':[{'kind':a['kind'],'station_id':a['station_id'],
                    'poll_interval_seconds':a['publication_interval_seconds'],
                    'interval_evidence':a.get('interval_evidence')} for a in s['sources']]}))
    else:run(config,dry_run=args.dry_run,collect_immediately=not args.wait_first,selected=args.station)

if __name__=='__main__':main()

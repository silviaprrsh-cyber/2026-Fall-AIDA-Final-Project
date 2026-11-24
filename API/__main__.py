from project_paths import resolve_runtime_path, archive_relative
import argparse
import json
from API.collector import load_config, run
from rdr.storage import DATA, ROOT

def main():
    parser=argparse.ArgumentParser(description='Red Deer River data collector (no API keys)')
    sub=parser.add_subparsers(dest='command',required=True)
    status=sub.add_parser('status',help='Show per-station configuration without network access')
    sub.add_parser('stop',help='Request a graceful stop of the recorded active run')
    watch=sub.add_parser('watch',help='Continuous acquisition until terminal stop / Ctrl+C')
    watch.add_argument('--dry-run',action='store_true',help='Exercise scheduler and stop without network calls')
    watch.add_argument('--wait-first',action='store_true',help='Wait each source interval before first acquisition')
    watch.add_argument('--station',action='append',help='Limit to a configured station; may repeat')
    watch.add_argument('--duration-seconds',type=float,help='Stop new requests automatically after this duration')
    watch.add_argument('--detached',action='store_true',help='Ignore stdin; requires a finite duration and supports the state-file stop control')
    args=parser.parse_args()
    if args.command=='stop':
        state_path=resolve_runtime_path(DATA/'state/active_run.json')
        if not state_path.exists():
            print('No recorded active run.');return
        state=json.loads(state_path.read_text(encoding='utf-8'))
        if state.get('status')!='running':
            print('The recorded run is already stopped.');return
        path=(resolve_runtime_path(ROOT/state['stop_file'])).resolve()
        if path.parent!=(resolve_runtime_path(DATA/'state')).resolve() or path.suffix!='.stop':
            raise ValueError('Invalid stop-control path')
        path.write_text('stop\n',encoding='utf-8')
        print('Stop requested; in-flight requests will finish or time out.');return
    config=load_config()
    if args.command=='status':
        for s in config['stations']:
            print(json.dumps({'station_id':s['station_id'],'enabled':s['enabled'],
                'calculation_interval_seconds':s.get('calculation_interval_seconds'),
                'mode':s.get('mode'),'sources':[{'kind':a['kind'],'station_id':a['station_id'],
                    'poll_interval_seconds':a['publication_interval_seconds'],
                    'interval_evidence':a.get('interval_evidence')} for a in s['sources']]}))
    else:run(config,dry_run=args.dry_run,collect_immediately=not args.wait_first,selected=args.station,
             duration_seconds=args.duration_seconds,detached=args.detached)

if __name__=='__main__':main()

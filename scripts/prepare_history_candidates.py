"""Select upstream historical stations using fresh WSC inventory and saved topology."""
import csv
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rdr.catalog import watercourse


def main():
    folder = ROOT / 'data/processed/tributary_history_20261012'
    meta_path = ROOT / 'data/sources/eccc_hydrometric_geomet/raw/tributary_history/20261013T024546Z/station_metadata_attempt1.json'
    obj = json.loads(meta_path.read_text())
    assert len(obj['features']) == obj['numberMatched']
    rows = list(csv.DictReader((folder/'station_index_normalized.csv').open(encoding='utf-8-sig', newline='')))
    index = {}
    for row in rows:
        index.setdefault(row['Station Number'], []).append(row)
    roots = {'LITTLE RED DEER RIVER', 'MEDICINE RIVER', 'SYLVAN CREEK', 'WASKASOO CREEK', 'BLINDMAN RIVER'}
    outlets = json.loads((ROOT/'data/processed/tributary_outlets.json').read_text())
    parent = {r['watercourse']: r['parent_river'] for r in outlets}
    # WSC stream-order rows place Block Creek below the Welsh Creek heading.
    parent['BLOCK CREEK'] = 'WELCH CREEK'
    lakes = {'SYLVAN LAKE': 'SYLVAN CREEK', 'CYGNET LAKE': 'SYLVAN CREEK', 'GULL LAKE': 'BLINDMAN RIVER'}
    candidates = []
    for f in obj['features']:
        p = f['properties']; sid = p['STATION_NUMBER']; river = watercourse(p['STATION_NAME'])
        if not sid.startswith('05C'):
            continue
        chain, current = [river], river
        while current not in roots and current in parent and parent[current] not in chain:
            current = parent[current]; chain.append(current)
        role = 'tributary_channel_station'
        evidence = 'Fresh WSC station inventory plus archived named-river parent hierarchy; hydraulic transfer unvalidated'
        if river in lakes:
            current = lakes[river]; chain = [river, current]; role = 'lake_level_reference'
            evidence = 'WSC stream-order inventory lake grouping; storage reference only, current outlet flow not established'
        if current not in roots:
            continue
        if sid not in index:
            raise ValueError(f'Station missing from fresh WSC reference index: {sid}')
        if river == 'BLOCK CREEK':
            positions = [i for i, r in enumerate(rows) if r['Station Number'] == sid]
            assert any('WELSH CREEK:' in r['Water Course'] for r in rows[max(0, positions[0]-3):positions[0]])
            evidence = 'Fresh WSC stream-order index: Block Creek nested under Welsh Creek in Medicine River group'
        candidates.append({'station_id': sid, 'name': p['STATION_NAME'], 'river': river,
            'root_tributary': current, 'parent_chain': chain, 'role': role,
            'longitude': f['geometry']['coordinates'][0], 'latitude': f['geometry']['coordinates'][1],
            'coordinate_crs': 'EPSG:4326', 'metadata_source': meta_path.relative_to(ROOT).as_posix(),
            'membership_evidence': evidence, 'provider_station_status': p.get('STATUS_EN'),
            'vertical_datum': p.get('VERTICAL_DATUM'),
            'index_periods': [{k: r[k] for k in ('Year From','Year To','Data Type','Operation Schedule')} for r in index[sid]]})
    candidates.sort(key=lambda r: r['station_id'])
    (folder/'candidates.json').write_text(json.dumps(candidates, indent=2), encoding='utf-8')
    print('Candidates',len(candidates))
    for r in candidates:
        print(r['station_id'],r['root_tributary'],r['role'])


if __name__ == '__main__':
    main()

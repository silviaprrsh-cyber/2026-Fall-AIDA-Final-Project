import io
import json
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from API.collector import (station_interval, listen_for_stop, ObservationStore, Collector,
                           load_config, source_schedules, station_calculation_interval)
from API.observations import precipitation,cadence


class CollectorTests(unittest.TestCase):
    def test_explicit_interval_agrees_with_etl_without_changing_source_schedules(self):
        from rdr.etl import station_windows
        station = {'station_id': 'S', 'enabled': True,
                   'calculation_interval_seconds': 7200,
                   'weather_link': {'weather_id': 'W'}, 'sources': [
                       {'kind': 'hydrometric_hourly_csv', 'station_id': 'S',
                        'publication_interval_seconds': 3600, 'url': 'water'},
                       {'kind': 'swob', 'station_id': 'W',
                        'publication_interval_seconds': 900, 'url': 'weather'}]}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'stations.json'
            original = json.dumps({'stations': [station]})
            path.write_text(original, encoding='utf-8')
            loaded = load_config(path)
            self.assertEqual(path.read_text(encoding='utf-8'), original)
        self.assertEqual(loaded['stations'][0]['calculation_interval_seconds'], 7200)
        jobs = source_schedules(loaded['stations'])
        self.assertEqual(sorted(j['source']['publication_interval_seconds'] for j in jobs.values()), [900, 3600])
        water = [{'station_id': 'S', 'observed_at': '2026-09-28T02:00:00+00:00',
                  'resolution': 'instantaneous', 'level_m': 1, 'discharge_m3_s': 2,
                  'raw_path': 'source.csv'}]
        for config in [loaded, {'stations': [station]}]:
            window = station_windows(water, [], config)[0]
            self.assertEqual(window['duration_seconds'], 7200)
            self.assertEqual(window['window_start'], '2026-09-28T00:00:00+00:00')

    def test_calculation_interval_fallback_and_invalid_overrides(self):
        station = {'sources': [{'kind': 'hydrometric_hourly_csv',
                                'publication_interval_seconds': 3600}]}
        self.assertEqual(station_calculation_interval(station), 3600)
        self.assertEqual(station_calculation_interval(dict(station, calculation_interval_seconds=None)), 3600)
        self.assertIsNone(station_calculation_interval({'sources': []}))
        for value in [0, -1, True, '7200', float('nan'), float('inf')]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                station_calculation_interval(dict(station, calculation_interval_seconds=value))

    def test_independent_maximum_intervals(self):
        a=[{'publication_interval_seconds':300},{'publication_interval_seconds':3600}]
        b=[{'publication_interval_seconds':900},{'publication_interval_seconds':60}]
        self.assertEqual(station_interval(a),3600)
        self.assertEqual(station_interval(b),900)

    def test_unknown_cadence_not_silently_defaulted(self):
        for v in [None,0,-1,True,float('nan'),float('inf')]:
            with self.assertRaises(ValueError):station_interval([{'publication_interval_seconds':v}])

    def test_stop_and_eof(self):
        for text in ['status\nSTOP\n','']:
            stop=threading.Event();listen_for_stop(stop,io.StringIO(text));self.assertTrue(stop.is_set())

    def test_missing_precipitation_is_not_zero(self):
        self.assertIsNone(precipitation({'pcpn_amt_pst1hr':None}))
        self.assertIsNone(precipitation({'pcpn_amt_pst1hr':0,'pcpn_amt_pst1hr-qa':-1}))
        self.assertEqual(precipitation({'pcpn_amt_pst1hr':0,'pcpn_amt_pst1hr-qa':100,'pcpn_amt_pst1hr-uom':'mm'})['value'],0)

    def test_timestamp_cadence_is_labelled_estimate(self):
        result=cadence(['2026-09-28T00:00:00Z','2026-09-28T01:00:00Z','2026-09-28T02:00:00Z','2026-09-28T03:00:00Z'])
        self.assertEqual(result['seconds'],3600)
        self.assertEqual(result['status'],'observed_estimate')

    def test_deduplication_revision_and_cursor(self):
        with tempfile.TemporaryDirectory() as temp:
            store=ObservationStore(Path(temp)/'obs.sqlite3')
            records=[('id1','2026-09-28T01:00:00+00:00',{'level':1},'raw/a.json')]
            store.write('water','S',records);store.write('water','S',records)
            store.write('water','S',[('id1',records[0][1],{'level':2},'raw/revision.json')])
            store.write('water','S',[('old','2026-09-27T00:00:00+00:00',{'level':0},'raw/old.json')])
            with store.connect() as db:
                self.assertEqual(db.execute('SELECT COUNT(*) FROM observations').fetchone()[0],2)
                self.assertEqual(json.loads(db.execute("SELECT payload FROM observations WHERE record_id='id1'").fetchone()[0]),{'level':2})
            self.assertEqual(store.cursor('water','S'),records[0][1])

    def test_stop_blocks_network(self):
        with tempfile.TemporaryDirectory() as temp:
            stop=threading.Event();stop.set();collector=Collector(stop,ObservationStore(Path(temp)/'obs.sqlite3'))
            with patch('API.collector.get_json') as network:
                self.assertEqual(collector.collect({'kind':'swob','station_id':'W','publication_interval_seconds':3600})['status'],'stopped')
                network.assert_not_called()

    def test_weather_pagination_not_limited_to_latest_48(self):
        with tempfile.TemporaryDirectory() as temp:
            collector=Collector(threading.Event(),ObservationStore(Path(temp)/'obs.sqlite3'))
            def feature(i):return {'id':str(i),'properties':{'msc_id-value':'W','date_tm-value':f'2026-09-28T0{i}:00:00Z','pcpn_amt_pst1hr':0}}
            pages=[{'features':[feature(1)],'links':[{'rel':'next','href':'https://api.weather.gc.ca/page2'}]},
                   {'features':[feature(2)],'links':[]}]
            with patch('API.collector.get_json',side_effect=pages) as network:
                rows=collector._fetch({'kind':'swob','station_id':'W'},'raw/test')
            self.assertEqual(len(rows),2);self.assertEqual(network.call_count,2)

    def test_wrong_weather_station_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            collector=Collector(threading.Event(),ObservationStore(Path(temp)/'obs.sqlite3'))
            with patch('API.collector.get_json',return_value={'features':[{'id':'x','properties':{'msc_id-value':'OTHER'}}]}):
                with self.assertRaises(ValueError):collector._fetch({'kind':'swob','station_id':'W'},'raw/test')

if __name__=='__main__':unittest.main()

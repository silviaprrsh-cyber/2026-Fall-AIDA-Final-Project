import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from API.collector import run
from API.datamart_notifications import DatamartNotifications
from API.__main__ import main


class TimedCollectionTests(unittest.TestCase):
    def test_stop_command_writes_only_the_recorded_state_control(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); data=root/'data'; state=data/'state'
            state.mkdir(parents=True)
            active={'status':'running','stop_file':'data/state/example.stop'}
            (state/'active_run.json').write_text(json.dumps(active))
            with patch('API.__main__.ROOT',root),patch('API.__main__.DATA',data),patch('sys.argv',['API','stop']):
                main()
            self.assertEqual((state/'example.stop').read_text(),'stop\n')

    def test_stop_command_rejects_a_control_path_outside_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); data=root/'data'; state=data/'state'
            state.mkdir(parents=True)
            (state/'active_run.json').write_text(json.dumps({'status':'running','stop_file':'outside.stop'}))
            with patch('API.__main__.ROOT',root),patch('API.__main__.DATA',data),patch('sys.argv',['API','stop']):
                with self.assertRaises(ValueError):main()
            self.assertFalse((root/'outside.stop').exists())

    def config(self, kind='swob', station='W'):
        return {'max_workers': 1, 'stations': [
            {'station_id': 'M', 'enabled': True, 'sources': [
                {'kind': kind, 'station_id': station, 'url': 'https://example.test',
                 'publication_interval_seconds': 0.05}]}]}

    def test_finite_detached_run_stops_and_saves_state(self):
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory)
            start = time.monotonic()
            with patch('API.collector.DATA', data), patch('API.collector.ROOT', data), patch('API.collector.Collector') as collector:
                run(self.config(), dry_run=True, detached=True, duration_seconds=0.35)
                collector.assert_not_called()
            state = json.loads((data/'state/last_run.json').read_text())
            self.assertEqual(state['reason'], 'duration_elapsed')
            self.assertEqual(state['status'], 'stopped')
            self.assertGreater(state['jobs_submitted'], 0)
            self.assertLess(time.monotonic()-start, 3)

    def test_detached_requires_duration_and_rejects_invalid_limits(self):
        with self.assertRaises(ValueError):
            run(self.config(), dry_run=True, detached=True)
        for value in [0, -1, True, float('inf'), float('nan')]:
            with self.assertRaises(ValueError):
                run(self.config(), dry_run=True, duration_seconds=value)

    def test_notifications_match_selected_product_and_coalesce(self):
        feed = DatamartNotifications(['05CC002'], threading.Event())
        with patch('API.datamart_notifications.log'):
            for prefix in ['', '20261010/WXO-DD/']:
                body = f'20261010210000 https://dd.weather.gc.ca/ {prefix}hydrometric/csv/AB/hourly/AB_05CC002_hourly_hydrometric.csv'
                feed.accept(body.encode())
            feed.accept(b'x https://dd.weather.gc.ca/ hydrometric/csv/AB/hourly/AB_05CA009_hourly_hydrometric.csv')
            feed.accept(b'x https://dd.weather.gc.ca/ hydrometric/csv/AB/daily/AB_05CC002_daily_hydrometric.csv')
        self.assertEqual(feed.notifications, 2)
        self.assertTrue(feed.take('05CC002'))
        self.assertFalse(feed.take('05CC002'))
        self.assertFalse(feed.take('05CA009'))

    def test_water_is_not_polled_without_a_new_notification(self):
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory)
            with patch('API.collector.DATA', data), patch('API.collector.ROOT', data), \
                    patch('API.datamart_notifications.DatamartNotifications') as factory, \
                    patch('API.collector.Collector') as collector:
                factory.return_value.take.return_value = False
                factory.return_value.status.return_value = {'connected': True}
                collector.return_value.collect.return_value = {'status': 'ok', 'records': 1}
                run(self.config('hydrometric_hourly_csv', '05CC002'),
                    detached=True, duration_seconds=0.7)
                self.assertEqual(collector.return_value.collect.call_count, 1)
                factory.return_value.close.assert_called_once()

    def test_stop_file_ends_detached_run(self):
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory)
            def stop_when_running():
                path = data/'state/active_run.json'
                deadline = time.monotonic()+2
                while not path.exists() and time.monotonic()<deadline:
                    time.sleep(0.01)
                if path.exists():
                    state = json.loads(path.read_text())
                    (data/state['stop_file']).touch()
            thread = threading.Thread(target=stop_when_running)
            thread.start()
            with patch('API.collector.DATA', data), patch('API.collector.ROOT', data):
                run(self.config(), dry_run=True, detached=True, duration_seconds=5)
            thread.join()
            state = json.loads((data/'state/last_run.json').read_text())
            self.assertEqual(state['reason'], 'stop_file')
            self.assertFalse((data/state['stop_file']).exists())

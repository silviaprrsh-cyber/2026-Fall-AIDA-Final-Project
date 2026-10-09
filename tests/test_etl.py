import json
import math
from pathlib import Path
import sqlite3
import tempfile
import unittest

from API.collector import calculation_interval, source_schedules
from rdr.etl import station_windows, write_database, calculate_sections
from rdr.hydraulics import (section_geometry, screen_section, reach_storage,
                            travel_time_seconds, routed_discharge, rating_level)
from rdr.rainfall import aggregate_precipitation, normalize_swob


def stamp(minutes):
    return f'2026-09-28T{minutes//60:02}:{minutes%60:02}:00+00:00'


def rain(a,b,amount,**extra):
    return {'station_id':'W','field':'precip','start':stamp(a),'end':stamp(b),
            'amount_mm':amount,'valid':True,'record_id':f'{a}-{b}',**extra}


class RainfallTests(unittest.TestCase):
    def test_quarter_hour_depths_are_summed_not_averaged(self):
        result=aggregate_precipitation([rain(0,15,1),rain(15,30,2),rain(30,45,0),rain(45,60,3)],stamp(0),stamp(60))
        self.assertEqual(result['precipitation_total_mm'],6)
        self.assertEqual(result['mean_precipitation_intensity_mm_h'],6)
        self.assertEqual(result['input_interval_count'],4)

    def test_intensity_is_weighted_by_duration(self):
        rows=[rain(0,15,None,kind='intensity',intensity_mm_h=8),
              rain(15,60,None,kind='intensity',intensity_mm_h=2)]
        result=aggregate_precipitation(rows,stamp(0),stamp(60))
        self.assertEqual(result['precipitation_total_mm'],3.5)
        self.assertEqual(result['mean_precipitation_intensity_mm_h'],3.5)
        longer=aggregate_precipitation([rain(0,120,6)],stamp(0),stamp(120))
        self.assertEqual(longer['mean_precipitation_intensity_mm_h'],3)

    def test_rolling_hour_is_used_once(self):
        rows=[rain(i,i+60,6) for i in range(61)]
        result=aggregate_precipitation(rows,stamp(0),stamp(60))
        self.assertEqual(result['precipitation_total_mm'],6)
        self.assertEqual(result['input_interval_count'],1)

    def test_overlap_and_missing_are_not_double_counted_or_zero_filled(self):
        rows=[rain(0,30,2),rain(15,45,3)]
        result=aggregate_precipitation(rows,stamp(0),stamp(60))
        self.assertEqual(result['coverage_fraction'],0.5)
        self.assertIsNone(result['precipitation_total_mm'])
        self.assertIsNone(result['mean_precipitation_intensity_mm_h'])
        self.assertEqual(aggregate_precipitation([],stamp(0),stamp(60))['status'],'missing')

    def test_latest_invalid_revision_supersedes_valid_value(self):
        rows=[rain(0,60,2,available_at=stamp(61)),
              rain(0,60,None,available_at=stamp(62),valid=False)]
        self.assertIsNone(aggregate_precipitation(rows,stamp(0),stamp(60))['precipitation_total_mm'])
        self.assertEqual(aggregate_precipitation(rows,stamp(0),stamp(60),as_of=stamp(61))['precipitation_total_mm'],2)
        self.assertIsNone(aggregate_precipitation(rows,stamp(0),stamp(60),as_of=stamp(60))['precipitation_total_mm'])

    def test_swob_period_and_quality(self):
        p={'msc_id-value':'W','date_tm-value':stamp(60),'pcpn_amt_pst15mts':1,
           'pcpn_amt_pst15mts-uom':'mm','pcpn_amt_pst15mts-qa':100}
        row=normalize_swob(p,'raw.json')[0]
        self.assertEqual(row['period_seconds'],900)
        self.assertEqual(row['start'],stamp(45))
        self.assertTrue(row['valid'])
        p['pcpn_amt_pst15mts-data_flag-value']='5'
        self.assertFalse(normalize_swob(p,'raw.json')[0]['valid'])


class HydraulicTests(unittest.TestCase):
    def test_partial_triangle_and_perimeter(self):
        geometry=section_geometry([(0,2),(2,0),(4,2)],1)
        self.assertAlmostEqual(geometry['area_m2'],1)
        self.assertAlmostEqual(geometry['surface_width_m'],2)
        self.assertAlmostEqual(geometry['wetted_perimeter_m'],2*math.sqrt(2))
        self.assertFalse(geometry['profile_truncated'])

    def test_disconnected_pools_require_main_channel_evidence(self):
        profile=[(0,2),(2,0),(4,2),(6,0),(8,2)]
        args=dict(level_m=1,gauge_zero_m=0,discharge_m3_s=10,
                  datum_verified=True,transfer_verified=True,profile_verified=True)
        result=screen_section(profile,**args)
        self.assertEqual(result['wet_components'],2)
        self.assertIsNone(result['mean_velocity_m_s'])
        selected=screen_section(profile,connected_offset_m=2,**args)
        self.assertEqual(selected['area_m2'],1)
        self.assertEqual(selected['mean_velocity_m_s'],10)

    def test_no_datum_or_transfer_means_no_live_risk(self):
        result=screen_section([(0,2),(2,0),(4,2)],level_m=1,gauge_zero_m=0)
        self.assertEqual(result['status'],'indeterminate')
        self.assertIsNone(result['risk_level'])

    def test_verified_synthetic_freeboard_velocity(self):
        result=screen_section([(0,2),(2,0),(4,2)],level_m=1,gauge_zero_m=0,
            discharge_m3_s=2,bank_elevations_m=[2,1.4],datum_verified=True,
            transfer_verified=True,profile_verified=True,banks_verified=True)
        self.assertEqual(result['mean_velocity_m_s'],2)
        self.assertAlmostEqual(result['freeboard_m'],0.4)
        self.assertEqual(result['risk_level'],'orange')

    def test_reach_and_routing_reject_double_counting(self):
        self.assertEqual(reach_storage(10,20,100),1500)
        self.assertEqual(travel_time_seconds(100,2),50)
        rows=[{'contributing_area_ids':['A'],'observed_at':stamp(0),'lag_seconds':3600,'discharge_m3_s':10},
              {'contributing_area_ids':['B'],'observed_at':stamp(30),'lag_seconds':1800,'discharge_m3_s':5}]
        self.assertEqual(routed_discharge(rows,target_time=stamp(60),incremental_runoff_m3_s=2),17)
        rows[1]['contributing_area_ids']=['A']
        with self.assertRaises(ValueError):routed_discharge(rows,target_time=stamp(60))
        with self.assertRaises(ValueError):routed_discharge(rows[:1],target_time=stamp(30))
        self.assertEqual(rating_level(15,[(10,2),(20,4)]),3)
        with self.assertRaises(ValueError):rating_level(25,[(10,2),(20,4)])


class PipelineTests(unittest.TestCase):
    def test_water_hour_does_not_slow_weather_quarter_hour(self):
        sources=[{'kind':'hydrometric_hourly_csv','station_id':'S','url':'water','publication_interval_seconds':3600},
                 {'kind':'swob','station_id':'W','url':'weather','publication_interval_seconds':900}]
        jobs=source_schedules([{'station_id':'S','sources':sources},
                              {'station_id':'T','sources':[sources[1]]}])
        self.assertEqual(len(jobs),2)
        self.assertEqual(jobs['swob','W']['source']['publication_interval_seconds'],900)
        self.assertEqual(jobs['swob','W']['monitoring_stations'],['S','T'])
        self.assertEqual(calculation_interval(sources),3600)
        water=[{'station_id':'S','resolution':'instantaneous','observed_at':stamp(65),
                'level_m':1,'discharge_m3_s':2,'raw_path':'raw/water.csv'}]
        rows=[rain(5,20,1),rain(20,35,2),rain(35,50,0),rain(50,65,3)]
        config={'stations':[{'station_id':'S','sources':sources,'weather_link':{'weather_id':'W'}}]}
        result=station_windows(water,rows,config)[0]
        self.assertEqual(result['window_start'],stamp(5))
        self.assertEqual(result['precipitation_total_mm'],6)

    def test_conflicting_shared_source_cadence_rejected(self):
        stations=[{'station_id':'A','sources':[{'kind':'swob','station_id':'W','url':'x','publication_interval_seconds':60}]},
                  {'station_id':'B','sources':[{'kind':'swob','station_id':'W','url':'x','publication_interval_seconds':900}]}]
        with self.assertRaises(ValueError):source_schedules(stations)

    def test_database_snapshot_closes_file_before_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)
            for value in [1,2]:write_database(path,{'sample':([{'value':value}],lambda row,index:'one')})
            db=sqlite3.connect(path/'project.sqlite3')
            try:self.assertEqual(json.loads(db.execute('SELECT payload FROM sample').fetchone()[0])['value'],2)
            finally:db.close()


if __name__=='__main__':unittest.main()

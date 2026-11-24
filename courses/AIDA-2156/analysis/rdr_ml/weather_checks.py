"""Executable weather feature assertions for the final reproducible package."""
from datetime import datetime, timedelta, timezone
import json
import numpy as np
from .weather import Weather, clean, SCALES


def main():
    origin = datetime(2026, 6, 2, 12, 35, tzinfo=timezone.utc)
    end = origin.replace(minute=0) - timedelta(hours=1)
    weather = object.__new__(Weather)
    weather.sha256 = 'synthetic-check'
    weather.rows = {end-timedelta(hours=i): {'precipitation': 1., 'temperature': 10.}
                    for i in range(24)}
    values, meta = weather.at(origin)
    assert np.allclose(values*SCALES, [1,6,24,10])
    assert meta['mean_precipitation_intensity_mm_h'] == {'1h':1., '6h':1., '24h':1.}
    weather.rows[origin.replace(minute=0)] = {'precipitation':1000., 'temperature':1000.}
    weather.at.cache_clear()
    assert np.allclose(weather.at(origin)[0], values), 'Future hour leaked into features'
    del weather.rows[end-timedelta(hours=5)]
    weather.at.cache_clear()
    try:
        weather.at(origin)
    except ValueError as exc:
        assert str(exc) == 'missing_or_flagged_weather_24h'
    else:
        raise AssertionError('Incomplete precipitation window accepted')
    assert clean(0,None,0)==0
    assert all(clean(value,flag,0) is None for value,flag in [(None,None),(1,'M'),(0,'T'),(-1,None)])
    weather.rows[end-timedelta(hours=5)] = {'precipitation':0., 'temperature':10.}
    weather.rows[end]['temperature'] = None
    weather.at.cache_clear()
    try:
        weather.at(origin)
    except ValueError as exc:
        assert str(exc) == 'missing_or_flagged_temperature'
    else:
        raise AssertionError('Missing temperature accepted')
    print(json.dumps({'status':'passed', 'checks':['1/6/24-hour totals and mean intensities',
        'future-hour exclusion', 'missing-hour rejection', 'zero vs missing vs trace',
        'negative precipitation rejection', 'missing-temperature rejection']}))


if __name__ == '__main__':
    main()

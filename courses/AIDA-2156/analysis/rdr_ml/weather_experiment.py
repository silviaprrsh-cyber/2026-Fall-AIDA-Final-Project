"""Run paired chronological weather/control experiments without changing defaults."""
import json
from pathlib import Path
import subprocess
import sys

from project_paths import WORKSPACE
from .core import metrics


def main():
    base = WORKSPACE/'courses/AIDA-2156/data'
    reports = base/'reports'
    artifacts = {}
    predictions = {}
    for name in ['weather_control', 'weather']:
        output = base/'processed'/f'segment_ml_{name}_60_20_20'
        command = [sys.executable, '-B', str(WORKSPACE/'run.py'), 'ml', 'train',
                   '--config', str(WORKSPACE/'shared-resources/config'/f'segment_ml_{name}.json'),
                   '--output', str(output), '--iterations', '120']
        subprocess.run(command, cwd=WORKSPACE, check=True)
        report = json.loads((output/'training_report.json').read_text())
        # Keep named reports even though the generic ML report is overwritten by the next arm.
        (reports/f'segment_ml_training_{name}_60_20_20.json').write_text(json.dumps(report,indent=2)+'\n')
        artifacts[name] = {k:report.get(k) for k in ['test','validation','calibration','selected_iteration',
                                                   'weather_manifest_sha256','parameter_count','iterations_completed']}
        predictions[name] = json.loads((output/'holdout_predictions.json').read_text())
    ids = [{r['trajectory_id'] for r in predictions[n] if r.get('label_status') == 'matched'}
           for n in ['weather_control','weather']]
    common = ids[0] & ids[1]
    paired = {n:metrics([r for r in rows if r['trajectory_id'] in common]) for n,rows in predictions.items()}
    result = {'experiment':'weather_vs_no_weather_joint_chain_60_20_20', 'arms':artifacts,
              'paired_origin_metrics':paired, 'common_test_origins':len(common),
              'comparison':'Same chronological source views and complete-weather cohort; each model uses its own predicted-arrival target matching.',
              'weather_features':['past_1h_precipitation_mm','past_6h_precipitation_mm',
                                  'past_24h_precipitation_mm','temperature_c'],
              'training':'120 bounded joint random-search proposals per arm; no optimizer or baseline formula change.',
              'limitations':['Point weather is not catchment-average rainfall.',
                             'One-hour conservative safety delay; no historical publication-time replay proof.',
                             'Previously inspected test period is not a new untouched test.',
                             'Endpoint accuracy does not verify intermediate stages or hydraulic validity.']}
    path=reports/'segment_ml_weather_comparison_60_20_20.json'
    path.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2),flush=True)


if __name__=='__main__':
    main()

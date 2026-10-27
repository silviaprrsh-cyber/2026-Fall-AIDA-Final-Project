"""Read-only optional audit of migration inputs; never needed to run the project."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from project_paths import WORKSPACE


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--original', type=Path, required=True)
    parser.add_argument('--template', type=Path, required=True)
    args = parser.parse_args()
    sources = {'original': args.original.resolve(), 'template': args.template.resolve()}
    manifest = json.loads((WORKSPACE/'shared-resources/results/manifest.json').read_text(encoding='utf-8'))
    changed = []
    for index, row in enumerate(manifest['files']):
        source = sources[row['source_tree']]/row['source']
        if not source.is_file() or digest(source) != row['source_sha256']:
            changed.append({'tree': row['source_tree'], 'path': row['source']})
        if index and index % 1000 == 0: print('Audited input files:', index, flush=True)
    report = {'checked_at_utc': datetime.now(timezone.utc).isoformat(),
              'input_files_checked': len(manifest['files']), 'changed_inputs': changed,
              'passed': not changed, 'method': 'SHA-256 compared with hashes captured before copying'}
    (WORKSPACE/'shared-resources/results/source_preservation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
    if changed: raise SystemExit(1)


if __name__ == '__main__':
    main()

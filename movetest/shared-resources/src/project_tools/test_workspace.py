"""Run migrated unit tests with outbound sockets disabled."""
import json
from pathlib import Path
import socket
import sys
import unittest
from unittest.mock import patch
from datetime import datetime, timezone
from project_paths import WORKSPACE


def main():
    suite = unittest.TestSuite()
    for folder in ['shared-resources/tests', 'courses/AIDA-2154/tests',
                   'courses/AIDA-2156/tests', 'courses/AIDA-2362/tests']:
        path = WORKSPACE/folder
        if path.exists():
            suite.addTests(unittest.TestLoader().discover(str(path), pattern='test_*.py'))
    with patch.object(socket.socket, 'connect', side_effect=RuntimeError('Network disabled for migration tests')), \
         patch.object(socket, 'create_connection', side_effect=RuntimeError('Network disabled for migration tests')):
        result = unittest.TextTestRunner(verbosity=2).run(suite)
    report = {'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'tests_run': result.testsRun,
              'failures': len(result.failures), 'errors': len(result.errors), 'skipped': len(result.skipped),
              'passed': result.wasSuccessful(), 'network_disabled': True}
    path = WORKSPACE/'shared-resources/results/unit_test_result.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    if not result.wasSuccessful(): sys.exit(1)


if __name__ == '__main__':
    main()

"""Bootstrap the split course packages without importing the original project."""
import os
from pathlib import Path
import runpy
import sys

WORKSPACE = Path(__file__).resolve().parent
SEARCH_PATHS = [WORKSPACE, WORKSPACE/'shared-resources/src',
                WORKSPACE/'courses/AIDA-2154/src', WORKSPACE/'courses/AIDA-2156/analysis',
                WORKSPACE/'courses/AIDA-2362/src']


def bootstrap():
    sys.dont_write_bytecode = True
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    # Let each installed geospatial library use its matching bundled database.
    # Inherited PostGIS paths can otherwise override the Python wheel's PROJ data.
    os.environ.pop('PROJ_LIB', None)
    os.environ.pop('PROJ_DATA', None)
    original = WORKSPACE.parent.resolve()
    sys.path[:] = [p for p in sys.path if p and Path(p).resolve() != original]
    for path in reversed(SEARCH_PATHS):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    os.chdir(WORKSPACE)


def main():
    bootstrap()
    if len(sys.argv) < 2:
        raise SystemExit('Usage: python run.py status | test | verify | cv-check | -m PACKAGE [ARGS]')
    command, args = sys.argv[1], sys.argv[2:]
    targets = {'status': ('API', ['status']), 'test': ('project_tools.test_workspace', []),
               'verify': ('project_tools.verify_workspace', []), 'cv-check': ('cv_tools.inspect_archive', [])}
    if command == '-m':
        if not args: raise SystemExit('A module name is required')
        module, args = args[0], args[1:]
    elif command in targets:
        module, prefix = targets[command]
        args = prefix + args
    else:
        raise SystemExit(f'Unknown command: {command}')
    sys.argv = [module] + args
    runpy.run_module(module, run_name='__main__', alter_sys=True)


if __name__ == '__main__':
    main()

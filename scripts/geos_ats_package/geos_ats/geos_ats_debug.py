import sys
import os
import glob
from pathlib import Path

mod_path = Path(__file__).resolve().parents[1]
sys.path.append(os.path.abspath(mod_path))
from geos_ats import main


def debug_geosats(build_root='~/GEOS/build-quartz-gcc@12-release', extra_args=[]):
    # Search for and parse the ats script
    build_root = os.path.expanduser(build_root)
    ats_script = os.path.join(build_root, 'integratedTests', 'geos_ats.sh')
    if not os.path.isfile(ats_script):
        raise InputError(
            'Could not find geos_ats.sh at the expected location...  Make sure to run \"make ats_environment\"')

    with open(ats_script, 'r') as f:
        header = f.readline()
        ats_args = f.readline().split()
        sys.argv.extend(ats_args[1:-1])
        sys.argv.extend(extra_args)

    main.main()


if (__name__ == '__main__'):
    # debug_geosats(extra_args=['-a', 'veryclean'])
    # debug_geosats(extra_args=['-a', 'rebaselinefailed'])
    debug_geosats()

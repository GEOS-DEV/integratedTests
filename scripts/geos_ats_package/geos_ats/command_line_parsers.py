import logging
import argparse
import os
import shutil
from pydoc import locate

action_options = {
    "run": "execute the test cases that previously did not pass.",
    "rerun": "ignore the status from previous runs, and rerun the tests.",
    "continue": "continue running, ignoring tests that have either passed or failed",
    "list": "list the test cases.",
    "commands": "display the command line of each test step.",
    "reset": "Removes Failed status from any test case.",
    "clean": "remove files generated by the test cases.",
    "veryclean": "does a clean plus removes non testcase created files (TestLog, results, ...)",
    "check": "skip the action steps and just run the check steps.",
    "rebaseline": "rebaseline the testcases from a previous run.",
    "rebaselinefailed": "rebaseline only failed testcases from a previous run.",
    "report": "generate a text or html report, see config for the reporting options.",
}

check_options = {
    "all": "run all checks",
    "none": "no additional checking",
    "stopcheck": "check the stop time and stop cycle",
    "curvecheck": "check the ultra curves",
    "restartcheck": "check the restart file",
}

verbose_options = {
    "debug": "Show detailed log information",
    "info": "Show typical log information",
    "warnings": "Show warnings only",
    "errors": "Show errors only",
}


def build_command_line_parser():
    parser = argparse.ArgumentParser(description="Runs GEOS integrated tests")

    parser.add_argument("geos_bin_dir", type=str, help="GEOS binary directory.")

    parser.add_argument("-w", "--workingDir", type=str, help="Initial working directory")

    action_names = ','.join(action_options.keys())
    parser.add_argument("-a", "--action", type=str, default="run", help=f"Test actions options ({action_names})")

    check_names = ','.join(check_options.keys())
    parser.add_argument("-c", "--check", type=str, default="all", help=f"Test check options ({check_names})")

    verbosity_names = ','.join(verbose_options.keys())
    parser.add_argument("-v", "--verbose", type=str, default="info", help=f"Log verbosity options ({verbosity_names})")

    parser.add_argument("-d", "--detail", action="store_true", default=False, help="Show detailed action/check options")

    parser.add_argument("-i", "--info", action="store_true", default=False, help="Info on various topics")

    parser.add_argument("-r",
                        "--restartCheckOverrides",
                        nargs='+',
                        action='append',
                        help='Restart check parameter override (name value)',
                        default=[])

    parser.add_argument("--salloc",
                        default=True,
                        help="Used by the chaosM machine to first allocate nodes with salloc, before running the tests")

    parser.add_argument(
        "--sallocoptions",
        type=str,
        default="",
        help="Used to override all command-line options for salloc. No other options with be used or added.")

    parser.add_argument("--ats", nargs='+', default=[], action="append", help="pass arguments to ats")

    parser.add_argument("--machine", default=None, help="name of the machine")

    parser.add_argument("--machine-dir", default=None, help="Search path for machine definitions")

    parser.add_argument("-l", "--logs", type=str, default=None)

    parser.add_argument(
        "--failIfTestsFail",
        action="store_true",
        default=False,
        help="geos_ats normally exits with 0. This will cause it to exit with an error code if there was a failed test."
    )

    parser.add_argument("-n", "-N", "--numNodes", type=int, default="2")

    parser.add_argument("ats_targets", type=str, nargs='*', help="ats files or directories.")

    return parser


def parse_command_line_arguments(args):
    parser = build_command_line_parser()
    options, unkown_args = parser.parse_known_args()
    exit_flag = False

    # Check action, check, verbosity items
    check = options.check
    if check not in check_options:
        print(
            f"Selected check option ({check}) not recognized.  Try running with --help/--details for more information")
        exit_flag = True

    action = options.action
    if action not in action_options:
        print(
            f"Selected action option ({action}) not recognized.  Try running with --help/--details for more information"
        )
        exit_flag = True

    verbose = options.verbose
    if verbose not in verbose_options:
        print(f"Selected verbose option ({verbose}) not recognized")
        exit_flag = True

    # Print detailed information
    if options.detail:
        for option_type, details in zip(['action', 'check'], [action_options, check_options]):
            print(f'\nAvailable {option_type} options:')
            for k, v in details.items():
                print(f'    {k}:  {v}')
        exit_flag = True

    if exit_flag:
        quit()

    return options


def patch_parser(parser):

    def add_option_patch(*xargs, **kwargs):
        """
        Convert type string to actual type instance
        """
        tmp = kwargs.get('type', str)
        type_map = {'string': str}
        if isinstance(tmp, str):
            if tmp in type_map:
                tmp = type_map[tmp]
            else:
                tmp = locate(tmp)
        kwargs['type'] = tmp
        parser.add_argument(*xargs, **kwargs)

    parser.add_option = add_option_patch

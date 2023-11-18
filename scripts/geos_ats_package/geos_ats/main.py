import sys
import os
import glob
import shutil
import signal
import subprocess
import time
import logging
from geos_ats import command_line_parsers

test_actions = ("run", "rerun", "check", "continue")
report_actions = ("run", "rerun", "report", "continue")

# Setup the logger
logging.basicConfig(level=logging.DEBUG, format='(%(asctime)s %(module)s:%(lineno)d) %(message)s')
logger = logging.getLogger('geos_ats')

# Job records
current_subproc = None
current_jobid = None
geos_atsStartTime = 0


def check_ats_targets(options, testcases, configOverride, args):
    """
    Determine which files, directories, or tests to run.
    Handle command line config options.
    """
    configOverride["executable_path"] = options.geos_bin_dir

    ats_files = []
    for a in options.ats_targets:
        if "=" in a:
            key, value = a.split("=")
            configOverride[key] = value
            args.remove(a)

        elif not options.info:
            if os.path.exists(a):
                args.remove(a)
                if os.path.isdir(a):
                    newfiles = glob.glob(os.path.join(a, "*.ats"))
                    ats_files.extend(newfiles)
                else:
                    ats_files.append(a)
            else:
                testcases.append(a)
        else:
            if options.action in test_actions:
                logger.error(f"The command line arg '{a}' is not recognized."
                             "  An ats file or a directory name is expected.")
                sys.exit(1)

    # If no files were specified, look in the target directories
    for d in ['.', 'integratedTests']:
        if len(ats_files) == 0:
            if os.path.isdir(d):
                ats_files.extend(glob.glob(os.path.join(d, "*.ats")))

    # prune out ats continue files.
    for a in ats_files[:]:
        if a.endswith("continue.ats"):
            ats_files.remove(a)

    return ats_files


def build_ats_arguments(options, ats_files, originalargv, config):
    # construct the argv to pass to the ATS:
    atsargv = []
    atsargv.append(originalargv[0])
    atsargv.append("--showGroupStartOnly")
    atsargv.append("--logs=%s" % options.logs)
    if config.batch_interactive:
        atsargv.append("--allInteractive")
    atsargv.extend(config.machine_options)
    for x in options.ats:
        # Add the appropriate argument indicators back based on their length
        if len(x[0]) == 1:
            x[0] = '-' + x[0]
        else:
            x[0] = '--' + x[0]
        atsargv.extend(x)

    for f in os.environ.get('ATS_FILTER', '').split(','):
        atsargv.extend(['-f', f])

    atsargv.extend(ats_files)
    sys.argv = atsargv


def write_log_dir_summary(logdir, originalargv):
    from geos_ats import configuration_record

    with open(os.path.join(logdir, "geos_ats.config"), "w") as logconfig:
        tmp = " ".join(originalargv[1:])
        logconfig.write(f'Run with: "{tmp}"\n')
        configuration_record.infoConfigShow(True, logconfig)


def handleShutdown(signum, frame):
    if current_jobid is not None:
        term = "scancel -n %s" % current_jobid
        subprocess.call(term, shell=True)
    sys.exit(1)


def handle_salloc_relaunch(options, originalargv, configOverride):
    tests = [
        options.action in test_actions, options.salloc, options.machine
        in ("SlurmProcessorScheduled", "GeosAtsSlurmProcessorScheduled"), "SLURM_JOB_ID" not in os.environ
    ]

    if all(tests):
        if options.sallocOptions != "":
            sallocCommand = ["salloc"] + options.sallocOptions.split(" ")
        else:
            sallocCommand = ["salloc", "-ppdebug", "--exclusive", "-N", "%d" % options.numNodes]
            if "testmodifier" in configOverride:
                if configOverride["testmodifier"] == "memcheck":
                    p = subprocess.Popen(['sinfo', '-o', '%l', '-h', '-ppdebug'], stdout=subprocess.PIPE)
                    out, err = p.communicate()
                    tarray = out.split(":")
                    seconds = tarray.pop()
                    minutes = tarray.pop()
                    hours = 0
                    days = 0
                    if len(tarray) > 0:
                        hours = tarray.pop()
                        try:
                            days, hours = hours.split('-')
                        except ValueError as e:
                            logger.debug(e)
                    limit = min(360, (24 * int(days) + int(hours)) * 60 + int(minutes))
                    sallocCommand.extend(["-t", "%d" % limit])

        # generate a "unique" name for the salloc job so we can remove it later
        timeNow = time.strftime('%H%M%S', time.localtime())
        current_jobid = "geos_ats_%s" % timeNow

        # add the name to the arguments (this will override any previous name specification)
        sallocCommand.extend(["-J", "%s" % current_jobid])

        # register our signal handler
        signal.signal(signal.SIGTERM, handleShutdown)
        command = sallocCommand

        # omit --workingDir on relaunch, as we have already changed directories
        relaunchargv = [x for x in originalargv if not x.startswith("--workingDir")]
        command += relaunchargv
        command += ["--logs=%s" % options.logs]
        p = subprocess.Popen(command)
        p.wait()
        sys.exit(p.returncode)


def getLogDirBaseName():
    return "TestLogs"


def create_log_directory(options):
    """
    When the action will run tests (e.g. "run", "rerun", "check", "continue", then the
    LogDir is numbered, and saved.  When the action does not run
    tests, the LogDir is temporary, and only sticks around if geos_ats
    exited abnormally.
    """
    from geos_ats import common_utilities
    if options.logs is None:
        if options.action in test_actions:
            basename = getLogDirBaseName()
            index = 1
            while True:
                options.logs = "%s.%03d" % (basename, index)
                if not os.path.exists(options.logs):
                    break
                index += 1

            # make the options.logs
            os.mkdir(options.logs)

            # make symlink
            try:
                if os.path.exists(basename):
                    if os.path.islink(basename):
                        os.remove(basename)
                    else:
                        logger.error(f"unable to replace {basename} with a symlink to {options.logs}")

                if not os.path.exists(basename):
                    os.symlink(options.logs, basename)

            except:
                logger.error("unable to name a symlink to to logdir")

        else:
            if options.action in test_actions:
                options.logs = "%s.%s" % (getLogDirBaseName(), options.action)
            elif options.info:
                options.logs = "%s.info" % (getLogDirBaseName())
    else:
        if not os.path.join(options.logs):
            os.mkdir(options.logs)


def check_timing_file(options, config):
    if options.action in ["run", "rerun", "continue"]:
        if config.timing_file:
            if not os.path.isfile(config.timing_file):
                logger.warning(f'Timing file does not exist {config.timing_file}')
                return

            from geos_ats import configuration_record
            with open(config.timing_file, "r") as filep:
                for line in filep:
                    if not line.startswith('#'):
                        tokens = line.split()
                        configuration_record.globalTestTimings[tokens[0]] = int(tokens[1])


def append_test_end_step(machine):
    """
    Add extra processing to the end of tests
    """
    originalNoteEnd = machine.noteEnd

    def noteEndWrapper(test):
        test.geos_atsTestCase.status.noteEnd(test)
        return originalNoteEnd(test)

    machine.noteEnd = noteEndWrapper


def check_working_dir(workingDir):
    if workingDir:
        if os.path.isdir(workingDir):
            os.chdir(workingDir)
        else:
            logger.error(f"The requested working dir does not appear to exist: {workingDir}")
            quit()


def infoOptions(title, options):
    from geos_ats import common_utilities
    topic = common_utilities.InfoTopic(title)
    topic.startBanner()
    table = common_utilities.TextTable(2)
    for opt, desc in options:
        table.addRow(opt, desc)
    table.printTable()
    topic.endBanner()


def infoParagraph(title, paragraphs):
    from geos_ats import common_utilities
    topic = common_utilities.InfoTopic(title)
    topic.startBanner()
    table = common_utilities.TextTable(1)
    for p in paragraphs:
        table.addRow(p)
    table.rowbreak = 1
    table.maxwidth = 75
    table.printTable()
    topic.endBanner()


def info(args):
    from geos_ats import (common_utilities, configuration_record, test_steps, suite_settings, test_case, test_modifier)

    infoLabels = lambda *x: suite_settings.infoLabels(suite_settings.__file__)
    infoOwners = lambda *x: suite_settings.infoOwners(suite_settings.__file__)

    menu = common_utilities.InfoTopic("geos_ats info menu")
    menu.addTopic("teststep", "Reference on all the TestStep", test_steps.infoTestSteps)
    menu.addTopic("testcase", "Reference on the TestCase", test_case.infoTestCase)
    menu.addTopic("labels", "List of labels", infoLabels)
    menu.addTopic("owners", "List of owners", infoOwners)
    menu.addTopic("config", "Reference on config options", configuration_record.infoConfig)
    menu.addTopic("actions", "Description of the command line action options",
                  lambda *x: infoOptions("command line actions", command_line_parsers.action_ptions))
    menu.addTopic("checks", "Description of the command line check options",
                  lambda *x: infoOptions("command line checks", command_line_parsers.check_options))
    menu.addTopic("modifiers", "List of test modifiers", test_modifier.infoTestModifier)
    # menu.addTopic("testconfig", "Information on the testconfig.py file",
    #               lambda *x: infoParagraph("testconfig", command_line_parsers.test_config_info))
    menu.process(args)


def report(manager):
    """The report action"""
    from geos_ats import (test_case, reporting, configuration_record)

    testcases = test_case.TESTS.values()

    if configuration_record.config.report_wait:
        reporter = reporting.ReportWait(testcases)
        reporter.report(sys.stdout)

    if configuration_record.config.report_text:
        reporter = reporting.ReportText(testcases)
        with open(configuration_record.config.report_text_file, "w") as filep:
            reporter.report(filep)
        if configuration_record.config.report_text_echo:
            with open(configuration_record.config.report_text_file, "r") as filep:
                sys.stdout.write(filep.read())

    if configuration_record.config.report_html:
        reporter = reporting.ReportHTML(testcases)
        reporter.report()

    if configuration_record.config.report_ini:
        reporter = reporting.ReportIni(testcases)
        with open(configuration_record.config.report_ini_file, "w") as filep:
            reporter.report(filep)

    if configuration_record.config.report_timing:
        reporter = reporting.ReportTiming(testcases)
        if not configuration_record.config.report_timing_overwrite:
            try:
                with open(configuration_record.config.timing_file, "r") as filep:
                    reporter.getOldTiming(filep)
            except IOError as e:
                logger.debug(e)
        with open(configuration_record.config.timing_file, "w") as filep:
            reporter.report(filep)


def summary(manager, alog, short=False):
    """Periodic summary and final summary"""
    from geos_ats import (reporting, configuration_record, test_case)

    if len(manager.testlist) == 0:
        return

    if hasattr(manager.machine, "getNumberOfProcessors"):
        totalNumberOfProcessors = getattr(manager.machine, "getNumberOfProcessors", None)()
    else:
        totalNumberOfProcessors = 1
    reporter = reporting.ReportTextPeriodic(manager.testlist)
    reporter.report(geos_atsStartTime, totalNumberOfProcessors)

    if configuration_record.config.report_html and configuration_record.config.report_html_periodic:
        testcases = test_case.TESTS.values()
        reporter = reporting.ReportHTML(testcases)
        reporter.report(refresh=30)

    if configuration_record.config.report_text:
        testcases = test_case.TESTS.values()
        reporter = reporting.ReportText(testcases)
        with open(configuration_record.config.report_text_file, "w") as filep:
            reporter.report(filep)


def append_geos_ats_summary(manager):
    initial_summary = manager.summary

    def new_summary(*xargs, **kwargs):
        initial_summary(*xargs, **kwargs)
        summary(manager, None)

    manager.summary = new_summary


def main():
    """
    The main driver for geos_ats:  it processes the command
    line arguments, then invokes that ats
    """
    # ---------------------------------
    # Handle command line arguments
    # ---------------------------------
    originalargv = sys.argv[:]
    options = command_line_parsers.parse_command_line_arguments(originalargv)

    # Set logging verbosity
    verbosity_options = {
        'debug': logging.DEBUG,
        'info': logging.INFO,
        'warning': logging.WARNING,
        'error': logging.ERROR
    }
    logger.setLevel(verbosity_options[options.verbose])

    # Set key environment variables before importing ats
    from geos_ats import machines
    search_path = ''
    if options.machine_dir is not None:
        if os.path.isdir(options.machine_dir):
            search_path = options.machine_dir
        else:
            logger.error(f'Target machine dir does not exist: {options.machine_dir}')
            logger.error('geos_ats will continue searching in the default path')

    if not search_path:
        search_path = os.path.dirname(machines.__file__)
    os.environ['MACHINE_DIR'] = search_path

    if options.machine:
        os.environ["MACHINE_TYPE"] = options.machine

    # ---------------------------------
    # Setup ATS
    # ---------------------------------
    configOverride = {}
    testcases = []
    configFile = ''
    check_working_dir(options.workingDir)
    create_log_directory(options)

    # Check the test configuration
    from geos_ats import configuration_record
    configuration_record.initializeConfig(configFile, configOverride, options)
    config = configuration_record.config
    config.geos_bin_dir = options.geos_bin_dir

    for r in options.restartCheckOverrides:
        if 'skip_missing' in r:
            config.restart_skip_missing = True
        elif 'exclude' in r:
            config.restart_exclude_pattern.append(r[-1])

    # Check the report location
    if options.logs:
        config.report_html_file = os.path.join(options.logs, 'test_results.html')
        config.report_text_file = os.path.join(options.logs, 'test_results.txt')
        config.report_ini_file = os.path.join(options.logs, 'test_results.ini')

    ats_files = check_ats_targets(options, testcases, configOverride, originalargv)
    build_ats_arguments(options, ats_files, originalargv, config)

    # Additional setup tasks
    check_timing_file(options, config)
    handle_salloc_relaunch(options, originalargv, configOverride)

    # Print config information
    logger.debug("*" * 80)
    for notation in config.report_notations:
        logger.debug(notation)
    logger.debug("*" * 80)

    # ---------------------------------
    # Initialize ATS
    # ---------------------------------
    geos_atsStartTime = time.time()

    # Note: the sys.argv is read here by default
    import ats    # type: ignore[import]
    ats.manager.init()
    logger.debug('Copying options to the geos_ats config record file')
    config.copy_values(ats.manager.machine)

    #  Glue global values
    ats.AtsTest.glue(action=options.action)
    ats.AtsTest.glue(checkoption=options.check)
    ats.AtsTest.glue(configFile=configFile)
    ats.AtsTest.glue(configOverride=configOverride)
    ats.AtsTest.glue(testmode=False)
    ats.AtsTest.glue(atsFlags=options.ats)
    ats.AtsTest.glue(atsFiles=ats_files)
    ats.AtsTest.glue(machine=options.machine)
    ats.AtsTest.glue(config=config)
    if len(testcases):
        ats.AtsTest.glue(testcases=testcases)
    else:
        ats.AtsTest.glue(testcases="all")

    from geos_ats import (common_utilities, suite_settings, test_case, test_steps, user_utilities)

    # Set ats options
    append_geos_ats_summary(ats.manager)
    append_test_end_step(ats.manager.machine)
    ats.manager.machine.naptime = 0.2
    ats.log.echo = True

    # Logging
    if options.action in ("run", "rerun", "check", "continue"):
        write_log_dir_summary(options.logs, originalargv)

    if options.action in test_actions:
        ats.manager.firstBanner()

    # ---------------------------------
    # Run ATS
    # ---------------------------------
    result = ats.manager.core()

    # Make sure all the testcases requested were found
    if testcases != "all":
        if len(testcases):
            logger.error(f"ERROR: Unknown testcases {str(testcases)}")
            logger.error(f"ATS files: {str(ats_files)}")
            sys.exit(1)

    # Report:
    if options.action in report_actions:
        report(ats.manager)

    # clean
    if options.action == "veryclean":
        common_utilities.removeLogDirectories(os.getcwd())
        files = [config.report_html_file, config.report_ini_file, config.report_text_file]
        for f in files:
            if os.path.exists(f):
                os.remove(f)

    # clean the temporary logfile that is not needed for certain actions.
    if options.action not in test_actions:
        if options.logs is not None:
            if os.path.exists(options.logs):
                shutil.rmtree(options.logs)

    # return 0 if all tests passed, 1 otherwise
    try:
        if options.failIfTestsFail:
            with open(os.path.join(options.logs, "test_results.html"), 'r') as f:
                contents = ''.join(f.readlines()).split("DETAILED RESULTS")[1]
                messages = [
                    "class=\"red\">FAIL", "class=\"yellow\">SKIPPED", "class=\"reddish\">FAIL",
                    "class=\"yellow\">NOT RUN"
                ]
                result = any([m in contents for m in messages])
    except IOError as e:
        logger.debug(e)

    # Other ATS steps not previously included:
    ats.manager.postprocess()
    ats.manager.finalReport()
    ats.manager.saveResults()
    ats.manager.finalBanner()

    # Remove unnecessary log dirs created with clean runs
    none_dir = os.path.join(options.workingDir, 'None')
    if os.path.exists(none_dir):
        shutil.rmtree(none_dir)

    return result


if __name__ == "__main__":
    result = main()
    sys.exit(result)

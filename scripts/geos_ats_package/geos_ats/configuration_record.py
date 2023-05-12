import os
import sys
from geos_ats.common_utilities import TextTable, InfoTopic, Error, Log
from geos_ats.suite_settings import testLabels
import difflib
import logging

################################################################################
# Config related classes and functions
################################################################################

# Get the active logger instance
logger = logging.getLogger('geos_ats')


class ConfigItem(object):

    def __init__(self, name, type, default, doc, public):
        self.name = name
        self.type = type
        self.default = default
        self.doc = doc
        self.value = default
        self.public = public


class Config(object):

    def __init__(self):
        self.__dict__["_items"] = {}

    def set(self, name, value):
        # error checking
        item = self._items[name]
        try:
            if item.type == str:
                value = item.type(value)
            else:
                if isinstance(value, str):
                    value = item.type(eval(value))
                else:
                    value = item.type(value)

        except ValueError:
            Error("Attempted to set config.%s (which is %s) with %s" % (name, str(item.type), str(value)))

        item.value = item.type(value)

    def copy_values(self, target):
        logger.debug("Copying command line options to config:")
        target_dict = vars(target)
        for k in self._items.keys():
            if k in target_dict:
                logger.debug(f"  {k}: {target_dict[k]}")
                self.set(k, target_dict[k])

    def get(self, name):
        # error checking
        return self._items[name].value

    def add(self, name, type, default, doc, public=True):
        item = ConfigItem(name, type, default, doc, public)
        self._items[item.name] = item

    def checkname(self, name):
        if name not in self.__dict__:
            matches = difflib.get_close_matches(name, self._items.keys())
            if len(matches) == 0:
                Error("Unknown config name: %s. "
                      "See 'geos_ats -i config' for the complete list." % (name))

            else:
                Error("Unknown config name: %s. "
                      "Perhaps you meant '%s'. "
                      "See 'geos_ats -i config' for the complete list." % (name, matches[0]))

    def __setattr__(self, name, value):
        if name in self._items:
            self.set(name, value)
        else:
            self.checkname(name)

    def __getattr__(self, name):
        if name in self._items:
            return self._items[name].value
        else:
            self.checkname(name)


# The global config object
config = Config()
# Global testTimings object
globalTestTimings = {}    # type: ignore[var-annotated]
# Depth of testconfig recursion
configDepth = 0


def infoConfigShow(public, outfile=sys.stdout):
    topic = InfoTopic("config show", outfile)
    topic.startBanner()
    import ats    # type: ignore[import]

    keys = sorted(config._items.keys())
    table = TextTable(3)
    for k in keys:
        item = config._items[k]
        if (public and item.public) or (not public):
            if item.default == item.value:
                diff = " "
            else:
                diff = "*"

            table.addRow(item.name, diff, item.value)

    table.printTable(outfile)

    cf = ats.tests.AtsTest.getOptions().get("configFile")
    outfile.write(f"\nConfig file: {cf}")

    configOverride = ats.tests.AtsTest.getOptions().get("configOverride", {})
    if configOverride:
        outfile.write("\nCommand line overrides:")
        table = TextTable(1)
        for key, value in configOverride.items():
            table.addRow(key)
        table.printTable(outfile)

    topic.endBanner()


def infoConfigDocumentation(public):

    topic = InfoTopic("config doc")
    topic.startBanner()

    keys = sorted(config._items.keys())
    table = TextTable(4)
    table.addRow("[NAME]", "[TYPE]", "[DEFAULT]", "[DOC]")

    for k in keys:
        item = config._items[k]
        if (public and item.public) or (not public):
            table.addRow(item.name, item.type.__name__, item.default, item.doc)

    table.colmax[2] = 20
    table.printTable()

    topic.endBanner()


def infoConfig(*args):

    menu = InfoTopic("config")
    menu.addTopic("show", "Show all the config options", lambda *x: infoConfigShow(True))
    menu.addTopic("doc", "Documentation for the config options", lambda *x: infoConfigDocumentation(True))
    menu.addTopic("showall", "Show all the config options (including the internal options)",
                  lambda: infoConfigShow(False))
    menu.addTopic("docall", "Documentation for the config options (including the internal options)",
                  lambda: infoConfigDocumentation(False))
    menu.process(args)


def initializeConfig(configFile, configOverride, options):

    # determine the directory where geos_ats is located.  Used to find
    # location of other programs.
    geos_atsdir = os.path.realpath(os.path.dirname(__file__))

    # configfile
    config.add("testbaseline_dir", str, "", "Base directory that contains all the baselines")

    config.add("geos_bin_dir", str, "", "Directory that contains 'geos' and related executables.")

    config.add("userscript_path", str, "",
               "Directory that contains scripts for testing, searched after test directory and executable_path.")

    config.add("clean_on_pass", bool, False, "If True, then after a TestCase passes, "
               "all temporary files are removed.")

    # geos options
    config.add("geos_default_args", str, "-i",
               "A string containing arguments that will always appear on the geos commandline")

    # reporting
    config.add("report_html", bool, True, "True if HTML formatted results will be generated with the report action")
    config.add("report_html_file", str, "test_results.html", "Location to write the html report")
    config.add("report_html_periodic", bool, True, "True to update the html file during the periodic reports")
    config.add("browser_command", str, "firefox -no-remote", "Command to use to launch a browser to view html results")
    config.add("browser", bool, False, "If True, then launch the browser_command to view the report_html_file")
    config.add("report_doc_dir", str, os.path.normpath(os.path.join(geos_atsdir, "..", "doc")),
               "Location to the test doc directory (used with html reports)")
    config.add("report_doc_link", bool, True, "Link against docgen (used with html reports)")
    config.add("report_doc_remake", bool, False,
               "Remake test documentation, even if it already exists (used with html reports)")

    config.add("report_text", bool, True, "True if you want text results to be generated with the report action")
    config.add("report_text_file", str, "test_results.txt", "Location to write the text report")
    config.add("report_text_echo", bool, True, "If True, echo the report to stdout")
    config.add("report_wait", bool, False, "Wait until all tests are complete before reporting")

    config.add("report_ini", bool, True, "True if you want ini results to be generated with the report action")
    config.add("report_ini_file", str, "test_results.ini", "Location to write the ini report")

    config.add("report_notations", type([]), [], "Lines of text that are inserted into the reports.")

    config.add("report_notbuilt_regexp", str, "(not built into this version)",
               "Regular expression that must appear in output to indicate that feature is not built.")

    config.add("checkmessages_always_ignore_regexp", type([]), ["not available in this version"],
               "Regular expression to ignore in all checkmessages steps.")

    config.add("checkmessages_never_ignore_regexp", type([]), ["not yet implemented"],
               "Regular expression to not ignore in all checkmessages steps.")

    config.add("report_timing", bool, False, "True if you want timing file to be generated with the report action")
    config.add("report_timing_overwrite", bool, False,
               "True if you want timing file to overwrite existing timing file rather than augment it")

    # timing and priority
    config.add("priority", str, "equal", "Method of prioritization of tests: [\"equal\", \"processors\",\"timing\"]")
    config.add("timing_file", str, "timing.txt", "Location of timing file")

    # batch
    config.add("batch_dryrun", bool, False,
               "If true, the batch jobs will not be submitted, but the batch scripts will be created")
    config.add("batch_interactive", bool, False, "If true, the batch jobs will be treated as interactive jobs")
    config.add("batch_bank", str, "", "The name of the bank to use")
    config.add("batch_ppn", int, 0, "Number of processors per node")
    config.add("batch_partition", str, "", "the batch partition, if not specified the default will be used.")
    config.add("batch_queue", str, "pbatch", "the batch queue.")
    config.add("batch_header", type([]), [], "Additional lines to add to the batch header")

    # retry
    config.add("max_retry", int, 2, "Maximum number of times to retry failed runs.")
    config.add("retry_err_regexp", str,
               "(launch failed|Failure in initializing endpoint|channel initialization failed)",
               "Regular expression that must appear in error log in order to retry.")

    # timeout
    config.add("default_timelimit", str, "30m",
               "This sets a default timelimit for all test steps which do not explicitly set a timelimit.")
    config.add("override_timelimit", bool, False,
               "If true, the value used for the default time limit will override the time limit for each test step.")

    # Decomposition Multiplication
    config.add(
        "decomp_factor", int, 1,
        "This sets the multiplication factor to be applied to the decomposition and number of procs of all eligible tests."
    )
    config.add("override_np", int, 0, "If non-zero, maximum number of processors to use for each test step.")

    # global environment variables
    config.add("environment", dict, {}, "Additional environment variables to use during testing")

    # General check config
    for check in ("restartcheck", ):
        config.add(
            "%s_enabled" % check, bool, True, "If True, this check has the possibility of running, "
            "but might not run depending on the '--check' command line option. "
            "If False, this check will never be run.")

    for check in ("hdf5_dif.py", ):
        config.add("%s_script" % check,
                   str,
                   os.path.join(geos_atsdir, "helpers/%s.py" % check),
                   "Location to the %s frontend script." % check,
                   public=False)

    # Checks:  Restartcheck
    config.add("restart_skip_missing", bool, False, "Determines whether new/missing fields are ignored")
    config.add("restart_exclude_pattern", list, [], "A list of field names to ignore in restart files")

    # Checks:  Curvecheck
    config.add("curvecheck_enabled", bool, True, "Determines whether curvecheck steps are run.")
    config.add("curvecheck_tapestry_mode", bool, False,
               "Provide temporary backwards compatibility for nighty and weekly suites until they are using geos_ats")
    config.add("curvecheck_absolute", float, 1e-5, "absolute tolerance")
    config.add("curvecheck_relative", float, 1e-5, "relative tolerance")
    config.add(
        "curvecheck_failtype", str, "composite",
        "String that represents failure check.  'composite or relative' will fail curvecheck if either the composite error or relative error is too high.  'absolute and slope' will fail only if both the absolute error check and the slope error check fail.  The default value is 'composite'."
    )
    config.add(
        "curvecheck_output", bool, False,
        "Curvecheck will output curvecheck files only if the curvecheck_failtype actually fails.  This parameter allows one to output files anyways; by default it is false."
    )
    config.add(
        "curvecheck_delete_temps", bool, True,
        "Curvecheck generates a number of temporary data files that are used to create the images for the html file.  If this parameter is true, curvecheck will delete these temporary files. By default, the parameter is true."
    )
    config.add("gnuplot_executable", str, os.path.join("/usr", "bin", "gnuplot"), "Location to gnuplot")

    # Rebaseline:
    config.add(
        "rebaseline_undo", bool, False, "If True, and the action is set to 'rebaseline',"
        " this option will undo (revert) a previous rebaseline.")
    config.add("rebaseline_ask", bool, True, "If True, the rebaseline will not occur until the user has anwered an"
               " 'are you sure?' question")

    # test modifier
    config.add("testmodifier", str, "", "Name of a test modifier to apply")

    # filters
    config.add("filter_maxprocessors", int, -1, "If not -1, Run only those tests where the number of"
               " processors is less than or equal to this value")

    # machines
    config.add("machine_options", list, [], "Arguments to pass to the machine module")

    config.add("script_launch", int, 0, "Whether to launch scripts (and other serial steps) on compute nodes")
    config.add("openmpi_install", str, "", "Location to the openmpi installation")
    config.add("openmpi_maxprocs", int, 0, "Number of maximum processors openmpi")
    config.add("openmpi_procspernode", int, 1, "Number of processors per node for openmpi")

    config.add(
        "openmpi_precommand", str, "", "A string that will be"
        " prepended to each command.  If the substring '%(np)s' is present,"
        " it will be replaced by then number of processors required for the"
        " test.  If the substring '%(J)s' is present, it will be replaced by"
        " the unique name of the test.")
    config.add("openmpi_args", str, "", "A string of arguments to mpirun")
    config.add(
        "openmpi_terminate", str, "", "A string that will be"
        " called upon abnormal termination.  If the substring '%(J)s' is present,"
        " it will be replaced by the unique name of the test.")

    config.add("windows_mpiexe", str, "", "Location to mpiexe")
    config.add("windows_nompi", bool, False, "Run executables on nompi processor")
    config.add("windows_oversubscribe", int, 1,
               "Multiplier to number of processors to allow oversubscription of processors")

    # populate the config with overrides from the command line
    for key, value in configOverride.items():
        try:
            setattr(config, key, value)
        except RuntimeError as e:
            # this allows for the testconfig file to define it's own
            # config options that can be overridden at the command line.
            logger.debug(e)

    # Setup the config dict
    if configFile:
        logger.warning("Config file override currently not available")

    ## override the config file from the command line
    for key, value in configOverride.items():
        setattr(config, key, value)

    # validate prioritization scheme
    if config.priority.lower().startswith("eq"):
        config.priority = "equal"
    elif config.priority.lower().startswith("proc"):
        config.priority = "processors"
    elif config.priority.lower().startswith("tim"):
        config.priority = "timing"
    else:
        Error("priority '%s' is not valid" % config.priority)

    ## environment variables
    for k, v in config.environment.items():
        os.environ[k] = v

import os
import ats    # type: ignore[import]
import glob
import shutil
import sys
import textwrap
import subprocess
import re
import logging
from geos_ats import common_utilities
from geos_ats.common_utilities import Error, Log
from geos_ats.configuration_record import config

logger = logging.getLogger('geos_ats')


def getGeosProblemName(deck, name):
    """
    Given an input deck and a name return the prefix Geos will attatch to it's output files.

    DECK [in]: The path to the input deck.
    NAME [in]: The name given to Geos on the command line.
    """
    if name is None:
        if deck.endswith(".xml"):
            return os.path.basename(deck)[:-4]
        else:
            return os.path.basename(deck)
    else:
        return name


def findMaxMatchingFile(file_path):
    """
    Given a path FILE_PATH where the base name of FILE_PATH is treated as a regular expression
    find and return the path of the greatest matching file/folder or None if no match is found.

    FILE_PATH [in]: The pattern to match.

    Examples:
        ".*" will return the file/folder with the greatest name in the current directory.

        "test/plot_*.hdf5" will return the file with the greatest name in the ./test directory
        that begins with "plot_" and ends with ".hdf5".
    """
    file_directory, pattern = os.path.split(file_path)
    if file_directory == "":
        file_directory = "."

    if not os.path.isdir(file_directory):
        return None

    max_match = ''
    pattern = re.compile(pattern)
    for file in os.listdir(file_directory):
        if pattern.match(file) is not None:
            max_match = max(file, max_match)

    if not max_match:
        return None

    return os.path.join(file_directory, max_match)


class TestParam(object):
    """
    A class that describes a parameter of a test step.
    """

    def __init__(self, name, doc, default=None):
        self.name = name
        self.doc = doc
        self.default = default


################################################################################
# TestStepBase
################################################################################


class TestStepBase(object):
    """
    The base clase for a test step.
    """

    defaultParams = (
        TestParam(
            "clean", "additional files to remove during the clean action."
            " clean may be a string or a list of strings.  The strings may contain"
            " wildcard characters."),
        TestParam(
            "timelimit", "maximum time the step is allowed to run before it is considerend a TIMEOUT."
            " Specified as a string such as: 1h30m, 60m, etc.", "None"),
        TestParam("stdout", "If set, the stdout will be placed in the named file, in the TestCase directory", None),
        TestParam("stderr", "If set, the stderr will be placed in the named file, in the TestCase directory", None),
        TestParam("expectedResult", "'PASS' or 'FAIL'", "'PASS'"),
        TestParam("delayed", "Whether execution of the step will be delayed", "False"),
        TestParam("minor", "Whether failure of this step is minor issue", "False"),
    )

    commonParams = {
        "name":
        TestParam("name", "Used to give other params default values.", "The name of the TestCase"),
        "deck":
        TestParam("deck", "Name of the input file.  Setting deck to False means no deck is used.", "<prob>.in"),
        "np":
        TestParam("np", "The number of processors to run on.", 1),
        "ngpu":
        TestParam("ngpu", "The number of gpus to run on when available.", 0),
        "check":
        TestParam(
            "check", "True or False. determines whether the default checksteps will "
            "be automatically be added after this step.", "True"),
        "baseline_dir":
        TestParam("baseline_dir", "subdirectory of config.testbaseline_dir where the test "
                  "baselines are located.", "<dirname>"),
        "output_directory":
        TestParam("output_directory", "subdirectory where the test log, params, rin, and "
                  "timehistory files are located.", "<dirname>"),
        "rebaseline":
        TestParam(
            "rebaseline", "additional files to rebaseline during the rebaseline action."
            " rebaseline may be a string or a list of strings."),
        "timehistfile":
        TestParam("timehistfile", "name of the file containing all the"
                  " timehist curves.", "testmode.<prob>.ul"),
        "basetimehistfile":
        TestParam("basetimehistfile", "location to the baseline timehistfile",
                  "<config.testbaseline_dir>/<baseline_dir>/<curvecheckfile>"),
        "allow_rebaseline":
        TestParam(
            "allow_rebaseline", "True if the second file should be re-baselined during a rebaseline action."
            "  False if the second file should not be rebaselined.", "True"),
        "testcase_name":
        TestParam("testcase_name", "The name of the testcase"),
        "testcase_out":
        TestParam("testcase_out", "The file where stdout for the testcase is accumulated"),
    }

    # namespace to place the params.
    class Params(object):
        pass

    def __init__(self):
        self.p = TestStepBase.Params()
        self.extraSteps = []

    def setParams(self, dictionary, paramlist):
        """
        Given a list of parameters PARAMLIST and a DICTIONARY set the parameters in
        PARAMLIST that are also in DICTIONARY but do not yet have a value.

        DICTIONARY [in]: The map from parameter names to values.
        PARAMLIST [in/out]: The list of parameters to update.
        """
        for p in paramlist:
            pname = p.name
            if getattr(self.p, pname, None) is None:
                setattr(self.p, pname, dictionary.get(pname, None))

    def requireParam(self, param):
        """
        Require that the given parameter is defined and not None.

        PARAM [in]: The name of the parameter to check.
        """
        if not hasattr(self.p, param):
            Error("%s must be given" % param)
        if getattr(self.p, param) is None:
            Error("%s must not be None" % param)

    def insertStep(self, steps):
        """
        Insert into the list of steps STEPS.

        STEPS [in/out]: The list of steps to insert into.
        """
        steps.append(self)

    def makeArgs(self):
        """
        Return the command line arguments for this step.
        """
        raise Error("Must implement this")

    def makeArgsForStatusKey(self):
        return self.makeArgs()

    def setStdout(self, dictionary):
        """
        Generate a unique stdout file using DICTIONARY.

        DICTIONARY [in/out]: The dictionary used to generate the unique name.
        """
        if self.p.stdout is None:
            stepname = self.p.name
            self.p.stdout = stepname + "." + self.label() + ".out"

        if self.p.stdout in dictionary:
            Log("Non-unique name for stdout file: %s" % self.p.stdout)
        else:
            dictionary[self.p.stdout] = 1

    def update(self, dictionary):
        """
        Update parameters using DICTIONARY. All parameters which already have values are not updated.
        Called by the owning TestCase to pass along it's arguments.

        DICTIONARY [in]: The dictionary used to update the parameters.
        """
        raise Error("Must implement this")

    def clean(self):
        """
        Remove files generated by this test step.
        """
        self._clean([])

    def _clean(self, paths, noclean=[]):
        """
        Delete files/folders in PATHS and self.p.clean as well as stdout and stderr
        but not in NOCLEAN. Paths to delete can have wildcard characters '*'.

        PATHS [in]: Paths to remove, can have wildcard characters.
        NOCLEAN [in]: Paths to ignore, can not have wildcard characters.
        """
        self._remove(paths, noclean)

        if hasattr(self.p, "clean"):
            if self.p.clean is not None:
                self._remove(self.p.clean, noclean)
        if hasattr(self.p, "stdout"):
            if self.p.stdout is not None:
                self._remove(self.p.stdout, noclean)
                self._remove("%s.*" % self.p.stdout, noclean)
        if hasattr(self.p, "stderr"):
            if self.p.stderr is not None:
                self._remove(self.p.stderr, noclean)
                self._remove("%s.*" % self.p.stderr, noclean)

    def _remove(self, paths, noclean):
        """
        Delete files/folders in PATHS but not in NOCLEAN.
        Paths to delete can have wildcard characters '*'.

        PATHS [in]: Paths to remove, can have wildcard characters.
        NOCLEAN [in]: Paths to ignore, can not have wildcard characters.
        """
        if isinstance(paths, str):
            paths = [paths]

        for path in paths:
            if self.getTestMode():
                Log("clean: %s" % path)
            else:
                delpaths = glob.glob(path)
                for p in delpaths:
                    if p in noclean:
                        continue
                    try:
                        if os.path.isdir(p):
                            shutil.rmtree(p)
                        else:
                            os.remove(p)
                    except OSError as e:
                        logger.debug(e)    # so that two simultaneous clean operations don't fail

    def getCheckOption(self):
        return ats.tests.AtsTest.getOptions().get("checkoption")

    def getTestMode(self):
        return ats.tests.AtsTest.getOptions().get("testmode")

    def isCheck(self):
        """
        Return True iff this is a check step.
        """
        return False

    def isDelayed(self):
        """
        Return True iff this step and all substeps should be moved to the end of the test case.
        """
        return self.p.delayed

    def isMinor(self):
        """
        Return True iff failure of this step is a minor issue.
        """
        return self.p.minor

    def saveOut(self):
        return self.p.stdout

    def saveErr(self):
        return self.p.stderr

    def useMPI(self):
        """
        Return True iff this step uses MPI.
        """
        return False

    def resultPaths(self):
        """
        Return a list of paths generated by this step.
        """
        return []

    def timelimit(self):
        return getattr(self.p, "timelimit", None)

    def expectedResult(self):
        return getattr(self.p, "expectedResult", "PASS")

    def handleCommonParams(self):
        """
        Handle all the common parameters.
        """
        if hasattr(self.p, "np"):
            if self.p.np is None:
                self.p.np = 1

        if hasattr(self.p, "ngpu"):
            if self.p.ngpu is None:
                self.p.ngpu = 0

        if hasattr(self.p, "check"):
            if self.p.check is None:
                self.p.check = True

        if hasattr(self.p, "allow_rebaseline"):
            if self.p.allow_rebaseline is None:
                self.p.allow_rebaseline = True

    def executable(self):
        """
        Return the path of the executable used to execute this step.
        """
        raise Error("Must implement this")

    def rebaseline(self):
        """
        Rebaseline this test step.
        """
        pass


################################################################################
# CheckTestStepBase
################################################################################
class CheckTestStepBase(TestStepBase):
    """
    Base class for check test steps.
    """

    checkParams = (TestParam(
        "enabled",
        "True or False. determines whether this step is enabled. Often times used to turn off automatic check steps",
        "True"), )

    def isCheck(self):
        return True

    def handleCommonParams(self):
        TestStepBase.handleCommonParams(self)

        if hasattr(self.p, "enabled"):
            if self.p.enabled is None:
                self.p.enabled = True


################################################################################
# geos
################################################################################
class geos(TestStepBase):
    """
    Class for the Geos test step.
    """

    doc = """
    This TestCase runs the geos executable."""

    command = "geosx [-i <deck>] [-r <restart_file>] [-x <x_partitions>] [-y <y_partitions>] [-z <z_partitions>] [-s <schema_level>] [-n <problem_name>] [-o <output_directory>] [ --suppress-pinned ] "

    params = TestStepBase.defaultParams + (
        TestStepBase.commonParams["name"], TestStepBase.commonParams["deck"], TestStepBase.commonParams["np"],
        TestStepBase.commonParams["ngpu"], TestStepBase.commonParams["check"],
        TestStepBase.commonParams["baseline_dir"], TestStepBase.commonParams["output_directory"],
        TestParam("restart_file", "The name of the restart file."),
        TestParam("x_partitions", "The number of partitions in the x direction."),
        TestParam("y_partitions", "The number of partitions in the y direction."),
        TestParam("z_partitions",
                  "The number of partitions in the z direction."), TestParam("schema_level", "The schema level."),
        TestParam("suppress-pinned", "Option to suppress use of pinned memory for MPI buffers."),
        TestParam("trace_data_migration", "Trace host-device data migration."))

    checkstepnames = ["restartcheck"]

    def __init__(self, restartcheck_params=None, curvecheck_params=None, **kw):
        """
        Initializes the parameters of this test step, and creates the appropriate check steps.

        RESTARTCHECK_PARAMS [in]: Dictionary that gets passed on to the restartcheck step.
        CURVECHECK_PARAMS [in]: Dictionary that gets passed on to the curvecheck step.
        KEYWORDS [in]: Dictionary that is used to set the parameters of this step and also all check steps.
        """

        TestStepBase.__init__(self)
        self.setParams(kw, self.params)

        checkOption = self.getCheckOption()
        self.checksteps = []
        if checkOption in ["all", "curvecheck"]:
            if curvecheck_params is not None:
                self.checksteps.append(curvecheck(curvecheck_params, **kw))

        if checkOption in ["all", "restartcheck"]:
            if restartcheck_params is not None:
                self.checksteps.append(restartcheck(restartcheck_params, **kw))

    def label(self):
        return "geos"

    def useMPI(self):
        return True

    def executable(self):
        # python = os.path.join(binDir, "..", "lib", "PYGEOS", "bin", "python3")
        # pygeosDir = os.path.join(binDir, "..", "..", "src", "pygeos")
        # return python + " -m mpi4py " + os.path.join( pygeosDir, "reentrantTest.py" )
        # return python + " -m mpi4py " + os.path.join( pygeosDir, "test.py" )
        # return config.geos_bin_dir
        return os.path.join(config.geos_bin_dir, 'geosx')

    def update(self, dictionary):
        self.setParams(dictionary, self.params)

        self.requireParam("deck")
        self.requireParam("name")
        self.requireParam("baseline_dir")
        self.requireParam("output_directory")

        self.handleCommonParams()

        self.setStdout(dictionary)

        # update all the checksteps
        if self.p.check:
            for step in self.checksteps:
                step.update(dictionary)

    def insertStep(self, steps):
        #  the step
        steps.append(self)

        #  the post conditions
        if self.p.check:
            for step in self.checksteps:
                step.insertStep(steps)

    def makeArgs(self):
        args = []

        if self.p.deck:
            args += ["-i", self.p.deck]

        if self.p.restart_file:
            args += ["-r", self.p.restart_file]

        if self.p.x_partitions:
            args += ["-x", self.p.x_partitions]

        if self.p.y_partitions:
            args += ["-y", self.p.y_partitions]

        if self.p.z_partitions:
            args += ["-z", self.p.z_partitions]

        if self.p.schema_level:
            args += ["-s", self.p.schema_level]

        if self.p.name:
            args += ["-n", self.p.name]

        if self.p.output_directory:
            args += ["-o", self.p.output_directory]

        # if self.p.ngpu == 0:
        if self.p.ngpu >= 0:
            args += ["--suppress-pinned"]

        if self.p.trace_data_migration:
            args += ["--trace-data-migration"]

        return list(map(str, args))

    def resultPaths(self):
        paths = []
        name = getGeosProblemName(self.p.deck, self.p.name)
        paths += [os.path.join(self.p.output_directory, "%s_restart_*") % name]
        paths += [os.path.join(self.p.output_directory, "silo*")]
        paths += [os.path.join(self.p.output_directory, "%s_bp_*" % name)]

        return paths

    def clean(self):
        self._clean(self.resultPaths())


################################################################################
# restartcheck
################################################################################
class restartcheck(CheckTestStepBase):
    """
    Class for the restart check test step.
    """

    doc = """CheckTestStep to compare a restart file against a baseline."""

    command = """restartcheck [-r RELATIVE] [-a ABSOLUTE] [-o OUTPUT] [-e EXCLUDE [EXCLUDE ...]] [-w] file_pattern baseline_pattern"""

    params = TestStepBase.defaultParams + CheckTestStepBase.checkParams + (
        TestStepBase.commonParams["deck"], TestStepBase.commonParams["name"], TestStepBase.commonParams["np"],
        TestStepBase.commonParams["allow_rebaseline"], TestStepBase.commonParams["baseline_dir"],
        TestStepBase.commonParams["output_directory"],
        TestParam("file_pattern", "Regex pattern to match file written out by geos."),
        TestParam("baseline_pattern", "Regex pattern to match file to compare against."),
        TestParam("rtol",
                  "Relative tolerance, default is 0.0."), TestParam("atol", "Absolute tolerance, default is 0.0."),
        TestParam("exclude", "Regular expressions matching groups to exclude from the check, default is None."),
        TestParam("warnings_are_errors", "Treat warnings as errors, default is True."),
        TestParam("suppress_output", "Whether to write output to stdout, default is True."),
        TestParam("skip_missing", "Whether to skip missing values in target or baseline files, default is False."))

    def __init__(self, restartcheck_params, **kw):
        """
        Set parameters with RESTARTCHECK_PARAMS and then with KEYWORDS.
        """
        CheckTestStepBase.__init__(self)
        self.p.warnings_are_errors = True
        if restartcheck_params is not None:
            self.setParams(restartcheck_params, self.params)
        self.setParams(kw, self.params)

    def label(self):
        return "restartcheck"

    def useMPI(self):
        return True

    def executable(self):
        if self.getTestMode():
            return "python -m mpi4py"
        else:
            return sys.executable + " -m mpi4py"

    def update(self, dictionary):
        self.setParams(dictionary, self.params)
        self.handleCommonParams()

        self.requireParam("deck")
        self.requireParam("baseline_dir")
        self.requireParam("output_directory")

        if self.p.file_pattern is None:
            self.p.file_pattern = getGeosProblemName(self.p.deck, self.p.name) + r"_restart_[0-9]+\.root"
        if self.p.baseline_pattern is None:
            self.p.baseline_pattern = self.p.file_pattern

        self.restart_file_regex = os.path.join(self.p.output_directory, self.p.file_pattern)
        self.restart_baseline_regex = os.path.join(self.p.baseline_dir, self.p.baseline_pattern)

        if self.p.allow_rebaseline is None:
            self.p.allow_rebaseline = True

    def insertStep(self, steps):
        if config.restartcheck_enabled and self.p.enabled:
            steps.append(self)

    def makeArgs(self):
        cur_dir = os.path.dirname(os.path.realpath(__file__))
        script_location = os.path.join(cur_dir, "helpers", "restart_check.py")
        args = [script_location]

        if self.p.atol is not None:
            args += ["-a", self.p.atol]
        if self.p.rtol is not None:
            args += ["-r", self.p.rtol]
        if self.p.warnings_are_errors:
            args += ["-w"]
        if self.p.suppress_output:
            args += ["-s"]
        if (self.p.skip_missing or config.restart_skip_missing):
            args += ["-m"]

        exclude_values = config.restart_exclude_pattern
        if self.p.exclude is not None:
            exclude_values.extend(self.p.exclude)
        for v in exclude_values:
            args += ["-e", v]

        args += [self.restart_file_regex, self.restart_baseline_regex]
        return list(map(str, args))

    def rebaseline(self):
        if not self.p.allow_rebaseline:
            Log("Rebaseline not allowed for restartcheck of %s." % self.p.name)
            return

        root_file_path = findMaxMatchingFile(self.restart_file_regex)
        if root_file_path is None:
            raise IOError("File not found matching the pattern %s in directory %s." %
                          (self.restart_file_regex, os.getcwd()))

        baseline_dir = os.path.dirname(self.restart_baseline_regex)
        root_baseline_path = findMaxMatchingFile(self.restart_baseline_regex)

        if root_baseline_path is not None:
            # Delete the baseline root file.
            os.remove(root_baseline_path)
            # Delete the directory holding the baseline data files.
            data_dir_path = os.path.splitext(root_baseline_path)[0]
            shutil.rmtree(data_dir_path)
        else:
            os.makedirs(baseline_dir, exist_ok=True)

        # Copy the root file into the baseline directory.
        shutil.copy2(root_file_path, os.path.join(baseline_dir, os.path.basename(root_file_path)))
        # Copy the directory holding the data files into the baseline directory.
        data_dir_path = os.path.splitext(root_file_path)[0]
        shutil.copytree(data_dir_path, os.path.join(baseline_dir, os.path.basename(data_dir_path)))

    def resultPaths(self):
        return [os.path.join(self.p.output_directory, "%s.restartcheck" % os.path.splitext(self.p.file_pattern)[0])]

    def clean(self):
        self._clean(self.resultPaths())


################################################################################
# curvecheck
################################################################################
class curvecheck(CheckTestStepBase):
    """
    Class for the curve check test step.
    """

    doc = """CheckTestStep to compare a curve file against a baseline."""

    command = """curve_check.py [-h] [-c CURVE [CURVE ...]] [-t TOLERANCE] [-w] [-o OUTPUT] [-n N_COLUMN] [-u {milliseconds,seconds,minutes,hours,days,years}] filename baseline"""

    params = TestStepBase.defaultParams + CheckTestStepBase.checkParams + (
        TestStepBase.commonParams["deck"], TestStepBase.commonParams["name"], TestStepBase.commonParams["np"],
        TestStepBase.commonParams["allow_rebaseline"], TestStepBase.commonParams["baseline_dir"],
        TestStepBase.commonParams["output_directory"],
        TestParam("filename", "Name of the target curve file written by GEOS."),
        TestParam("curves", "A list of parameter, setname value pairs."),
        TestParam(
            "tolerance",
            "Curve check tolerance (||x-y||/N), can be specified as a single value or a list of floats corresponding to the curves."
        ), TestParam("warnings_are_errors", "Treat warnings as errors, default is True."),
        TestParam("script_instructions", "A list of (path, function, value, setname) entries"),
        TestParam("time_units", "Time units to use for plots."))

    def __init__(self, curvecheck_params, **kw):
        """
        Set parameters with CURVECHECK_PARAMS and then with KEYWORDS.
        """
        CheckTestStepBase.__init__(self)
        self.p.warnings_are_errors = True
        if curvecheck_params is not None:
            c = curvecheck_params.copy()
            Nc = len(c.get('curves', []))

            # Note: ats seems to store list/tuple parameters incorrectly
            # Convert these to strings
            for k in ['curves', 'script_instructions']:
                if k in c:
                    if isinstance(c[k], (list, tuple)):
                        c[k] = ';'.join([','.join(c) for c in c[k]])

            # Check whether tolerance was specified as a single float, list
            # and then convert into a comma-delimited string
            tol = c.get('tolerance', 0.0)
            if isinstance(tol, (float, int)):
                tol = [tol] * Nc
            c['tolerance'] = ','.join([str(x) for x in tol])

            self.setParams(c, self.params)
        self.setParams(kw, self.params)

    def label(self):
        return "curvecheck"

    def useMPI(self):
        return True

    def executable(self):
        if self.getTestMode():
            return "python"
        else:
            return sys.executable

    def update(self, dictionary):
        self.setParams(dictionary, self.params)
        self.handleCommonParams()

        self.requireParam("deck")
        self.requireParam("baseline_dir")
        self.requireParam("output_directory")

        self.baseline_file = os.path.join(self.p.baseline_dir, self.p.filename)
        self.target_file = os.path.join(self.p.output_directory, self.p.filename)
        self.figure_root = os.path.join(self.p.output_directory, 'curve_check')

        if self.p.allow_rebaseline is None:
            self.p.allow_rebaseline = True

    def insertStep(self, steps):
        if config.restartcheck_enabled and self.p.enabled:
            steps.append(self)

    def makeArgs(self):
        cur_dir = os.path.dirname(os.path.realpath(__file__))
        script_location = os.path.join(cur_dir, "helpers", "curve_check.py")
        args = [script_location]

        if self.p.curves is not None:
            for c in self.p.curves.split(';'):
                args += ["-c"]
                args += c.split(',')
        if self.p.tolerance is not None:
            for t in self.p.tolerance.split(','):
                args += ["-t", t]
        if self.p.time_units is not None:
            args += ["-u", self.p.time_units]
        if self.p.script_instructions is not None:
            for c in self.p.script_instructions.split(';'):
                args += ["-s"]
                args += c.split(',')
        if self.p.warnings_are_errors:
            args += ["-w"]

        args += ['-o', self.figure_root]
        args += [self.target_file, self.baseline_file]
        return list(map(str, args))

    def rebaseline(self):
        if not self.p.allow_rebaseline:
            Log("Rebaseline not allowed for curvecheck of %s." % self.p.name)
            return

        baseline_dir = os.path.split(self.baseline_file)[0]
        os.makedirs(baseline_dir, exist_ok=True)
        shutil.copyfile(self.target_file, self.baseline_file)

    def resultPaths(self):
        figure_pattern = os.path.join(self.figure_root, '*.png')
        figure_list = sorted(glob.glob(figure_pattern))
        return [self.target_file] + figure_list

    def clean(self):
        self._clean(self.resultPaths())


def infoTestStepParams(params, maxwidth=None):
    if maxwidth is None:
        maxwidth = max(10, max([len(p.name) for p in params]))
    for p in params:
        paramdoc = p.doc
        if p.default is not None:
            paramdoc += " (default = %s)" % (p.default)
        paramdoc = textwrap.wrap(paramdoc, width=100 - maxwidth)
        logger.debug(" %*s:" % (maxwidth, p.name), paramdoc[0].strip())
        for line in paramdoc[1:]:
            logger.debug(" %*s  %s" % (maxwidth, "", line.strip()))


def infoTestStep(stepname):
    topic = common_utilities.InfoTopic(stepname)
    topic.startBanner()

    logger.debug(f"TestStep: {stepname}")
    stepclass = globals()[stepname]
    if not hasattr(stepclass, "doc"):
        return

    logger.debug("Description:")
    doc = textwrap.dedent(stepclass.doc)
    doc = textwrap.wrap(doc, width=100)
    for line in doc:
        logger.debug("   ", line.strip())

    logger.debug("Command:")
    doc = textwrap.dedent(stepclass.command)
    doc = textwrap.wrap(doc, width=100)
    logger.debug(f"    {doc[0].strip()}")
    for line in doc[1:]:
        logger.debug(f'\\\n    {" " * len(stepname)}  {line}')

    # compute max param width:
    allparams = [p.name for p in stepclass.params]
    if hasattr(stepclass, "checkstepnames"):
        for checkstep in stepclass.checkstepnames:
            checkclass = globals()[checkstep]
            if not hasattr(checkclass, "doc"):
                continue
            allparams.extend([p.name for p in checkclass.params])
    maxwidth = max(10, max([len(p) for p in allparams]))

    logger.debug("Parameters:")
    infoTestStepParams(stepclass.params, maxwidth)

    paramset = set([p.name for p in stepclass.params])

    if hasattr(stepclass, "checkstepnames"):
        for checkstep in stepclass.checkstepnames:
            logger.debug(f"CheckStep: {checkstep}")
            checkparams = []
            checkclass = globals()[checkstep]
            if not hasattr(checkclass, "doc"):
                continue
            for p in checkclass.params:
                if p.name not in paramset:
                    checkparams.append(p)

            infoTestStepParams(checkparams, maxwidth)

    topic.endBanner()


def infoTestSteps(*args):
    """This function is used to print documentation about the teststeps to stdout"""

    # get the list of step classes
    steps = []
    checkstepnames = []

    for k, v in globals().items():
        if not isinstance(v, type):
            continue

        if v in (CheckTestStepBase, TestStepBase):
            continue
        try:
            if issubclass(v, CheckTestStepBase):
                checkstepnames.append(k)
            elif issubclass(v, TestStepBase):
                steps.append(k)
        except TypeError as e:
            logger.debug(e)

    steps = sorted(steps)
    checkstepnames = sorted(checkstepnames)
    steps = steps + checkstepnames

    def all():
        for s in steps:
            infoTestStep(s)

    topic = common_utilities.InfoTopic("teststep")
    topic.addTopic("all", "full info on all the teststeps", all)

    for s in steps:
        stepclass = globals()[s]
        doc = getattr(stepclass, "doc", None)
        topic.addTopic(s, textwrap.dedent(doc).strip(), lambda ss=s: infoTestStep(ss))

    topic.process(args)


# Register test step definitions
ats.manager.define(geos=geos)
ats.manager.define(restartcheck=restartcheck)
ats.manager.define(config=config)

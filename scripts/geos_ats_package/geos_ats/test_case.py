import ats    # type: ignore[import]
import os
import sys
import shutil
import errno
import logging
import glob

test = ats.manager.test
testif = ats.manager.testif

from geos_ats.suite_settings import testLabels, testOwners
from geos_ats.common_utilities import Error, Log, InfoTopic, TextTable, removeLogDirectories
from geos_ats.configuration_record import config, globalTestTimings
from geos_ats import reporting
from geos_ats import test_modifier

TESTS = {}
BASELINE_PATH = "baselines"
logger = logging.getLogger('geos_ats')


class Batch(object):
    """A class to represent batch options"""

    def __init__(self, enabled=True, duration="1h", ppn=0, altname=None):

        if enabled not in (True, False):
            Error("enabled must be a boolean")

        self.enabled = enabled
        self.duration = duration

        try:
            dur = ats.Duration(duration)
            self.durationSeconds = dur.value
        except ats.AtsError as e:
            logger.error(e)
            Error("bad time specification: %s" % duration)

        self.ppn = ppn    # processor per node
        self.altname = altname    # alternate name to use when launcing the batch job


class TestCase(object):
    """Encapsulates one test case, which may include many steps"""

    def __init__(self, name, desc, label=None, labels=None, steps=[], **kw):

        try:
            self.initialize(name, desc, label, labels, steps, **kw)
        except Exception as e:
            # make sure error messages get logged, then get out of here.
            logging.error(e)
            Log(str(e))
            raise Exception(e)

    def initialize(self, name, desc, label=None, labels=None, steps=[], batch=Batch(enabled=False), **kw):

        self.name = name
        self.desc = desc
        self.batch = batch

        action = ats.tests.AtsTest.getOptions().get("action")

        if kw.get("output_directory", False):
            self.path = os.path.abspath(kw.get("output_directory"))
        else:
            self.path = os.path.join(os.getcwd(), self.name)

        self.dirname = os.path.basename(self.path)

        try:
            os.makedirs(self.path)
        except OSError as e:
            if e.errno == errno.EEXIST and os.path.isdir(self.path):
                pass
            else:
                logger.debug(e)
                raise Exception()

        self.atsGroup = None
        self.dictionary = {}
        self.dictionary.update(kw)
        self.nodoc = self.dictionary.get("nodoc", False)
        self.statusFile = os.path.abspath("TestStatus_%s" % self.name)
        self.status = None
        self.outname = os.path.join(self.path, "%s.data" % self.name)
        self.errname = os.path.join(self.path, "%s.err" % self.name)
        self.dictionary["name"] = self.name
        self.dictionary["output_directory"] = self.path
        self.dictionary["baseline_dir"] = os.path.join(os.getcwd(), BASELINE_PATH, self.dirname)
        self.dictionary["testcase_out"] = self.outname
        self.dictionary["testcase_err"] = self.errname
        self.dictionary["testcase_name"] = self.name

        # check for test cases, testcases can either be the string
        # "all" or a list of full test names.
        testcases = ats.tests.AtsTest.getOptions().get("testcases")
        if testcases == "all":
            pass
        elif self.name in testcases:
            testcases.remove(self.name)
            pass
        else:
            return

        if self.name in TESTS:
            Error("Name already in use: %s" % self.name)

        TESTS[self.name] = self

        # check for independent
        if config.override_np > 0:
            # If number of processors is overridden, prevent independent
            # runs in same directory since some output files key on
            # number of processors.
            self.independent = False
        else:
            self.independent = self.dictionary.get("independent", False)
        if self.independent not in (True, False):
            Error("independent must be either True or False: %s" % str(self.independent))

        # check for depends
        self.depends = self.dictionary.get("depends", None)
        if self.depends == self.name:
            # This check avoid testcases depending on themselves.
            self.depends = None

        self.handleLabels(label, labels)

        # complete the steps.
        #  1. update the steps with data from the dictionary
        #  2. substeps are inserted into the list of steps (the steps are flattened)
        for step in steps:
            step.update(self.dictionary)

        self.steps = []
        for step in steps:
            step.insertStep(self.steps)

        # test modifier
        modifier = test_modifier.Factory(config.testmodifier)
        newSteps = modifier.modifySteps(self.steps, self.dictionary)
        if newSteps:
            # insert the modified steps, including any extra steps that may have
            # been added by the modifier.
            self.steps = []
            for step in newSteps:
                step.insertStep(self.steps)
                for extraStep in step.extraSteps:
                    extraStep.insertStep(newSteps)
            self.steps = newSteps
        else:
            Log("# SKIP test=%s : testmodifier=%s" % (self.name, config.testmodifier))
            self.status = reporting.SKIP
            return

        # Check for explicit skip flag
        if action in ("run", "rerun", "continue"):
            if self.dictionary.get("skip", None):
                self.status = reporting.SKIP
                return

        # Filtering tests on maxprocessors
        npMax = self.findMaxNumberOfProcessors()
        if config.filter_maxprocessors != -1:
            if npMax > config.filter_maxprocessors:
                Log("# FILTER test=%s : max processors(%d > %d)" % (self.name, npMax, config.filter_maxprocessors))
                self.status = reporting.FILTERED
                return

        # Filtering tests on maxGPUS
        ngpuMax = self.findMaxNumberOfGPUs()

        # filter based on not enough resources
        if action in ("run", "rerun", "continue"):
            tests = [
                not ats.tests.AtsTest.getOptions().get("testmode"), not self.batch.enabled,
                hasattr(ats.manager.machine, "getNumberOfProcessors")
            ]
            if all(tests):

                totalNumberOfProcessors = getattr(ats.manager.machine, "getNumberOfProcessors")()
                if npMax > totalNumberOfProcessors:
                    Log("# SKIP test=%s : not enough processors to run (%d > %d)" %
                        (self.name, npMax, totalNumberOfProcessors))
                    self.status = reporting.SKIP
                    return

                # If the machine doesn't specify a number of GPUs then it has none.
                totalNumberOfGPUs = getattr(ats.manager.machine, "getNumberOfGPUS", lambda: 1e90)()
                if ngpuMax > totalNumberOfGPUs:
                    Log("# SKIP test=%s : not enough gpus to run (%d > %d)" % (self.name, ngpuMax, totalNumberOfGPUs))
                    self.status = reporting.SKIP
                    return

        # filtering test steps based on action
        if action in ("run", "rerun", "continue"):
            checkoption = ats.tests.AtsTest.getOptions().get("checkoption")
            if checkoption == "none":
                self.steps = [step for step in self.steps if not step.isCheck()]
        elif action == "check":
            self.steps = [step for step in self.steps if step.isCheck()]

        # move all the delayed steps to the end
        reorderedSteps = []
        for step in self.steps:
            if not step.isDelayed():
                reorderedSteps.append(step)
        for step in self.steps:
            if step.isDelayed():
                reorderedSteps.append(step)
        self.steps = reorderedSteps

        # filter based on previous results:
        if action in ("run", "check", "continue"):
            # read the status file
            self.status = test_caseStatus(self)

            # if previously passed then skip
            if self.status.isPassed():
                Log("# SKIP test=%s (previously passed)" % (self.name))
                # don't set status here, as we want the report to reflect the pass
                return

            if action == "continue":
                if self.status.isFailed():
                    Log("# SKIP test=%s (previously failed)" % (self.name))
                    # don't set status here, as we want the report to reflect the pass
                    return

        # Perform the action:
        if action in ("run", "continue"):
            Log("# run test=%s" % (self.name))
            self.testCreate()

        elif action == "rerun":
            Log("# rerun test=%s" % (self.name))
            self.testCreate()

        elif action == "check":
            Log("# check test=%s" % (self.name))
            self.testCreate()

        elif action == "commands":
            self.testCommands()

        elif action == "reset":
            if self.testReset():
                Log("# reset test=%s" % (self.name))

        elif action == "clean":
            Log("# clean test=%s" % (self.name))
            self.testClean()

        elif action == "veryclean":
            Log("# veryclean test=%s" % (self.name))
            self.testVeryClean()

        elif action == "rebaseline":
            self.testRebaseline()

        elif action == "rebaselinefailed":
            self.testRebaselineFailed()

        elif action == "list":
            self.testList()

        elif action in ("report"):
            self.testReport()

        else:
            Error("Unknown action?? %s" % action)

    def resultPaths(self, step=None):
        """Return the paths to output files for the testcase.  Used in reporting"""
        paths = [self.outname, self.errname]
        if step:
            for x in step.resultPaths():
                fullpath = os.path.join(self.path, x)
                if os.path.exists(fullpath):
                    paths.append(fullpath)

        return paths

    def testReset(self):
        self.status = test_caseStatus(self)
        ret = self.status.resetFailed()
        self.status.writeStatusFile()
        return ret

    def testClean(self):
        if os.path.exists(self.statusFile):
            os.remove(self.statusFile)
        if os.path.exists(self.outname):
            os.remove(self.outname)
        if os.path.exists(self.errname):
            os.remove(self.errname)
        for step in self.steps:
            step.clean()

    def testVeryClean(self):

        def _remove(path):
            delpaths = glob.glob(path)
            for p in delpaths:
                if os.path.exists(p):
                    try:
                        if os.path.isdir(p):
                            shutil.rmtree(p)
                        else:
                            os.remove(p)
                    except OSError:
                        pass    # so that two simultaneous clean operations don't fail

        # clean
        self.testClean()
        # remove log directories
        removeLogDirectories(os.getcwd())
        # remove extra files
        if len(self.steps) > 0:
            _remove(config.report_html_file)
            _remove(config.report_text_file)
            _remove(self.path)
            _remove("*.core")
            _remove("core")
            _remove("core.*")
            _remove("vgcore.*")
            _remove("*.btr")
            _remove("TestLogs*")
            _remove("*.ini")

    def findMaxNumberOfProcessors(self):
        npMax = 1
        for step in self.steps:
            np = getattr(step.p, "np", 1)
            npMax = max(np, npMax)
        return npMax

    def findMaxNumberOfGPUs(self):
        gpuMax = 0
        for step in self.steps:
            ngpu = getattr(step.p, "ngpu", 0) * getattr(step.p, "np", 1)
            gpuMax = max(ngpu, gpuMax)
        return gpuMax

    def testCreate(self):
        atsTest = None
        keep = ats.tests.AtsTest.getOptions().get("keep")

        # remove outname
        if os.path.exists(self.outname):
            os.remove(self.outname)
        if os.path.exists(self.errname):
            os.remove(self.errname)

        # create the status file
        if self.status is None:
            self.status = test_caseStatus(self)

        maxnp = 1
        for stepnum, step in enumerate(self.steps):
            np = getattr(step.p, "np", 1)
            maxnp = max(np, maxnp)

        if config.priority == "processors":
            priority = maxnp
        elif config.priority == "timing":
            priority = max(globalTestTimings.get(self.name, 1) * maxnp, 1)
        else:
            priority = 1

        # start a group
        ats.tests.AtsTest.newGroup(priority=priority)

        # keep a reference to the ats test group
        self.atsGroup = ats.tests.AtsTest.group

        # if depends
        if self.depends:
            priorTestCase = TESTS.get(self.depends, None)
            if priorTestCase is None:
                Log("Warning: Test %s depends on testcase %s, which is not scheduled to run" %
                    (self.name, self.depends))
            else:
                if priorTestCase.steps:
                    atsTest = getattr(priorTestCase.steps[-1], "atsTest", None)

        for stepnum, step in enumerate(self.steps):

            np = getattr(step.p, "np", 1)
            ngpu = getattr(step.p, "ngpu", 0)
            executable = step.executable()
            args = step.makeArgs()

            # set the label
            label = "%s/%s_%d_%s" % (self.dirname, self.name, stepnum + 1, step.label())

            # call either 'test' or 'testif'
            if atsTest is None:
                func = lambda *a, **k: test(*a, **k)
            else:
                func = lambda *a, **k: testif(atsTest, *a, **k)

            # timelimit
            kw = {}

            if self.batch.enabled:
                kw["timelimit"] = self.batch.duration

            if (step.timelimit() and not config.override_timelimit):
                kw["timelimit"] = step.timelimit()
            else:
                kw["timelimit"] = config.default_timelimit

            atsTest = func(executable=executable,
                           clas=args,
                           np=np,
                           ngpu=ngpu,
                           label=label,
                           serial=(not step.useMPI() and not config.script_launch),
                           independent=self.independent,
                           batch=self.batch.enabled,
                           **kw)

            # ats test gets a reference to the TestStep and the TestCase
            atsTest.geos_atsTestCase = self
            atsTest.geos_atsTestStep = step

            # TestStep gets a reference to the atsTest
            step.atsTest = atsTest

            # Add the step the test status object
            self.status.addStep(atsTest)

            # set the expected result
            if step.expectedResult() == "FAIL" or step.expectedResult() is False:
                atsTest.expectedResult = ats.FAILED
                # The ATS does not permit tests to depend on failed tests.
                # therefore we need to break here
                self.steps = self.steps[:stepnum + 1]
                break

        # end the group
        ats.tests.AtsTest.endGroup()

        self.status.resetFailed()
        self.status.writeStatusFile()

    def commandLine(self, step):
        args = []
        executable = step.executable()
        commandArgs = step.makeArgs()
        assert isinstance(commandArgs, list)
        for a in commandArgs:
            if " " in a:
                args.append('"%s"' % a)
            else:
                args.append(a)

        argsstr = " ".join(args)
        return executable + " " + argsstr

    def testCommands(self):
        Log("\n# commands test=%s" % (self.name))
        for step in self.steps:
            np = getattr(step.p, "np", 1)
            usempi = step.useMPI()
            stdout = getattr(step.p, "stdout", None)
            commandline = self.commandLine(step).replace('%%', '%')
            if stdout:
                Log("np=%d %s > %s" % (np, commandline, stdout))
            else:
                Log("np=%d %s" % (np, commandline))

    def testRebaseline(self):
        rebaseline = True
        if config.rebaseline_ask:
            while 1:
                if config.rebaseline_undo:
                    logger.info(f"Are you sure you want to undo the rebaseline for TestCase '{self.name}'?", flush=True)
                else:
                    logger.info(f"Are you sure you want to rebaseline TestCase '{self.name}'?", flush=True)

                x = input('[y/n] ')
                x = x.strip()
                if x == "y":
                    break
                if x == "n":
                    rebaseline = False
                    break
        else:
            Log("\n# rebaseline test=%s" % (self.name))

        if rebaseline:
            for step in self.steps:
                step.rebaseline()

    def testRebaselineFailed(self):
        config.rebaseline_ask = False
        self.status = test_caseStatus(self)
        if self.status.isFailed():
            self.testRebaseline()

    def testList(self):
        Log("# test=%s : labels=%s" % (self.name.ljust(32), " ".join(self.labels)))

    def testReport(self):
        self.status = test_caseStatus(self)

    def handleLabels(self, label, labels):
        """set the labels, and verify they are known to the system, the avoid typos"""
        if labels is not None and label is not None:
            Error("specify only one of 'label' or 'labels'")

        if label is not None:
            self.labels = [label]
        elif labels is not None:
            self.labels = labels
        else:
            self.labels = []

        for x in self.labels:
            if x not in testLabels:
                Error(f"unknown label {x}. run 'geos_ats -i labels' for a list")


class test_caseStatus(object):

    def __init__(self, testCase):
        self.testCase = testCase
        self.statusFile = self.testCase.statusFile
        self.readStatusFile()

    def readStatusFile(self):
        if os.path.exists(self.statusFile):
            f = open(self.statusFile, "r")
            self.status = [eval(x.strip()) for x in f.readlines()]
            f.close()
        else:
            self.status = []

    def writeStatusFile(self):
        assert self.status is not None

        with open(self.statusFile, "w") as f:
            f.writelines([str(s) + '\n' for s in self.status])

    def testKey(self, step):
        np = getattr(step.p, "np", 1)
        key = str((np, step.label(), step.executable(), step.makeArgsForStatusKey()))
        return key

    def testData(self, test):
        key = self.testKey(test.geos_atsTestStep)
        result = test.status

        if result == ats.PASSED and test.expectedResult == ats.FAILED:
            result = ats.FAILED
        endTime = getattr(test, "endTime", None)
        startTime = getattr(test, "startTime", None)
        data = {}
        data["key"] = key
        data["result"] = str(result)
        data["startTime"] = startTime
        data["endTime"] = endTime
        return key, data

    def findStep(self, step):
        key = self.testKey(step)
        for s in self.status:
            if key in s["key"]:
                return s

        return None

    def isPassed(self):
        for step in self.testCase.steps:
            status = self.findStep(step)
            if status:
                if status["result"] == "EXPT":
                    # do not continue after an expected fail
                    return True
                elif status["result"] == "PASS":
                    continue
                else:
                    return False
            else:
                return False
        return True

    def isFailed(self):
        for step in self.testCase.steps:
            status = self.findStep(step)
            if status:
                if status["result"] == "EXPT":
                    # do not continue after an expected fail
                    return False
                elif status["result"] == "PASS":
                    continue
                elif status["result"] == "FAIL":
                    return True
                else:
                    return False
            else:
                return False
        return False

    def resetFailed(self):
        ret = False
        for step in self.testCase.steps:
            status = self.findStep(step)
            if status:
                if status["result"] == "EXPT":
                    # do not continue after an expected fail
                    status["result"] = "INIT"
                    ret = True
                elif status["result"] == "FAIL":
                    status["result"] = "INIT"
                    ret = True
                else:
                    continue
        return ret

    def totalTime(self):
        total = 0.0
        for step in self.testCase.steps:
            status = self.findStep(step)
            if status:
                steptime = status["endTime"] - status["startTime"]
                assert steptime >= 0
                total += steptime
        return total

    def addStep(self, test):
        key, data = self.testData(test)
        found = False
        for s in self.status:
            if key == s["key"]:
                found = True
                break

        if not found:
            self.status.append(data)

    def noteEnd(self, test):
        """Update the TestStatus file for this test case"""
        # update the status
        key, data = self.testData(test)

        self.readStatusFile()
        found = False
        for i, s in enumerate(self.status):
            if key in s["key"]:
                self.status[i] = data
                found = True
                break

        if not found:
            logger.warning(f"NOT FOUND: {key} {self.statusFile}")
        assert found
        self.writeStatusFile()

        # append to stdout/stderr file
        for stream in ("outname", "errname"):
            sourceFile = getattr(test, stream)
            dataFile = getattr(self.testCase, stream)

            if not os.path.exists(sourceFile):
                continue

            # Append to the TestCase files
            f1 = open(dataFile, "a")
            f2 = open(sourceFile, "r")
            f1.write(":" * 20 + "\n")
            f1.write(self.testCase.commandLine(test.geos_atsTestStep) + "\n")
            f1.write(":" * 20 + "\n")
            f1.write(f2.read())
            f1.close()
            f2.close()

            # Copy the stdout or stderr, if requested
            if stream == "outname":
                destFile = test.geos_atsTestStep.saveOut()
            else:
                destFile = test.geos_atsTestStep.saveErr()

            if destFile:
                destFile = os.path.join(self.testCase.path, destFile)
                shutil.copy(sourceFile, destFile)

        # If this is the last step (and it passed), clean the temporary files
        if config.clean_on_pass:
            lastStep = (test.geos_atsTestStep is self.testCase.steps[-1])
            if lastStep and self.isPassed():
                for step in self.testCase.steps:
                    step.clean()


def infoTestCase(*args):
    """This function is used to print documentation about the testcase"""

    topic = InfoTopic("testcase")
    topic.startBanner()

    logger.info("Required parameters")
    table = TextTable(3)
    table.addRow("name", "required", "The name of the test problem")
    table.addRow("desc", "required", "A brief description")
    table.addRow("label", "required", "A string or sequence of strings to tag the TestCase.  See info topic 'labels'")
    table.addRow("owner", "optional",
                 "A string or sequence of strings of test owners for this TestCase.  See info topic 'owners'")
    table.addRow(
        "batch", "optional", "A Batch object.  Batch(enabled=True, duration='1h', ppn=0, altname=None)."
        " ppn is short for processors per node (0 means to use the global default)."
        " altname will be used for the batch job's name if supplied, otherwise the full name of the test case is used."
    ),
    table.addRow("depends", "optional", "The name of a testcase that this testcase depends")
    table.addRow("steps", "required", "A sequence of TestSteps objects.  See info topic 'teststeps'")

    table.printTable()

    topic.endBanner()


# Make available to the tests
ats.manager.define(TestCase=TestCase)
ats.manager.define(Batch=Batch)

#ATS:bgqos_0_ASQ machines.bgqos_0_ASQ bgqos_0_ASQMachine 16

from ats import machines, debug, atsut    # type: ignore[import]
from ats import log, terminal
from ats import configuration
from ats.atsut import RUNNING, TIMEDOUT, SKIPPED, BATCHED, INVALID, PASSED, FAILED, CREATED, FILTERED, HALTED, EXPECTED    # type: ignore[import]
import utils    # type: ignore[import]
import time
import sys


class bgqos_0_ASQMachine(machines.Machine):
    """The chaos family with processor scheduling.
    """

    def init(self):

        self.npBusy = 0

        self.stepToUse = None
        self.stepInUse = None

        self.npMax = self.numberTestsRunningMax

        self.nodeProcAvailDic = {}

    def addOptions(self, parser):
        "Add options needed on this machine."
        parser.add_option("--partition",
                          action="store",
                          type="string",
                          dest='partition',
                          default='pdebug',
                          help="Partition in which to run jobs with np > 0")
        parser.add_option("--numNodes",
                          action="store",
                          type="int",
                          dest='numNodes',
                          default=-1,
                          help="Number of nodes to use")
        parser.add_option("--srunOnlyWhenNecessary",
                          action="store_true",
                          dest='srun',
                          default=False,
                          help="Use srun only for np > 1")
        parser.add_option("--removeSrunStep",
                          action="store_true",
                          dest='removeSrunStep',
                          default=True,
                          help="Set to use srun job step.")

    def examineOptions(self, options):
        "Examine options from command line, possibly override command line choices."
        # Grab option values.
        super(bgqos_0_ASQMachine, self).examineOptions(options)
        self.npMax = self.numberTestsRunningMax

        import os
        self.removeSrunStep = options.removeSrunStep
        if not self.removeSrunStep:
            if 'SLURM_NNODES' not in os.environ:
                self.removeSrunStep = True

        if options.numNodes == -1:
            if 'SLURM_NNODES' in os.environ:
                options.numNodes = int(os.environ['SLURM_NNODES'])

            else:
                options.numNodes = 1
        self.numNodes = options.numNodes

        if self.npMax == 1:
            self.numNodes = 1
        self.numberMaxProcessors = self.npMax * self.numNodes

        self.srunOnlyWhenNecessary = options.srun
        self.partition = options.partition

        if not self.removeSrunStep:
            self.allNodeList = utils.getAllHostnames()
            if len(self.allNodeList) == 0:
                self.removeSrunStep = True
            else:
                self.stepId, self.nodeStepNumDic = utils.setStepNumWithNode(len(self.allNodeList))
                for oneNode in self.allNodeList:
                    self.nodeProcAvailDic[oneNode] = self.npMax
                self.stepInUse = self.stepToUse

                # Let's check if there exists a srun <defunct> process
                if len(self.allNodeList) > 0:
                    srunDefunct = utils.checkForSrunDefunct(self.allNodeList[0])
                    self.numberMaxProcessors -= srunDefunct
                    self.nodeProcAvailDic[self.allNodeList[0]] -= srunDefunct

        self.numberTestsRunningMax = self.numberMaxProcessors

    def getResults(self):
        results = super(bgqos_0_ASQMachine, self).getResults()
        results.srunOnlyWhenNecessary = self.srunOnlyWhenNecessary
        results.partition = self.partition
        results.numNodes = self.numNodes
        results.numberMaxProcessors = self.numberMaxProcessors

        if not self.removeSrunStep:
            results.allNodeList = self.allNodeList

        return results

    def label(self):
        return "BG/Q %d nodes %d processors per node." % (self.numNodes, self.npMax)

    def calculateCommandList(self, test):
        """Prepare for run of executable using a suitable command. First we get the plain command
         line that would be executed on a vanilla serial machine, then we modify it if necessary
         for use on this machines.
        """
        commandList = self.calculateBasicCommandList(test)
        if self.srunOnlyWhenNecessary and test.np <= 1:
            return commandList

        if test.options.get('checker_test'):
            return commandList
        # namebase is a space-free version of the name
        test.jobname = f"t{test.np}_{test.serialNumber}{test.namebase}"

        np = max(test.np, 1)
        minNodes = np / self.npMax + (np % self.npMax != 0)

        #
        # These should be removed
        #
        #        if not self.removeSrunStep:
        #            self.nodeProcAvailDic, self.stepToUse, test.numNodesToUse = utils.findAvailableStep(self.allNodeList, self.nodeProcAvailDic, self.nodeStepNumDic, self.npMax, np, self.stepInUse)
        #
        #            test.step= self.stepToUse
        #            self.stepInUse= self.stepToUse
        #
        #            if self.stepToUse is None:
        #                return None
        #
        #        if not self.removeSrunStep:
        #            if self.stepToUse is not None:
        #                #test.srunRelativeNode = self.stepToUse
        #                finalList =  ["srun",
        #                              #"-N", "".join([minNumNodes, "-", str(test.numNodesToUse)]),
        #                              #"-r", str(self.stepToUse),
        #                              "-n", str(np),
        #                              "-p", self.partition,
        #                              "--share",
        #                              "--label", "-J", test.jobname] +commandList
        #                self.stepToUse= None
        #                return finalList

        #
        # bgqos should go into here
        #
        return [
            "srun",
            "-N%i-%i" % (minNodes, minNodes), "-n",
            str(np), "-p", self.partition, "--label", "-J", test.jobname
        ] + commandList

    def canRun(self, test):
        "Do some precalculations here to make canRunNow quicker."
        test.requiredNP = max(test.np, 1)
        test.numberOfNodesNeeded, r = divmod(test.requiredNP, self.npMax)
        if r:
            test.numberOfNodesNeeded += 1

        if self.removeSrunStep:
            test.requiredNP = max(test.np, self.npMax * test.numberOfNodesNeeded)
        if test.requiredNP > self.numberMaxProcessors:
            return "Too many processors required, %d (limit is %d)" % (test.requiredNP, self.numberMaxProcessors)

    def canRunNow(self, test):
        "Is this machine able to run this test now? Return True/False"
        if (self.npBusy + test.requiredNP) > self.numberMaxProcessors:
            return False

        elif self.removeSrunStep:
            return True

        return True

    def noteLaunch(self, test):
        """A test has been launched."""

        if not self.removeSrunStep:
            if test.srunRelativeNode < 0:
                self.nodeProcAvailDic = utils.removeFromUsedTotalDicNoSrun(self.nodeProcAvailDic, self.nodeStepNumDic,
                                                                           self.npMax, test.np, self.allNodeList)
            else:
                self.nodeProcAvailDic = utils.removeFromUsedTotalDic(self.nodeProcAvailDic, self.nodeStepNumDic,
                                                                     self.npMax, test.step, test.np,
                                                                     test.numberOfNodesNeeded, test.numNodesToUse,
                                                                     test.srunRelativeNode, self.stepId,
                                                                     self.allNodeList)
            self.npBusy += max(test.np, 1)
        else:
            # this is necessary when srun exclusive is used.
            self.npBusy += max(test.np, test.numberOfNodesNeeded * self.npMax)

        if debug():
            log(f"Max np={self.numberMaxProcessors}. Launched {test.name} with np= {test.np} tests, total proc in use = {self.npBusy}",
                echo=True)
            self.scheduler.schedule(
                f"Max np= {self.numberMaxProcessors}. Launched {test.name} with np= {test.np} tests, total proc in use = self.npBusy"
            )

        self.numberTestsRunning = self.npBusy

    def noteEnd(self, test):
        """A test has finished running. """

        if not self.removeSrunStep:

            self.npBusy -= max(test.np, 1)
        else:
            # this is necessary when srun exclusive is used.
            self.npBusy -= max(test.np, test.numberOfNodesNeeded * self.npMax)

        if debug():
            log("Finished %s, #total proc in use = %d" % (test.name, self.npBusy), echo=True)
            self.scheduler.schedule("Finished %s, #total proc in use = %d" % (test.name, self.npBusy))

        self.numberTestsRunning = self.npBusy

    def periodicReport(self):
        "Report on current status of tasks"
        # Let's also write out the tests that are waiting ....

        super(bgqos_0_ASQMachine, self).periodicReport()
        currentEligible = [t.name for t in self.scheduler.testlist() if t.status is atsut.CREATED]

        if len(currentEligible) > 1:
            terminal("WAITING:", ", ".join(currentEligible[:5]), "... (more)")

    def kill(self, test):
        "Final cleanup if any."
        # kill the test
        # This is necessary -- killing the srun command itself is not enough to end the job... it is still running (squeue will show this)
        import subprocess

        if test.status is RUNNING or test.status is TIMEDOUT:
            try:
                retcode = subprocess.call("scancel" + " -n  " + test.jobname, shell=True)
                if retcode < 0:
                    log("---- kill() in bgqos_0_ASQ.py, command= scancel -n  %s failed with return code -%d  ----" %
                        (test.jobname, retcode),
                        echo=True)
            except OSError as e:
                log("---- kill() in bgqos_0_ASQ.py, execution of command failed (scancel -n  %s) failed:  %s----" %
                    (test.jobname, e),
                    echo=True)

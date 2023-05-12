#ATS:SequentialMachine  SELF lassenMachine  1
#ATS:lassen           SELF lassenMachine   1

from ats import machines    # type: ignore[import]
from ats import machines, debug, atsut
from ats import log, terminal
from ats import configuration
from ats.atsut import RUNNING, TIMEDOUT    # type: ignore[import]
from ats import AtsTest
import os
import subprocess
import logging


class lassenMachine(machines.Machine):
    """
    run from a backend node on Lassen
    """

    def init(self):
        self.numtests = 0
        self.numProcsAvailable = 0
        self.logger = logging.getLogger('geos_ats')

    def examineOptions(self, options):
        "Examine options from command line, possibly override command line choices."
        super(lassenMachine, self).examineOptions(options)

        # Get total cpu cores available, and convert to number of gpus!
        self.numberMaxProcessors = int(os.getenv("LSB_MAX_NUM_PROCESSORS", "0")) - 1
        self.numberMaxGPUS = self.numberMaxProcessors / 10

        self.numberTestsRunningMax = self.numberMaxProcessors
        self.numProcsAvailable = self.numberMaxProcessors

    def getNumberOfProcessors(self):
        return self.numberMaxProcessors

    def getNumberOfGPUS(self):
        return self.numberMaxGPUS

    def addOptions(self, parser):
        "Add options needed on this machine."

        parser.add_option("--numNodes",
                          action="store",
                          type="int",
                          dest='numNodes',
                          default=1,
                          help="Number of nodes to use")

        return

    def calculateCommandList(self, test):
        """Prepare for run of executable using a suitable command. First we get the plain command
         line that would be executed on a vanilla serial machine, then we modify it if necessary
         for use on this machines.
        """
        options = AtsTest.getOptions()
        basicCommands = self.calculateBasicCommandList(test)
        commandList = []

        ngpu = test.ngpu
        commandList += ["lrun", "-n", "%d" % test.np, "--pack", "-g", "%d" % ngpu]
        commandList += basicCommands
        return commandList

    def canRun(self, test):
        """Is this machine able to run the test interactively when resources become available?
           If so return ''. Otherwise return the reason it cannot be run here.
        """
        np = max(test.np, 1)
        if np > self.numberMaxProcessors:
            return f"Too many processors needed ({np})"

        gpusPerTask = test.ngpu
        if np * gpusPerTask > self.numberMaxGPUS:
            err = f"Too many gpus needed ({np * gpusPerTask:d})"
            self.logger.error(err)
            return err

    def canRunNow(self, test):
        """We let lrun do the scheduling so return true."""
        return True

    def noteLaunch(self, test):
        """A test has been launched."""
        self.numtests += 1

    def noteEnd(self, test):
        """A test has finished running. """
        self.numtests -= 1

    def periodicReport(self):
        "Report on current status of tasks"
        terminal("-" * 80)
        terminal("Running jobs:")
        os.system("jslist -r")
        terminal("Queued jobs:")
        os.system("jslist -p")
        terminal("-" * 80)

    def kill(self, test):
        "Final cleanup if any."

        if test.status is RUNNING or test.status is TIMEDOUT:
            # It is possible that the job stopped on its own
            # so OK
            try:
                test.child.terminate()
            except:
                logger.info("Terminating job")

            try:
                retcode = subprocess.call("jskill all", shell=True)
                if retcode < 0:
                    log("command= %s failed with return code %d" % ("jskill all", retcode), echo=True)
            except:
                logger.info("Killing job")

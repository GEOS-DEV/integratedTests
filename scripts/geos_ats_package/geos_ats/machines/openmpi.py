#ATS:openmpi machines.openmpi OpenmpiMachine 16

import os
import ats    # type: ignore[import]
from ats import machines
from ats import terminal
from ats import log
import shlex
from ats.atsut import RUNNING, TIMEDOUT    # type: ignore[import]
from ats import AtsTest
import logging


class OpenmpiMachine(machines.Machine):
    "Openmpi Machine."

    def init(self):
        self.numtests = 0
        self.maxtests = 0
        self.numProcsAvailable = 0
        self.logger = logging.getLogger('geos_ats')

    def examineOptions(self, options):
        "Examine options from command line, possibly override command line choices."
        super(OpenmpiMachine, self).examineOptions(options)
        # openmpi_numnodes is actually number of jobs
        self.precommand = options.openmpi_precommand
        self.terminate = options.openmpi_terminate
        self.install = options.openmpi_install

        if options.openmpi_mpirun:
            mpirunCmd = options.openmpi_mpirun
        else:
            mpirunCmd = "mpirun"
        self.mpirun = os.path.join(self.install, "bin", mpirunCmd)

        self.openmpi_args = options.openmpi_args.split()
        # numberTestsRunningMax is actually the number of processors
        if options.openmpi_maxprocs > 0:
            self.numberMaxProcessors = options.openmpi_maxprocs
        else:
            self.numberMaxProcessors = options.openmpi_procspernode * options.openmpi_numnodes
        self.numberTestsRunningMax = self.numberMaxProcessors
        self.numProcsAvailable = self.numberMaxProcessors

        # Copy options for geos_ats config
        self.openmpi_numnodes = options.openmpi_numnodes
        self.openmpi_maxprocs = options.openmpi_maxprocs
        self.maxtests = options.openmpi_maxprocs
        self.openmpi_procspernode = options.openmpi_procspernode
        self.openmpi_precommand = options.openmpi_precommand
        self.openmpi_terminate = options.openmpi_terminate
        self.openmpi_install = options.openmpi_install
        self.openmpi_mpirun = options.openmpi_mpirun

    def getNumberOfProcessors(self):
        return self.numberMaxProcessors

    def addOptions(self, parser):
        "Add options needed on this machine."
        parser.add_option("--openmpi_numnodes",
                          "--numNodes",
                          action="store",
                          type="int",
                          dest='openmpi_numnodes',
                          default=2,
                          help="Number of nodes to use")

        parser.add_option("--openmpi_maxprocs",
                          "--maxProcs",
                          action="store",
                          type="int",
                          dest='openmpi_maxprocs',
                          default=0,
                          help="Maximum number of processors to use")

        parser.add_option("--openmpi_procspernode",
                          "--procsPerNode",
                          action="store",
                          type="int",
                          dest='openmpi_procspernode',
                          default=1,
                          help="Number of processors per node")

        parser.add_option("--openmpi_precommand",
                          action="store",
                          type="str",
                          dest='openmpi_precommand',
                          default="",
                          help="Prepend to each command")

        parser.add_option("--openmpi_terminate",
                          action="store",
                          type="str",
                          dest='openmpi_terminate',
                          default="",
                          help="Command for abnormal termination")

        parser.add_option("--openmpi_install",
                          action="store",
                          type="str",
                          dest='openmpi_install',
                          default="",
                          help="Location of the openmpi install")

        parser.add_option("--openmpi_args",
                          action="store",
                          type="str",
                          dest='openmpi_args',
                          default="",
                          help="Arguments for openmpi mpirun command")

        parser.add_option("--openmpi_mpirun",
                          action="store",
                          type="str",
                          dest='openmpi_mpirun',
                          default="",
                          help="Set the mpi execution command")

    def calculateCommandList(self, test):
        """Prepare for run of executable using a suitable command. First we get the plain command
         line that would be executed on a vanilla serial machine, then we modify it if necessary
         for use on this machines.
        """
        options = AtsTest.getOptions()
        basicCommands = self.calculateBasicCommandList(test)
        if self.precommand:
            import time
            timeNow = time.strftime('%H%M%S', time.localtime())
            test.jobname = "t%d_%d%s%s" % (test.np, test.serialNumber, test.namebase, timeNow)
            pre = self.precommand % {"np": test.np, "J": test.jobname}
            commandList = pre.split()
        else:
            commandList = []

        commandList += [self.mpirun, "-n", "%d" % test.np]
        commandList += self.openmpi_args
        commandList += basicCommands
        return commandList

    def canRun(self, test):
        """Is this machine able to run the test interactively when resources become available?
           If so return ''.  Otherwise return the reason it cannot be run here.
        """
        np = max(test.np, 1)
        if np > self.numberMaxProcessors:
            return "Too many processors needed (%d)" % np

    def canRunNow(self, test):
        "Is this machine able to run this test now? Return True/False"
        np = max(test.np, 1)
        return ((self.numtests < self.maxtests) and (self.numProcsAvailable >= np))

    def noteLaunch(self, test):
        """A test has been launched."""
        np = max(test.np, 1)
        self.numProcsAvailable -= np
        self.numtests += 1

    def noteEnd(self, test):
        """A test has finished running. """
        np = max(test.np, 1)
        self.numProcsAvailable += np
        self.numtests -= 1

    def periodicReport(self):
        "Report on current status of tasks"
        terminal("-" * 80)
        terminal("CURRENTLY RUNNING %d of %d tests." % (self.numtests, self.maxtests))
        terminal("-" * 80)
        terminal("CURRENTLY UTILIZING %d processors (max %d)." %
                 (self.numberMaxProcessors - self.numProcsAvailable, self.numberMaxProcessors))
        terminal("-" * 80)

    def kill(self, test):
        "Final cleanup if any."
        import subprocess

        if test.status is RUNNING or test.status is TIMEDOUT:
            # It is possible that the job stopped on its own
            # so OK
            try:
                test.child.terminate()
            except:
                self.logger.debug("Terminating job`")

            if self.terminate:
                try:
                    term = self.terminate % {"J": test.jobname}
                    retcode = subprocess.call(term, shell=True)
                    if retcode < 0:
                        log(f"---- kill() in openmpi.py, command= {term} failed with return code -{retcode}  ----",
                            echo=True)
                except:
                    self.logger.debug("Terminating job`")

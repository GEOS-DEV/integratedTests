#ATS:Nersc machines.nersc Nersc 20
#ATS:slurm8                  machines.nersc Nersc  8
#ATS:slurm12                 machines.nersc Nersc 12
#ATS:slurm16                 machines.nersc Nersc 16
#ATS:slurm20                 machines.nersc Nersc 20
#ATS:slurm24                 machines.nersc Nersc 24
#ATS:chaos_5_x86_64_ib       machines.nersc Nersc 16

from geos_ats.scheduler import scheduler
from geos_ats.machine_utilities import CheckForEarlyTimeOut
from slurmProcessorScheduled import SlurmProcessorScheduled    # type: ignore[import]
import subprocess
import logging


class Nersc(SlurmProcessorScheduled):

    def init(self):
        super(Nersc, self).init()
        self.logger = logging.getLogger('geos_ats')
        if not self.runWithSalloc:
            try:
                # Try to get the number of processors per node via sinfo.
                # We might want to propose this change for the ATS core.
                # CPUs (%c) is actually threads, so multiply sockets (%X) X cores (%Y)
                # to get actual number of processors (we ignore hyprethreading).
                sinfoCmd = 'sinfo -o"%X %Y"'
                proc = subprocess.Popen(sinfoCmd, shell=True, stdout=subprocess.PIPE)
                stdout_value = proc.communicate()[0]
                (sockets, cores) = stdout_value.split('\n')[1].split()
                self.npMaxH = int(sockets) * int(cores)
            except:
                self.logger.debug("Failed to identify npMaxH")
        else:
            self.npMaxH = self.npMax
        self.scheduler = scheduler()

    def label(self):
        return "Nersc: %d nodes, %d processors per node." % (self.numNodes, self.npMax)

    def checkForTimeOut(self, test):
        """ Check the time elapsed since test's start time.  If greater
        then the timelimit, return true, else return false.  test's
        end time is set if time elapsed exceeds time limit.
        Also return true if retry string if found."""
        retval, fraction = super(Nersc, self).checkForTimeOut(test)
        return CheckForEarlyTimeOut(test, retval, fraction)

    def calculateCommandList(self, test):
        command = super(Nersc, self).calculateCommandList(test)
        command.remove("--mpibind=off")
        return command

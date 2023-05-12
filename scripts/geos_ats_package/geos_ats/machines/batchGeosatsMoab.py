#BATS:batchGeosatsMoab  batchGeosatsMoab BatchGeosatsMoab -1

from ats import machines, configuration, log, atsut, times, AtsTest    # type: ignore[import]
import subprocess, sys, os, shlex, time, socket, re
import utils, batchTemplate    # type: ignore[import]
from batch import BatchMachine    # type: ignore[import]
import logging

debug = configuration.debug
logger = logging.getLogger('geos_ats')


class BatchGeosatsMoab(BatchMachine):
    """The batch machine
    """

    def init(self):

        super(BatchGeosatsMoab, self).init()

        if "SLURM_NNODES" in os.environ.keys():
            self.ppn = int(os.getenv("SLURM_TASKS_PER_NODE", "1").split("(")[0])
        elif "SLURM_JOB_NUM_NODES" in os.environ.keys():
            self.ppn = int(os.getenv("SLURM_JOB_CPUS_PER_NODE", "1").split("(")[0])
        else:
            self.ppn = 0

        self.numberTestsRunningMax = 2048

    def canRun(self, test):
        return ''

    def load(self, testlist):
        """Receive a list of tests to possibly run.
           Submit the set of tests to batch.
        """

        self.testlist = testlist

        for t in testlist:

            # for each test group make an msub file
            if t.groupSerialNumber == 1:
                testCase = getattr(t, "geos_atsTestCase", None)
                if testCase:
                    batchFilename = os.path.join(testCase.dirnamefull, "batch_%s.msub" % testCase.name)
                    self.writeSubmitScript(batchFilename, testCase)
                    self.jobid = self.submitBatchScript(testCase.name, batchFilename)

    def writeSubmitScript(self, batchFilename, testCase):

        fc = open(batchFilename, "w")
        batch = testCase.batch

        # get references to the options and configuration
        options = AtsTest.getOptions()
        config = options.get("config", None)

        # ppn
        # 1.  first check batch object
        # 2.  then check config
        # 3.  then check slurm variables
        ppn = 0
        if batch.ppn != 0:
            ppn = batch.ppn
        elif config.batch_ppn != 0:
            ppn = config.batch_ppn
        else:
            ppn = self.ppn

        if ppn == 0:
            raise RuntimeError("""
            Unable to find the number of processors per node in
            BatchGeosatsMoab.  Try setting batch_ppn=<ppn> on the
            command line.""")

        # Specifies parallel Lustre file system.
        gresLine = ""
        if self.gres is not None:
            gresLine = "#MSUB -l gres=" + self.gres,

        # determine the max number of processors in this job
        maxprocs = testCase.findMaxNumberOfProcessors()
        minNodes = maxprocs / ppn + (maxprocs % ppn != 0)

        # MSUB options
        msub_str = '#!/bin/csh'

        if batch.altname:
            msub_str += f"\n#MSUB -N {batch.altname} # name of the job"
        else:
            msub_str += f"\n#MSUB -N {testCase.name} # name of the job"

        if config.batch_queue:
            msub_str += f"\n#MSUB -q {config.batch_queue} # run the the specific queue (pdebug, pbatch, etc)"

        if config.batch_bank:
            msub_str += f"\n#MSUB -A {config.batch_bank} # the bank account to charge "

        if config.batch_partition:
            msub_str += f"\n#MSUB -l partition={config.batch_partition} # constraints"

        msub_str += f"\n#MSUB -V    # all environment variable are exported"
        msub_str += f"\n#MSUB -l nodes={minNodes}:ppn={ppn} # number of nodes"
        msub_str += f"\n#MSUB -l walltime={batch.durationSeconds} # max runtime in seconds"
        batchFilename_abs = batchFilename
        msub_str += f"\n#MSUB -o {batchFilename_abs}.out"
        msub_str += f"\n#MSUB -e {batchFilename_abs}.err"

        # write out the batch header
        for line in config.batch_header:
            msub_str += f"\n{line}"

        msub_str += f"\n\ncd {testCase.dirnamefull}"

        # pull out options to construct the command line
        action = options.get("action")
        checkoption = options.get("checkoption")
        configFile = options.get("configFile")
        configOverride = options.get("configOverride")
        atsFlags = options.get("atsFlags")
        geos_atsPath = options.get("geos_atsPath")
        machine = options.get("machine")

        # construct the command line
        msub_str += f'\n{geos_atsPath} -a {action} -c {checkoption}'
        msub_str += f' -f {configFile} -N {minNodes:d} --machine={machine}'

        for key, value in configOverride.items():
            if key.startswith("batch"):
                continue

            msub_str += f' {key}="{value}"'

        for flag in atsFlags:
            msub_str += f' --ats "{flag}"'

        msub_str += f" batch_interactive=True {testCase.name}"

        # Write and close the file
        fc.write(msub_str)
        fc.close()

    def submitBatchScript(self, testname, batchFilename):

        options = AtsTest.getOptions()
        config = options.get("config", None)
        if config and config.batch_dryrun:
            return

        p = subprocess.Popen(["msub", batchFilename], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        out = p.communicate()[0]

        if p.returncode:
            raise RuntimeError(f"Error submitting {testname} to batch: {out}")

        try:
            jobid = int(out)
            logger.info(f" Submitting {testname}, jobid = {jobid:d}")
        except:
            err = f"Error submitting {testname} to batch: {out}"
            logger.error(err)
            raise RuntimeError(err)

"""Defines GeosATS scheduler for interactive jobs."""
import os
import re
import time
from geos_ats.configuration_record import config
from geos_ats.common_utilities import Log
from ats.log import log    # type: ignore[import]
from ats.atsut import PASSED, FAILED, CREATED, EXPECTED, TIMEDOUT    # type: ignore[import]
from ats.schedulers import StandardScheduler    # type: ignore[import]


class GeosAtsScheduler(StandardScheduler):
    """Custom scheduler for GeosATS"""
    name = "GeosATS Scheduler"

    def testEnded(self, test):
        """Manage scheduling and reporting tasks for a test that ended.
        Log result for every test but only show certain ones on the terminal.
        Prune group list if a group is finished.
        """
        echo = self.verbose or (test.status not in (PASSED, EXPECTED))
        g = test.group
        n = len(g)

        msg = f"{test.status} #{test.serialNumber} {test.name} {test.message}"
        if n > 1:
            msg += f" Group {g.number} #{test.groupSerialNumber} of {n}"
        log(msg, echo=echo)

        self.schedule(msg, time.asctime())
        self.removeBlock(test)
        if g.isFinished():
            g.recordOutput()
            if not hasattr(g, "retries"):
                g.retries = 0
            if test.status in [FAILED, TIMEDOUT] and g.retries < config.max_retry:
                with open(test.geos_atsTestCase.errname) as f:
                    erroutput = f.read()
                    if re.search(config.retry_err_regexp, erroutput):
                        f.close()
                        os.rename(test.geos_atsTestCase.errname, "%s.%d" % (test.geos_atsTestCase.errname, g.retries))
                        os.rename(test.geos_atsTestCase.outname, "%s.%d" % (test.geos_atsTestCase.outname, g.retries))
                        g.retries += 1
                        for t in g:
                            t.status = CREATED
                        Log(f"# retry test={test.geos_atsTestCase.name} ({g.retries}/{config.max_retry})")
                        return
            self.groups.remove(g)

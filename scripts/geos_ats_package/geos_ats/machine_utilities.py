# Common functions for geos_ats modifications to machine files

from geos_ats.configuration_record import config
import re
import os


def CheckForEarlyTimeOut(test, retval, fraction):
    if not retval:
        return retval, fraction
    else:
        if (config.max_retry > 0) and (config.retry_err_regexp != "") and (not hasattr(test, "checkstart")):
            sourceFile = getattr(test, "errname")
            if os.path.exists(sourceFile):
                test.checkstart = 1
                with open(sourceFile) as f:
                    erroutput = f.read()
                    if re.search(config.retry_err_regexp, erroutput):
                        return 1, fraction
        return 0, fraction

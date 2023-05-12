import ats    # type: ignore[import]
import os


################################################################################
#  Common functions available to the tests
#  (each must be registered via ats.manager.define()
################################################################################
def which(program):

    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    fpath, fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            path = path.strip('"')
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file

    return None


def getEnviron(name):
    import os
    try:
        return os.environ[name]
    except:
        return None


ats.manager.define(which=which)
ats.manager.define(getEnviron=getEnviron)

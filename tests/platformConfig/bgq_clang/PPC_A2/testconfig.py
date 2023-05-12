# Source parent platform configuration file, but only if this is the first configuration file read.
# If we got here otherwise, we assume that the parent config file sent us here.
if configDepth == 1:
    sourceParentConfig()
# Setup executable path with default path.  This is a required call and should be called before the baseline directory is set.
# machine.setGeosxPath( "build-bgqos_0_clang4.0.0-debug/bin" )

# Disable testing that either doesn't work on this platform or
# because we don't want those tests running.
config.stopcheck_enabled = 0
config.restartcheck_enabled = 0
config.plotcheck_enabled = 0
config.silocheck_enabled = 0
config.diff_enabled = 0
config.checkmessages_enabled = 0
config.visit_enabled = 0
config.visitexpression_enabled = 0
config.visitcompare_enabled = 0

# Default time limit
config.override_timelimit = 1    # This overrides timelimits specified in test specific ats files
config.default_timelimit = "2h"

### To run this on BGQ use

    ### aleats -N <no_procs> --sallocoptions "-t <time_limit> --exclusive" -f <path_to_bgq_specific_config_file>

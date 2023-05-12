# Source parent platform configuration file, but only if this is the first configuration file read.
# If we got here otherwise, we assume that the parent config file sent us here.
if configDepth == 1:
    sourceParentConfig()
# Setup executable path with default path.  This is a required call and should be called before the baseline directory is set.
# This is just a guess to what the eventual BLT windows path will be, but is not actually used yet.
# machine.setAle3dPath( "build-windows_intel18/x64/ParRelease" )
# Use toss3 baselines until we have windows baselines

# Disable checks that are not available yet for windows
config.restartcheck_enabled = False

config.silocheck_relative = 1.e-6
config.silocheck_absolute = 1e-6
config.stopcheck_time_relative = 1e-5
config.stopcheck_cycle_relative = 1e-5

config.curvecheck_relative = 1e-4
config.curvecheck_absolute = 1e-6

config.clean_on_pass = True

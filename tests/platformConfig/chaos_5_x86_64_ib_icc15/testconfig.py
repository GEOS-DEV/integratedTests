# Source parent platform configuration file, but only if this is the first configuration file read.
# If we got here otherwise, we assume that the parent config file sent us here.
if configDepth == 1:
    sourceParentConfig()
# Setup executable path with default path.  This is a required call and should be called before the baseline directory is set.
# machine.setGeosxPath("/g/g14/corbett5/geosx/build-toss_3_x86_64_ib-gcc@7.1.0-debug/bin")

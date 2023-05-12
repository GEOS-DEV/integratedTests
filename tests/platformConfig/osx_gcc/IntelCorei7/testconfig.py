# Source parent platform configuration file, but only if this is the first configuration file read.
# If we got here otherwise, we assume that the parent config file sent us here.
if configDepth == 1:
    sourceParentConfig()

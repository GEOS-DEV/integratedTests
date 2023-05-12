import sys
from . import machines

# Add the machines module to the ats.atsMachines submodule,
# So that ats can find our custom definitions at runtime
sys.modules['ats.atsMachines.machines'] = machines

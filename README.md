# integratedTests
Repository to hold the integrated testing framework code and files
Please do not use PR unless you are modifying source code.
Rebaseline commits should be merged directly with develop.


# Before running tests
GEOSX tests are built and run using python (>=3.7) and the geosxats package.
We highly recommend that you work within a virtual python environment to avoid package conflicts
(see https://docs.python.org/3/library/venv.html).

If you have defined an appropriate version of python in your cmake host config file (Python3_EXECUTABLE), then 
running 'make ats_environment' will install the required tools in that environment
(or a virtual environment derived from it) and then link the required scripts to the bin directory.


# Running tests
To run the integrated test system, move to the build directory for the version of python you
would like to test.
You can run the tests with the command 'make ats_run' or by executing the 'geos_ats.sh' script in the 'build/integratedTests' directory.
During the tests, their status will be shown on the terminal and in log files in the 'build/integratedTests/TestResults' directory.
The logs include a useful html overview ('build/integratedTests/TestResults/test_results.html') that can be opened in your browser of choice.

To cleanup old tests, you can run the command 'make ats_clean' or execute the 'geos_ats.sh' script with the '-a veryclean' argument.
Similarly, to rebaseline tests, you can run 'make ats_rebaseline' or 'make ats_rebaselinefailed'.

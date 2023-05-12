###############################################################################
Integrated Tests
###############################################################################

About
=================================
*integratedTests* is a submodule of *GEOSX* residing at the top level of the directory structure. It will run *GEOSX* with various *.xml* files and compare the output against a baseline.

Notes: you may need to install h5py_ and mpi4py_.

.. _h5py: http://docs.h5py.org/en/latest/build.html
.. _mpi4py: https://mpi4py.readthedocs.io/en/stable/

Do not forget to retrieve the baselines with the git LFS (large file storage) plugin.
If the content of your baselines is something like:

  [somebody@somewhere:/tmp]$ cat /path/to/GEOSX/integratedTests/tests/allTests/sedov/baselines/sedov_8/0to100_restart_000000100/rank_0000003.hdf5
  version https://git-lfs.github.com/spec/v1
  oid sha256:09bbe1e92968852cb915b971af35b0bba519fae7cf5934f3abc7b709ea76308c
  size 1761208

then it means that the LFS plugin was not activated. ``git lfs install`` and ``git lfs pull`` should help you fix this.


Structure
=================================
The *integratedTests* directory is composed of two main directories, *integratedTests/geosxats* and *integratedTests/tests/allTests*. The *integratedTests/geosxats* directory contains all the machinery involved in running the tests including the main executable *integratedTests/geosxats/geosxats*. The *integratedTests/tests/allTests* directory contains all the actual tests themselves, including the *.xml* files and the baselines.

.. code-block:: sh

  - integratedTests/
    - geosxats/
      - geosxats
  - update/
    - run/
      - sedov/
      - beamBending/
        - baselines/
          - beamBending/
            - <baseline-files>
        - beamBending.ats
        - beamBending.xml

Arguments
=================================
The program takes a number of arguments, the most important ones are

* The path to the *GEOSX* binary directory (*<build-dir>/bin*)
* --workingDir WORKINGDIR which sets the working (test) directory.
* -N NUMNODES specifies the number of nodes to use the default is the minimum number that the tests require.
* -a {veryclean, rebaseline, ...} specify a specific action, *veryclean* deletes all output files, and *rebaseline* lets you rebaseline all or some of the tests.
* -h prints out the *geosxats* help.

How to Run the Tests
=================================
To run all the tests from the top level *GEOSX* directory you would do

.. code-block:: sh

  integratedTests/geosxats/geosxats <build-path>/bin --workingDir integratedTests/tests/allTests


To run only the *sedov* tests you would do

.. code-block:: sh

  integratedTests/geosxats/geosxats <build-path>/bin --workingDir integratedTests/tests/allTests/sedov

However if you want to run all the tests there's an easier way. In the build directory there's a symbolic link to *integratedTests/tests/allTests* called *integratedTests* and a bash script *geosxats.sh* that wraps *integratedTests/geosxats/geosxats* and passes it the path to the binary directory and the *integratedTests/tests/allTests* directory along with any other command line arguments. To run this script do the following

.. code-block:: sh

  cd <build-path>
  ./geosxats.sh

If the script or symbolic link is not present you will need to reconfigure by running the `config-build.py script.

When the program has finished running you will see something like this

.. code-block:: sh

   FAIL RUN : 0

   UNEXPECTEDPASS : 0

   FAIL RUN (OPTIONAL STEP) : 0

   FAIL CHECK : 1
   (  beamBending  )

   FAIL CHECK (MINOR) : 0

   TIMEOUT : 0

   NOT RUN : 0

   INPROGRESS : 0

   FILTERED : 0

   RUNNING : 0

   PASSED : 3
   (  sedov 2D_100x100_incompr_linear 2D_100x100_incompr_linear_faceBC  )

   EXPECTEDFAIL : 0

   SKIPPED : 0

   BATCHED : 0

   NOT BUILT : 0

    TOTAL TIME           : 0:01:13
    TOTAL PROCESSOR-TIME : 0:02:13
    AVAIL PROCESSOR-TIME : 1:28:26
    RESOURCE UTILIZATION :  2.51%

    LONGEST RUNNING TESTS:
       0:01:13 sedov
       0:00:23 2D_100x100_incompr_linear_faceBC
       0:00:22 2D_100x100_incompr_linear
       0:00:14 beamBending

       Status     :  TestCase    :  Directory               :  Elapsed :  Resources :  TestStep
       ---------- :  ----------- :  ----------------------- :  ------- :  --------- :  ------------
       FAIL CHECK :  beamBending :  beamBending/beamBending :  0:00:14 :  0:00:14   :  restartcheck
       ---------- :  ----------- :  ----------------------- :  ------- :  --------- :  ------------

  Generating HTML documentation files (running 'atddoc')...
    Failed to create HTML documentation in /g/g14/corbett5/geosx/mirror/integratedTests/update/doc

  Undocumented test problems:
  beamBending 2D_100x100_incompr_linear 2D_100x100_incompr_linear_faceBC sedov

Ignore the error regarding the failure to create a HTML documentation file and the warning about the undocumented test problems. The only important thing is if any of the tests aren't in the *PASSED* category. For a nice summary of the results open the *test_results.html* file in the *geosxats* working directory.

When running the tests multiple times in a row, only tests that failed to pass will run. If you would like to run all the tests again call

.. code-block:: sh

  ./geosxats.sh -a veryclean

which will delete all the generated files. Furthermore these generated files are not ignored by *git*, so until you run *veryclean* the *integratedTests* repo will register changes.

**Note**: On some development machines geosxats won't run parallel tests by default (e.g. on an linux laptop or workstation), and as a result many tests will be skipped.  We highly recommend running tests on an MPI-aware platform.

Output Created By a Test
=================================
Since the *beamBending* test failed let's look at it's output. The output for the *beamBending* test is stored in *integratedTests/tests/allTests/beamBending/beamBending* directory. In addition to any files *GEOSX* itself creates you will find

* *beamBending.data* which holds all of the standard output of the various steps.
* *beamBending.err* which holds all of the standard error output of the various steps.
* *beamBending.geosx.out* which holds all of the standard output for only the *geosx* step.
* *beamBending_restart_000000003.restartcheck* which holds all of the standard output for only the *restartcheck* step.
* *beamBending_restart_000000003_diff.hdf5* which mimmics the hierarchy of the restart file and has links to the differing data datasets.

The RestartCheck File
---------------------------------
Currently the only manner of check that we support is a restart check, this check compares a restart file output at the end of a run against a baseline. The program that does the diff
is *integratedTests/geosxats/helpers/restartcheck.py*. The program compares the two restart files and writes out a *.restart_check* file with the results, as well as exiting with an error code if the files compare differently.

This program takes a number of arguments
and they are as follows

* Regex specifying the restart file. If the regex matches multiple files the one with the greater string is selected. For example *restart_100.hdf5* wins out over *restart_088.hdf5*.
* Regex specifying the baseline file.
* -r The relative tolerance for floating point comparison, the default is 0.0.
* -a The absolute tolerance for floating point comparison, the default is 0.0.
* -e A list of regex expressions that match paths in the restart file tree to exclude from comparison. The default is [.*/commandLine].
* -w Force warnings to be treated as errors, default is false.
* -s Suppress output to stdout, default is False.

The *.restart_check* file itself starts off with a summary of the arguments. The program then compares the *.root* files and if they are similar proceeds to compare all the *.hdf5* data files.

If the program encounters any differences it will spit out an error message. An error message for scalar values looks as follows

.. code-block:: sh

  Error: /datagroup_0000000/sidre/external/ProblemManager/domain/ConstitutiveManager/shale/YoungsModulus
    Scalar values of types float64 and float64 differ: 22500000000.0, 10000022399.9.

Where the first value is the value in the test's restart file and the second is the value in the baseline.

An example of an error message for arrays is

.. code-block:: sh

  Error: /datagroup_0000000/sidre/external/ProblemManager/domain/MeshBodies/mesh1/Level0/nodeManager/TotalDisplacement
    Arrays of types float64 and float64 have 1836 values of which 1200 have differing values.
    Statistics of the differences greater than 0:
      max_index = (1834,), max = 2.47390764755, mean = 0.514503482629, std = 0.70212888881

This means that the max absolute difference is 2.47 which occurs at value 1834. Of the values that are not equal the mean absolute difference is 0.514 and the standard deviation of the absolute difference is 0.702.

When the tolerances are non zero the comparison is a bit more complicated. From the *FileComparison.compareFloatArrays* method documentation

.. code-block:: sh

  Entries x1 and x2 are  considered equal iff
      |x1 - x2| <= ATOL or |x1 - x2| <= RTOL * |x2|.
  To measure the degree of difference a scaling factor q is introduced. The goal is now to minimize q such that
      |x1 - x2| <= ATOL * q or |x1 - x2| <= RTOL * |x2| * q.
  If RTOL * |x2| > ATOL
      q = |x1 - x2| / (RTOL * |x2|)
  else
      q = |x1 - x2| / ATOL.
  If the maximum value of q over all the entries is greater than 1.0 then the arrays are considered different and an error message is produced.

An sample error message is

.. code-block:: sh

  Error: /datagroup_0000000/sidre/external/ProblemManager/domain/MeshBodies/mesh1/Level0/nodeManager/TotalDisplacement
    Arrays of types float64 and float64 have 1836 values of which 1200 fail both the relative and absolute tests.
      Max absolute difference is at index (1834,): value = 2.07474948094, base_value = 4.54865712848
      Max relative difference is at index (67,): value = 0.00215842135281, base_value = 0.00591771127792
    Statistics of the q values greater than 1.0 defined by the absolute tolerance: N = 1200
      max = 16492717650.3, mean = 3430023217.52, std = 4680859258.74
    Statistics of the q values greater than 1.0 defined by the relative tolerance: N = 0

The restart check step can be run in parallel using mpi via

.. code-block:: sh

  mpirun -n NUM_PROCESSES python -m mpi4py restartcheck.py ...

In this case rank zero reads in the restart root file and then each rank parses a subset of the data files creating a *.$RANK.restartcheck* file. Rank zero then merges the output from each of these files into the main *.restartcheck* file and prints it to standard output.

The *.diff.hdf5* File
---------------------------------
Each error generated in the *restartcheck* step creates a group with three children in the *_diff.df5* file. For example the error given above will generate a hdf5 group

.. code-block:: sh

  /FILENAME/datagroup_0000000/sidre/external/ProblemManager/domain/MeshBodies/mesh1/Level0/nodeManager/TotalDisplacement

with datasets *baseline*, *run* and *message* where *FILENAME* is the name of the restart data file being compared. The *message* dataset contains a copy of the error message while *baseline* is a symbolic link to the baseline dataset and *run* is a sumbolic link to the dataset genereated by the run. This allows for easy access to the raw data underlying the diff without data duplication. For example if you want to extract the datasets into python you could do this:

.. code-block:: python

  import h5py
  file_path = "beamBending_restart_000000003_diff.hdf5"
  path_to_data = "/beamBending_restart_000000011_0000000.hdf5/datagroup_0000000/sidre/external/ProblemManager/domain/MeshBodies/mesh1/Level0/nodeManager/TotalDisplacement"
  f = h5py.File("file_path", "r")
  error_message = f["path_to_data/message"]
  run_data = f["path_to_data/run"][:]
  baseline_data = f["path_to_data/baseline"][:]

  # Now run_data and baseline_data are numpy arrays that you may use as you see fit.
  rtol = 1e-10
  atol = 1e-15
  absolute_diff = np.abs(run_data - baseline_data) < atol
  hybrid_diff = np.close(run_data, baseline_data, rtol, atol)

When run in parallel each rank creates a *.$RANK.diff.hdf5* file which contains the diff of each data file processed by that rank.

The *.ats* File
=================================
The *.ats* file is a python script that describes the *TestCases* to run and steps for each *TestCase*. Each *.ats* file needs to have at least one *TestCase* and each *TestCase* needs to have at least one step.

A simple example is the *beamBending.ats* file

.. code-block:: python

  TestCase(
    name = "beamBending",
    desc = "Tests beam bending.",
    label = "auto",
    owner = "Ben Corbett",
    independent = True,
    steps = (geosx(deck="beamBending.xml"),)

This creates a *TestCase* called beamBending with a single step that runs *GEOSX* with the *beamBending.xml* input file, a *restartcheck* step automatically follows each *geosx* step. So this file describes a test that runs the *beamBending* problem and compares the restart file against the baseline.

A slightly more complicated example is the *singlePhaseFlow.ats* file.

.. code-block:: python

  decks = ("2D_100x100_incompr_linear",
           "2D_100x100_incompr_linear_faceBC")
  descriptions = ("Testing the single phase incompressible flow solver.",
                  "Testing the single phase incompressible flow solver with face boundary conditions.")

  for i in range(len(decks)):
      deck = decks[i]
      description = descriptions[i]
      TestCase(
          name = deck,
          desc = description,
          label = "auto",
          owner = "Ben Corbett",
          independent = True,
          steps = (geosx(deck=deck + ".xml"),)
      )

This creates two *TestCases* each of which runs a different problem. The *independent* parameter means that the two *TestCases* can be executed independently of each other. When a *TestCase* executes it uses it's name to create a directory where all the output files are stored so if you have multiple *TestCases* in an *.ats* file it's imperative that they have unique names.

Finally there's the *sedov.ats* file which tests that starting from a restart file has no impact on the final solution.

.. code-block:: python

  import os

  TestCase(
      name = "sedov",
      desc = "Test the basic sedov problem and restart capabilities.",
      label = "auto",
      owner = "Ben Corbett",
      independent = True,
      steps = (geosx(deck="sedov.xml",
                     name="0to100"),
               geosx(deck="sedov.xml",
                     name="50to100",
                     restart_file=os.path.join(testcase_name, "0to100_restart_000000050.root"),
                     baseline_pattern="0to100_restart_[0-9]+\.root",
                     allow_rebaseline=False)
              )
  )

This creates a single *TestCase* That executes *GEOSX* twice. The first step does 100 time steps followed by a *restartcheck* step. The second *geosx* step executes the original 100 time step *xml* file but restarts using the restart file output half way through the first run. Each *geosx* step gets its name from the *xml* file, but this can be overridden by the *name* parameter Furthermore the default behavior is to look for a baseline in the *baselines/<TestCaseName>* directory named *TestStepName_restart_[0-9]+\.root*, however the second step overrides this to instead compare against the "0to100" baseline. Because of this it does not allow rebaselining.

You can pass parameters to the *restartcheck* step in a dictionary passed as an argument to the *geosx* step. For example to set the tolerance you would do

.. code-block:: python

  restartcheck_params={}
  restartcheck_params["atol"] = 1.5E-10
  restartcheck_params["rtol"] = 1E-12

  TestCase(
      name = "sedov",
      desc = "Test the basic sedov problem and restart capabilities.",
      label = "auto",
      owner = "Ben Corbett",
      independent = True,
      steps = (geosx(deck="sedov.xml",
                     name="0to100",
                     restartcheck_params=restartcheck_params))
  )

For more info see *integratedTests/geosxats/GeosxAtsTestSteps.py* and *integratedTests/geosxats/GeosxAtsTestCase.py*

Adding a Test
=================================
To add a new test create a new folder in the `integratedTests/tests/allTests* directory. At a minimum this new folder needs to include an *.ats* file. Using the beamBending example, after creating *beamBending.ats* the directory should look like

.. code-block:: sh

  - integratedTests/tests/allTests/beamBending/
    - beamBending.ats
    - beamBending.xml

At this point you should run the test. Assuming the *geosx* step is successful the *restartcheck* step will fail because there are no baselines. At this point the directory should look like

.. code-block:: sh

  - integratedTests/tests/allTests/beamBending/
    - beamBending/
      - <geosx files>...
      - <ats files>...
    - beamBending.ats
    - beamBending.xml
    - <ats files>...

Now run

.. code-block:: sh

  ./geosxats.sh -a rebaseline

and rebaseline your test. Finally run the test a second time and confirm that it passes. Note that unless you disable the restartcheck step you will need to output a restart file. Although not strictly necessary it is best to put the *xml* file in the main *GEOSX* repo and create an relative symbolic link to it in the test directory.

Rebaselining Tests
=================================
Occasionally it is necessary to rebaseline one or more tests due to feature changes in the code.  We suggest the following workflow:

In the GEOSX repository, create a branch with your modifications:

.. code-block:: sh

  cd <GEOSX-path>
  git checkout -b user/feature/newFeature

Add your changes, confirm it passes all the continuous integration tests, and get approval for a pull request.

Now, confirm that your integratedTests submodule is up to date:

.. code-block:: sh

  git submodule

This will list the commit hash for all submodules.  Check that the integrated tests submodule is on develop and that the commit hash is the same one as the latest GEOSX develop branch points to.  If you have somehow fallen behind, go into integratedTests, checkout develop, and pull.

Now go to the integratedTests submodule and check out a branch for your new baselines.  It is a good idea to name branch something similar to your feature branch so it is obvious the two branches are related.

.. code-block:: sh

  cd <integratedTests-path>
  git checkout -b user/rebase/newFeature

Go back to your GEOSX build directory and run the integrated tests

.. code-block:: sh

  cd <build-path>
  ./geosxats.sh

Confirm that any tests that fail need to be **legitimately** rebaselined.  Arbitrarily changing baselines defeats the purpose of the integrated tests.  In your PR discussion, please identify which tests will change and any unusual behavior.

We can now actually rebaseline the tests

.. code-block:: sh

  ./geosxats -a rebaseline

You’ll be prompted to confirm whether rebaselining is required for every integrated test, one at a time, via a ``[y/n]`` prompt. Make sure to only answer ``y`` to the tests that you actually want to rebaseline, otherwise correct baselines for already passing tests will still be updated and bloat your pull request and repository size.

Confirm that the rebaselines are working as expected, by cleaning the test dir and re-running the checks:

.. code-block:: sh

  ./geosxats -a veryclean
  ./geosxats


At this point you should pass all the integratedTests.  Clean the branch and commit your changes to the baseline branch.

.. code-block:: sh

  ./geosxats -a veryclean
  cd <integratedTests-path>
  git status
  git add *
  git commit -m "Updating baselines"
  git push

If you haven't already set up your local branch to point to a remote branch, you will be prompted to do so when attempting to push.  You will then want to create a pull request in the integratedTests repository. Once you have merge approval for your PR, you can merge your rebaseline branch into ``integratedTests/develop``.

At this point, you need to get your GEOSX ``user/feature/newFeature`` branch pointing to the head commit on ``integratedTests/develop``.  We will check out the latest version of the test repo and add it to our feature branch:

.. code-block:: sh

  cd <integratedTests-path>
  git checkout develop
  git pull

  cd <GEOSX-path>
  git add integratedTests
  git commit -m "Updating integratedTests hash"
  git push

You may also want to run ``git submodule`` to confirm the submodule hash is what we expect, the last commit in ``integratedTests/develop``. Once your feature branch passes all Continuous Integration tests, it can be successfully merged into ``GEOSX/develop``.

Tips
----
**Parallel Tests**: On some development machines geosxats won't run parallel tests by default (e.g. on an linux laptop or workstation), and as a result many baselines will be skipped.  We highly recommend running tests and rebaselining on an MPI-aware platform.

**Filtering Checks**: A common reason for rebaselining is that you have changed the name of an XML node in the input files.  While the baselines may be numerically identical, the restarts will fail because they contain different node names.  In this situation, it can be useful to add a filter to the restart check script.  If you open ``integratedTests/geosxats/helpers/restartcheck.py``, at line 12 you will find a line:

.. code-block:: python

  EXCLUDE_DEFAULT = [".*/commandLine", ".*/schema$", ".*/globalToLocalMap"]

This variable contains paths to be excluded from the restart checks.  For example, we recently renamed the XML block ``<SystemSolverParameters/>`` to ``<LinearSolverParameters/>``.  In doing so, we had to rebaseline every test even though we expected no numerical differences.  Temporarily adding the following filter helped us rapidly check this was indeed the case:

.. code-block:: python

  EXCLUDE_DEFAULT = [".*/SystemSolverParameters", ".*/LinearSolverParameters", ".*/commandLine", ".*/schema$", ".*/globalToLocalMap"]

You may find this approach useful for quickly filtering tests to distinguish between expected and unexpected failures.

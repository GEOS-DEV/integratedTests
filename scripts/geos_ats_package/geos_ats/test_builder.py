import os
from .test_steps import geos
from .test_case import TestCase

def generate_geos_tests_1( decks, restartcheck_params ):
    """ 
    """
    for deck, description, partitions, restart, num_steps in decks:
        for partition in partitions:
            nx = partition[0]
            ny = partition[1]
            nz = partition[2]
            N = nx * ny * nz

            testcase_name = "%s_%02d" % (deck, N)
            base_name = "0to%d" % num_steps

            steps = (geos(deck=deck + ".xml",
                        name=base_name,
                        np=N,
                        ngpu=N,
                        x_partitions=nx,
                        y_partitions=ny,
                        z_partitions=nz,
                        restartcheck_params=restartcheck_params), )

            if restart > 0:
                steps += (geos(deck=deck + ".xml",
                            name="%dto%d" % (restart, num_steps),
                            np=N,
                            ngpu=N,
                            x_partitions=nx,
                            y_partitions=ny,
                            z_partitions=nz,
                            restart_file=os.path.join(testcase_name, "%s_restart_%09d" % (base_name, restart)),
                            baseline_pattern="%s_restart_[0-9]+\.root" % base_name,
                            allow_rebaseline=False,
                            restartcheck_params=restartcheck_params), )

            TestCase(name=testcase_name,
                     desc=description,
                     label="auto",
                     owner="Sergey Klevtsov",
                     independent=True,
                     steps=steps)
            
def generate_geos_tests_2(decks, restartcheck_params, curvecheck_params_base):
    """
    """
    for deck in decks:
        # deck, description, partitions, restart_step, num_steps
        for partition in deck["partitions"]:
            nx = partition[0]
            ny = partition[1]
            nz = partition[2]
            N = nx * ny * nz
            testcase_name = "{}_{:02d}".format(deck["name"], N)
            base_name = "0to{:d}".format(deck["check_step"])

            curvecheck_params = None
            if ("aperture_curve_method" in deck) and ("pressure_curve_method" in deck):
                curvecheck_params = curvecheck_params_base.copy()
                curvecheck_params["script_instructions"][0][1] = deck["aperture_curve_method"]
                curvecheck_params["script_instructions"][1][1] = deck["pressure_curve_method"]

            if (curvecheck_params is not None) and ("tolerance" in deck):
                curvecheck_params["tolerance"] = deck["tolerance"]

            steps = [geos(deck="{}.xml".format(deck["name"]),
                        name=base_name,
                        np=N,
                        ngpu=N,
                        x_partitions=nx,
                        y_partitions=ny,
                        z_partitions=nz,
                        restartcheck_params=restartcheck_params,
                        curvecheck_params=curvecheck_params)]

            if deck["restart_step"] > 0:
                steps.append(geos(deck="{}.xml".format(deck["name"]),
                            name="{:d}to{:d}".format(deck["restart_step"], deck["check_step"]),
                            np=N,
                            ngpu=N,
                            x_partitions=nx,
                            y_partitions=ny,
                            z_partitions=nz,
                            restart_file=os.path.join(testcase_name, "{}_restart_{:09d}".format(base_name, deck["restart_step"])),
                            baseline_pattern=f"{base_name}_restart_[0-9]+\.root",
                            allow_rebaseline=False,
                            restartcheck_params=restartcheck_params))

            tmp = TestCase(name=testcase_name,
                           desc=deck["description"],
                           label="auto",
                           owner="GEOS team",
                           independent=True,
                           steps=steps)

def generate_geos_tests_3( decks, partitions, restartcheck_params ):

    for nx, ny, nz in partitions:
        N = nx * ny * nz

        testcase_name = "SurfaceGenerator_%02d" % N
        TestCase(name=testcase_name,
                desc="Test the basic surface generator problem and restart capabilities.",
                label="auto",
                owner="R Settgast",
                independent=True,
                steps=(geos(deck="SurfaceGenerator.xml",
                            name="0to3",
                            np=N,
                            ngpu=N,
                            x_partitions=nx,
                            y_partitions=ny,
                            z_partitions=nz,
                            restartcheck_params=restartcheck_params),
                        geos(deck="SurfaceGenerator.xml",
                            name="2to3",
                            np=N,
                            ngpu=N,
                            x_partitions=nx,
                            y_partitions=ny,
                            z_partitions=nz,
                            restart_file=os.path.join(testcase_name, "0to3_restart_000000001"),
                            baseline_pattern="0to3_restart_[0-9]+\.root",
                            allow_rebaseline=False,
                            restartcheck_params=restartcheck_params)))

    for deck, description in decks:
        for partition in partitions:
            nx = partition[0]
            ny = partition[1]
            nz = partition[2]
            N = nx * ny * nz

            testcase_name = "%s_%02d" % (deck, N)

            TestCase(name=testcase_name,
                    desc=description,
                    label="auto",
                    owner="H Wu",
                    independent=True,
                    steps=(geos(deck=deck + ".xml",
                                name=deck,
                                np=N,
                                ngpu=N,
                                x_partitions=nx,
                                y_partitions=ny,
                                z_partitions=nz,
                                restartcheck_params=restartcheck_params), ))
            
def generate_geos_tests_4( partitions, restartcheck_params, curvecheck_params ):
    for partition in partitions:
        nx = partition[0]
        ny = partition[1]
        nz = partition[2]
        N = nx * ny * nz

        TestCase(name="beamBending_%02d" % N,
                desc="Tests beam bending on %d ranks." % N,
                label="auto",
                owner="Ben Corbett",
                independent=True,
                steps=(geos(deck="beamBending.xml",
                            name="beamBending",
                            np=N,
                            ngpu=N,
                            x_partitions=nx,
                            y_partitions=ny,
                            z_partitions=nz,
                            restartcheck_params=restartcheck_params,
                            curvecheck_params=curvecheck_params), ))

        TestCase(name="beamBending_vem_%02d" % N,
                desc="Tests beam bending on %d ranks applying Virtual Elements." % N,
                label="auto",
                owner="Andrea Borio",
                independent=True,
                steps=(geos(deck="beamBending_vem_smoke.xml",
                            name="beamBending_vem",
                            np=N,
                            ngpu=N,
                            x_partitions=nx,
                            y_partitions=ny,
                            z_partitions=nz,
                            restartcheck_params=restartcheck_params), ))

        TestCase(name="beamBending_hybridHexPrism_%02d" % N,
                desc="Tests beam bending on %d ranks on general polyhedral mesh." % N,
                label="auto",
                owner="Andrea Borio",
                independent=True,
                steps=(geos(deck="beamBending_hybridHexPrism_smoke.xml",
                            name="beamBending_hybridHexPrism",
                            np=N,
                            ngpu=N,
                            x_partitions=nx,
                            y_partitions=ny,
                            z_partitions=nz,
                            restartcheck_params=restartcheck_params), ))



def generate_geos_tests_5( partitions, restartcheck_params, curvecheck_params ):
    for nx, ny, nz in partitions:
        N = nx * ny * nz

        testcase_name = "sedov_%d" % N

        TestCase(name=testcase_name,
                desc="Test the basic sedov problem and restart capabilities on %d ranks." % N,
                label="auto",
                owner="Ben Corbett",
                independent=True,
                steps=(geos(deck="sedov.xml",
                            np=N,
                            ngpu=N,
                            x_partitions=nx,
                            y_partitions=ny,
                            z_partitions=nz,
                            name="0to100",
                            restartcheck_params=restartcheck_params,
                            curvecheck_params=curvecheck_params,
                            ),
                        geos(deck="sedov.xml",
                            np=N,
                            ngpu=N,
                            x_partitions=nx,
                            y_partitions=ny,
                            z_partitions=nz,
                            name="50to100",
                            restart_file=os.path.join(testcase_name, "0to100_restart_000000050"),
                            baseline_pattern="0to100_restart_[0-9]+\.root",
                            allow_rebaseline=False,
                            restartcheck_params=restartcheck_params)))

def generate_geos_tests_6( partitions, restartcheck_params ):
    for nx, ny, nz in partitions:
        N = nx * ny * nz

        testcase_name = "gravity_%02d" % N
        TestCase(name=testcase_name,
                desc="Test the gravity application in solid mechanics solver  on %d ranks." % N,
                label="auto",
                owner="RRS",
                independent=True,
                steps=(geos(deck="gravity.xml",
                            name="0to2",
                            np=N,
                            ngpu=N,
                            x_partitions=nx,
                            y_partitions=ny,
                            z_partitions=nz,
                            restartcheck_params=restartcheck_params),
                        geos(deck="gravity.xml",
                            name="1to2",
                            np=N,
                            ngpu=N,
                            x_partitions=nx,
                            y_partitions=ny,
                            z_partitions=nz,
                            restart_file=os.path.join(testcase_name, "0to2_restart_000000001"),
                            baseline_pattern="0to2_restart_[0-9]+\.root",
                            allow_rebaseline=False,
                            restartcheck_params=restartcheck_params)))


def generate_geos_tests_7( partitions, restartcheck_params ):
    for nx, ny, nz in partitions:
        N = nx * ny * nz

        testcase_name = "plasticCubeReset_%02d" % N
        TestCase(name=testcase_name,
                desc="Test the initialization step of for solid mechanics on %d ranks." % N,
                label="auto",
                owner="RRS",
                independent=True,
                steps=(geos(deck="plasticCubeReset.xml",
                            name="0to7",
                            np=N,
                            ngpu=N,
                            x_partitions=nx,
                            y_partitions=ny,
                            z_partitions=nz,
                            restartcheck_params=restartcheck_params),
                        geos(deck="plasticCubeReset.xml",
                            name="4to7",
                            np=N,
                            ngpu=N,
                            x_partitions=nx,
                            y_partitions=ny,
                            z_partitions=nz,
                            restart_file=os.path.join(testcase_name, "0to7_restart_000000001"),
                            baseline_pattern="0to7_restart_[0-9]+\.root",
                            allow_rebaseline=False,
                            restartcheck_params=restartcheck_params)))

def generate_geos_tests_8( partitions, restartcheck_params ):
    for nx, ny, nz in partitions:
        N = nx * ny * nz

        testcase_name = "SSLE-sedov_%02d" % N
        TestCase(name=testcase_name,
                desc="Test the small strain linear elastic solver on %d ranks." % N,
                label="auto",
                owner="RRS",
                independent=True,
                steps=(geos(deck="SSLE-sedov.xml",
                            name="0to100",
                            np=N,
                            ngpu=N,
                            x_partitions=nx,
                            y_partitions=ny,
                            z_partitions=nz,
                            restartcheck_params=restartcheck_params),
                        geos(deck="SSLE-sedov.xml",
                            name="50to100",
                            np=N,
                            ngpu=N,
                            x_partitions=nx,
                            y_partitions=ny,
                            z_partitions=nz,
                            restart_file=os.path.join(testcase_name, "0to100_restart_000000050"),
                            baseline_pattern="0to100_restart_[0-9]+\.root",
                            allow_rebaseline=False,
                            restartcheck_params=restartcheck_params)))


class Description(object):

    def __init__(self, description_builder, label, owner, isIndependent):
        """
        The ATS description of the test case for poro-elastic coupling.

        description_builder: callable
            A callable taking the partition tuple in argument and returning the TestCase description.
        label: str
            The label of the TestCase
        owner: str
            The owner of the TestCase
        isIndependent: boolean
            Is the TestCase independent from other cases?
        """
        self.description_builder = description_builder
        self.label = label
        self.owner = owner
        self.isIndependent = isIndependent


def _n_ranks(partition):
    """
    Returns the number of ranks for a given MPI partitioning.

    partition: iterable
        The MPI cartesian partitioning.
        (x, y, z) ranks are supposed to be integers (or None which will be considered as 1).
    """
    result = 1
    # I wanted to do `filter( None, partition )` with the `filter` builtin function
    # but it has been rewritten by ATS. This is sooo wrong :(
    for n in partition:
        result *= n if n else 1
    return result


def _build_poro_elastic_coupling_case(deck, cycles, partitions, description, restartcheck_params, test_name_builder):
    """
    Generic function that build the poro-elastic cases.
    A first run is done and a second takes an intermediate timestep to validate the restart.

    deck: str
        XML input file
    cycles: pair of integers
        The (intermediate_cycle, last_cycle). First being the restart initial timestep.
        The second being the last simulated cycle.
    partitions: Iterable of length-3 iterables
        The (x, y, z) parallel partitioning.
        `None` can be provided when nothing has to be done in the considered direction.
    description: Description
        Description of the TestCase
    restartcheck_params: dict
        Restart validation parameters (relative or absolute tolerance mainly).
    test_name_builder: callable
        A callable taking the partition tuple in argument and returning the test name.
    """
    for partition in partitions:
        nx, ny, nz = partition
        N = _n_ranks(partition)

        test_name = test_name_builder(partition)

        steps = []

        main_name = "main_run"

        # The simulation will generate data for two cycles
        intermediate_cycle, last_cycle = cycles
        # We only validate for the final result.
        # A restart simulation is run and meant to provide the same final result too.
        main_baseline_pattern = "%s_restart_%09d\.root" % (main_name, last_cycle)
        # FIXME Implement a geos::getRestartFile( name, cycle )!

        main_step = geos(deck=deck,
                         name=main_name,
                         np=N,
                         ngpu=N,
                         x_partitions=nx,
                         y_partitions=ny,
                         z_partitions=nz,
                         baseline_pattern=main_baseline_pattern,
                         restartcheck_params=restartcheck_params)

        steps.append(main_step)

        restartcheck_name = "restartcheck_run_from_%d_to_%d" % (intermediate_cycle, last_cycle)
        restartcheck_file = os.path.join(test_name, "%s_restart_%09d" % (main_name, intermediate_cycle))
        # The restart check baseline pattern is the same as the main baseline pattern
        # because we want to validate the same output
        restartcheck_baseline_pattern = main_baseline_pattern
        restart_step = geos(deck=deck,
                            name=restartcheck_name,
                            np=N,
                            ngpu=N,
                            x_partitions=nx,
                            y_partitions=ny,
                            z_partitions=nz,
                            restart_file=restartcheck_file,
                            baseline_pattern=restartcheck_baseline_pattern,
                            allow_rebaseline=False,
                            restartcheck_params=restartcheck_params)

        steps.append(restart_step)

        TestCase(name=test_name,
                 desc=description.description_builder(partition),
                 label=description.label,
                 owner=description.owner,
                 independent=description.isIndependent,
                 steps=steps)


def _build_Terzaghi_cases():
    description = Description(lambda part: "Terzaghi's 1D Consolidation on %d ranks" % _n_ranks(part), "auto",
                              "Nicola Castelletto", True)
    restartcheck_params = {"atol": 1.0e-8, "rtol": 2.0e-8}
    _build_poro_elastic_coupling_case("PoroElastic_Terzaghi_FIM.xml", (50, 91),
                                      ((1, None, None), (2, None, None), (7, None, None)), description,
                                      restartcheck_params,
                                      lambda part: "PoroElastic_Terzaghi_FIM_%02d" % _n_ranks(part))


def _build_Mandel_fim_cases():
    description = Description(lambda part: "Mandel's 2D Consolidation on %d ranks" % _n_ranks(part), "auto",
                              "Nicola Castelletto, Jian Huang", True)
    restartcheck_params = {"atol": 1.0e-8, "rtol": 2.0e-8}
    _build_poro_elastic_coupling_case("PoroElastic_Mandel_smoke_fim.xml", (2, 4), ((1, 1, 1), (3, 1, 1), (3, 1, 2)),
                                      description, restartcheck_params,
                                      lambda part: "PoroElastic_Mandel_smoke_fim_%s-%s-%s" % part)

def _build_Mandel_sequential_cases():
    description = Description(lambda part: "Sequential Mandel's 2D Consolidation on %d ranks" % _n_ranks(part), "auto",
                              "Nicola Castelletto, Jian Huang", True)
    restartcheck_params = {"atol": 1.0e-8, "rtol": 2.0e-8}
    _build_poro_elastic_coupling_case("PoroElastic_Mandel_smoke_sequential.xml", (2, 4), ((1, 1, 1), (3, 1, 1), (3, 1, 2)),
                                      description, restartcheck_params,
                                      lambda part: "PoroElastic_Mandel_smoke_sequential_%s-%s-%s" % part)

def _build_Mandel_prism6_cases():
    description = Description(
        lambda part: "Mandel's 2D Consolidation using VEM-MFD on a prism mesh on %d ranks" % _n_ranks(part), "auto",
        "Andrea Borio, Francois Hamon", True)
    restartcheck_params = {"atol": 1.0e-8, "rtol": 2.0e-8}
    _build_poro_elastic_coupling_case("PoroElastic_Mandel_prism6_smoke.xml", (2, 4), ((1, 1, 1), ), description,
                                      restartcheck_params,
                                      lambda part: "PoroElastic_Mandel_prism6_smoke_%s-%s-%s" % part)


def _build_Deadoil_fim_cases():
    description = Description(lambda part: "Deadoil 3 phase poroelastic case on %d ranks" % _n_ranks(part), "auto",
                              "N. Castelletto & M. Cusini", True)
    restartcheck_params = {"atol": 1.0e-8, "rtol": 2.0e-8}
    _build_poro_elastic_coupling_case("PoroElastic_deadoil_3ph_baker_2d_fim.xml", (0, 15), ((1, 1, 1), (2, 1, 2)),
                                      description, restartcheck_params,
                                      lambda part: "PoroElastic_deadoil_3ph_baker_2d_fim_%s-%s-%s" % part)

def _build_Deadoil_sequential_cases():
    description = Description(lambda part: "Sequential Deadoil 3 phase poroelastic case on %d ranks" % _n_ranks(part), "auto",
                              "N. Castelletto & M. Cusini", True)
    restartcheck_params = {"atol": 1.0e-8, "rtol": 2.0e-8}
    _build_poro_elastic_coupling_case("PoroElastic_deadoil_3ph_baker_2d_sequential.xml", (0, 15), ((1, 1, 1), (2, 1, 2)),
                                      description, restartcheck_params,
                                      lambda part: "PoroElastic_deadoil_3ph_baker_2d_sequential_%s-%s-%s" % part)

def _build_PoroElasticWell_cases():
    description = Description(lambda part: "PoroElastic wellbore problem on %d ranks" % _n_ranks(part), "auto",
                              "Jian Huang", True)
    restartcheck_params = {"atol": 1.0e-8, "rtol": 2.0e-8}
    _build_poro_elastic_coupling_case("PoroElastic_Wellbore_smoke.xml", (2, 8), ((1, 1, 1), (2, 2, 1)), description,
                                      restartcheck_params, lambda part: "PoroElastic_Wellbore_smoke_%s-%s-%s" % part)


def _build_PoroDruckerPragerWell_cases():
    description = Description(lambda part: "PoroDruckerPrager wellbore problem on %d ranks" % _n_ranks(part), "auto",
                              "Jian Huang", True)
    restartcheck_params = {"atol": 1.0e-8, "rtol": 2.0e-8}
    _build_poro_elastic_coupling_case("PoroDruckerPrager_Wellbore_smoke.xml", (2, 8), ((1, 1, 1), (2, 2, 1)),
                                      description, restartcheck_params,
                                      lambda part: "PoroDruckerPrager_Wellbore_smoke_%s-%s-%s" % part)


def _build_PoroDelftEggWell_cases():
    description = Description(lambda part: "PoroDelftEgg wellbore problem on %d ranks" % _n_ranks(part), "auto",
                              "Jian Huang", True)
    restartcheck_params = {"atol": 1.0e-8, "rtol": 2.0e-8}
    _build_poro_elastic_coupling_case("PoroDelftEgg_Wellbore_smoke.xml", (2, 8), ((1, 1, 1), (2, 2, 1)), description,
                                      restartcheck_params, lambda part: "PoroDelftEgg_Wellbore_smoke_%s-%s-%s" % part)


def _build_PoroModifiedCamClayWell_cases():
    description = Description(lambda part: "PoroModifiedCamClay wellbore problem on %d ranks" % _n_ranks(part), "auto",
                              "Jian Huang", True)
    restartcheck_params = {"atol": 1.0e-8, "rtol": 2.0e-8}
    _build_poro_elastic_coupling_case("PoroModifiedCamClay_Wellbore_smoke.xml", (2, 8), ((1, 1, 1), (2, 2, 1)),
                                      description, restartcheck_params,
                                      lambda part: "PoroModifiedCamClay_Wellbore_smoke_%s-%s-%s" % part)


def _build_PoroImpermeableFault_cases():
    description = Description(lambda part: "Impermeable fault problem on %d ranks" % _n_ranks(part), "auto",
                              "Jian Huang", True)
    restartcheck_params = {"atol": 1.0e-5, "rtol": 2.0e-7}
    _build_poro_elastic_coupling_case("PoroElastic_impermeableFault_smoke.xml", (0, 1), ((1, 1, 1), (2, 2, 1)),
                                      description, restartcheck_params,
                                      lambda part: "PoroImpermeableFault_smoke_%s-%s-%s" % part)


def _build_PoroPermeableFault_cases():
    description = Description(lambda part: "Permeable fault problem on %d ranks" % _n_ranks(part), "auto", "Jian Huang",
                              True)
    restartcheck_params = {"atol": 1.0e-5, "rtol": 2.0e-7}
    _build_poro_elastic_coupling_case("PoroElastic_permeableFault_smoke.xml", (0, 1), ((1, 1, 1), (2, 2, 1)),
                                      description, restartcheck_params,
                                      lambda part: "PoropermeableFault_smoke_%s-%s-%s" % part)


def _build_PoroStaircaseSinglePhasePeacemanWell_cases():
    description = Description(
        lambda part: "Staircase single-phase poroelastic problem with Peaceman wells on %d ranks" % _n_ranks(part),
        "auto", "Francois Hamon", True)
    restartcheck_params = {"atol": 1.0e-5, "rtol": 2.0e-7}
    _build_poro_elastic_coupling_case("PoroElastic_staircase_singlephase_3d.xml", (6, 11), ((1, 1, 1), (2, 2, 1)),
                                      description, restartcheck_params,
                                      lambda part: "PoroElastic_staircase_singlephase_3d_%s-%s-%s" % part)


def _build_PoroStaircaseCO2PeacemanWell_cases():
    description = Description(
        lambda part: "Staircase CO2 poroelastic problem with Peaceman wells on %d ranks" % _n_ranks(part), "auto",
        "Francois Hamon", True)
    restartcheck_params = {"atol": 1.0e-5, "rtol": 2.0e-7}
    _build_poro_elastic_coupling_case("PoroElastic_staircase_co2_3d.xml", (22, 33), ((1, 1, 1), (2, 2, 1)), description,
                                      restartcheck_params, lambda part: "PoroElastic_staircase_co2_3d_%s-%s-%s" % part)


def _build_PoroElasticPEBICO2FIM_cases():
    description = Description(
        lambda part: "CO2 poroelastic problem with VEM-TPFA (FIM) on a PEBI mesh on %d ranks" % _n_ranks(part), "auto",
        "Francois Hamon", True)
    restartcheck_params = {"atol": 1.0e-5, "rtol": 2.0e-7}
    _build_poro_elastic_coupling_case("PoroElastic_hybridHexPrism_co2_fim_3d.xml", (10, 20), ((1, 1, 1), (2, 2, 1)),
                                      description, restartcheck_params,
                                      lambda part: "PoroElastic_hybridHexPrism_co2_fim_3d_%s-%s-%s" % part)


def _build_PoroElasticPEBICO2Sequential_cases():
    description = Description(
        lambda part: "CO2 poroelastic problem with VEM-TPFA (Sequential) on a PEBI mesh on %d ranks" % _n_ranks(part),
        "auto", "Francois Hamon", True)
    restartcheck_params = {"atol": 1.0e-5, "rtol": 2.0e-7}
    _build_poro_elastic_coupling_case("PoroElastic_hybridHexPrism_co2_sequential_3d.xml", (10, 20),
                                      ((1, 1, 1), (2, 2, 1)), description, restartcheck_params,
                                      lambda part: "PoroElastic_hybridHexPrism_co2_sequential_3d_%s-%s-%s" % part)


def _build_PoroElasticGravity_cases():
    description = Description(lambda part: "Single-phase poroelastic problem with gravity on %d ranks" % _n_ranks(part),
                              "auto", "Francois Hamon", True)
    restartcheck_params = {"atol": 1.0e-5, "rtol": 2.0e-7}
    _build_poro_elastic_coupling_case("PoroElastic_gravity.xml", (5, 10), ((1, 1, 1), (1, 1, 2)), description,
                                      restartcheck_params, lambda part: "PoroElastic_gravity_%s-%s-%s" % part)


def test_poro_elastic_coupling_cases():
    _build_Terzaghi_cases()
    _build_Mandel_fim_cases()
    _build_Mandel_sequential_cases()    
    _build_Mandel_prism6_cases()
    _build_Deadoil_fim_cases()
    _build_Deadoil_sequential_cases()    
    _build_PoroElasticWell_cases()
    _build_PoroDruckerPragerWell_cases()
    _build_PoroDelftEggWell_cases()
    _build_PoroModifiedCamClayWell_cases()
    _build_PoroImpermeableFault_cases()
    _build_PoroPermeableFault_cases()
    _build_PoroStaircaseSinglePhasePeacemanWell_cases()
    _build_PoroStaircaseCO2PeacemanWell_cases()
    _build_PoroElasticPEBICO2FIM_cases()
    _build_PoroElasticPEBICO2Sequential_cases()
    _build_PoroElasticGravity_cases()

def generate_poroelastic_tests():
    test_poro_elastic_coupling_cases()
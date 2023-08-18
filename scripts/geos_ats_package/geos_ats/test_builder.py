import os
from typing import Iterable
from dataclasses import dataclass, asdict

from .test_steps import geos
from .test_case import TestCase


@dataclass    
class RestartcheckParameters:
    atol: float
    rtol: float

    def as_dict(self):
        return asdict(self)

@dataclass
class CurveCheckParameters:
    filename: str
    tolerance: list[float]
    script_instructions: list[list[str]]
    curves: list[list[str]]

    def as_dict(self):
        return asdict(self)

@dataclass
class TestDeck:
    name: str
    description: str
    partitions: list[tuple[int, int, int]]
    restart_step: int
    check_step: int
    restartcheck_params: RestartcheckParameters = None
    curvecheck_params: CurveCheckParameters = None
    
    @classmethod
    def from_dict(cls, data_dict):
        return cls(
            name=data_dict["name"],
            description=data_dict["description"],
            partitions=data_dict["partitions"],
            restart_step=data_dict["restart_step"],
            check_step=data_dict["check_step"]
        )

def generate_geos_tests( decks: Iterable[TestDeck] ):
    """
    """
    for deck in decks:

        restartcheck_params=None
        curvecheck_params=None

        if deck.restartcheck_params is not None:
            restartcheck_params= deck.restartcheck_params.as_dict()

        if deck.curvecheck_params is not None:
            curvecheck_params = deck.curvecheck_params.as_dict()

        for partition in deck.partitions:
            nx, ny, nz = partition
            N = nx * ny * nz

            testcase_name = "{}_{:02d}".format(deck.name, N)
            base_name = "0to{:d}".format(deck.check_step) 

            steps = [ geos(deck="{}.xml".format(deck.name),
                        name=base_name,
                        np=N,
                        ngpu=N,
                        x_partitions=nx,
                        y_partitions=ny,
                        z_partitions=nz,
                        restartcheck_params=restartcheck_params,
                        curvecheck_params=curvecheck_params) ]

            if deck.restart_step > 0:
                steps.append(geos(deck=deck.name + ".xml",
                            name="{:d}to{:d}".format(deck.restart_step, deck.check_step),
                            np=N,
                            ngpu=N,
                            x_partitions=nx,
                            y_partitions=ny,
                            z_partitions=nz,
                            restart_file=os.path.join(testcase_name, "{}_restart_{:09d}".format(base_name, deck.restart_step) ),
                            baseline_pattern=f"{base_name}_restart_[0-9]+\.root",
                            allow_rebaseline=False,
                            restartcheck_params=restartcheck_params,
                            curvecheck_params=curvecheck_params ) )

            TestCase(name=testcase_name,
                     desc=deck.description,
                     label="auto",
                     owner="GEOS team",
                     independent=True,
                     steps=steps)
   
            
def generate_geos_tests_from_dictionary( decks, restartcheck_params, curvecheck_params_base=None ):
    """
    """
    
    restartcheck_params_instance = RestartcheckParameters(**restartcheck_params)
    deck_instances = []
        
    for deck in decks:
            
        deck_instance = TestDeck.from_dict( deck )
        deck_instance.restartcheck_params = restartcheck_params_instance

        if curvecheck_params_base is not None:
            if ("aperture_curve_method" in deck) and ("pressure_curve_method" in deck):
                curvecheck_params = curvecheck_params_base.copy()
                curvecheck_params["script_instructions"][0][1] = deck["aperture_curve_method"]
                curvecheck_params["script_instructions"][1][1] = deck["pressure_curve_method"]
                
                if  ("tolerance" in deck):
                    curvecheck_params["tolerance"] = deck["tolerance"]

                deck_instance.curvecheck_params = CurveCheckParameters(**curvecheck_params)

            elif("script_instructions" in curvecheck_params_base):
                deck_instance.curvecheck_params = CurveCheckParameters(**curvecheck_params_base)         

        deck_instances.append(deck_instance)

    generate_geos_tests( deck_instances )            
import os
from .test_steps import geos
from .test_case import TestCase

from dataclasses import dataclass

from typing import Tuple


@dataclass    
class RestartcheckParameters:
    atol: float
    rtol: float

    def as_dict(self):
        return {
            "atol": self.atol,
            "rtol": self.rtol,
        }

@dataclass
class CurveCheckParameters:
    filename: str
    tolerance: list[float]
    script_instructions: list[list[str]]
    curves: list[list[str]]

    def as_dict(self):
        return {
            "filename": self.filename,
            "tolerance": self.tolerance,
            "script_instructions": self.script_instructions,
            "curves": self.curves
        } 

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
    
    @classmethod
    def from_values(cls, values):
        return cls(
            name=values[0],
            description=values[1],
            partitions=values[2],
            restart_step=values[3],
            check_step=values[4]
        )

def generate_geos_tests( deck_instances: Tuple[TestDeck] ):
    
    for deck_instance in deck_instances:
        if not isinstance(deck_instance, TestDeck):
            raise ValueError("Input tuple must contain instances of the TestDeck class.")
        
        if deck_instance.restartcheck_params is not None:
            restartcheck_params_dict = deck_instance.restartcheck_params.as_dict()
        else:
            restartcheck_params_dict=None

        if deck_instance.curvecheck_params is not None:
            curvecheck_params_dict = deck_instance.curvecheck_params.as_dict()
        else:
            curvecheck_params_dict=None

        for partition in deck_instance.partitions:
            nx = partition[0]
            ny = partition[1]
            nz = partition[2]
            N = nx * ny * nz

            testcase_name = "{}_{:02d}".format(deck_instance.name, N)
            base_name = "0to{:d}".format(deck_instance.check_step) 

            steps = [ geos(deck="{}.xml".format(deck_instance.name),
                        name=base_name,
                        np=N,
                        ngpu=N,
                        x_partitions=nx,
                        y_partitions=ny,
                        z_partitions=nz,
                        restartcheck_params=restartcheck_params_dict,
                        curvecheck_params=curvecheck_params_dict) ]

            if deck_instance.restart_step > 0:
                steps.append(geos(deck=deck_instance.name + ".xml",
                            name="{:d}to{:d}".format(deck_instance.restart_step, deck_instance.check_step),
                            np=N,
                            ngpu=N,
                            x_partitions=nx,
                            y_partitions=ny,
                            z_partitions=nz,
                            restart_file=os.path.join(testcase_name, "{}_restart_{:09d}".format(base_name, deck_instance.restart_step) ),
                            baseline_pattern=f"{base_name}_restart_[0-9]+\.root",
                            allow_rebaseline=False,
                            restartcheck_params=restartcheck_params_dict,
                            curvecheck_params=curvecheck_params_dict ) )

            TestCase(name=testcase_name,
                     desc=deck_instance.description,
                     label="auto",
                     owner="GEOS team",
                     independent=True,
                     steps=steps)
    

def generate_geos_tests_from_values( decks, restartcheck_params ):
    """ 
    """
    restartcheck_params_instance = RestartcheckParameters(**restartcheck_params)
    deck_instances = [TestDeck.from_values(deck_data) for deck_data in decks]
    for deck_instance in deck_instances:
        deck_instance.restartcheck_params = restartcheck_params_instance

    generate_geos_tests( deck_instances )
   
            
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
import os
from typing import (
    Iterable,
    List,
    Tuple,
)
from dataclasses import dataclass, asdict
from ats.tests import AtsTest
from lxml import etree
from .test_steps import geos
from .test_case import TestCase


@dataclass(frozen=True)
class RestartcheckParameters:
    atol: float
    rtol: float

    def as_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class CurveCheckParameters:
    filename: str
    tolerance: Iterable[float]
    curves: List[List[str]]
    script_instructions: Iterable[Iterable[str]] = None
    time_units: str = "seconds"

    def as_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class TestDeck:
    name: str
    description: str
    partitions: Iterable[Tuple[int, int, int]]
    restart_step: int
    check_step: int
    restartcheck_params: RestartcheckParameters = None
    curvecheck_params: CurveCheckParameters = None


def collect_block_names(fname):
    """
    Collect block names in an xml file

    Args:
        fname (str): The path to the xml

    Returns:
        dict: Pairs of top-level block names and lists of child block names
    """
    pwd = os.getcwd()
    actual_dir, actual_fname = os.path.split(os.path.realpath(fname))
    os.chdir(actual_dir)

    # Collect the block names in this file
    results = {}
    parser = etree.XMLParser(remove_comments=True)
    tree = etree.parse(actual_fname, parser=parser)
    root = tree.getroot()
    for child in root.getchildren():
        results[child.tag] = [grandchild.tag for grandchild in child.getchildren()]

    # Collect block names in included files
    for included_root in root.findall('Included'):
        for included_file in included_root.findall('File'):
            f = included_file.get('name')
            child_results = collect_block_names(f)
            for k, v in child_results.items():
                if k in results:
                    results[k].extend(v)
                else:
                    results[k] = v
    os.chdir(pwd)
    return results


def generate_geos_tests(decks: Iterable[TestDeck]):
    """
    """
    for ii, deck in enumerate(decks):

        restartcheck_params = None
        curvecheck_params = None

        if deck.restartcheck_params is not None:
            restartcheck_params = deck.restartcheck_params.as_dict()

        if deck.curvecheck_params is not None:
            curvecheck_params = deck.curvecheck_params.as_dict()

        for partition in deck.partitions:
            nx, ny, nz = partition
            N = nx * ny * nz

            testcase_name = "{}_{:02d}".format(deck.name, N)
            base_name = "0to{:d}".format(deck.check_step)
            xml_file = "{}.xml".format(deck.name)
            xml_blocks = collect_block_names(xml_file)

            checks = []
            if curvecheck_params:
                checks.append('curve')

            steps = [
                geos(deck=xml_file,
                     name=base_name,
                     np=N,
                     ngpu=N,
                     x_partitions=nx,
                     y_partitions=ny,
                     z_partitions=nz,
                     restartcheck_params=restartcheck_params,
                     curvecheck_params=curvecheck_params)
            ]

            if deck.restart_step > 0:
                checks.append('restart')
                steps.append(
                    geos(deck=xml_file,
                         name="{:d}to{:d}".format(deck.restart_step, deck.check_step),
                         np=N,
                         ngpu=N,
                         x_partitions=nx,
                         y_partitions=ny,
                         z_partitions=nz,
                         restart_file=os.path.join(testcase_name,
                                                   "{}_restart_{:09d}".format(base_name, deck.restart_step)),
                         baseline_pattern=f"{base_name}_restart_[0-9]+\.root",
                         allow_rebaseline=False,
                         restartcheck_params=restartcheck_params))

            AtsTest.stick(level=ii)
            AtsTest.stick(checks=','.join(checks))
            AtsTest.stick(solvers=','.join(xml_blocks.get('Solvers', [])))
            AtsTest.stick(outputs=','.join(xml_blocks.get('Outputs', [])))
            AtsTest.stick(constitutive_models=','.join(xml_blocks.get('Constitutive', [])))
            TestCase(name=testcase_name,
                     desc=deck.description,
                     label="auto",
                     owner="GEOS team",
                     independent=True,
                     steps=steps)

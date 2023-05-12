import ats    # type: ignore[import]
from geos_ats import common_utilities
from geos_ats.configuration_record import config
from geos_ats import test_steps
import os
import logging

logger = logging.getLogger('geos_ats')


class TestModifier(object):
    """Base class for test modifiers.  It modifies the steps of a test_case to create a new test"""

    def modifySteps(self, originalSteps, dictionary):
        """Overload this function to generate a new sequence of steps from the existing sequence of steps"""
        return originalSteps


class TestModifierDefault(TestModifier):
    label = "default"
    doc = "Default test modifier:  Add a step to check stdout for info and critical warning"

    def modifySteps(self, steps, dictionary):
        return steps


def Factory(name):
    """Function that returns the correct TestModifier based on the name"""
    if not name:
        return TestModifierDefault()

    for k, v in globals().items():
        if not isinstance(v, type):
            continue
        if v == TestModifier:
            continue
        try:
            if issubclass(v, TestModifier):
                if v.label == name:
                    return v()
        except TypeError as e:
            logger.debug(e)

    common_utilities.Error("Unknown test modifier: %s" % name)


def infoTestModifier(*args):
    modifiers = []
    for k, v in globals().items():
        if not isinstance(v, type):
            continue
        if v == TestModifier:
            continue
        try:
            if issubclass(v, TestModifier):
                modifiers.append(k)
        except TypeError as e:
            logger.debug(e)

    modifiers = sorted(modifiers)

    topic = common_utilities.InfoTopic("test modifiers")
    topic.startBanner()
    table = common_utilities.TextTable(2)

    for m in modifiers:
        mclass = globals()[m]
        doc = getattr(mclass, "doc", None)
        label = getattr(mclass, "label", None)
        table.addRow(label, doc)

    table.printTable()
    topic.endBanner()

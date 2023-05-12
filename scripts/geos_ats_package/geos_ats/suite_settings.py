from geos_ats import common_utilities
import logging

testLabels = [
    "geos",
    "auto",    # label used when the tests were automatically converted.  Will be deprecated.
]

testOwners = [("corbett5", "Ben Corbett")]
logger = logging.getLogger('geos_ats')


def infoOwners(filename):
    topic = common_utilities.InfoTopic("owners")
    topic.startBanner()

    owners = sorted(testOwners)

    table = common_utilities.TextTable(2)
    for o in owners:
        table.addRow(o[0], o[1])

    table.printTable()

    logger.info(f"The list can be found in: {filename}")
    topic.endBanner()


def infoLabels(filename):

    topic = common_utilities.InfoTopic("labels")
    topic.startBanner()

    labels = sorted(testLabels[:])

    logger.info("Test labels:")
    for o in labels:
        logger.info(f"  {o}")

    logger.info(f"The list can be found in: {filename}")
    topic.endBanner()

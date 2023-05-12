#!/bin/env python

import optparse
import subprocess
import os
import sys
#import glob
import shutil
import logging

logger = logging.getLogger('geos_ats')


def switch(booleans, i):
    booleans[i] = not booleans[i]


def DeclareCompoundRuleClass(name, RuleA, RuleB):
    """
    Declares a class of name name that is a new rule that is
    the combination of 2 base rules.
    """
    tmp = type(name, (RuleA, RuleB), {})
    tmp.numToggles = RuleA.numToggles + RuleB.numToggles
    tmp.numCombinations = RuleA.numCombinations * RuleB.numCombinations

    # Define the initializer for the new class
    def newInit(self, toggles):
        RuleA.__init__(self, toggles, 0, RuleA.numToggles)
        RuleB.__init__(self, toggles, RuleA.numToggles)

    tmp.__init__ = newInit
    globals()[name] = tmp
    return tmp


def GenRules(RuleType):
    """ Generator that produces a rule for each possible combination of toggles"""

    nt = RuleType.numToggles
    nc = RuleType.numCombinations
    """" toggles is [1,2,4,8,16,...] masked by the bitmap of the rulecount.
    For example, if nt = 3 (and thus nc = 8), resulting generated toggles are:
    [0,0,0]
    [1,0,0]
    [0,2,0]
    [1,2,0]
    [0,0,4]
    [1,0,4]
    [0,2,4]
    [1,2,4]
    Note that the resulting rule can be uniquely ID'd by the sum of the toggle array.
"""

    for i in range(nc):
        toggles = [i & pow(2, x) for x in range(nt)]
        tmp = RuleType(toggles)
        tmp.refresh()
        yield tmp


class Rule(object):
    """ Base class for the rules"""

    def __init__(self, nToggles, nCombinations, toggles):
        self.numToggles = nToggles
        self.numCombinations = nCombinations
        self.toggles = toggles
        self.repStrings = {}
        """ Assumes toggles is set in a way consistent with what is done in GenRules"""
        self.id = sum(self.toggles)
        self.repStrings["@@POS@@"] = str(self.id)

    def GetPosition(self):
        return self.id * 1.0

    def refresh(self):
        pass

    def replaceString(self, string):
        tmp = string
        for s in self.repStrings:
            tmp = tmp.replace(s, self.repStrings[s])
        return tmp

    def sedFile(self, fIn, fOut):
        inFile = open(fIn)
        outFile = open(fOut, 'w')
        for line in inFile:
            outFile.write(self.replaceString(line))
        inFile.close()
        outFile.close()

    def checkTimehist(self):
        # timehist
        logger.error('checkTimehist method not defined')


class SetupRules(Rule):
    numToggles = 2
    numCombinations = pow(2, numToggles)

    def __init__(self, toggles, minToggle=0, maxToggle=None):
        self.setupMin = minToggle
        self.setupMax = maxToggle
        Rule.__init__(self, SetupRules.numToggles, SetupRules.numCombinations, toggles)

    def refresh(self):
        mtoggles = self.toggles[self.setupMin:self.setupMax]

        underscoredName = mtoggles[0]
        self.isTenthCycle = mtoggles[1]

        self.baseName = "foo%i" % self.id
        self.baseName = "%s%s" % (self.baseName, "_001" if underscoredName else "")
        self.repStrings["@@BASE@@"] = self.baseName

        self.inputDeck = "%s.in" % self.baseName
        self.repStrings["@@DECK@@"] = self.inputDeck

        self.restartBaseName = "%s_001" % self.baseName
        self.restartName = "%s_%s" % (self.restartBaseName, "00010" if self.isTenthCycle else "00000")
        self.repStrings["@@RF@@"] = self.restartName

        super(SetupRules, self).refresh()

    def GetInputDeckName(self):
        return self.inputDeck

    def GetInitialRestartName(self):
        return self.restartName

    def GetBaseName(self):
        return self.baseName


class CommandLineRules(Rule):
    numToggles = 2
    numCombinations = pow(2, numToggles)

    def __init__(self, toggles, minToggle=0, maxToggle=None):
        self.clMin = minToggle
        self.clMax = maxToggle
        Rule.__init__(self, CommandLineRules.numToggles, CommandLineRules.numCombinations, toggles)

    def refresh(self):
        mtoggles = self.toggles[self.clMin:self.clMax]
        self.probDefined = mtoggles[0]    # use the -prob flag
        self.restartDefined = mtoggles[1]    # use the -rf flag

        #        self.prob = "-prob %s" % "@@BASE@@" if self.probDefined else ""
        #        self.rf = "-rf %s" % "@@RF@@" if self.restartDefined else ""
        self.prob = "@@BASE@@" if self.probDefined else ""
        self.rf = "@@RF@@" if self.restartDefined else ""

        self.repStrings["@@CL_PROB@@"] = self.prob
        self.repStrings["@@CL_RF@@"] = self.rf

        super(CommandLineRules, self).refresh()


def main():

    generator = GenRules(SetupRules)
    for rule in generator:
        vals = (rule.GetInputDeckName(), rule.GetInitialRestartName(), rule.GetPosition())
        logger.debug(rule.replaceString("InputDeck: %s\tRestartFile: %s\tPos: %f" % vals))

    DeclareCompoundRuleClass("SetupCommand", SetupRules, CommandLineRules)
    logger.debug(SetupCommand.numCombinations)
    generator = GenRules(SetupCommand)
    logger.debug("compound:")
    for rule in generator:
        vals = (rule.GetInputDeckName(), rule.GetInitialRestartName(), rule.GetPosition(), rule.prob, rule.rf)
        logger.debug(rule.replaceString("InputDeck: %s\tRestartFile: %s\tPos: %f\t%s\t%s" % vals))

    return

    dbg = True
    parser = optparse.OptionParser()

    # argument to check results of pdldiff script
    #    parser.add_option("-p", "--pdldiff", type = "string", dest = "pdldiff" )
    (options, args) = parser.parse_args()
    #    assert options.gnuplot

    assert len(args) == 4

    base = args[0]
    sourceDeck = args[1]
    atsFile = args[2]
    outdir = args[3]
    assert os.path.exists(sourceDeck)
    assert os.path.exists(atsFile)

    if os.path.exists(outdir):
        try:
            shutil.rmtree(outdir)
        except:
            logger.debug(f"Could not remove directory: {outdir}")

    # make a directory
    try:
        os.mkdir(outdir)
        # copy in the input deck and other necessary files for running the problem
        shutil.copy(sourceDeck, os.path.join(outdir, "%s.ain" % base))
        shutil.copy("leos1.05.h5", outdir)
    except:
        logger.debug(f"Could not create directory: {outdir}")

    # copy in the ats file template, replacing appropriate text as we go
    outp = open(os.path.join(outdir, "%s.ats" % base), 'w')
    inp = open(atsFile, 'r')
    for line in inp:
        line = line.replace("BASE", base)
        outp.write(line)
    # sub = subprocess.call(['sed', 's/BASE/%s/'%base,atsFile],stdout=outp)
    inp.close()
    outp.close()

    sys.exit(0)


if __name__ == "__main__":
    main()

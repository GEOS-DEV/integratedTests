import difflib
import sys
import textwrap
import os
import shutil
import subprocess
import logging

################################################################################
#  Common code for displaying information to the user.
################################################################################

logger = logging.getLogger('geos_ats')


def Error(msg):
    raise RuntimeError("Error: %s" % msg)


def Log(msg):
    import ats    # type: ignore[import]
    testmode = False
    try:
        testmode = ats.tests.AtsTest.getOptions().get("testmode")
    except AttributeError as e:
        logger.debug(e)

    if testmode:
        ats.log("ALEATS: " + msg, echo=True)
    else:
        ats.log(msg, echo=True)


class TextTable(object):

    def __init__(self, columns):
        self.table = []
        self.sep = " : "
        self.indent = "    "
        self.columns = columns
        self.colmax = [None] * columns

        self.maxwidth = self._getwidth()
        self.rowbreak = None
        self.rowbreakstyle = " "

    def _getwidth(self):
        maxwidth = 100
        if os.name == "posix":
            try:
                sttyout = subprocess.Popen(["stty", "size"], stdout=subprocess.PIPE).communicate()[0]
                maxwidth = int(sttyout.split()[1])
            except:
                # If the stty size approach does not work, the use a default maxwidth
                logger.debug("Using default maxwidth")

        return maxwidth

    def setHeader(self, *row):
        assert (len(row) == self.columns)
        self.table.insert(0, row)
        self.table.insert(1, None)

    def addRowBreak(self):
        self.table.append(None)

    def addRow(self, *row):
        assert (len(row) == self.columns)
        self.table.append(row)

    def setColMax(self, colindex, max):
        self.colmax[colindex] = max

    def printTable(self, outfile=sys.stdout):
        table_str = ''
        if len(self.table) == 0:
            return

        # find the max column sizes
        colWidth = []
        for i in range(self.columns):
            colWidth.append(max([len(str(row[i])) for row in self.table if row is not None]))

        # adjust the colWidths down if colmax is step
        for i in range(self.columns):
            if self.colmax[i] is not None:
                if colWidth[i] > self.colmax[i]:
                    colWidth[i] = self.colmax[i]

        # last column is floating

        total = sum(colWidth) + self.columns * (1 + len(self.sep)) + len(self.indent)
        if total > self.maxwidth:
            colWidth[-1] = max(10, self.maxwidth - (total - colWidth[-1]))

        # output the table
        rowbreakindex = 0
        for row in self.table:

            # row break controls.
            # if row is None then this is a break
            addBreak = (row is None) or (self.rowbreak and rowbreakindex > 0 and rowbreakindex % self.rowbreak == 0)
            if addBreak:
                table_str += self.indent
                for i in range(self.columns):
                    if i < self.columns - 1:
                        table_str += f"{self.rowbreakstyle * colWidth[i]}{self.sep}"
                    else:
                        table_str += self.rowbreakstyle * colWidth[i]
                table_str += '\n'

            if row is None:
                rowbreakindex = 0
                continue
            else:
                rowbreakindex += 1

            # determine how many lines are needed by each column of this row.
            lines = []

            for i in range(self.columns):
                if isinstance(row[i], str):
                    drow = textwrap.dedent(row[i])
                else:
                    drow = str(row[i])

                if i == self.columns - 1:
                    lines.append(textwrap.wrap(drow, colWidth[i], break_long_words=False))
                else:
                    lines.append(textwrap.wrap(drow, colWidth[i], break_long_words=True))

            maxlines = max([len(x) for x in lines])

            # output the row
            for j in range(maxlines):
                table_str += self.indent
                for i in range(self.columns):
                    if len(lines[i]) > j:
                        entry = lines[i][j].ljust(colWidth[i])
                    else:
                        entry = " ".ljust(colWidth[i])

                    if i < self.columns - 1:
                        table_str += f"{entry}{self.sep}"
                    else:
                        table_str += entry

                table_str += '\n'

        outfile.write(table_str)


class InfoTopic(object):

    def __init__(self, topic, outfile=sys.stdout):
        self.topic = topic
        self.subtopics = []
        self.outfile = outfile

    def addTopic(self, topic, brief, function):
        self.subtopics.append((topic, brief, function))

    def startBanner(self):
        self.outfile.write("=" * 80 + '\n')
        self.outfile.write(self.topic.center(80))
        self.outfile.write("\n" + "=" * 80 + '\n')

    def endBanner(self):
        self.outfile.write("." * 80 + '\n')

    def findTopic(self, topicName):
        for topic in self.subtopics:
            if topic[0] == topicName:
                return topic
        return None

    def displayMenu(self):
        self.startBanner()

        table = TextTable(3)
        for i, topic in enumerate(self.subtopics):
            table.addRow(i, topic[0], topic[1])

        table.addRow(i + 1, "exit", "")
        table.printTable()

        import ats
        if ats.tests.AtsTest.getOptions().get("testmode"):
            return

        while True:
            logger.info("Enter a topic: ")
            sys.stdout.flush()

            try:
                line = sys.stdin.readline()
            except KeyboardInterrupt as e:
                logger.debug(e)
                return None

            value = line.strip()
            topic = self.findTopic(value)
            if topic:
                return topic
            try:
                index = int(value)
                if index >= 0 and index < len(self.subtopics):
                    return self.subtopics[index]
                if index == len(self.subtopics):
                    return None

            except ValueError as e:
                logger.debug(e)

    def process(self, args):

        if len(args) == 0:
            topic = self.displayMenu()
            if topic is not None:
                topic[2]()
        else:
            topicName = args[0]
            topic = self.findTopic(topicName)
            if topic:
                topic[2](*args[1:])
            else:
                logger.warning(f"unknown topic: {topicName}")


def removeLogDirectories(dir):
    # look for subdirs containing 'ats.log' and 'geos_ats.config'
    # look for symlinks that point to such a directory
    files = os.listdir(dir)
    deldir = []
    for f in files:
        ff = os.path.join(dir, f)
        if os.path.isdir(ff) and not os.path.islink(ff):
            tests = [
                all([os.path.exists(os.path.join(ff, "ats.log")),
                     os.path.exists(os.path.join(ff, "geos_ats.config"))]),
                f.find("TestLogs.") == 0
            ]
            if any(tests):
                deldir.append(ff)
                shutil.rmtree(ff)

    for f in files:
        ff = os.path.join(dir, f)
        if os.path.islink(ff):
            pointsto = os.path.realpath(ff)
            if pointsto in deldir:
                os.remove(ff)

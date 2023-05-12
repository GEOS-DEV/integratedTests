import os
import socket
import subprocess
import time
import re
from geos_ats.configuration_record import config
import sys
import ats    # type: ignore[import]
from configparser import ConfigParser
import logging

# Get the active logger instance
logger = logging.getLogger('geos_ats')

# The following are ALEATS test status values.
# The order is important for the ReportGroup: lower values take precendence
FAILRUN = 0
FAILCHECK = 1
FAILCHECKMINOR = 2
TIMEOUT = 3
INPROGRESS = 4
NOTRUN = 5
FILTERED = 6
RUNNING = 7
SKIP = 8
BATCH = 9
FAILRUNOPTIONAL = 10
NOTBUILT = 11
PASS = 12
EXPECTEDFAIL = 13
UNEXPECTEDPASS = 14

# A tuple of test status values.
STATUS = (FAILRUN, UNEXPECTEDPASS, FAILRUNOPTIONAL, FAILCHECK, FAILCHECKMINOR, TIMEOUT, NOTRUN, FILTERED, RUNNING,
          INPROGRESS, PASS, EXPECTEDFAIL, SKIP, BATCH, NOTBUILT)

STATUS_NOTDONE = (NOTRUN, RUNNING, INPROGRESS, BATCH)


class ReportBase(object):
    """Base class for reporting.  The constructor takes in a sequence
    of testcases (of type test_case), and from each testcase, a
    ReportTestCase object is created."""

    def __init__(self, testcases):
        pass


class ReportTiming(ReportBase):
    """Reporting class that is used for outputting test timings"""

    def __init__(self, testcases):
        self.reportcases = [ReportTestCase(t) for t in testcases]
        self.timings = {}

    def getOldTiming(self, fp):
        for line in fp:
            if not line.startswith('#'):
                tokens = line.split()
                self.timings[tokens[0]] = int(tokens[1])

    def report(self, fp):
        for testcase in self.reportcases:
            if testcase.status in [PASS, TIMEOUT]:
                self.timings[testcase.testcase.name] = int(testcase.testcase.status.totalTime())
        output = ""
        for key in sorted(self.timings):
            output += "%s %d\n" % (key, self.timings[key])
        fp.writelines(output)


class ReportIni(ReportBase):
    """Minimal reporting class that is used for bits status emails"""

    def __init__(self, testcases):
        self.reportcases = [ReportTestCase(t) for t in testcases]

        # A dictionary where the key is a status, and the value is a sequence of ReportTestCases
        self.reportcaseResults = {}
        for status in STATUS:
            self.reportcaseResults[status] = [t for t in self.reportcases if t.status == status]

        self.displayName = {}
        self.displayName[FAILRUN] = "FAILRUN"
        self.displayName[FAILRUNOPTIONAL] = "FAILRUNOPTIONAL"
        self.displayName[FAILCHECK] = "FAILCHECK"
        self.displayName[FAILCHECKMINOR] = "FAILCHECKMINOR"
        self.displayName[TIMEOUT] = "TIMEOUT"
        self.displayName[NOTRUN] = "NOTRUN"
        self.displayName[INPROGRESS] = "INPROGRESS"
        self.displayName[FILTERED] = "FILTERED"
        self.displayName[RUNNING] = "RUNNING"
        self.displayName[PASS] = "PASSED"
        self.displayName[SKIP] = "SKIPPED"
        self.displayName[BATCH] = "BATCHED"
        self.displayName[NOTBUILT] = "NOTBUILT"
        self.displayName[EXPECTEDFAIL] = "EXPECTEDFAIL"
        self.displayName[UNEXPECTEDPASS] = "UNEXPECTEDPASS"

    def __getTestCaseName(testcase):
        return testcase.testcase.name

    def report(self, fp):
        configParser = ConfigParser()

        configParser.add_section("Info")
        configParser.set("Info", "Time", time.strftime("%a, %d %b %Y %H:%M:%S"))
        try:
            platform = socket.gethostname()
        except:
            logger.debug("Could not get host name")
            platform = "unknown"
        configParser.set("Info", "Platform", platform)

        extraNotations = ""
        for line in config.report_notations:
            line_split = line.split(":")
            if len(line_split) != 2:
                line_split = line.split("=")
            if len(line_split) != 2:
                extraNotations += "\"" + line.strip() + "\""
                continue
            configParser.set("Info", line_split[0].strip(), line_split[1].strip())
        if extraNotations != "":
            configParser.set("Info", "Extra Notations", extraNotations)

        configParser.add_section("Results")
        configParser.add_section("Custodians")
        configParser.add_section("Documentation")
        undocumentedTests = []
        for status in STATUS:
            testNames = []
            for reportcaseResult in self.reportcaseResults[status]:
                testName = reportcaseResult.testcase.name
                testNames.append(testName)

                owner = getowner(testName, reportcaseResult.testcase)
                if owner is not None:
                    configParser.set("Custodians", testName, owner)

                if config.report_doc_link:
                    linkToDocumentation = os.path.join(config.report_doc_dir, testName, testName + ".html")
                    if os.path.exists(linkToDocumentation):
                        configParser.set("Documentation", testName, linkToDocumentation)
                    else:
                        if not reportcaseResult.testcase.nodoc:
                            undocumentedTests.append(testName)
                linkToDocumentation = getowner(testName, reportcaseResult.testcase)
            testNames = sorted(testNames)
            configParser.set("Results", self.displayName[status], ";".join(testNames))
        undocumentedTests = sorted(undocumentedTests)
        configParser.set("Documentation", "undocumented", ";".join(undocumentedTests))
        configParser.write(fp)


class ReportText(ReportBase):

    def __init__(self, testcases):

        ReportBase.__init__(self, testcases)

        self.reportcases = [ReportTestCase(t) for t in testcases]

        # A dictionary where the key is a status, and the value is a sequence of ReportTestCases
        self.reportcaseResults = {}
        for status in STATUS:
            self.reportcaseResults[status] = [t for t in self.reportcases if t.status == status]

        self.displayName = {}
        self.displayName[FAILRUN] = "FAIL RUN"
        self.displayName[FAILRUNOPTIONAL] = "FAIL RUN (OPTIONAL STEP)"
        self.displayName[FAILCHECK] = "FAIL CHECK"
        self.displayName[FAILCHECKMINOR] = "FAIL CHECK (MINOR)"
        self.displayName[TIMEOUT] = "TIMEOUT"
        self.displayName[NOTRUN] = "NOT RUN"
        self.displayName[INPROGRESS] = "INPROGRESS"
        self.displayName[FILTERED] = "FILTERED"
        self.displayName[RUNNING] = "RUNNING"
        self.displayName[PASS] = "PASSED"
        self.displayName[SKIP] = "SKIPPED"
        self.displayName[BATCH] = "BATCHED"
        self.displayName[NOTBUILT] = "NOT BUILT"
        self.displayName[EXPECTEDFAIL] = "EXPECTEDFAIL"
        self.displayName[UNEXPECTEDPASS] = "UNEXPECTEDPASS"

    def report(self, fp):
        """Write out the text report to the give file pointer"""
        self.writeSummary(fp, (FAILRUN, UNEXPECTEDPASS, FAILRUNOPTIONAL, FAILCHECK, FAILCHECKMINOR, TIMEOUT, NOTRUN,
                               INPROGRESS, FILTERED, PASS, EXPECTEDFAIL, SKIP, BATCH, NOTBUILT))
        self.writeLongest(fp, 5)
        self.writeDetails(fp, (FAILRUN, UNEXPECTEDPASS, FAILRUNOPTIONAL, FAILCHECK, FAILCHECKMINOR, TIMEOUT, FILTERED))

    def writeSummary(self, fp, statuses=STATUS):
        """The summary groups each TestCase by its status."""
        fp.write("=" * 80)

        from geos_ats import common_utilities
        for status in statuses:

            tests = self.reportcaseResults[status]
            num = len(tests)
            fp.write(f"\n {self.displayName[status]} : {num}")
            if num > 0:
                testlist = []
                for test in tests:
                    testname = test.testcase.name
                    retries = getattr(test.testcase.atsGroup, "retries", 0)
                    if retries > 0:
                        testname += '[retry:%d]' % retries
                    testlist.append(testname)
                fp.write(f' ( {" ".join( testlist )} ) ')

    def writeDetails(self,
                     fp,
                     statuses=(FAILRUN, UNEXPECTEDPASS, FAILRUNOPTIONAL, FAILCHECK, FAILCHECKMINOR, INPROGRESS),
                     columns=("Status", "TestCase", "Elapsed", "Resources", "TestStep", "OutFile")):
        """This function provides more information about each of the test cases"""

        from geos_ats import common_utilities

        table = common_utilities.TextTable(len(columns))
        table.setHeader(*columns)
        table.rowbreakstyle = "-"
        printTable = False

        for status in statuses:
            tests = self.reportcaseResults[status]

            if len(tests) == 0:
                continue

            printTable = True
            for test in tests:
                testcase = test.testcase
                label = ""
                pathstr = ""
                if test.laststep:
                    paths = testcase.resultPaths(test.laststep)
                    label = test.laststep.label()
                    pathstr = " ".join([os.path.relpath(x) for x in paths])

                row = []
                for col in columns:
                    if col == "Status":
                        statusDisplay = self.displayName[test.status]
                        retries = getattr(testcase.atsGroup, "retries", 0)
                        if retries > 0:
                            statusDisplay += "/retry:%d" % retries
                        row.append(statusDisplay)
                    elif col == "Directory":
                        row.append(os.path.relpath(testcase.path))
                    elif col == "TestCase":
                        row.append(testcase.name)
                    elif col == "TestStep":
                        row.append(label)
                    elif col == "OutFile":
                        row.append(pathstr)
                    elif col == "Elapsed":
                        row.append(ats.times.hms(test.elapsed))
                    elif col == "Resources":
                        row.append(ats.times.hms(test.resources))
                    else:
                        raise RuntimeError(f"Unknown column {col}")

                table.addRow(*row)

            table.addRowBreak()

        fp.write('\n')
        if printTable:
            table.printTable(fp)
        fp.write('\n')

    def writeLongest(self, fp, num=5):
        """The longer running tests are reported"""

        timing = []

        for test in self.reportcases:
            elapsed = test.elapsed
            if elapsed > 0:
                timing.append((elapsed, test))

        timing = sorted(timing, reverse=True)

        if len(timing) > 0:
            fp.write('\n')
            fp.write('\n  LONGEST RUNNING TESTS:')
            for elapsed, test in timing[:num]:
                fp.write(f"  {ats.times.hms(elapsed)} {test.testcase.name}")


class ReportTextPeriodic(ReportText):
    """This class is used during the periodic reports.  It is
    initialized with the actual ATS tests from the ATS manager object.
    The report inherits from ReportText, and extend that behavior with
    """

    def __init__(self, atstests):

        self.atstest = atstests
        testcases = list(set([test.geos_atsTestCase for test in atstests]))
        ReportText.__init__(self, testcases)

    def report(self, startTime, totalProcessors=None):
        self.writeSummary(sys.stdout,
                          (FAILRUN, UNEXPECTEDPASS, FAILRUNOPTIONAL, FAILCHECK, FAILCHECKMINOR, TIMEOUT, NOTRUN,
                           INPROGRESS, FILTERED, RUNNING, PASS, EXPECTEDFAIL, SKIP, BATCH, NOTBUILT))
        self.writeUtilization(sys.stdout, startTime, totalProcessors)
        self.writeLongest(sys.stdout)
        self.writeDetails(sys.stdout, (FAILRUN, UNEXPECTEDPASS, FAILRUNOPTIONAL, FAILCHECK, FAILCHECKMINOR, RUNNING),
                          ("Status", "TestCase", "Directory", "Elapsed", "Resources", "TestStep"))

    def writeUtilization(self, fp, startTime, totalProcessors=None):
        """Machine utilization is reported"""
        totalResourcesUsed = 0.0
        totaltime = time.time() - startTime
        for test in self.reportcases:
            elapsed = test.elapsed
            resources = test.resources
            totalResourcesUsed += resources

        if totalResourcesUsed > 0:
            fp.write('\n')
            fp.write(f"\n  TOTAL TIME           : {ats.times.hms( totaltime )}")
            fp.write(f"\n  TOTAL PROCESSOR-TIME : {ats.times.hms(totalResourcesUsed )}")

            if totalProcessors:
                availableResources = totalProcessors * totaltime
                utilization = totalResourcesUsed / availableResources * 100.0
                fp.write(f"  AVAIL PROCESSOR-TIME : {ats.times.hms(availableResources )}")
                fp.write(f"  RESOURCE UTILIZATION : {utilization:5.3g}%")


class ReportHTML(ReportBase):
    """HTML Reporting"""

    # only launch a web browser once.
    launchedBrowser = False

    def __init__(self, testcases):
        ReportBase.__init__(self, testcases)

        self.reportcases = [ReportTestCase(t) for t in testcases]

        # A dictionary keyed by Status.  The value is a list of ReportGroup
        self.groupResults = None

        # A sorted list of all the ReportGroup
        self.groups = None

        # Initialize the ReportGroups
        self.initializeReportGroups()

        self.color = {}
        self.color[FAILRUN] = "red"
        self.color[FAILRUNOPTIONAL] = "yellow"
        self.color[FAILCHECK] = "reddish"
        self.color[FAILCHECKMINOR] = "reddish"
        self.color[TIMEOUT] = "reddish"
        self.color[NOTRUN] = "yellow"
        self.color[INPROGRESS] = "blue"
        self.color[FILTERED] = "blueish"
        self.color[RUNNING] = "orange"
        self.color[PASS] = "green"
        self.color[SKIP] = "yellow"
        self.color[BATCH] = "yellow"
        self.color[NOTBUILT] = "blueish"
        self.color[EXPECTEDFAIL] = "green"
        self.color[UNEXPECTEDPASS] = "red"

        self.displayName = {}
        self.displayName[FAILRUN] = "FAIL RUN"
        self.displayName[FAILRUNOPTIONAL] = "FAIL RUN (OPTIONAL STEP)"
        self.displayName[FAILCHECK] = "FAIL CHECK"
        self.displayName[FAILCHECKMINOR] = "FAIL CHECK (MINOR)"
        self.displayName[TIMEOUT] = "TIMEOUT"
        self.displayName[NOTRUN] = "NOT RUN"
        self.displayName[INPROGRESS] = "INPROGRESS"
        self.displayName[FILTERED] = "FILTERED"
        self.displayName[RUNNING] = "RUNNING"
        self.displayName[PASS] = "PASSED"
        self.displayName[SKIP] = "SKIPPED"
        self.displayName[BATCH] = "BATCHED"
        self.displayName[NOTBUILT] = "NOTBUILT"
        self.displayName[EXPECTEDFAIL] = "EXPECTEDFAIL"
        self.displayName[UNEXPECTEDPASS] = "UNEXPECTEDPASS"

        self.html_filename = config.report_html_file

    def initializeReportGroups(self):
        testdir = {}

        # place testcases into groups
        for reportcase in self.reportcases:
            dirname = reportcase.testcase.dirname
            if dirname not in testdir:
                testdir[dirname] = []
            testdir[dirname].append(reportcase)

        self.groups = [ReportGroup(key, value) for key, value in testdir.items()]

        # place groups into a dictionary keyed on the group status
        self.groupResults = {}
        for status in STATUS:
            self.groupResults[status] = [g for g in self.groups if g.status == status]

    def report(self, refresh=0):
        # potentially regenerate the html documentation for the test suite.
        # # This doesn't seem to work:
        # self.generateDocumentation()

        sp = open(self.html_filename, 'w')

        if refresh:
            if not any(g.status in (RUNNING, NOTRUN, INPROGRESS) for g in self.groups):
                refresh = 0

        self.writeHeader(sp, refresh)
        self.writeSummary(sp)
        if config.report_doc_link:
            self.writeDoclink(sp)

        # Set the columns to display
        if config.report_doc_link:
            groupColumns = ("Name", "Custodian", "Status")
        else:
            groupColumns = ("Name", "Status")

        testcaseColumns = ("Status", "Name", "TestStep", "Age", "Elapsed", "Resources", "Output")

        # write the details
        self.writeTable(sp, groupColumns, testcaseColumns)
        self.writeFooter(sp)
        sp.close()

        # launch the browser, if requested.

        self.browser()

    def generateDocumentation(self):
        """Generate the HTML documentation using atddoc"""
        if not config.report_doc_link:
            return

        testdocfile = os.path.join(config.report_doc_dir, "testdoc.html")
        if (os.path.exists(testdocfile) and not config.report_doc_remake):
            # Check for any atd files newer than the test html documentation
            newest = 0
            for root, dirs, files in os.walk(config.report_doc_dir):
                for file in files:
                    if file.endswith(".atd"):
                        filetime = os.path.getmtime(os.path.join(root, file))
                        if filetime > newest:
                            newest = filetime
            if os.path.getmtime(testdocfile) > newest:
                logger.info(f"HTML documentation found in {os.path.relpath(testdocfile)}.  Not regenerating.")
                return

        logger.info("Generating HTML documentation files (running 'atddoc')...")
        retcode = True
        try:
            geos_atsdir = os.path.realpath(os.path.dirname(__file__))
            atddoc = os.path.join(geos_atsdir, "atddoc.py")
            #retcode = subprocess.call( atddoc, cwd=config.report_doc_dir, stdout=subprocess.PIPE)
            retcode = subprocess.call(atddoc, cwd=config.report_doc_dir)
        except OSError as e:
            logger.debug(e)
        if retcode:
            logger.info(f"  Failed to create HTML documentation in {config.report_doc_dir}")
        else:
            logger.info(f"  HTML documentation created in {config.report_doc_dir}")

    def writeRowHeader(self, sp, groupColumns, testcaseColumns):
        header = f"""
        <!-- =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
           HEADER BEGIN
        =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=- -->
        <tr>
          <th colspan="{len(groupColumns)}" class="lightondark3"> TEST GROUP </th>
          <th colspan="{len(testcaseColumns)}" class="lightondark3"> TEST CASE </th>
        </tr>
        </tr>
        """

        for col in groupColumns:
            if col == "Name":
                header += '\n <th class="lightondark3"> NAME </th>'
            elif col == "Custodian":
                header += '\n <th class="lightondark3"> CUSTODIAN</th>'
            elif col == "Status":
                header += '\n <th class="lightondark3"> STATUS </th>'
            else:
                raise RuntimeError(f"Unknown column {col}")

        for col in testcaseColumns:
            if col == "Status":
                header += '\n <th class="lightondark3"> STATUS</th>'
            elif col == "Name":
                header += '\n <th class="lightondark3"> NAME </th>'
            elif col == "TestStep":
                header += '\n <th class="lightondark3"> LAST<br> STEP</th>'
            elif col == "Age":
                header += '\n <th class="lightondark3"> AGE</th>'
            elif col == "Elapsed":
                header += '\n <th class="lightondark3"> ELAPSED</th>'
            elif col == "Resources":
                header += '\n <th class="lightondark3"> RESOURCES</th>'
            elif col == "Output":
                header += '\n <th class="lightondark3"> OUTPUT</th>'
            else:
                raise RuntimeError(f"Unknown column {col}")

        header += """</tr>
        <!-- =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
          HEADER END
         =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=- -->
        """
        sp.write(header)

    def writeTable(self, sp, groupColumns, testcaseColumns):
        colspan = len(groupColumns) + len(testcaseColumns)
        header = f"""
          <table border="2" cellpadding="2">
          <tr>
            <th colspan="{colspan}" class=lightondark1> DETAILED RESULTS </th>
          </tr>
        """

        undocumented = []

        rowcount = 0
        testgroups = []
        for status in STATUS:
            testgroups.extend(self.groupResults[status])

        for test in testgroups:
            rowspan = len(test.testcases)
            if rowcount <= 0:
                self.writeRowHeader(sp, groupColumns, testcaseColumns)
                rowcount += 30
            rowcount -= rowspan

            header += f"""
            <!-- =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
            {test.name.upper()}
            =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=- -->
                <tr>
                 <td rowspan="{rowspan}" class="probname">
            """

            for col in groupColumns:
                if col == "Name":
                    header += f"""<a name={test.name}>{test.name}</a>
                    </td>
                    """

                elif col == "Custodian":
                    if config.report_doc_link:
                        owner = getowner(test.name, test.testcases[0].testcase)
                        if owner is not None:
                            header += f'\n     <td rowspan="{rowspan}"> &nbsp; {owner} </td>'
                        else:
                            header += f'\n     <td rowspan="{rowspan}" class="yellowish"> &nbsp;'
                            header += '\n <a title="Document \'CUSTODIAN\' in the .atd file">?</a> &nbsp; </td>'

                elif col == "Status":
                    header += f'<td rowspan="{rowspan}" class="{self.color[test.status]}">{self.displayName[test.status]}</td>'
                else:
                    raise RuntimeError(f"Unknown column {col}")

            for testcase in test.testcases:
                for col in testcaseColumns:

                    if col == "Status":
                        statusDisplay = self.displayName[testcase.status]
                        retries = getattr(testcase.testcase.atsGroup, "retries", 0)
                        if retries > 0:
                            statusDisplay += "<br>retry: %d" % retries
                        header += f'\n<td class="{self.color[testcase.status]}">{statusDisplay}</td>'

                    elif col == "Name":
                        # If an .html file exists for this problem, create a reference to it
                        testref = ""
                        testlinksuffix = ""
                        if config.report_doc_link:
                            docfound = False
                            # first check for the full problem name, with the domain extension
                            testhtml = os.path.join(config.report_doc_dir, test.name, testcase.testcase.name + ".html")
                            if os.path.exists(testhtml):
                                docfound = True
                            else:
                                # next check for the full problem name without the domain extension
                                testhtml = os.path.join(config.report_doc_dir, test.name,
                                                        testcase.testcase.name + ".html")
                                if os.path.exists(testhtml):
                                    docfound = True
                                else:
                                    # final check for any of the input file names
                                    for step in testcase.testcase.steps:
                                        if getattr(step.p, "deck", None):
                                            [inputname, suffix] = getattr(step.p, "deck").rsplit('.', 1)
                                            testhtml = os.path.join(config.report_doc_dir, test.name,
                                                                    inputname + ".html")
                                            if os.path.exists(testhtml):
                                                # match with the first input file
                                                docfound = True
                                                break

                            if docfound:
                                testref = 'href="%s"' % (testhtml)
                            else:
                                if not testcase.testcase.nodoc:
                                    testlinksuffix += '<br>undocumented'
                                    undocumented.append(testcase.testcase.name)

                        header += f"\n<td><a {testref} name={testcase.testcase.name}>{testcase.testcase.name}</a>{testlinksuffix}</td>"

                    elif col == "TestStep":
                        if testcase.laststep:
                            header += f"\n<td>{testcase.laststep.label()}</td>"
                        else:
                            header += "\n<td> &nbsp;</td>"

                    elif col == "Age":
                        if not testcase.laststep:
                            header += "\n<td> &nbsp;</td>"
                            continue

                        if testcase.diffage:
                            difftime = testcase.diffage
                            days = int(difftime) / 86400
                            if days > 0:
                                difftime -= days * 86400
                            hours = int(difftime) / 3600
                            if days == 0:
                                # "New" diff file - don't color
                                header += f'\n<td>{hours}h</td>'
                            elif days > 6:
                                # "Old" diff file (1+ week) - color reddish
                                header += f'\n<td class="reddish">{days}d{hours}h</td>'
                            else:
                                # less than a week old - but aging.  Color yellowish
                                header += f'\n<td class="reddish">{days}d{hours}h</td>'
                        else:
                            header += "\n<td> &nbsp;</td>"

                    elif col == "Elapsed":
                        if not testcase.elapsed:
                            header += "\n<td> &nbsp;</td>"
                        else:
                            header += f"\n<td>{ats.times.hms(testcase.elapsed)}</td>"

                    elif col == "Resources":
                        if not testcase.resources:
                            header += "\n<td> &nbsp;</td>"
                        else:
                            header += f"\n<td>{ats.times.hms(testcase.resources)}</td>"

                    elif col == "Output":

                        header += "\n<td>"
                        seen = {}
                        for stepnum, step in enumerate(testcase.testcase.steps):
                            paths = testcase.testcase.resultPaths(step)
                            for p in paths:
                                # if p has already been accounted for, doesn't exist, or is an empty file, don't print it.
                                if (((p in seen) or not os.path.exists(p)) or (os.stat(p)[6] == 0)):
                                    continue
                                header += f"\n<a href=\"file://{p}\">{os.path.basename(p)}</a><br>"
                                seen[p] = 1
                        header += "\n</td>"
                    else:
                        raise RuntimeError(f"Unknown column {col}")

                header += '\n</tr>'

        header += '\n</table>'

        if config.report_doc_link:
            header += '\n<h3>Undocumented test problems:</h3>'
            header += '\n<ul>'
            if len(undocumented) > 0:
                logger.debug('Undocumented test problems:')
            for undoc in undocumented:
                header += f'\n <li> {undoc} </li>'
                logger.debug(undoc)
            header += "\n</ul>\n"

        sp.write(header)

    def writeHeader(self, sp, refresh):
        gentime = time.strftime("%a, %d %b %Y %H:%M:%S")
        header = """
        <html>
         <head>
        """

        if refresh:
            header += f'  <META HTTP-EQUIV="refresh" CONTENT="{refresh}">'

        header += f"""  <title>Test results - generated on {gentime} </title>
          <style type="text/css">
           th, td {{
            font-family: "New Century Schoolbook", Times, serif;
            font-size: smaller ;
            vertical-align: top;
            background-color: #EEEEEE ;
           }}
           body {{
            font-family: "New Century Schoolbook", Times, serif;
            font-size: medium ;
            background-color: #FFFFFF ;
           }}
           table {{
            empty-cells: hide;
           }}

           .lightondark1 {{
               background-color: #888888;
               color:            white;
               font-size:        x-large;
           }}
           .lightondark2 {{
               background-color: #888888;
               color:            white;
               font-size:        large;
           }}
           .lightondark3 {{
               background-color: #888888;
               color:            white;
               font-size:        medium;
           }}

           th,td {{ background-color:#EEEEEE }}
           td.probname {{ background-color: #CCCCCC; font-size: large ; text-align: center}}
           td.red     {{ background-color: #E10000; color: white }}
           td.reddish {{ background-color: #FF6666; }}
           td.orange  {{ background-color: #FF9900; }}
           td.orangish{{ background-color: #FFBB44; }}
           td.yellow  {{ background-color: #EDED00; }}
           td.yellowish {{ background-color: #FFFF99; }}
           td.green   {{ background-color: #00C000; }}
           td.greenyellow {{background-color: #99FF00; }}
           td.blue    {{ background-color: #0000FF; color: white }}
           td.blueish {{ background-color: #33CCFF; }}
           th.red     {{ background-color: #E10000; color: white }}
           th.reddish {{ background-color: #FF6666; }}
           th.orange  {{ background-color: #FF9900; }}
           th.orangish{{ background-color: #FFBB44; }}
           th.yellow  {{ background-color: #EDED00; }}
           th.yellowish {{ background-color: #FFFF99; }}
           th.green   {{ background-color: #00C000; }}
           th.greenyellow {{background-color: #99FF00; }}
           th.blue    {{ background-color: #0000FF; color: white }}
           th.blueish {{ background-color: #33CCFF; }}
          </style>
         </head>
        <body>
        """

        # Notations:
        try:
            platform = socket.gethostname()
        except:
            logger.debug("Could not get host name")
            platform = "unknown"

        if os.name == "nt":
            username = os.getenv("USERNAME")
        else:
            username = os.getenv("USER")

        header += f"""
        <h2>
        <table border="2" cellpadding="2">
        <tr><td>
        Test results: {gentime}<br>
        User: {username}<br>
        Platform: {platform}<br>
        """

        for line in config.report_notations:
            header += f"{line}<br>"

        header += """</tr>
        </td>
        </table>
        </h2>
        """

        sp.write(header)

    def writeSummary(self, sp):
        summary = """
        <table border="2" cellpadding="2" caption="Summary">
         <tr><th colspan="3" class="lightondark1"> SUMMARY </th></tr>
         <tr>
          <th class="lightondark2"> STATUS </th>
          <th class="lightondark2"> COUNT  </th>
          <th class="lightondark2"> PROBLEM LIST </th>
         </tr>
        """

        haveRetry = False
        for status in STATUS:
            cases = self.groupResults[status]
            num = len(cases)
            summary += f"""
            <tr>
              <th class="{self.color[status]}">{self.displayName[status]}</th>
              <td> &nbsp;{num} </td>
              <td>
            """

            if num > 0:
                casestring = ' '
                for case in cases:
                    casename = case.name
                    caseref = case.name
                    retries = 0
                    for test in case.testcases:
                        retries += getattr(test.testcase.atsGroup, "retries", 0)
                    if retries > 0:
                        haveRetry = True
                        casename += '*'
                    summary += f'\n <a href="#{caseref}">{casename}</a> '
                summary += '\n'
                summary += casestring
            else:
                summary += '\n&nbsp;'

            summary += '\n</td></tr>'

        summary += '\n</table>'
        if haveRetry:
            summary += '\n* indicates that test was retried at least once.'

        sp.write(summary)

    # Write link to documentation for html
    def writeDoclink(self, sp):
        doc = """
        <p>
        Test problem names with a hyperlink have been documented,
        the HTML version of which can be viewed by clicking on the link.
        """

        testdoc = os.path.join(config.report_doc_dir, 'testdoc.html')
        testsumm = os.path.join(config.report_doc_dir, 'testdoc-summary.txt')
        if os.path.exists(testdoc) and os.path.exists(testsumm):
            doc += f"""
            <br>
            Or, you can <a href="{testdoc}">click here </a> for the
            main page, or <a href="{testsumm}"> here </a> for the
            one page text summary.  If the documentation appears out of
            date, rerun 'atddoc' in this directory.
            """

        doc += '\n</p>'
        sp.write(doc)

    def writeFooter(self, sp):
        footer = """
         </body>
        </html>
        """
        sp.write(footer)

    def browser(self):
        if ReportHTML.launchedBrowser:
            return

        if not config.browser:
            return

        ReportHTML.launchedBrowser = True
        command = config.browser_command.split()
        command.append("file:%s" % config.report_html_file)
        subprocess.Popen(command)


class ReportWait(ReportBase):
    """This class is used while with the report_wait config option"""

    def __init__(self, testcases):
        ReportBase.__init__(self, testcases)
        self.testcases = testcases

    def report(self, fp):
        """Write out the text report to the give file pointer"""
        import time

        start = time.time()
        sleeptime = 60    # interval to check (seconds)

        while True:
            notdone = []
            for t in self.testcases:
                t.testReport()
                report = ReportTestCase(t)
                if report.status in STATUS_NOTDONE:
                    notdone.append(t)

            if notdone:
                rr = ReportText(self.testcases)
                rr.writeSummary(sys.stdout,
                                (FAILRUN, UNEXPECTEDPASS, FAILRUNOPTIONAL, FAILCHECK, FAILCHECKMINOR, TIMEOUT, NOTRUN,
                                 INPROGRESS, FILTERED, PASS, EXPECTEDFAIL, SKIP, BATCH, NOTBUILT))
                time.sleep(sleeptime)
            else:
                break


class ReportTestCase(object):
    """This class represents the outcome from a TestCase.  It hides
    differences between off-line reports and the periodic reports
    (when the actual ATS test object is known).  In addition to
    determining the testcase outcome, it also notes the last TestStep
    that was run, age of the test, the total elapsed time and total
    resources used."""

    def __init__(self, testcase):

        self.testcase = testcase    # test_case
        self.status = None    # One of the STATUS values (e.g. FAILRUN, PASS, etc.)
        self.laststep = None
        self.diffage = None
        self.elapsed = 0.0
        self.resources = 0.0

        now = time.time()
        outcome = None
        teststatus = testcase.status

        # The following algorithm determines the outcome for this testcase by looking at the TestCase's status object.
        if teststatus is None:
            self.status = NOTRUN
            return
        elif teststatus in (FILTERED, SKIP):
            self.status = teststatus
            return
        else:
            for stepnum, step in enumerate(testcase.steps):

                # Get the outcome and related information from the TestStep.
                outcome, np, startTime, endTime = self._getStepInfo(step)

                if outcome == "PASS":
                    # So far so good, move on to the next step
                    dt = endTime - startTime
                    self.elapsed += dt
                    self.resources += np * dt
                    continue
                if outcome == "EXPT":
                    dt = endTime - startTime
                    self.elapsed += dt
                    self.resources += np * dt
                    outcome = "EXPECTEDFAIL"
                    self.status = EXPECTEDFAIL
                    break    # don't continue past an expected failure
                if outcome == "UNEX":
                    dt = endTime - startTime
                    self.elapsed += dt
                    self.resources += np * dt
                    outcome = "UNEXPECTEDPASS"
                    self.status = UNEXPECTEDPASS
                    break    # don't continue past an unexpected pass
                elif outcome == "SKIP":
                    self.status = SKIP
                    break
                elif outcome == "EXEC":
                    # the step is currently running, break
                    self.laststep = step
                    self.status = RUNNING
                    dt = now - startTime
                    self.elapsed += dt
                    self.resources += np * dt
                    break

                if outcome == "INIT" or outcome == "BACH":
                    if stepnum == 0:
                        # The TestCase is scheduled to run, but has not yet started.
                        if outcome == "BACH":
                            self.status = BATCH
                        else:
                            self.status = NOTRUN

                        break
                    else:
                        # At least one step in the TestCase has started (and passed), but nothing is running now.
                        self.status = INPROGRESS
                        self.laststep = step
                        if endTime:
                            self.diffage = now - endTime
                            dt = endTime - startTime
                            self.elapsed += dt
                            self.resources += np * dt
                        break
                elif outcome == "FILT":
                    # The test won't run because of a filter
                    self.status = FILTERED
                else:
                    # One of the failure modes.
                    self.laststep = step
                    if endTime:
                        self.diffage = now - endTime
                        dt = endTime - startTime
                        self.elapsed += dt
                        self.resources += np * dt
                    if outcome == "TIME":
                        self.status = TIMEOUT
                    elif self.laststep.isCheck():
                        if self.laststep.isMinor():
                            self.status = FAILCHECKMINOR
                        else:
                            self.status = FAILCHECK
                    else:
                        if self.laststep.isMinor():
                            self.status = FAILRUNOPTIONAL
                        else:
                            self.status = FAILRUN
                            try:
                                with open(step.p.stdout, 'r') as fp:
                                    for line in fp:
                                        if re.search(config.report_notbuilt_regexp, line):
                                            self.status = NOTBUILT
                                            break
                            except:
                                pass
                    break

        if outcome is None:
            self.status = NOTRUN

        if outcome == "PASS":
            # Don't set the laststep, but use it to get the endTime
            self.status = PASS
            laststep = step
            laststatus = teststatus.findStep(laststep)
            assert (laststatus)
            self.diffage = now - laststatus["endTime"]

        assert self.status in STATUS

    def _getStepInfo(self, teststep):
        """This function hides the differences between the TestStatus
        files and the information you can get from the ats test
        object.  It returns (status, np, startTime, endTime )"""

        atsTest = getattr(teststep, "atsTest", None)
        endTime = None
        startTime = None

        if atsTest is not None:
            status = str(atsTest.status)
            startTime = getattr(atsTest, "startTime", None)
            endTime = getattr(atsTest, "endTime", None)
            if status == "PASS" and atsTest.expectedResult == ats.FAILED:
                status = "FAIL"
            if status == "FAIL" and atsTest.expectedResult == ats.FAILED:
                status = "UNEX"
        else:
            stepstatus = self.testcase.status.findStep(teststep)
            if stepstatus is None:
                status = "INIT"
            else:
                status = stepstatus["result"]
                startTime = stepstatus["startTime"]
                endTime = stepstatus["endTime"]

        np = getattr(teststep.p, "np", 1)

        if status in ("SKIP", "FILT", "INIT", "PASS", "FAIL", "TIME", "EXEC", "BACH", "EXPT", "UNEX"):
            return (status, np, startTime, endTime)
        else:
            return ("SKIP", np, startTime, endTime)


class ReportGroup(object):
    """A class to represent a group of TestCases.  Currently, the only
    grouping done is at the directory level: every testcase in a
    directory belongs to the same ReportGroup."""

    def __init__(self, groupName, testcases):
        self.name = groupName
        self.testcases = testcases
        self.status = NOTRUN
        if self.testcases:
            self.status = min([case.status for case in self.testcases])
        assert self.status in STATUS

    def __cmp__(self, other):
        return self.name == other.name


def getowner(dirname, testcase=None):
    owner = ""
    if not config.report_doc_link:
        try:
            atdfile = os.path.join(config.report_doc_dir, dirname, dirname + ".atd")
            with open(atdfile, "r") as fp:
                for line in fp:
                    match = re.search("CUSTODIAN:: +(.*)$", line)
                    if not match:
                        owner = match.group(1)
                        break
        except IOError as e:
            logger.debug(e)
    if owner == "" and testcase and ("owner" in testcase.dictionary):
        return testcase.dictionary["owner"]
    return owner

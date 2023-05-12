
import os
import sys
import subprocess

########################################################################
#  MachineConfig
########################################################################
class MachineConfig(object):
    """A base class for machine specific configuration"""
    
    name = "Unknown"
    
    def __init__(self):
        self.clientroot = relpath("..")
        self.geosx = None
        self.version = None    # None or a tuple of ints (e.g. self.version = (4,16,6) )
        self.platformConfig = None # None or a string
        self.geosx = None


    def setGeosxPath(self, defaultSubdir):
        """Determine and set the path to geosx"""
        self.geosx = os.path.join(defaultSubdir, "geosx")
        config.geosx_executable = self.geosx
        self.setGeosxData()


    def setGeosxData( self ):
        """Set the machine data that requires geosx to be set (called by setGeosxPath)"""
        self.version = self.getGeosxVersion()
        self.platformConfig = self.getGeosxPlatformConfig()

        if self.version:
            config.report_notations.append( "geosx version : %s" % (".".join(str(x) for x in self.version) ) )
        else:
            config.report_notations.append( "geosx version : Unknown" )

        config.report_notations.append("geosx path : %s" % self.geosx)
        if not os.path.exists(self.geosx):
            config.report_notations.append("Warning: the geosx executable does not exist")

        if self.platformConfig:
            config.report_notations.append("config : %s" % self.platformConfig) 
        else:
            config.report_notations.append("config : Unknown")


    def isMatch( self ):
        """return True if this machines matches the platform and the geosx passed into the constructor"""
        return False


    def setup( self ): 
        """setup configuration for this machine, assuming isMatch returned True"""
        config.machine_options.append('--numNodes=%d' % options.numNodes )
        

    def setupChecks(self):
        """Setup additional configuration to do the checks, such as the baseline directory"""
        # config.silocheck_silodiff = os.path.join("/usr","gapps","silo","current","chaos_5_x86_64_ib","bin","silodiff")
        # config.visit_executable = os.path.join("/usr", "gapps", "visit", "bin", "visit")


    def command( self ):
        """Command-line to run geosx -V"""
        return [self.geosx, "-V"]


    def geosxV( self ):
        """Call geosx, and get its verbose information"""

        if self.geosxv:
            return self.geosxv

        command = self.command()
        try:
            p = subprocess.Popen( command,
                                  stdout = subprocess.PIPE,
                                  stderr = subprocess.STDOUT)
        except Exception, e:
            return []

        out = p.communicate()[0]
        if p.returncode != 0:
            return []

        self.geosxv = out.split("\n")
        return self.geosxv


    def getGeosxPlatformConfig(self):
        return None
    

    # def getALE3DPlatformConfig( self ):
    #     """Find the platform configuration"""
    #     lines = self.geosxV()
    #     for l in lines:
    #         if l.startswith("Platform config"):
    #             toks = l.split()
    #             if len(toks) < 4:
    #                 return None
    #             return toks[3]

    #     return None

    def getCompiler( self ):
        config = self.getGeosxPlatformConfig()
        if config:
           configArray = config.split('-')
           if len(configArray) > 1:
              return configArray[1]
        return ""
    
    def getPlatformSuffix( self ):
        config = self.getGeosxPlatformConfig()
        if config:
           configArray = config.split('-', 2)
           if len(configArray) > 2:
              return configArray[2]
        return ""
    
    def getSysType( self ):
        """Return the SysType, used to find the baseline directory"""
        return os.getenv("SYS_TYPE", "" )

    def getCPU( self ):
        """Return the CPU type, used to find the baseline directory"""
        return ""
    

    def getGeosxVersion( self ):
        return None

    # def getALE3DVersion( self ):
    #     """Find the geosx version"""
    #     lines = self.geosxV()
    #     if not lines:
    #         return None

    #     for l in lines:
    #         if l.startswith("ALE3D"):
    #             line0 = l
    #             toks = line0.split()
    #             break

    #     if len(toks) < 4:
    #         return None
    #     try:
    #         version = toks[3][1:] # get rid of the v
    #         versions = [int(x) for x in  version.split(".")]
    #         return versions
    #     except:
    #         return None


########################################################################
#  SlurmProcessorScheduled
########################################################################
class Config_SlurmProcessorScheduled(MachineConfig):

    name = "SlurmProcessorScheduled"
    
    def __init__(self):
        MachineConfig.__init__(self)

    def getCPU( self ):
        """Return the CPU type, used to find the baseline directory"""
        return "IntelXeon"

    def isMatch(self):
        systype = self.getSysType()
        if systype in ['chaos_4_x86_64_ib', 'chaos_5_x86_64_ib', 'toss_3_x86_64_ib', 'toss_4_x86_64_ib']:
            return True
        return False

    def setup(self):

        MachineConfig.setup(self)
        
        config.script_launch = 1

        systype = self.getSysType()
        if os.getenv("BATCH_TYPE", None) is None:
            if systype in ['chaos_4_x86_64_ib', 'chaos_5_x86_64_ib', 'toss_3_x86_64_ib', 'toss_4_x86_64_ib']:
                os.environ["BATCH_TYPE"] = "batchGeosxatsMoab"

        # assuming mvapich
        config.environment["VIADEV_USE_SHMEM_COLL"] = "0"
        config.environment["PSM_RANKS_PER_CONTEXT"] = "4"
        # assuming mvapich2
        config.environment["MV2_USE_SHMEM_COLL"] = "0"

class Config_GeosxAtsSlurmProcessorScheduled(Config_SlurmProcessorScheduled):

    name = "GeosxAtsSlurmProcessorScheduled"

    def __init__(self):
        Config_SlurmProcessorScheduled.__init__(self)

########################################################################
#  NERSC
########################################################################
class Config_nersc(Config_GeosxAtsSlurmProcessorScheduled):

    name = "Nersc"

    def isMatch(self):
        return os.getenv("NERSC_HOST", None) is not None


########################################################################
#  openmpi
########################################################################
class Config_openmpi(MachineConfig):

    name = "openmpi"
    
    def __init__(self):
        MachineConfig.__init__(self)

    def getInstallDir(self):
         if "openmpi_install" not in configOverride:
             return os.path.join("/usr", "apps", "geosx",
                                 "packages.icc91-x86-64-openmpi-tcp",
                                 "openmpi", "1.4.3")
         else:
             return config.openmpi_install

    def getPrecommand(self):
        systype = self.getSysType()
        if "openmpi_precommand" not in configOverride:
            if systype in ['chaos_4_x86_64_ib', 'chaos_5_x86_64_ib', 'toss_3_x86_64_ib', 'toss_4_x86_64_ib']:
                return "salloc -J %(J)s -n %(np)s -ppdebug"
            return ""
        else:
            return config.openmpi_precommand
        
    def command(self):
        install = self.getInstallDir()
        mpirun = os.path.join(install, "bin", "mpirun" )
        precommand = self.getPrecommand() 
        if precommand:
            d = { "np": 1, "J": "mpirun" }
            precommand = precommand % d
            return precommand.split() + [mpirun, self.geosx, "-V"]
        else:
            return [mpirun, self.geosx, "-V"]
    
    def isMatch(self):
        # openmpi machine must always be explicitly specified
        return False

    def setup(self):

        MachineConfig.setup(self)
        systype = self.getSysType()
        
        if "openmpi_install" not in configOverride:
            config.openmpi_install = self.getInstallDir()
        if "openmpi_args" not in configOverride:
            if systype in ['chaos_4_x86_64_ib', 'chaos_5_x86_64_ib', 'toss_3_x86_64_ib', 'toss_4_x86_64_ib']:
               config.openmpi_args = "--bind-to none"
        if "openmpi_terminate" not in configOverride:
            if systype in ['chaos_4_x86_64_ib', 'chaos_5_x86_64_ib', 'toss_3_x86_64_ib', 'toss_4_x86_64_ib']:
               config.openmpi_terminate = "scancel -n %(J)s"
            
        config.openmpi_precommand = self.getPrecommand()
           
        config.machine_options.append('--numNodes=%d' % options.numNodes )
        config.machine_options.append('--procsPerNode=%d' % config.openmpi_procspernode )
        config.machine_options.append('--maxProcs=%d' % config.openmpi_maxprocs )
        config.machine_options.append('--openmpi_precommand=%s' % config.openmpi_precommand )
        config.machine_options.append('--openmpi_install=%s' % config.openmpi_install )
        config.machine_options.append('--openmpi_args=%s' % config.openmpi_args)
        config.machine_options.append('--openmpi_terminate=%s' % config.openmpi_terminate)

        if os.getenv("BATCH_TYPE", None) is None:
            if systype in ['chaos_4_x86_64_ib', 'chaos_5_x86_64_ib', 'toss_3_x86_64_ib', 'toss_4_x86_64_ib']:
                os.environ["BATCH_TYPE"] = "batchGeosxatsMoab"


########################################################################
#  cray
########################################################################
class Config_cray(MachineConfig):

    name = "cray"
    
    def __init__(self):
        MachineConfig.__init__(self)

    def command(self):
        return ["aprun", self.geosx, "-V"]
    
    def isMatch(self):
        if "cray" in os.uname()[2]:
             return True

        return False

    def setup(self):
        MachineConfig.setup(self)

        

########################################################################
#  dawnHTC
########################################################################
class Config_dawnHTC(MachineConfig):

    name = "dawnHTC"

    def __init__(self):
        MachineConfig.__init__(self)

    def isMatch(self):
        systype = self.getSysType()
        if systype in  ['sles_10_ppc64']:
            return True
        return False

    def setup(self):
        MachineConfig.setup(self)
        
        pass

########################################################################
#  bgqos_0
########################################################################
class Config_bgqos_0(MachineConfig):

    name = "bgqos_0_ASQ"

    def __init__(self):
        MachineConfig.__init__(self)

    def command(self):
        srun = os.path.join("/usr", "bin", "srun" )
        return [srun, "-ppdebug", self.geosx, "-V"]
    
    def getCPU( self ):
        """Return the CPU type, used to find the baseline directory"""
        return "PPC_A2"

    def isMatch(self):
        systype = os.getenv('SYS_TYPE', "")
        if systype in  ['bgqos_0']:
            return True
        return False

    def setup(self):
        MachineConfig.setup(self)
        
        pass

########################################################################
#  lassen
########################################################################
class Config_lassen(MachineConfig):

    name = "lassen"

    def isMatch(self):
        systype = os.getenv('SYS_TYPE', "")
        return systype == 'blueos_3_ppc64le_ib_p9'

########################################################################
#  summit
########################################################################
class Config_summit(MachineConfig):

    name = "summit"

    def isMatch(self):
        return os.getenv('LMOD_SYSTEM_NAME', "") == "summit"

######################################################################
#  darwin (OS X)
######################################################################

class Config_darwin(Config_openmpi):
    from os.path import expanduser
    home = expanduser("~")

    name = "darwin"

    def __init__(self):
        MachineConfig.__init__(self)

    def getInstallDir(self):
         if "openmpi_install" not in configOverride:
             return os.path.join( os.environ.get('MPORTS_PATH','/opt/local') )
         else:
             return config.openmpi_install

    def getCPU( self ):
        try:
           sysctl = subprocess.check_output(['/usr/sbin/sysctl', "-n", "machdep.cpu.brand_string"]).strip()
           if all(x in sysctl for x in ['Intel', 'Core', 'i7']):
               return "IntelCorei7"
        except:
           pass
        return ""

    def getSysType( self ):
        return "osx"

    def getCompiler( self ):
        config = self.getALE3DPlatformConfig()
        if config:
           configArray = config.split('-')
           if len(configArray) > 2:
              return configArray[2]
        return ""

    def isMatch(self):
        return sys.platform == 'darwin'

    def setup(self):
        Config_openmpi.setup(self)

        # Set the ALEATS_NO_YOGRT environment variable to suppress the 2nd timelimit update test
        if not os.environ.get("ALEATS_NO_YOGRT"):
            os.environ['ALEATS_NO_YOGRT'] = '1'

        # Switch to mpiexec so we can set a timelimit:
        config.machine_options.append("--openmpi_mpirun=%s" % "mpiexec")

        # Set a timelimit for each test to prevent hanging at errors:
        maxTimeInMins = 10
        if 'smoke' in os.getcwd():
            maxTimeInMins = 2

        os.environ['MPIEXEC_TIMEOUT'] = str(maxTimeInMins*60) # seconds

        # Add the path to the local repo's copy of ncdump and ncgen for the tetBrick test:
        os.environ['PATH'] += ":" + os.path.join(self.clientroot, "imports", "netcdf", "ncdump")
        os.environ['PATH'] += ":" + os.path.join(self.clientroot, "imports", "netcdf", "ncgen")

        # If a public install is set up, add its copy of ncdump and ncgen:
        if 'ALE3D_LIBRARIES_BASE' in os.environ:
            # Get the version number for netcdf:
            with open(os.path.join(self.clientroot, "host-configs", "BaseLibraryInfo.cmake")) as f:
                for line in f:
                    if "NETCDF_VER" in line:
                        # Line should look like: set(NETCDF_VER         "3.6.3a" CACHE PATH "")
                        sline = line.strip() # Just in case white space gets added
                        netcdf_ver = sline.split('"')[1]
                        break

            # Add the bin path:
            os.environ['PATH'] += ":" + os.path.join(os.environ['ALE3D_LIBRARIES_BASE'], "netcdf", netcdf_ver, "bin")

        # Store the path to multitable for the tests that use it:
        os.environ['ALEATS_MULTITABLE_FILE_PATH'] = os.path.join(self.clientroot, "offsiteDataFiles", "multitable.h5")

    def setupChecks(self):
        Config_openmpi.setupChecks(self)
        config.gnuplot_executable=os.path.join( os.environ.get('MPORTS_PATH','/opt/local'), "bin", "gnuplot" )
        # config.silocheck_silodiff=os.path.join(self.clientroot, "imports", "silo", "tools", "browser", "silodiff")

        # Using these values as a first pass before rebaselining (left here for reference):
        #config.curvecheck_relative = 1e-3
        #config.curvecheck_absolute = 1e-3

        
        
        

########################################################################
#  winParallel
########################################################################
class Config_winParallel(MachineConfig):

    name = "winParallel"

    def __init__(self):
        MachineConfig.__init__(self)

    def setGeosxPath( self, defaultSubdir = ""):
        """Determine and set the path to geosx"""

        if "executable_path" not in configOverride:
            if "--nompi" in options.ats :
                config.executable_path = os.path.realpath(os.path.join(self.clientroot,"src","Win32","x64","Debug"))
            else :
                config.executable_path = os.path.realpath(os.path.join(self.clientroot,"src","Win32","x64","ParRelease"))
        if "userscript_path" not in configOverride:
            config.userscript_path = os.path.join(self.clientroot, "userscripts")

        self.geosx = os.path.join(config.executable_path, "geosx.exe" )

        config.geosx_udf_path = config.executable_path

        self.setGeosxData()
        

    def isMatch(self):
        if os.name == "nt":
            return True
        return False

    def setup(self):

        """setup configuration for this machine, assuming isMatch returned True"""

        if "windows_mpiexe" not in configOverride:
            config.windows_mpiexe = os.getenv("VISIT_MPIEXEC",
                os.path.join("c:\\", "Program Files", "Microsoft HPC Pack 2008 R2", "Bin", "mpiexec.exe"))

        config.machine_options.append('--numNodes=%d' % options.numNodes )
        if config.windows_nompi:
            config.machine_options.append('--nompi' )
        config.machine_options.append('--oversubscribe=%s' % config.windows_oversubscribe )
        config.machine_options.append('--mpiexe=%s' % config.windows_mpiexe )

    def setupChecks(self):
        
        MachineConfig.setupChecks(self)
        # config.silocheck_silodiff = os.path.join("C:\\","a3d","browser","silodiff_ats.bat")
        # config.visit_executable = os.path.join(os.getenv("VISITLOC",
        #        os.path.join("C:\\", "Program Files", "LLNL", "Visit 2.12.3")),"visit.exe")
        config.gnuplot_executable = os.path.join("C:\\", "Program Files", "gnuplot", "bin", "gnuplot.exe")

    
########################################################################
#  handleMachineType
########################################################################        
def handleMachineType( ):
    """Determine the correct machinetype, and related options"""
    
    SupportedMachines = (Config_GeosxAtsSlurmProcessorScheduled,
                         Config_SlurmProcessorScheduled,
                         Config_nersc,
                         Config_dawnHTC,
                         Config_bgqos_0,
                         Config_lassen,
                         Config_summit,
                         Config_darwin,
                         Config_winParallel,
                         Config_cray,
                         Config_openmpi)

    # if the machineType is not specified on the command line
    # look in the environment variable
    
    if options.machineType is None:
        options.machineType = os.getenv("MACHINE_TYPE", None)

    # If the machineType is still None, then attempt to detemine it
    # though os.name, systype or other means (isMatch)
    if options.machineType is None:
        for MachineConfigType in SupportedMachines:
            machine = MachineConfigType()
            if machine.isMatch():
                options.machineType = machine.name
                machine.setup()
                machine.setupChecks()
                return machine

        machine = MachineConfig() 
        options.machineType = machine.name 
        return machine


    else:
        for MachineConfigType in SupportedMachines:
            if options.machineType == MachineConfigType.name:
                machine = MachineConfigType()
                machine.setup()
                machine.setupChecks()
                return machine

        machine = MachineConfig() 
        return machine

machine = handleMachineType( )

config.report_notations.append("machine : %s" % machine.name)
config.report_notations.append("directory : %s" % os.getcwd())
    
try:
   # testSuite must be set in the testconfig in the subdirectory (e.g. update/testconfig.py)
   config.report_doc_dir = (relpath (os.path.join(testSuite,"doc")))
   # FIXME This may need to be adjusted
   config.report_notations.append("suite = %s" % testSuite.capitalize())
   platformConfigDir = relpath(os.path.join(testSuite,"platformConfig"))
except:
   # This is for compatibility with old testconfig files.
   platformConfigDir = None

if platformConfigDir and os.path.exists(platformConfigDir):
   # Source the appropriate platform config (if not already specified)
   havePlatformFile = False

   for cfile in configfiles:
      # If a file in the config file stack is in the platform config directory
      # for this suite, the user must have specified the platform config file.
      # We do not have to source another one, as it will be read after its
      # parent (i.e. this file).
      if os.path.realpath(cfile).startswith(os.path.realpath(platformConfigDir)):
         havePlatformFile = True
         break

   if not havePlatformFile:
      if os.name == 'nt' :
         platform = 'nt'
      elif sys.platform == 'darwin':
         platform = 'darwin'
      else:
         platform = machine.getSysType()

      if platform == 'bgqos_0':
         defaultPlatformConfig = os.path.join("bgq_clang","PPC_A2")
      elif platform == 'chaos_5_x86_64_ib':
         defaultPlatformConfig = os.path.join("chaos_5_x86_64_ib_icc15")
      elif platform == 'toss_3_x86_64_ib':
         defaultPlatformConfig = os.path.join("toss_3_x86_64_ib_icc16")
      elif platform == 'toss_4_x86_64_ib':
         defaultPlatformConfig = os.path.join("toss_4_x86_64_ib")
      elif platform == 'darwin':
         defaultPlatformConfig = os.path.join("osx_gcc", "IntelCorei7")
      else:
         defaultPlatformConfig = os.path.join(platform)

      if not os.path.exists(os.path.join(platformConfigDir, defaultPlatformConfig, "testconfig.py" )):
         print "No platform configuration exists for %s in %s." % (platform, testSuite)
         # This is the platform configuration to use if no configuration exists for the platform.
         defaultPlatformConfig = os.path.join("toss_3_x86_64_ib_icc16")

      print "Using platform configuration %s." % defaultPlatformConfig
      sourceConfig( os.path.join(platformConfigDir, defaultPlatformConfig, "testconfig.py" ) )

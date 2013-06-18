#!/usr/bin/python
# Ian Rees, 2012
#
# This is a new version of the EMAN2 build and post-install package management system.
# The original version was a collection of shell scripts, with various scripts for
# setting configuration information, CVS checkout, build, package, upload, etc., run
# via a cron job. 
#
# This script expects the following directory layout:
# 
#   <target>/
#       co/
#           <cvsmodule>.<cvstag>/                               EMAN2 source from CVS, e.g. "eman2.daily", "eman2.EMAN2_0_5"
#       local/                
#           [lib,bin,include,doc,share,qt4,...]                 PREFIX for dependency library installs -- think /usr/local
#       extlib/
#           <cvsmodule>.<cvstag>/[lib,bin,site-packages,...]    Stripped down copy of local/ that only includes required libraries.
#       build/
#           <cvsmodule>.<cvstag>/                               CMake configure and build directory
#       stage/
#           <cvsmodule>.<cvstag>/                               Staging area for distribution
#               EMAN2/[bin,lib,extlib,...]                      EMAN2 installation
#       images/                                                 Completed, packaged distributions
#

import os
import re
import shutil
import subprocess
import glob
import datetime
import argparse

VERSION = 1.1

##### Helper functions #####

def log(msg):
    print "=====", msg, "====="

def find_exec(root='.'):
    """Find executables (using +x permissions)."""
    # find . -type f -perm +111 -print
    p = check_output(['find', root, '-type', 'f', '-perm', '+111'])
    # unix find may print empty lines; strip those out.
    return filter(None, [i.strip() for i in p.split("\n")])

def find_ext(ext='', root='.'):
    """Find files with a particular extension. Include the ".", e.g. ".txt". """
    found = []
    for root, dirs, files in os.walk(root):
        found.extend([os.path.join(root, i) for i in files if i.endswith(ext)])
    return found

def mkdirs(path):
    """mkdir -p"""
    if not os.path.exists(path):
        os.makedirs(path)
  
def rmtree(path):
    """rm -rf"""
    if os.path.exists(path):
        shutil.rmtree(path)

def retree(path):
    """rm -rf; mkdir -p"""
    if os.path.exists(path):
        shutil.rmtree(path)
    if not os.path.exists(path):
        os.makedirs(path)  
    
def cmd(*popenargs, **kwargs):
    print "Running:", 
    print " ".join(*popenargs)
    process = subprocess.Popen(*popenargs, **kwargs)
    process.wait()  
    
def echo(*popenargs, **kwargs):
    print " ".join(popenargs)    
    
def check_output(*popenargs, **kwargs):
    """Copy of subprocess.check_output()"""
    if 'stdout' in kwargs:
        raise ValueError('stdout argument not allowed, it will be overridden.')
    process = subprocess.Popen(stdout=subprocess.PIPE, *popenargs, **kwargs)
    output, unused_err = process.communicate()
    retcode = process.poll()
    if retcode:
        cmd = kwargs.get("args")
        if cmd is None:
            cmd = popenargs[0]
        raise subprocess.CalledProcessError(retcode, cmd)            
    return output




##### Targets #####

class Target(object):
    """Target-specific configuration and build commands."""

    # All these attrs will be copied into the args Namespace.
    python = '/usr/bin/python'

    # Used in the final archive filename
    target_desc = 'source'

    # These will be turned back into file references...
    # INSTALL.txt
    installtxt = """Instructions for installing EMAN2."""
    # eman2.bashrc
    bashrc = "#!/bin/sh"
    # eman2.cshrc
    cshrc = "#!/bin/csh"
    
    def __init__(self, args):
        args = self.update_args(args)
        args = self.update_cwds(args)
        self.args = args
        # print "Updated args:"
        # for k,v in sorted(vars(args).items()): print k, v, "\n\n"

    def update_args(self, args):
        # Add a bunch of attributes to the args Namespace
        args.python = self.python
        args.distname = '%s.%s'%(args.cvsmodule, args.cvstag)
        args.installtxt = self.installtxt
        args.bashrc = self.bashrc
        args.cshrc = self.cshrc
        args.target_desc = self.target_desc
        return args

    def update_cwds(self, args):
        # Find a nicer way of doing this.
        # I just want to avoid excessive duplicate os.join()
        # calls in the main code, because each one is a chance for an error.        
        args.cwd_co           = os.path.join(args.root, 'co')
        args.cwd_co_distname  = os.path.join(args.root, 'co',      args.distname)
        args.cwd_extlib       = os.path.join(args.root, 'extlib',  args.distname)
        args.cwd_build        = os.path.join(args.root, 'build',   args.distname)
        args.cwd_images       = os.path.join(args.root, 'images',  args.distname)
        args.cwd_stage        = os.path.join(args.root, 'stage',   args.distname)
        args.cwd_rpath        = os.path.join(args.root, 'stage',   args.distname, args.cvsmodule.upper())
        args.cwd_rpath_extlib = os.path.join(args.cwd_rpath, 'extlib')
        args.cwd_rpath_lib    = os.path.join(args.cwd_rpath, 'lib')        

        # OS X links using absolute pathnames; update these to @rpath macro.
        # This dictionary contains regex sub keys/values
        # that will be used to process the output
        # from otool -L.
        args.replace = {
            # The basic paths
            '^%s/local/'%(args.root): '@rpath/extlib/',
            '^%s/build/%s/'%(args.root, args.distname): '@rpath/',
            # Boost's bjam build doesn't set install_name
            '^libboost_python.dylib': '@rpath/extlib/lib/libboost_python.dylib',
            # Same with EMAN2.. for now..
            '^libEM2.dylib': '@rpath/lib/libEM2.dylib',
            '^libGLEM2.dylib': '@rpath/lib/libGLEM2.dylib',
        }
        return args
        
    def _run(self, commands):
        # Run a series of Builder commands
        for c in commands:
            # pass the args Namespace to the Builder.
            c(self.args).run()

    def run(self, commands):
        for i in commands:
            getattr(self, i)()
        
    def checkout(self):
        self._run([Checkout])

    def build(self):
        self._run([CMakeBuild])
    
    def install(self):
        self._run([FixLinks, FixInterpreter, CopyShrc, CopyExtlib, FixInstallNames])
       
    def package(self):
        raise NotImplementedError
        
    def upload(self):
        raise NotImplementedError
    
        

class MacTarget(Target):
    """Generic Mac target."""
    
    installtxt = """Welcome to EMAN2 for Mac OS X.

    Installing EMAN2 is simple. 

    If clarification of any step is needed, we have created a visual guide with screenshots in the EMAN2 wiki:
        http://blake.grid.bcm.edu/emanwiki/EMAN2/Install/BinaryInstall_OSXVisualGuide

    1. Copy the "EMAN2" folder to /Applications.

    2. If you use the bash shell, add the following line to your ".profile" file:
            test -r /Applications/EMAN2/eman2.bashrc && source /Applications/EMAN2/eman2.bashrc
        Similarly, if you use the csh shell, add the following line to ".cshrc":
            test -r /Applications/EMAN2/eman2.cshrc && source /Applications/EMAN2/eman2.cshrc
        (one way to open your .profile file is to run "touch ~/.profile; open -e ~/.profile" in the Terminal.)

    3. Restart your terminal program for a fresh shell. EMAN2 should now be installed and function properly.

    Please visit the EMAN2 homepage at http://blake.bcm.tmc.edu/emanwiki/EMAN2 for usage documentation.
    """    
    
    bashrc = """#!/bin/sh
    export EMAN2DIR=/Applications/EMAN2/
    export PATH=$EMAN2DIR/bin:$EMAN2DIR/extlib/bin:$PATH
    export PYTHONPATH=$EMAN2DIR/lib:$EMAN2DIR/bin:$EMAN2DIR/extlib/site-packages:$PYTHONPATH
    """

    cshrc = """#!/bin/csh
    setenv EMAN2DIR /Applications/EMAN2
    set path=(${EMAN2DIR}/bin ${EMAN2DIR}/extlib/bin $path)
    if ( $?PYTHONPATH ) then
    else
    setenv PYTHONPATH
    endif
    setenv PYTHONPATH ${EMAN2DIR}/lib:${EMAN2DIR}/bin:${EMAN2DIR}/extlib/site-packages:${PYTHONPATH}
    """    
    
    def build(self):
        self._run([CMakeBuild])
    
    def install(self):
        self._run([FixLinks, FixInterpreter, CopyShrc, CopyExtlib, FixInstallNames])
        
    def package(self):
        self._run([MacPackage])
    
    def upload(self):
        self._run([MacUpload])


class SnowLeopardTarget(MacTarget):
    python = "/usr/bin/python2.6"
    target_desc = 'snowleopard'
    
    
class LionTarget(MacTarget):
    python = "/usr/bin/python2.7"
    target_desc = 'lion'


class LinuxTarget(Target):
    bashrc = """#!/bin/sh
    export EMAN2DIR=$HOME/EMAN2/
    export PATH=$EMAN2DIR/bin:$EMAN2DIR/extlib/bin:$PATH
    export PYTHONPATH=$EMAN2DIR/lib:$EMAN2DIR/bin:$EMAN2DIR/extlib/site-packages:$PYTHONPATH
    export LD_LIBRARY_PATH=$EMAN2DIR/lib:$EMAN2DIR/extlib/lib:$EMAN2DIR/extlib/qt4/lib:$EMAN2DIR/extlib/python/lib:$LD_LIBRARY_PATH
    """

    def install(self): 
        self._run([CopyShrc, CopyExtlib])
       


class Linux64Target(LinuxTarget):
    pass 
    


# TODO: Use a register() type system.
TARGETS = {
    'i686-apple-darwin10': SnowLeopardTarget,
    'i686-apple-darwin11': LionTarget,
    'i686-redhat-linux': LinuxTarget,
    'x86_64-redhat-linux': Linux64Target
}
    


##### Builder Modules #####

class Builder(object):
    """Build step."""
    
    def __init__(self, args):
        # Reference to Target configuration args Namespace
        self.args = args
    
    #@abstractmethod
    def run(self):
        """Each builder class must implement run()."""
        return NotImplementedError
        
        
# Checkout command.
class Checkout(Builder):
    """Checkout module from CVS."""
    
    def run(self):
        log("Checking out: %s -r %s"%(self.args.cvsmodule, self.args.cvstag))

        print("Removing previous checkout: %s"%self.args.cwd_co_distname)
        retree(self.args.cwd_co_distname)
        
        cvs = ['cvs', '-d', self.args.cvsroot, 'co', '-d', self.args.distname]
        if self.args.cvstag != 'daily':
            cvs.extend(['-r', self.args.cvstag])

        cvs.append(self.args.cvsmodule)
        cmd(cvs, cwd=self.args.cwd_co)


# Build sub-command.
class CMakeBuild(Builder):
    """Run cmake, build, and install."""
    def run(self):
        log("Building")
        
        print("Removing previous install: %s"%self.args.cwd_stage)
        retree(self.args.cwd_stage)

        print("Running cmake")
        cmd(['cmake', self.args.cwd_co_distname], cwd=self.args.cwd_build)
        
        if self.args.clean:
            print("Running make clean")
            cmd(['make', 'clean'], cwd=self.args.cwd_build)
        
        print("Running make")
        cmd(['make'], cwd=self.args.cwd_build)
        
        print("Running make install")
        cmd(['make', 'install'], cwd=self.args.cwd_build)
        

# Build sub-command.
class CopyExtlib(Builder):
    def run(self):
        log("Copying dependencies")
        # print self.args.cwd_extlib, "->", self.args.cwd_rpath_extlib
        try:
            shutil.copytree(self.args.cwd_extlib, self.args.cwd_rpath_extlib, symlinks=True)        
        except:
            pass


# Build sub-command.
class CopyShrc(Builder):
    def run(self):
         log("Copying INSTALL.txt and shell rc files")
         mkdirs(os.path.join(self.args.cwd_stage))
         mkdirs(os.path.join(self.args.cwd_rpath))
         with open(os.path.join(self.args.cwd_stage, 'INSTALL.txt'), 'w') as f:
             f.write(self.args.installtxt)
         with open(os.path.join(self.args.cwd_rpath, 'eman2.bashrc'), 'w') as f:
             f.write(self.args.bashrc)
         with open(os.path.join(self.args.cwd_rpath, 'eman2.cshrc'), 'w') as f:
             f.write(self.args.cshrc)


# Build sub-command.
class FixInterpreter(Builder):
    """Fix the Python interpreter to point to /usr/bin/python<version>."""
    def run(self):
        log("Fixing Python interpreter hashbang")
        # Add sparx script; find a way to have it found automatically.
        sparx = os.path.join(self.args.cwd_rpath, 'bin', 'sparx') 
        for i in find_ext('.py', root=self.args.cwd_rpath) + [sparx]:
            # print i
            with open(i) as f:
                data = f.readlines()
            if data and data[0].startswith("#!") and "python" in data[0]:
                data[0] = "#!%s\n"%self.args.python
                with open(i, "w") as f:
                    f.writelines(data)


# Build sub-command. Mac specific.
class FixLinks(Builder):
    def run(self):
        log("Creating .dylib -> .so links for Python")
        # Need to set the current working directory for os.symlink
        cwd = os.getcwd()
        os.chdir(self.args.cwd_rpath_lib)
        for f in glob.glob("*.dylib"):
            # print f, "->", f.replace(".dylib", ".so")
            try:
                os.symlink(f, f.replace(".dylib", ".so"))
            except:
                pass
        os.chdir(cwd)

        
# Build sub-command. Mac specific.
class FixInstallNames(Builder):
    """Process all binary files (executables, libraries) to rename linked libraries."""
    
    def find_deps(self, filename):
        """Find linked libraries using otool -L."""
        p = check_output(['otool','-L',filename])
        # otool doesn't return an exit code on failure, so check..
        if "not an object file" in p:
            raise Exception, "Not Mach-O binary"
        # Just get the dylib install names
        p = [i.strip().partition(" ")[0] for i in p.split("\n")[1:]]
        return p

    def id_rpath(self, filename):
        """Generate the @rpath for a file, relative to the current directory as @rpath root."""
        p = len(filename.split("/"))-1
        f = os.path.join("@loader_path", *[".."]*p)
        return f

    def run(self):
        log("Fixing install_name")
        cwd = os.getcwd()
        os.chdir(self.args.cwd_rpath)       
 
        # Find all files that end in .so/.dylib, or are executable
        # This will include many script files, but we will ignore
        # these failures when running otool/install_name_tool
        targets = set()
        targets |= set(find_ext('.so', root=self.args.cwd_rpath))
        targets |= set(find_ext('.dylib', root=self.args.cwd_rpath))
        targets |= set(find_exec(root=self.args.cwd_rpath))

        for f in sorted(targets):
            # Get the linked libraries and
            # check if the file is a Mach-O binary
            try:
                libs = self.find_deps(f)
            except Exception, e:
                continue

            # print f
            # Strip the absolute path down to a relative path
            frel = f.replace(self.args.cwd_rpath, "")[1:]

            # Set the install_name.
            install_name_id = os.path.join('@rpath', frel)
            # print "\tsetting id:", install_name_id
            cmd(['install_name_tool', '-id', install_name_id, f])

            # Set @rpath, this is a reference to the root of the package.
            # Linked libraries will be referenced relative to this.
            rpath = self.id_rpath(frel)
            # print "\tadding @rpath:", rpath
            try: cmd(['install_name_tool', '-add_rpath', rpath, f])
            except: pass

            # Process each linked library with the regexes in REPLACE.
            for lib in libs:
                olib = lib
                for k,v in self.args.replace.items():
                    lib = re.sub(k, v, lib)
                if olib != lib:
                    # print "\t", olib, "->", lib
                    try: cmd(['install_name_tool', '-change', olib, lib, f])
                    except: pass


class UnixPackage(Builder):
    def run(self):
        # Make tgz
        raise NotImplementedError

class UnixUpload(Builder):
    def run(self):
        # Upload
        raise NotImplementedError
    
        
class MacPackage(Builder):
    def run(self):
        log("Building disk image")
        mkdirs(os.path.join(self.args.cwd_images))
        
        now = datetime.datetime.now().strftime('%Y-%m-%d')   
        with open(os.path.join(self.args.cwd_rpath, 'build_date.'+now), 'w') as f:
            f.write("Built on %s"%now)

        # Create a symlink to /Applications
        print "Linking to /Applications in cwd: ", self.args.cwd_stage
        cmd(['ln', '-s', '/Applications', 'Applications'], cwd=self.args.cwd_stage)

        volname = "%s %s for Mac OS X %s, built on %s"%(self.args.cvsmodule.upper(), self.args.cvstag, self.args.target_desc, now)
        imgname = "%s.%s.%s.dmg"%(self.args.cvsmodule, self.args.cvstag, self.args.target_desc)
        img = os.path.join(self.args.cwd_images, imgname)
        hdi = ['hdiutil', 'create', '-ov', '-srcfolder', self.args.cwd_stage, '-volname', volname, img]
        cmd(hdi)


class MacUpload(Builder):
    def run(self):
        log("Uploading disk image")
        imgname = "%s.%s.%s.dmg"%(self.args.cvsmodule, self.args.cvstag, self.args.target_desc)
        img = os.path.join(self.args.cwd_images, imgname)
        scpdest = "eman@%s:%s/%s"%(self.args.scphost, self.args.scpdest, imgname)
        scp = ['scp', img, scpdest]
        cmd(scp)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('commands',    help='Build commands', nargs='+')
    parser.add_argument('--version',   action='version', version=VERSION)
    parser.add_argument('--target',    help='Build target', default=os.getenv('TARGET'))
    parser.add_argument('--root',      help='Build system root', default='/build')
    parser.add_argument('--clean',     help='Make clean', type=int, default=1)
    parser.add_argument('--cvsroot',   help='CVS: root', default="eman@blake.grid.bcm.edu:/usr/local/CVS/CVS")
    parser.add_argument('--cvsmodule', help='CVS: module', default='eman2')
    parser.add_argument('--cvstag',    help='CVS: tag', default='daily')
    parser.add_argument('--scphost',   help='Upload: scp host', default='10.10.9.104')
    parser.add_argument('--scpdest',   help='Upload: scp destination directory', default='/home/zope-extdata/reposit/ncmi/software/counter_222/software_86')
    
    args = parser.parse_args()
    print "EMAN2 Nightly Build -- Version: %s -- Target: %s -- Date: %s"%(VERSION, args.target, datetime.datetime.utcnow().isoformat())
    target = TARGETS.get(args.target, Target)(args)
    target.run(args.commands)


    
    

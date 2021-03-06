#!/usr/bin/env python
#
# Author: Steven Ludtke 2014/04/27
# Copyright (c) 2014- Baylor College of Medicine


# This software is issued under a joint BSD/GNU license. You may use the
# source code in this file under either license. However, note that the
# complete EMAN2 and SPARX software packages have some GPL dependencies,
# so you are responsible for compliance with the licenses of these packages
# if you opt to use BSD licensing. The warranty disclaimer below holds
# in either instance.
#
# This complete copyright notice must be included in any revised version of the
# source code. Additional authorship citations may be added, but existing
# author citations must be preserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  2111-1307 USA
#
#

from EMAN2 import *
from EMAN2jsondb import *
import os,sys

class nothing:
	def __init__(self,x=None,y=None,z=None,q=None):
		return

try: 
	from PyQt4 import QtCore, QtGui, Qt
	from emimage2d import EMImage2DWidget
	from emplot2d import EMPlot2DWidget
	from emimagemx import EMImageMXWidget
	from valslider import ValSlider,CheckBox,ValBox
	from emshape import EMShape
except:
	QtGui=nothing()
	QtCore=nothing()
	QtCore.QObject=nothing()
	QtGui.QWidget=nothing()


# ok, this is kind of bad style, but really don't want to have to drag this flag around through many objects
invert_on_read=False

def load_micrograph(filename):
	n=EMUtil.get_image_count(filename)
	if n==0 :
		QtGui.QMessageBox.warning(None,"Error","The file {} contains no images".format(newfilename))
		return
	elif n==1 :
		img=EMData(filename,0)		# single image
	else :
		img=EMData(filename,0)		# movie stack (we assume)
		for i in xrange(1,n):
			im=EMData(filename,i)
			img.add(im)
		img.mult(1.0/n)
		
	if invert_on_read : img.mult(-1.0)
	return img

def main():
	progname = os.path.basename(sys.argv[0])
	usage = """prog [options] <image> <image2>....

	The even newer version of e2boxer. Complete rewrite. Incomplete.
	
	This program 
"""
	parser = EMArgumentParser(usage=usage,version=EMANVERSION)

	parser.add_pos_argument(name="micrographs",help="List the file to process with e2boxer here.", default="", guitype='filebox', browser="EMBoxesTable(withmodal=True,multiselect=True)",  row=0, col=0,rowspan=1, colspan=3, mode="boxing,extraction")
	parser.add_argument("--invert",action="store_true",help="If specified, inverts input contrast. Particles MUST be white on a darker background.",default=False, guitype='boolbox', row=3, col=2, rowspan=1, colspan=1, mode="extraction")
	parser.add_argument("--boxsize","-B",type=int,help="Box size in pixels",default=-1, guitype='intbox', row=2, col=0, rowspan=1, colspan=3, mode="boxing,extraction")
	parser.add_argument("--ptclsize","-P",type=int,help="Longest axis of particle in pixels (diameter, not radius)",default=-1, guitype='intbox', row=2, col=0, rowspan=1, colspan=3, mode="boxing,extraction")
	parser.add_argument("--apix",type=float,help="Angstroms per pixel for all images",default=-1, guitype='floatbox', row=4, col=0, rowspan=1, colspan=1, mode="autofit['self.pm().getAPIX()']")
	parser.add_argument("--voltage",type=float,help="Microscope voltage in KV",default=-1, guitype='floatbox', row=4, col=1, rowspan=1, colspan=1, mode="autofit['self.pm().getVoltage()']")
	parser.add_argument("--cs",type=float,help="Microscope Cs (spherical aberation)",default=-1, guitype='floatbox', row=5, col=0, rowspan=1, colspan=1, mode="autofit['self.pm().getCS()']")
	parser.add_argument("--ac",type=float,help="Amplitude contrast (percentage, default=10)",default=10, guitype='floatbox', row=5, col=1, rowspan=1, colspan=1, mode='autofit')
	parser.add_argument("--no_ctf",action="store_true",default=False,help="Disable CTF determination", guitype='boolbox', row=3, col=0, rowspan=1, colspan=1, mode="extraction")
	parser.add_argument("--autopick",type=str,default=None,help="Perform automatic particle picking. Provide mode and parameter string")
	parser.add_argument("--write_dbbox",action="store_true",default=False,help="Export EMAN1 .box files",guitype='boolbox', row=3, col=0, rowspan=1, colspan=1, mode="extraction")
	parser.add_argument("--write_ptcls",action="store_true",default=False,help="Extract selected particles from micrographs and write to disk", guitype='boolbox', row=3, col=1, rowspan=1, colspan=1, mode="extraction[True]")
	parser.add_argument("--gui", action="store_true", default=False, help="Interactive GUI mode")
	parser.add_argument("--ppid", type=int, help="Set the PID of the parent process, used for cross platform PPID",default=-1)
	parser.add_argument("--verbose", "-v", dest="verbose", action="store", metavar="n", type=int, default=0, help="verbose level [0-9], higner number means higher level of verboseness")

	(options, args) = parser.parse_args()
	
	global invert_on_read
	if options.invert : invert_on_read = True


	#####
	# Parameter Validation
	project_db = js_open_dict("info/project.json")

	if not (options.gui or options.write_ptcls or options.write_dbbox or options.autopick):
		print "Error: No actions specified. Try --gui for interactive/semi-automated particle picking." 

	if not options.no_ctf :
		if options.voltage>1500 :
			options.voltage/=1000
			print "Voltage specified in kV. Adjusting specified value to ",options.voltage
		if options.voltage<10 :
			try: 
				options.voltage=project_db["global.microscope_voltage"]
				print "Using project voltage of ",options.voltage,"kV"
			except:
				print "Error: No voltage specified, and no project settings available. Disabling CTF mode."
				options.no_ctf=True
		if options.cs<0 :
			try:
				options.cs=project_db["global.microscope_cs"]
				print "Using project Cs of ",options.cs,"mm"
			except:
				print "Error: No Cs specified, and no project settings available. Disabling CTF mode."
				options.no_ctf=True
		if options.ac<0 and not options.no_ctf:
			print "Error: Invalid %AC value. Disabling CTF mode."
			options.no_ctf=True
		if options.ac<1.0 :
			print "Warning: %AC should be specified as a %. If you intended a %AC>1%, please try again. Will proceed with the specified value"
	
	if options.apix<=0 :
		try:
			options.apix=project_db["global.apix"]
			print "Warning: No A/pix specified. Using ",options.apix," from project. Please insure this is correct for the images being boxed!"
		except:
			print "Error: Value required for A/pixel. If this is a non TEM image, suggest --apix=1 and --no_ctf."
			sys.exit(1)
		
	logid=E2init(sys.argv,options.ppid)

	if options.autopick!=None :
		pass

	if options.gui :
		if isinstance(QtGui,nothing) :
			print "====================================="
			print "ERROR: GUI mode unavailable without PyQt4"
			sys.exit(1)
		from emapplication import EMApp
		app=EMApp()
		gui=GUIBoxer(args,options.voltage,options.apix,options.cs,options.ac,options.boxsize,options.ptclsize)
		gui.show()
		app.exec_()

	if options.write_dbbox:
		pass
	
	if options.write_ptcls:
		pass
		

	E2end(logid)
	
class boxerByRef(QtCore.QObject):
	@staticmethod
	def setup_gui(gridlay):
		return
	
	@staticmethod
	def do_autobox(gridlay):
		return
	
class boxerGauss(QtCore.QObject):
	@staticmethod
	def setup_gui(gridlay):
		return
	
	@staticmethod
	def do_autobox(gridlay):
		return
	
class GUIBoxer(QtGui.QWidget):
	# Dictionary of autopickers
	# to add a new one, provide name:(Qt_setup_function,picker_execution_function)
	# Qt_setup_function(self,empty_grid_layout)
	# picker_execution_function(self,...

	aboxmodes = [ ("by Ref","auto_ref",boxerByRef), ("Gauss","auto_gauss",boxerGauss) ]
	boxcolors = { "selected":(0.9,0.9,0.9), "manual":(0,0,0), "refgood":(0,0.8,0), "refbad":(0.8,0,0), "unknown":[.4,.4,.1], "auto_ref":(.1,.1,.4), "auto_gauss":(.4,.1,.4) }
	
	def __init__(self,imagenames,voltage=None,apix=None,cs=None,ac=10.0,box=256,ptcl=200):
		"""The 'new' e2boxer interface.
		"""

		QtGui.QWidget.__init__(self,None)
#		self.setWindowIcon(QtGui.QIcon(get_image_directory() + "ctf.png"))

		self.data=None
		self.curfilename = None				# current selected file for boxing
		self.filenames=imagenames			# list of available filenames
		self.micrograph=None
		self.boxes=None

		self.defaultvoltage=voltage
		self.defaultapix=apix
		self.defaultcs=cs
		self.defaultac=ac
		
		self.db = None						# open JSON file for current image

		self.wimage=EMImage2DWidget()
		self.wimage.setWindowTitle("Micrograph")

		self.wparticles=EMImageMXWidget()
		self.wparticles.setWindowTitle("Particles")
		
		self.wrefs=EMImageMXWidget()
		self.wrefs.setWindowTitle("Box Refs")
		
		self.wbadrefs=EMImageMXWidget()
		self.wbadrefs.setWindowTitle("Bad Box Refs")


		#self.wfft=EMImage2DWidget()
		#self.wfft.setWindowTitle("e2evalimage - 2D FFT")

		#self.wplot=EMPlot2DWidget()
		#self.wplot.setWindowTitle("e2evalimage - Plot")

		self.wimage.connect(self.wimage,QtCore.SIGNAL("mousedown"),self.imgmousedown)
		self.wimage.connect(self.wimage,QtCore.SIGNAL("mousedrag"),self.imgmousedrag)
		self.wimage.connect(self.wimage,QtCore.SIGNAL("mouseup")  ,self.imgmouseup)
		self.wparticles.connect(self.wparticles,QtCore.SIGNAL("mousedown"),self.ptclmousedown)
		self.wparticles.connect(self.wparticles,QtCore.SIGNAL("mousedrag"),self.ptclmousedrag)
		self.wparticles.connect(self.wparticles,QtCore.SIGNAL("mouseup")  ,self.ptclmouseup)
		self.wrefs.connect(self.wparticles,QtCore.SIGNAL("mousedown"),self.refmousedown)
		self.wrefs.connect(self.wparticles,QtCore.SIGNAL("mousedrag"),self.refmousedrag)
		self.wrefs.connect(self.wparticles,QtCore.SIGNAL("mouseup")  ,self.refmouseup)

		self.wimage.mmode="app"
		self.wparticles.mmode="app"

		# This object is itself a widget we need to set up
		self.gbl = QtGui.QGridLayout(self)
		self.gbl.setMargin(8)
		self.gbl.setSpacing(6)

		# Micrograph list
		self.setlist=QtGui.QListWidget(self)
		self.setlist.setSizePolicy(QtGui.QSizePolicy.Preferred,QtGui.QSizePolicy.Expanding)
		for i in imagenames:
			self.setlist.addItem(i)
		self.gbl.addWidget(self.setlist,0,0,12,2)

		self.setlist.connect(self.setlist,QtCore.SIGNAL("currentRowChanged(int)"),self.newSet)
		self.setlist.connect(self.setlist,QtCore.SIGNAL("keypress"),self.listKey)
		
		# Mouse Modes
		self.mmode="manual"
		self.boxmm=QtGui.QGroupBox("Mouse Mode",self)
		self.boxmm.setFlat(False)
		self.gbl.addWidget(self.boxmm,0,2,3,2)
		
		self.hbl0=QtGui.QHBoxLayout(self.boxmm)
		
		self.bmmanual=QtGui.QPushButton("Manual")
		self.bmmanual.setToolTip("Manual selection of particles. No impact on autoselection.")
		self.bmmanual.setAutoExclusive(True)
		self.bmmanual.setCheckable(True)
		self.bmmanual.setChecked(True)
		self.hbl0.addWidget(self.bmmanual)
		
		self.bmdel=QtGui.QPushButton("Delete")
		self.bmdel.setToolTip("Delete particles from any mode. Can also shift-click in other mouse modes.")
		self.bmdel.setAutoExclusive(True)
		self.bmdel.setCheckable(True)
		self.hbl0.addWidget(self.bmdel)
		
		self.bmgref=QtGui.QPushButton("Good Refs")
		self.bmgref.setToolTip("Identify some good particles. Available to all autoboxers.")
		self.bmgref.setAutoExclusive(True)
		self.bmgref.setCheckable(True)
		self.hbl0.addWidget(self.bmgref)

		self.bmbref=QtGui.QPushButton("Bad Refs")
		self.bmbref.setToolTip("Identify regions which should not be selected as particles.")
		self.bmbref.setAutoExclusive(True)
		self.bmbref.setCheckable(True)
		self.hbl0.addWidget(self.bmbref)

		QtCore.QObject.connect(self.bmmanual,QtCore.SIGNAL("clicked(bool)"),self.setMouseManual)
		QtCore.QObject.connect(self.bmdel,QtCore.SIGNAL("clicked(bool)"),self.setMouseDel)
		QtCore.QObject.connect(self.bmgref,QtCore.SIGNAL("clicked(bool)"),self.setMouseGoodRef)
		QtCore.QObject.connect(self.bmbref,QtCore.SIGNAL("clicked(bool)"),self.setMouseBadRef)

		# Global parameters
		self.boxparm=QtGui.QGroupBox("Parameters",self)
		self.boxparm.setFlat(False)
		self.gbl.addWidget(self.boxparm,3,2,3,3)
		
		self.gbl1=QtGui.QGridLayout(self.boxparm)
		self.gbl1.setMargin(8)
		self.gbl1.setSpacing(6)
		
		self.vbbsize = ValBox(label="Box Size:",value=box)
		self.gbl1.addWidget(self.vbbsize,0,0)
		
		self.vbbpsize = ValBox(label="Ptcl Size:",value=ptcl)
		self.gbl1.addWidget(self.vbbpsize,0,1)
		
		self.vbbapix = ValBox(label="A/pix:",value=apix)
		self.gbl1.addWidget(self.vbbapix,0,2)
		
		self.vbvoltage = ValBox(label="Voltage:",value=voltage)
		self.gbl1.addWidget(self.vbvoltage,1,0)

		self.vbbac = ValBox(label="% AC:",value=ac)
		self.gbl1.addWidget(self.vbbac,1,1)
		
		self.vbcs = ValBox(label="Cs:",value=cs)
		self.gbl1.addWidget(self.vbcs,1,2)


		# Autoboxing Tabs
		self.autolbl = QtGui.QLabel("Autoboxing Methods:")
		self.gbl.addWidget(self.autolbl,7,2)
		self.autotab = QtGui.QTabWidget()
		self.gbl.addWidget(self.autotab,8,2,6,3)

		self.bautobox = QtGui.QPushButton("Autobox")
		self.gbl.addWidget(self.bautobox,7,4)
		
		QtCore.QObject.connect(self.bautobox,QtCore.SIGNAL("clicked(bool)"),self.doAutoBox)
		
		# Individual tabs from Dictionary
		self.abwid=[]
		for name,bname,cls in GUIBoxer.aboxmodes:
			w=QtGui.QWidget()
			gl=QtGui.QGridLayout(w)
			self.abwid.append((w,gl))
			cls.setup_gui(gl)
			self.autotab.addTab(w,name)
			
		
		self.setWindowTitle("e2boxer21 - Control Panel")

		self.wimage.show()
#		self.wfft.show()
#		self.wplot.show()
		E2loadappwin("e2boxer21","main",self)
		E2loadappwin("e2boxer21","image",self.wimage.qt_parent)
		E2loadappwin("e2boxer21","particles",self.wparticles.qt_parent)
		E2loadappwin("e2boxer21","refs",self.wrefs.qt_parent)
		E2loadappwin("e2boxer21","badrefs",self.wbadrefs.qt_parent)

		self.newSet(0)




	#QWidget *firstPageWidget = new QWidget;
    #QWidget *secondPageWidget = new QWidget;
    #QWidget *thirdPageWidget = new QWidget;

    #QStackedWidget *stackedWidget = new QStackedWidget;
    #stackedWidget->addWidget(firstPageWidget);
    #stackedWidget->addWidget(secondPageWidget);
    #stackedWidget->addWidget(thirdPageWidget);

    #QVBoxLayout *layout = new QVBoxLayout;
    #layout->addWidget(stackedWidget);
    #setLayout(layout);
		
		 #QComboBox *pageComboBox = new QComboBox;
    #pageComboBox->addItem(tr("Page 1"));
    #pageComboBox->addItem(tr("Page 2"));
    #pageComboBox->addItem(tr("Page 3"));
    #connect(pageComboBox, SIGNAL(activated(int)),stackedWidget, SLOT(setCurrentIndex(int)));

		#self.lboxmode=QtGui.QLabel("Mode:",self)
		#self.gbl.addWidget(self.lboxmode,10,0)

		#self.sboxmode=QtGui.QComboBox(self)
		#self.sboxmode.addItem("Manual")
		#self.sboxmode.addItem("Reference")
		#self.sboxmode.setCurrentIndex(1)
		#self.gbl.addWidget(self.sboxmode,10,1)

		#self.lanmode=QtGui.QLabel("Annotate:",self)
		#self.gbl.addWidget(self.lanmode,12,0)

		#self.sanmode=QtGui.QComboBox(self)
		#self.sanmode.addItem("Box")
		#self.sanmode.addItem("Box+dot")
		#self.sanmode.addItem("Circle")
		#self.sanmode.addItem("None")
		#self.gbl.addWidget(self.sanmode,12,1)

		#self.sdefocus=ValSlider(self,(0,5),"Defocus:",0.0,90)
		#self.gbl.addWidget(self.sdefocus,0,2,1,3)

		#self.squality=ValSlider(self,(0,9),"Quality (0-9):",0,90)
		#self.squality.setIntonly(True)

		#self.gbl.addWidget(self.squality,6,2,1,3)

		#self.brefit=QtGui.QPushButton("Autobox")
		#self.gbl.addWidget(self.brefit,7,2)

		#self.bclrauto=QtGui.QPushButton("Clear Auto")
		#self.gbl.addWidget(self.bclrauto,7,3)

		#self.bclrall=QtGui.QPushButton("Clear All")
		#self.gbl.addWidget(self.bclrall,7,4)

		#self.sapix=ValBox(self,(0,500),"A/pix:",1.0,90)
		#if self.defaultapix!=None : self.sapix.setValue(self.defaultapix)
		#self.gbl.addWidget(self.sapix,10,2)

		#self.svoltage=ValBox(self,(0,500),"Voltage (kV):",200,90)
		#if self.defaultvoltage!=None : self.svoltage.setValue(self.defaultvoltage)
		#self.gbl.addWidget(self.svoltage,11,2)

		#self.scs=ValBox(self,(0,5),"Cs (mm):",4.1,90)
		#if self.defaultcs!=None : self.scs.setValue(self.defaultcs)
		#self.gbl.addWidget(self.scs,12,2)

		#self.sboxsize=ValBox(self,(0,500),"Box Size:",256,90)
		#self.sboxsize.intonly=True
		#self.gbl.addWidget(self.sboxsize,13,2)

		#self.sptclsize=ValBox(self,(0,500),"Ptcl Size:",256,90)
		#self.sptclsize.intonly=True
		#self.gbl.addWidget(self.sptclsize,14,2)

		#QtCore.QObject.connect(self.sdefocus, QtCore.SIGNAL("valueChanged"), self.newCTF)
		#QtCore.QObject.connect(self.sapix, QtCore.SIGNAL("valueChanged"), self.newCTF)
		#QtCore.QObject.connect(self.svoltage, QtCore.SIGNAL("valueChanged"), self.newCTF)
		#QtCore.QObject.connect(self.scs, QtCore.SIGNAL("valueChanged"), self.newCTF)
		#QtCore.QObject.connect(self.sboxsize, QtCore.SIGNAL("valueChanged"), self.newBox)
##		QtCore.QObject.connect(self.soversamp, QtCore.SIGNAL("valueChanged"), self.newBox)
		#QtCore.QObject.connect(self.squality,QtCore.SIGNAL("valueChanged"),self.newQualityFactor)
		#QtCore.QObject.connect(self.setlist,QtCore.SIGNAL("currentRowChanged(int)"),self.newSet)
		#QtCore.QObject.connect(self.setlist,QtCore.SIGNAL("keypress"),self.listkey)
		#QtCore.QObject.connect(self.sboxmode,QtCore.SIGNAL("currentIndexChanged(int)"),self.newBoxMode)

		#self.resize(720,380) # figured these values out by printing the width and height in resize event

		#### This section is responsible for background updates
		#self.busy=False
		#self.needupdate=True
		#self.needredisp=False
		#self.procthread=None
		#self.errors=None		# used to communicate errors back from the reprocessing thread

		#self.timer=QTimer()
		#QtCore.QObject.connect(self.timer, QtCore.SIGNAL("timeout()"), self.timeOut)
		#self.timer.start(100)

#		self.recalc()

	def setMouseManual(self,x):
		self.mmode="manual"
	
	def setMouseDel(self,x):
		self.mmode="del"
	
	def setMouseGoodRef(self,x):
		self.mmode="refgood"
	
	def setMouseBadRef(self,x):
		self.mmode="refbad"
		

	def imgmousedown(self,event) :
		m=self.wimage.scr_to_img((event.x(),event.y()))
		boxsize2=self.vbbsize.getValue()//2
		ptclsize=self.vbbpsize.getValue()

		self.curbox=0
		# check to see if click was inside an existing box, in which case we move it
		for i in self.boxes:
			if abs(m.x-i[0])<boxsize2 and abs(m.y-i[1])<boxsize2 : 
				self.curbox=i
				break
		else :
			# Create a new box
			if self.mmode=="del" : return	 # This is for creating a new box, so clearly not desirable in delete mode
			self.curbox=len(self.boxes)
			self.boxes.append((m[0],m[1],self.mmode))
			self.__addBox(self.curbox,self.boxes[-1])
			
			
				
		#self.guiim.add_shape("cen",["rect",.9,.9,.4,x0,y0,x0+2,y0+2,1.0])

	def imgmousedrag(self,event) :
		if self.calcmode==0:
			m=self.wimage.scr_to_img((event.x(),event.y()))
			parms=self.parms[self.curset]
			parms[2]=(m[0]-parms[0]/2,m[1]-parms[0]/2)
			self.needredisp=True
			self.recalc()
			

		# box deletion when shift held down
		#if event.modifiers()&Qt.ShiftModifier:
			#for i,j in enumerate(self.boxes):

	def imgmouseup(self,event) :
		m=self.wimage.scr_to_img((event.x(),event.y()))
		if self.calcmode==1:
			parms=self.parms[self.curset]
			nx=self.data["nx"]/parms[0]-1
			grid=int((m[0]-parms[0]/2)/parms[0])+int((m[1]-parms[0]/2)/parms[0])*nx
			if grid in parms[3] : parms[3].remove(grid)
			else: parms[3].add(grid)
			self.needredisp=True
			self.recalc()

	def ptclmousedown(self,event) :
		return
	
	def ptclmousedrag(self,event) :
		return

	def ptclmouseup(self,event) :
		return

	def refmousedown(self,event) :
		return
	
	def refmousedrag(self,event) :
		return

	def refmouseup(self,event) :
		return

	def newSet(self,val):
		"called when a new data set is selected from the list"

		first=True
		newfilename=str(self.setlist.item(val).text())
		if newfilename==self.curfilename : return

		# Write the current image parameters to the database
		if self.curfilename!=None and self.boxes!=None :
			self.save_boxes()
			first=False


		self.micrograph=load_micrograph(newfilename)
		self.wimage.set_data(self.micrograph)
		if first : E2loadappwin("e2boxer21","image",self.wimage.qt_parent)
		self.curfilename=newfilename
		self.restore_boxes()

	def save_boxes(self):
		js=js_open_dict(info_name(self.curfilename))
		js["boxes"]=self.boxes
		
	def restore_boxes(self):
		# first we restore the list of box locations
		js=js_open_dict(info_name(self.curfilename))
		try: self.boxes=js["boxes"]
		except: self.boxes=[]
		boxsize=self.vbbsize.getValue()
		ptclsize=self.vbbpsize.getValue()
		micro=self.wimage.get_data()
		
		self.wimage.del_shapes()
		if len(self.boxes)==0 : 
			self.wparticles.set_data([])
			return
		
		# Then we extract the actual boxed out particles
		goodrefs=[]
		badrefs=[]
		self.particles=[]
		for i,box in enumerate(self.boxes):
			self.__addBox(i,box)

			# extract the data
			boxim=self.micrograph.get_clip(Region(box[0]-boxsize//2,box[1]-boxsize//2,boxsize,boxsize))
			boxim["ptcl_source_coord"]=(box[0],box[1])
			if box[2]=="refgood":
				goodrefs.append(boxim)
			elif box[2]=="refbad":
				badrefs.append(boxim)
			else:
				self.particles.append(boxim)
		
		# finally redisplay as appropriate
		self.wimage.update()
		self.wparticles.set_data(self.particles)
		if len(self.particles)>0 : self.wparticles.show()
				
		if len(goodrefs)+len(badrefs)!=0:
			self.goodrefs=goodrefs
			self.badrefs=badrefs
			self.wrefs.set_data(self.goodrefs)
			self.wbadrefs.set_data(self.badrefs)
			
			if len(self.goodrefs)>0 : self.wrefs.show()
			if len(self.badrefs)>0 : self.wbadrefs.show()

	def __addBox(self,i,box):
		"""takes the number of the box in self.boxes and the (x,y,mode) tuple and displays it"""
		# Display the actual box
		boxsize=self.vbbsize.getValue()
		ptclsize=self.vbbpsize.getValue()
		try: color=self.boxcolors[box[2]]
		except: color=self.boxcolors["unknown"]
		self.wimage.add_shape("box{}".format(i),EMShape(("rect",color[0],color[1],color[2],box[0]-boxsize//2,box[1]-boxsize//2,box[0]+boxsize//2,box[1]+boxsize//2,2)))
		self.wimage.add_shape("cir{}".format(i),EMShape(("circle",color[0],color[1],color[2],box[0],box[1],ptclsize/2,1.5)))

		

	def listKey(self,event):
		pass

		#if event.key()>=Qt.Key_0 and event.key()<=Qt.Key_9 :
			#q=int(event.key())-Qt.Key_0
			#self.squality.setValue(q)
		#elif event.key() == Qt.Key_Left:
			#self.sdefocus.setValue(self.sdefocus.getValue()-0.03)
		#elif event.key() == Qt.Key_Right:
			#self.sdefocus.setValue(self.sdefocus.getValue()+0.03)
		#elif event.key()==Qt.Key_I :
			#self.doImport()
		#elif event.key()==Qt.Key_U :
			#self.unImport()

		
	def doAutoBox(self,b):
		"""Autobox button pressed, find the right algorithm and call it"""
		
		name,bname,fn1=self.aboxmodes[self.autotab.currentIndex()]
		
		print name," called"

	def closeEvent(self,event):
#		QtGui.QWidget.closeEvent(self,event)
		E2saveappwin("e2boxer21","main",self)
		E2saveappwin("e2boxer21","image",self.wimage.qt_parent)
		E2saveappwin("e2boxer21","particles",self.wparticles.qt_parent)
		E2saveappwin("e2boxer21","refs",self.wrefs.qt_parent)
		E2saveappwin("e2boxer21","badrefs",self.wbadrefs.qt_parent)

		#self.writeCurParm()
		event.accept()
		QtGui.qApp.exit(0)
		#app=QtGui.qApp
		#if self.wimage != None:
			#app.close_specific(self.wimage)
			#self.wimage = None
		#if self.wfft != None:
			#app.close_specific(self.wfft)
		#if self.wplot != None:
			#app.close_specific(self.wplot)
		#app.close_specific(self)
#		self.emit(QtCore.SIGNAL("module_closed")) # this signal is important when e2ctf is being used by a program running its own event loop


	#def update_plot(self):
##		if self.wplot == None: return # it's closed/not visible

		#if self.incalc : return		# no plot updates during a recomputation

		#parms=self.parms[self.curset]
		#apix=self.sapix.getValue()
		#ds=1.0/(apix*parms[0]*parms[5])
		#ctf=parms[1]
		#bg1d=array(ctf.background)
		#r=len(ctf.background)
		#s=arange(0,ds*r,ds)

		## This updates the FFT CTF-zero circles
		#if self.f2danmode==0 :
			#fit=ctf.compute_1d(len(s)*2,ds,Ctf.CtfType.CTF_AMP)
			#shp={}
			#nz=0
			#for i in range(1,len(fit)):
				#if fit[i-1]*fit[i]<=0.0:
					#nz+=1
					#shp["z%d"%i]=EMShape(("circle",0.0,0.0,1.0/nz,r,r,i,1.0))

			#self.wfft.del_shapes()
			#self.wfft.add_shapes(shp)
			#self.wfft.updateGL()
		## Single measurement circle mode
		#elif self.f2danmode==1 :
			#self.wfft.del_shapes()
			#if self.ringrad==0: self.ringrad=1.0
			#self.wfft.add_shape("ring",EMShape(("circle",0.2,1.0,0.2,r,r,self.ringrad,1.0)))
			#self.wfft.add_shape("ringlbl",EMShape(("scrlabel",0.2,1.0,0.2,10,10,"r=%d pix -> 1/%1.2f 1/A (%1.4f)"%(self.ringrad,1.0/(self.ringrad*ds),self.ringrad*ds),24.0,2.0)))
			#self.wfft.updateGL()
		## 2-D Crystal mode
		#elif self.f2danmode==2 :
			#shp={}
			#for a in range(-5,6):
				#for b in range(-5,6):
					#shp["m%d%d"%(a,b)]=EMShape(("circle",1.0,0.0,0.0,a*self.xpos1[0]+b*self.xpos2[0]+self.fft["nx"]/2-1,a*self.xpos1[1]+b*self.xpos2[1]+self.fft["ny"]/2,3,1.0))

			#self.wfft.del_shapes()
			#self.wfft.add_shapes(shp)
			#self.wfft.add_shape("xtllbl",EMShape(("scrlabel",1.0,0.3,0.3,10,10,"Unit Cell: %1.2f,%1.2f"%(1.0/(hypot(*self.xpos1)*ds),1.0/(hypot(*self.xpos2)*ds)),60.0,2.0)))
##			except: pass
			#self.wfft.updateGL()
		#else:
			#self.wfft.del_shapes()
			#self.wfft.updateGL()


		## Now update the plots for the correct plot mode
		#if self.plotmode==0:
			#try: bgsub=self.fft1d-bg1d
			#except:
				#print "Error computing bgsub on this image"
				#return
			#self.wplot.set_data((s,bgsub),"fg-bg",quiet=True,color=0)

			#fit=array(ctf.compute_1d(len(s)*2,ds,Ctf.CtfType.CTF_AMP))		# The fit curve
			#fit=fit*fit			# squared

			## auto-amplitude for b-factor adjustment
			#rto,nrto=0,0
			#for i in range(int(.04/ds)+1,min(int(0.15/ds),len(s)-1)):
				#if bgsub[i]>0 :
					#rto+=fit[i]
					#nrto+=fabs(bgsub[i])
			#if nrto==0 : rto=1.0
			#else : rto/=nrto
			#fit=[fit[i]/rto for i in range(len(s))]

##			print ctf_cmp((self.sdefocus.value,self.sbfactor.value,rto),(ctf,bgsub,int(.04/ds)+1,min(int(0.15/ds),len(s)-1),ds,self.sdefocus.value))

			#self.wplot.set_data((s,fit),"fit",color=1)
			#self.wplot.setAxisParms("s (1/"+ "$\AA$" +")","Intensity (a.u)")
		#elif self.plotmode==1:
			#self.wplot.set_data((s[1:],self.fft1d[1:]),"fg",quiet=True,color=1)
			#self.wplot.set_data((s[1:],bg1d[1:]),"bg",color=0)
			#self.wplot.setAxisParms("s (1/"+ "$\AA$" +")","Intensity (a.u)")
		#elif self.plotmode==2:
			#if self.fft1dang==None: self.recalc_real()
			#bgsub=self.fft1d-bg1d
			#bgsuba=[array(self.fft1dang[i])-bg1d for i in xrange(4)]
					## Write the current image parameters to the database

##			for i in xrange(4): bgsuba[i][0]=0
			#self.wplot.set_data((s,bgsub),"fg",quiet=True,color=0)
			#self.wplot.set_data((s[3:],bgsuba[0][3:]),"fg 0-45",quiet=True,color=2)
			#self.wplot.set_data((s[3:],bgsuba[1][3:]),"fg 45-90",quiet=True,color=3)
			#self.wplot.set_data((s[3:],bgsuba[2][3:]),"fg 90-135",quiet=True,color=4)
			#self.wplot.set_data((s[3:],bgsuba[3][3:]),"fg 135-180",quiet=True,color=6)

			#fit=array(ctf.compute_1d(len(s)*2,ds,Ctf.CtfType.CTF_AMP))		# The fit curve
			#fit=fit*fit			# squared

			## auto-amplitude for b-factor adjustment
			#rto,nrto=0,0
			#for i in range(int(.04/ds)+1,min(int(0.15/ds),len(s)-1)):
				#if bgsub[i]>0 :
					#rto+=fit[i]
					#nrto+=fabs(bgsub[i])
			#if nrto==0 : rto=1.0
			#else : rto/=nrto
			#fit/=rto

			#self.wplot.set_data((s,fit),"fit",color=1)
			#self.wplot.setAxisParms("s (1/"+ "$\AA$" + ")","Intensity (a.u)")

		#elif self.plotmode==3:
			#if self.fft1dang==None: self.recalc_real()
			##bgsub=self.fft1d-bg1d
			##bgsuba=[array(self.fft1dang[i])-bg1d for i in xrange(4)]
			#fg=self.fft1d
			#fga=[array(self.fft1dang[i]) for i in xrange(4)]

			#for i in xrange(4): fga[i][0]=0
			#self.wplot.set_data((s,fg),"fg",quiet=True,color=0)
			#self.wplot.set_data((s,fga[0]),"fg 0-45",quiet=True,color=2)
			#self.wplot.set_data((s,fga[1]),"fg 45-90",quiet=True,color=3)
			#self.wplot.set_data((s,fga[2]),"fg 90-135",quiet=True,color=4)
			#self.wplot.set_data((s,fga[3]),"fg 135-180",quiet=True,color=6)

			##fit=array(ctf.compute_1d(len(s)*2,ds,Ctf.CtfType.CTF_AMP))		# The fit curve
			##fit=fit*fit			# squared

			### auto-amplitude for b-factor adjustment
			##rto,nrto=0,0
			##for i in range(int(.04/ds)+1,min(int(0.15/ds),len(s)-1)):
				##if bgsub[i]>0 :
					##rto+=fit[i]
					##nrto+=fabs(bgsub[i])
			##if nrto==0 : rto=1.0
			##else : rto/=nrto
			##fit/=rto

			##self.wplot.set_data((s,fit),"fit",color=1)
			##self.wplot.setAxisParms("s (1/"+ "$\AA$" + ")","Intensity (a.u)")
		#if self.plotmode==4:
			#if min(bg1d)<=0.0 : bg1d+=min(bg1d)+max(bg1d)/10000.0
			#ssnr=(self.fft1d-bg1d)/bg1d
			#self.wplot.set_data((s,ssnr),"SSNR",quiet=True,color=0)

			##fit=array(ctf.compute_1d(len(s)*2,ds,Ctf.CtfType.CTF_AMP))		# The fit curve
			##fit=fit*fit			# squared

			### auto-amplitude for b-factor adjustment
			##rto,nrto=0,0
			##for i in range(int(.04/ds)+1,min(int(0.15/ds),len(s)-1)):
				##if bgsub[i]>0 :
					##rto+=fit[i]
					##nrto+=fabs(bgsub[i])
			##if nrto==0 : rto=1.0
			##else : rto/=nrto
			##fit=[fit[i]/rto for i in range(len(s))]

###			print ctf_cmp((self.sdefocus.value,self.sbfactor.value,rto),(ctf,bgsub,int(.04/ds)+1,min(int(0.15/ds),len(s)-1),ds,self.sdefocus.value))

			##self.wplot.set_data((s,fit),"fit",color=1)
			#self.wplot.setAxisParms("s (1/"+ "$\AA$" + ")","Est. SSNR")


	#def timeOut(self):
		#if self.busy : return

		## Redisplay before spawning thread for more interactive display
		#if self.needredisp :
			#try: self.redisplay()
			#except: pass

		## Spawn a thread to reprocess the data
		#if self.needupdate and self.procthread==None:
			#self.procthread=threading.Thread(target=self.recalc_real)
			#self.procthread.start()

		#if self.errors:
			#QtGui.QMessageBox.warning(None,"Error","The following processors encountered errors during processing of 1 or more images:"+"\n".join(self.errors))
			#self.errors=None

	#def doRefit(self):
		#parms=self.parms[self.curset]
		#apix=self.sapix.getValue()
		#ds=1.0/(apix*parms[0]*parms[5])
		
		#try:
			#parms[1]=e2ctf.ctf_fit(self.fft1d,parms[1].background,parms[1].background,self.fft,self.fftbg,parms[1].voltage,parms[1].cs,parms[1].ampcont,apix,bgadj=False,autohp=True,verbose=1)
		#except:
			#print "CTF Autofit Failed"
			#traceback.print_exc()
			#parms[1].defocus=1.0

		#self.sdefocus.setValue(parms[1].defocus,True)
		#self.sbfactor.setValue(parms[1].bfactor,True)
		#self.sampcont.setValue(parms[1].ampcont,True)
		
		#self.update_plot()


	#def unImport(self,val=None):
		#print "unimport ",base_name(self.setlist.item(self.curset).text())
		#item=base_name(self.setlist.item(self.curset).text())
		#try: os.unlink("micrographs/%s.hdf"%item)
		#except: print "Couldn't delete micrographs/%s.hdf"%item

	#def doImport(self,val=None):
		#"""Imports the currently selected image into a project"""
		#print "import ",base_name(self.setlist.item(self.curset).text())

		## This is just the (presumably) unique portion of the filename
		#item=base_name(self.setlist.item(self.curset).text())

		## create directory if necessary
		#if not os.access("micrographs",os.R_OK) :
			#try : os.mkdir("micrographs")
			#except:
				#QtGui.QMessageBox.warning(self,"Error !","Cannot create micrographs directory")
				#return

		##db=db_open_dict("bdb:micrographs#%s"%item)
		#self.data["ctf"]=self.parms[self.curset][1]
		
		#if self.cinvert.getValue()!=0 : self.data.mult(-1)
		#if self.cxray.getValue() : self.data.process_inplace("threshold.clampminmax.nsigma",{"nsigma":4,"tomean":1})
		#self.data.write_image("micrographs/%s.hdf"%item)
		#self.writeCurParm()

##		js_open_dict(info_name(item))["ctf"]=[self.parms[val][1],None,None,None,None]
## 		db_parms=db_open_dict("bdb:e2ctf.parms")
## 		db_parms[item]=[self.parms[val][1].to_string(),self.fft1d,self.parms[val][1].background,self.parms[val][4]]

	#def writeCurParm(self):
		#"Called to store the current parameters for this image to the frameparms database"
		#parms=self.parms[self.curset]
		#js=js_open_dict(info_name(self.curfilename))
		#js.setval("ctf_frame",parms,True)
		#js.setval("quality",parms[4])
## 		db_fparms=db_open_dict("bdb:e2ctf.frameparms")
## 		curtag=item_name(str(self.setlist.item(self.curset).text()))
## 		db_fparms[curtag]=self.parms[self.curset]


	#def recalc(self):
		#self.needupdate=True

	#def recalc_real(self):
		#"Called to recompute the power spectra, also updates plot"

		#self.needupdate=False

		#if self.data==None :
			#self.procthread=None
			#return

		#self.incalc=True	# to avoid incorrect plot updates

		## To simplify expressions
		#parms=self.parms[self.curset]
		#apix=self.sapix.getValue()
		#if len(parms)==5 : parms.append(1)		# for old projects where there was no oversampling specification
		#else: parms[5]=max(1,int(parms[5]))
		#ds=1.0/(apix*parms[0]*parms[5])

		## Mode where user drags the box around the parent image
		#if self.calcmode==0:

			## extract the data and do an fft
			#clip=self.data.get_clip(Region(parms[2][0],parms[2][1],parms[0],parms[0]))
			#clip.process_inplace("normalize.edgemean")

			#if parms[5]>1 :
				#clip=clip.get_clip(Region(0,0,parms[0]*parms[5],parms[0]*parms[5]))		# since we aren't using phases, doesn't matter if we center it or not
			#self.fft=clip.do_fft()
##			self.fft.mult(1.0/parms[0]**2)
			#self.fft.mult(1.0/parms[0])

		## mode where user selects/deselcts tiled image set
		#elif self.calcmode==1:
			## update the box display on the image
			#nx=self.data["nx"]/parms[0]-1
			#self.fft=None
			#nbx=0
			#for x in range(nx):
				#for y in range(self.data["ny"]/parms[0]-1):
					## User deselected this one
					#if int(x+y*nx) in parms[3] : continue

					## read the data and make the FFT
					#clip=self.data.get_clip(Region(x*parms[0]+parms[0]/2,y*parms[0]+parms[0]/2,parms[0],parms[0]))
					#clip.process_inplace("normalize.edgemean")
					#if parms[5]>1 :
						#clip=clip.get_clip(Region(0,0,parms[0]*parms[5],parms[0]*parms[5]))		# since we aren't using phases, doesn't matter if we center it or not
					#fft=clip.do_fft()
##					fft.mult(parms[0])
					#fft.ri2inten()
					#if self.fft==None: self.fft=fft
					#else: self.fft+=fft
					#nbx+=1

			#self.fft.mult(1.0/(nbx*parms[0]**2))
			#self.fft.process_inplace("math.sqrt")
			#self.fft["is_intensity"]=0				# These 2 steps are done so the 2-D display of the FFT looks better. Things would still work properly in 1-D without it
##			self.fft.mult(1.0/(nbx*parms[0]**2))

		#self.fftbg=self.fft.process("math.nonconvex")
		#self.fft1d=self.fft.calc_radial_dist(self.fft.get_ysize()/2,0.0,1.0,1)	# note that this handles the ri2inten averages properly
		#if self.plotmode==2 or self.plotmode==3:
			#self.fft1dang=array(self.fft.calc_radial_dist(self.fft.get_ysize()/2,0.0,1.0,4,self.sang45.getValue()*.017453292,1))	# This form generates 4 sequential power spectra representing angular ranges
			#self.fft1dang=self.fft1dang.reshape((4,self.fft.get_ysize()/2))
		#else:
			#self.fft1dang=None

		## Compute 1-D curve and background
		#bg_1d=e2ctf.low_bg_curve(self.fft1d,ds)
		#parms[1].background=bg_1d
		#parms[1].dsbg=ds

		#self.fft1d=array(self.fft1d)

		#self.needredisp=True
		#self.incalc=False
		#time.sleep(.2)			# help make sure update has a chance
		#self.procthread=None
##		dbquality = self.db[os.path.basename(self.curfilename)]
##		print dbquality
## 		item=item_name(self.curfilename)
## 		db=db_open_dict("bdb:e2ctf.parms")
## 		if db[item]==None or db[item[3]]==None : db[item]=[parms[1].to_string(),self.fft1d,parms[1].background,5]
## #		print item,db[item][3]
## 		try: self.squality.setValue(int(db[item[3]]))
## 		except: self.squality.setValue(5)

	#def redisplay(self):

		#if self.incalc: return

		#self.needredisp=False
		#self.busy=True
		#parms=self.parms[self.curset]
		#apix=self.sapix.getValue()
		#ds=1.0/(apix*parms[0]*parms[5])


		## Fitting not done yet. Need to make 2D background somehow
		#if parms[1].defocus==0:
			#self.doRefit()

		#self.wimage.show()
		#self.wfft.show()
		#self.wplot.show()

		#self.update_plot()

		## To simplify expressions

		#if self.calcmode==0:
			## update the box display on the image
			#self.wimage.del_shapes()
			#self.wimage.add_shape("box",EMShape(("rect",.3,.9,.3,parms[2][0],parms[2][1],parms[2][0]+parms[0],parms[2][1]+parms[0],1)))
			#self.wimage.updateGL()
		#elif self.calcmode==1:
			## update the box display on the image
			#nx=self.data["nx"]/parms[0]-1
			#shp={}
			#for x in range(nx):
				#for y in range(self.data["ny"]/parms[0]-1):
					## User deselected this one
					#if int(x+y*nx) in parms[3] : continue

					## Make a shape for this box
					#shp["box%02d%02d"%(x,y)]=EMShape(("rect",.3,.9,.3,(x+.5)*parms[0],(y+.5)*parms[0],(x+1.5)*parms[0],(y+1.5)*parms[0],1))

			#self.wimage.del_shapes()
			#self.wimage.add_shapes(shp)
			#self.wimage.updateGL()

		#if self.f2dmode>0 :
			#if self.f2dmode==1 : self.wfft.set_data(self.fft-self.fftbg)
			#else : self.wfft.set_data(self.fftbg)

		#else :
			#self.wfft.set_data(self.fft)
		#self.busy=False

	#def newCalcMode(self,mode):
		#self.calcmode=mode
		#self.recalc()

	#def new2DMode(self,mode):
		#self.f2dmode=mode
		#self.recalc()

	#def new2DAnMode(self,mode):
		#self.f2danmode=mode
		#self.needredisp=True

	#def newPlotMode(self,mode):
		#self.plotmode=mode
		#self.wplot.set_data(None,replace=True,quiet=True)	# clear the data so plots are properly redisplayed, but don't update the display
		#self.needredisp=True

	#def newBox(self):
		#parms=self.parms[self.curset]
		#parms[0]=self.sboxsize.value
##		parms[5]=self.soversamp.value
		#parms[5]=1
		#parms[3]=set()
		#self.recalc()

	#def newQualityFactor(self):
		#parms=self.parms[self.curset]
		#parms[4]=self.squality.value


	#def newCTF(self) :
		#parms=self.parms[self.curset]
		#parms[1].defocus=self.sdefocus.value
		#parms[1].bfactor=self.sbfactor.value
		#parms[1].dfdiff=self.sdfdiff.value
		#parms[1].dfang=self.sdfang.value
		#parms[1].apix=self.sapix.value
		#parms[1].ampcont=self.sampcont.value
		#parms[1].voltage=self.svoltage.value
		#parms[1].cs=self.scs.value
		#self.needredisp=True



	#def fftmousedown(self,event,m) :
		##m=self.wfft.scr_to_img((event.x(),event.y()))

		#if self.f2danmode==1:
			#self.ringrad=hypot(m[0]-self.fft["nx"]/2,m[1]-self.fft["ny"]/2)
			#self.needredisp=True
		#elif self.f2danmode==2:
			#if (event.modifiers()&Qt.ControlModifier): self.xpos2=((m[0]-self.fft["nx"]/2)/3.0,(m[1]-self.fft["ny"]/2)/3.0)
			#else: self.xpos1=((m[0]-self.fft["nx"]/2)/3.0,(m[1]-self.fft["ny"]/2)/3.0)
			#self.needredisp=True


		##self.guiim.add_shape("cen",["rect",.9,.9,.4,x0,y0,x0+2,y0+2,1.0])

	#def fftmousedrag(self,event,m) :
		##m=self.wfft.scr_to_img((event.x(),event.y()))

		#if self.f2danmode==1:
			#self.ringrad=hypot(m[0]-self.fft["nx"]/2,m[1]-self.fft["ny"]/2)
			#self.needredisp=True
		#elif self.f2danmode==2:
			#if (event.modifiers()&Qt.ControlModifier): self.xpos2=((m[0]-self.fft["nx"]/2)/3.0,(m[1]-self.fft["ny"]/2)/3.0)
			#else: self.xpos1=((m[0]-self.fft["nx"]/2)/3.0,(m[1]-self.fft["ny"]/2)/3.0)
			#self.needredisp=True
		## box deletion when shift held down
		##if event.modifiers()&Qt.ShiftModifier:
			##for i,j in enumerate(self.boxes):

	#def fftmouseup(self,event,m) :
		#"up"
		##m=self.wfft.scr_to_img((event.x(),event.y()))


	#def plotmousedown(self,event) :
		#"mousedown in plot"
##		m=self.guiim.scr_to_img((event.x(),event.y()))

#def tiled(img,box):
	#imgc=img.process("math.meanshrink",{"n":2})		# shrink image by 2 for boxing
	#boxc=good_boxsize(box/2,larger=True)			# box size in reduced image
	#nxb=4*imgc["nx"]/boxc-2		# number of boxes along x direction
	#nyb=4*imgc["ny"]/boxc-2
	#radius=boxc/2.6
	
	#mask1=EMData(boxc,boxc,1)
	#mask1.to_one()
	#mask1.process_inplace("mask.gaussian",{"outer_radius":radius,"exponent":4.0})
	## Mask 2 is the 'inverse' (1.0-val) of mask1, with the addition of a soft outer edge to reduce periodic boundary condition issues
	#mask2=mask1.copy()*-1+1
##		mask1.process_inplace("mask.decayedge2d",{"width":4})
	#mask2.process_inplace("mask.decayedge2d",{"width":2})
	##mask1.clip_inplace(Region(-(ys2*(oversamp-1)/2),-(ys2*(oversamp-1)/2),ys,ys))
	##mask2.clip_inplace(Region(-(ys2*(oversamp-1)/2),-(ys2*(oversamp-1)/2),ys,ys))
	
	## ratio1,2 give us info about how much of the image the mask covers for normalization purposes
	#ratio1=mask1.get_attr("square_sum")/(boxc*boxc)	#/1.035
	#ratio2=mask2.get_attr("square_sum")/(boxc*boxc)

	#cor=EMData(nxb,nyb)

	#vecs=[]
	#for y in xrange(nyb):
		#for x in xrange(nxb):
			#im1=imgc.get_clip(Region(boxc/8+x*boxc/4,boxc/8+y*boxc/4,boxc,boxc))
			#im1.process_inplace("normalize.edgemean")
			
			#im2=im1.copy()

	##		print im2.get_size(), im1.get_size()

			## now we compute power spectra for the 2 regions defined by the masks
			#im1.mult(mask1)
			#imf=im1.do_fft()
			#imf.ri2inten()
			#imf/=(imf["nx"]*imf["ny"]*ratio1)
			#cen_1d=imf.calc_radial_dist(imf.get_ysize()/2,0.0,1.0,1)
			
			#im2.mult(mask2)
			#imf=im2.do_fft()
			#imf.ri2inten()
			#imf/=(imf["nx"]*imf["ny"]*ratio2)
			#edg_1d=imf.calc_radial_dist(imf.get_ysize()/2,0.0,1.0,1)

			#vec=EMData(imf["ny"]/4-2,1,1)		# We skip the first 2 points and only go to 1/2 Nyquist
			#for i in xrange(2,imf["ny"]/4):
				#vec[i]=(cen_1d[i]-edg_1d[i])/edg_1d[i]		# expressed as a SSRN
			
			#vecs.append(vec)
			
			#img[(5*boxc/8+x*boxc/4)*2,(5*boxc/8+y*boxc/4)*2]=(vec["mean"]+0.5)*10.0
			#cor[x,y]=vec["sigma"]
	
	#cor.update()
	#return vecs,cor

#def detect(img,box):
	#img.process_inplace("normalize.edgemean")
	
	#radius=box/2.6
	#zro=img["ctf"].zero(0)*img["ctf"].apix*box
	#wvlen=box*2.0/zro	# 1/2 the wavelength of the 1st zero
##	wvlen=box/zro	# the wavelength of the 1st zero

	#mask1c=EMData(box,box,1)
	#mask1c.process_inplace("testimage.sinewave.circular",{"wavelength":wvlen,"phase":0.0})
	#mask1c.process_inplace("mask.gaussian",{"outer_radius":radius,"exponent":4.0})
##	mask1c.process_inplace("normalize.unitlen")
	#mask1c.process_inplace("normalize")
	#mask1c/=box*box
	#print mask1c["mean"],mask1c["sigma"],wvlen,zro
	#mask1c.clip_inplace(Region(-(img["nx"]-box)/2.0,-(img["ny"]-box)/2.0,img["nx"],img["ny"]))
	#mask1c.process_inplace("xform.phaseorigin.tocorner")

	#mask1s=EMData(box,box,1)
	#mask1s.process_inplace("testimage.sinewave.circular",{"wavelength":wvlen,"phase":pi/2.0})
	#mask1s.process_inplace("mask.gaussian",{"outer_radius":radius,"exponent":4.0})
##	mask1s.process_inplace("normalize.unitlen")
	#mask1s.process_inplace("normalize")
	#mask1s/=box*box
	#print mask1c["mean"],mask1c["sigma"],wvlen,zro
	#mask1s.clip_inplace(Region(-(img["nx"]-box)/2.0,-(img["ny"]-box)/2.0,img["nx"],img["ny"]))
	#mask1s.process_inplace("xform.phaseorigin.tocorner")

	#c1=img.calc_ccf(mask1c)
	#c1.process_inplace("math.squared")
	#s1=img.calc_ccf(mask1s)
	#s1.process_inplace("math.squared")
	#c1.add(s1)
	#c1.process_inplace("normalize")
	

	#display((c1,img),True)
	## Mask 2 is the 'inverse' (1.0-val) of mask1, with the addition of a soft outer edge to reduce periodic boundary condition issues
	##mask2=mask1.copy()*-1+1
###		mask1.process_inplace("mask.decayedge2d",{"width":4})
	##mask2.process_inplace("mask.decayedge2d",{"width":4})
	##mask1.clip_inplace(Region(-(ys2*(oversamp-1)/2),-(ys2*(oversamp-1)/2),ys,ys))
	##mask2.clip_inplace(Region(-(ys2*(oversamp-1)/2),-(ys2*(oversamp-1)/2),ys,ys))


if __name__ == "__main__":
	main()

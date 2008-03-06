#!/usr/bin/env python
#
# Author: Steven Ludtke, 04/10/2003 (sludtke@bcm.edu)
# Copyright (c) 2000-2006 Baylor College of Medicine
#
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
# Foundation, Inc., 59 Temple Place, Suite 330, Boston MA 02111-1307 USA
#
#

from EMAN2_cppwrap import *
from bisect import bisect_left
from pyemtbx.imagetypes import *
from pyemtbx.box import *
#from Sparx import *
from sys import exit
import os
import time
import shelve
import re

EMANVERSION="EMAN2 v1.90"

Vec3f.__str__=lambda x:"Vec3f"+str(x.as_list())

Transform3D.__str__=lambda x:"Transform3D(\t%7.4g\t%7.4g\t%7.4g\n\t\t%7.4g\t%7.4g\t%7.4g\n\t\t%7.4g\t%7.4g\t%7.4g)\nPretrans:%s\nPosttrans:%s"%(x.at(0,0),x.at(0,1),x.at(0,2),x.at(1,0),x.at(1,1),x.at(1,2),x.at(2,0),x.at(2,1),x.at(2,2),str(x.get_pretrans()),str(x.get_posttrans()))

GUIMode=0
GUIbeingdragged=None

# Aliases
EMData.get=EMData.get_value_at
EMData.set=EMData.set_value_at

def timer(fn,n=1):
	a=time.time()
	for i in range(n): fn()
	print time.time()-a

def E2init(argv) :
#	THIS CANNOT GO HERE. GUI toolkits must ONLY
#	be imported by GUI-dependent programs
#        from OpenGL import GLUT
#	GLUT.glutInit( argv )

	"""E2init(argv)
This function is called to log information about the current job to the local logfile"""
	try:
		db=shelve.open(".eman2log")
	except:
		return -1
		
	try:
		n=db["count"]
		db["count"]=n+1
	except:
		n=1
		db["count"]=n
	db[str(n)]={"pid":os.getpid(),"start":time.time(),"args":argv}
	db.close()

	return n

def E2end(n):
	"""E2end(n)
This function is called to log the end of the current job. n is returned by E2init"""
	db=shelve.open(".eman2log")
	d=db[str(n)]
	d["end"]=time.time()
	db[str(n)]=d
	db.close()
	
	return n

def E2saveappwin(app,key,win):
	"""stores the window geometry using the application default mechanism for later restoration. Note that
	this will only work with Qt windows"""
	pos=win.pos()
	sz=win.size()
	geom=(pos.x(),pos.y(),win.width(),win.height())
	E2setappval(app,key,geom)
	
def E2loadappwin(app,key,win):
	"""restores a geometry saved with E2saveappwin"""
	geom=E2getappval(app,key)
	win.resize(geom[2],geom[3])
	win.move(geom[0],geom[1])

def E2setappval(app,key,value):
	"""E2setappval
This function will set an application default value both in the local directory and ~/.eman2
When settings are read, the local value is checked first, then if necessary, the global value."""
	try:
		app.replace(".","_")
		key.replace(".","_")
	except: 
		print "Error with E2setappval, app and key must be strings"
		return
	
	try:
		db=shelve.open(".eman2settings")
		db[app+"."+key]=value
		db.close()
	except:
		pass

	try:
		dir=os.getenv("HOME")
		dir+="/.eman2"
		os.mkdir(dir)
	except:
		return
		
	try:
		db=shelve.open(dir+"/appdefaults")
		db[app+"."+key]=value
		db.close()
	except:
		return


def E2getappval(app,key):
	"""E2getappval
This function will get an application default by first checking the local directory, followed by
~/.eman2"""
	try:
		app.replace(".","_")
		key.replace(".","_")
	except: 
		print "Error with E2getappval, app and key must be strings"
		return None
	
	try:
		db=shelve.open(".eman2settings")
		ret=db[app+"."+key]
		db.close()
		return ret
	except:
		pass
	
	try:
		dir=os.getenv("HOME")
		dir+="/.eman2"
		db=shelve.open(dir+"/appdefaults")
		ret=db[app+"."+key]
		db.close()

		return ret
	except: pass
	
	return None

def parsesym(optstr):
	
	[sym, dict] = parsemodopt(optstr)
	if sym[0] in ['c','d','h']:
		dict["nsym"] = int(sym[1:])
		sym = sym[0]

	sym = Symmetries.get(sym, dict)
	return sym

parseparmobj1=re.compile("([^\(]*)\(([^\)]*)\)")	# This parses test(n=v,n2=v2) into ("test","n=v,n2=v2")
parseparmobj2=re.compile("([^=,]*)=([^,]*)")		# This parses "n=v,n2=v2" into [("n","v"),("n2","v2")]
parseparmobj3=re.compile("[^:]\w*=*[-\w.]*") # This parses ("a:v1=2:v2=3") into ("a", "v1=2", "v2=3") 
parseparmobj4=re.compile("\w*[^=][\w.]*") # This parses ("v1=2") into ("v1", "2")
def parsemodopt(optstr):
	"""This is used so the user can provide the name of a comparator, processor, etc. with options
	in a convenient form. It will parse "dot(normalize=1,negative=0)" and return
	("dot",{"normalize":1,"negative":0})"""
	
	if not optstr or len(optstr)==0 : return (None,{})
	
	print optstr
	p_1 = re.findall( parseparmobj3, optstr )
	print p_1
	if len(p_1)==0: return (optstr,{})
	
	r2 = {}
	for i in range (1, len(p_1)):
		print  p_1[i]
		args = re.findall( parseparmobj4, p_1[i] )
		print args
		if len(args) != 2:
			print "ERROR: Command line parameter options failed"
			print "\tSpecify parameters using this syntax - optiontype:p1=v1:p2=v2 etc"
			print "\tThe problems arguments are:"
			print args
			exit(1)
		
		v = args[1]
		try: v=int(v)
		except:
			try: v=float(v)
			except:
				if v[0]=='"' and v[-1]=='"' : v=j[1][1:-1]
		
		r2[args[0]] = v

	return (p_1[0], r2)

parseparmobj_logical = re.compile(">=|<=|==|~=|!=|<|>") 	# finds the logical operators <=, >=, ==, ~=, !=, <, >
parseparmobj_logical_words = re.compile("\w*[^=!<>~][\w.]*") # splits ("v1?2") into ("v1","2") where ? can be any combination of the characters "=!<>~"
def parsemodopt_logical(optstr):

	if not optstr or len(optstr)==0 : return (None)
	
	p_1 = re.findall( parseparmobj_logical_words, optstr )
	
	if len(p_1)==0: return (optstr,{})
	
	if ( len(p_1) != 2 ):
		print "ERROR: parsemodopt_logical currently only supports single logical expressions"
		print "Could not handle %s" %optstr
		exit(1)
	
	p_2 = re.findall( parseparmobj_logical, optstr )
	
	if ( len(p_2) != 1 ):
		print "ERROR: could not find logical expression in %s" %optstr
		exit(1)
	
	
	if ( p_2[0] not in ["==", "<=", ">=", "!=", "~=", "<", ">"] ):
		print "ERROR: parsemodopt_logical %s could not extract logical expression" %(p_2[0])
		print "Must be one of \"==\", \"<=\", \">=\", \"<\", \">\" \"!=\" or \~=\" "
		exit(1)

	return (p_1[0], p_2[0], p_1[1])

def display(img):
	
	if GUIMode:
		import emimage
		return emimage.EMImage(img)
	else:
		# In non interactive GUI mode, this will display an image or list of images with e2display
		try: os.unlink("/tmp/img.hed")
		except: pass
		try: os.unlink("/tmp/img.img")
		except: pass
		if isinstance(img,list) or isinstance(img,tuple) :
			for i in img: i.write_image("/tmp/img.hed",-1)
		else:
			img.write_image("/tmp/img.hed")
	#	os.system("v2 /tmp/img.hed")
		os.system("e2display.py /tmp/img.hed")

def plot(data,show=1,size=(800,600),path="plot.png"):
	"""plots an image or an array using the matplotlib library"""
	import matplotlib
	matplotlib.use('Agg')
	import pylab
	pylab.figure(figsize=(size[0]/72.0,size[1]/72.0),dpi=72)
	if isinstance(data,EMData) :
		a=[]
		for i in range(data.get_xsize()): 
			a.append(data.get_value_at(i,0,0))
		pylab.plot(a)
	elif isinstance(data,list) or isinstance(data,tuple):
		if isinstance(data[0],list) or isinstance(data[0],tuple) :
			pylab.plot(data[0],data[1])
		else:
			try:
				a=float(data[0])
				pylab.plot(data)
			except:
				print "List, but data isn't floats"
				return
	else :
		print "I don't know how to plot that type"
		return
	
	pylab.savefig(path)
	if show:
		try: os.system("display "+path)
		except: pass
		
# Get the uniform dimension of the (square) input images. For instance
# if the images are all 128x128 this will return 128. If the dimensions of the
# images are not uniform an error is printed and the program exits.
def gimme_image_dimensions2D( imagefilename ):
	
	#pdb.set_trace()
	
	read_header_only = True
	e = EMData();
	images = e.read_images(imagefilename,[], read_header_only)
	
	xsize = images[0].get_xsize()
	ysize = images[0].get_ysize()
	
	
	for i in range(1,len(images)):
		if (images[i].get_xsize() != xsize):
			print "ERROR: make3d does not currently support the reconstruction of images that do not have uniform dimensions"
			print "Image %d x dimension does not match that of image 0 ( %d != %d )" % (images[i].get_xsize(), xsize)
			exit(1)
		if (images[i].get_ysize() != ysize):
			print "ERROR: make3d does not currently support the reconstruction of images that do not have uniform dimensions"
			print "Image %d y dimension does not match that of image 0 ( %d != %d )" % (images[i].get_ysize(), ysize)
			exit(1)
			
	
	# if we make it here all the image dimensions are uniform and equal in all directions, it is safe to return xsize or ysize
	return (xsize, ysize)

# get the three dimensions of a an image
def gimme_image_dimensions3D( imagefilename ):
	
	#pdb.set_trace()
	
	read_header_only = True
	e = EMData();
	e.read_image(imagefilename,0, read_header_only)
	
	xsize = e.get_xsize()
	ysize = e.get_ysize()
	zsize = e.get_zsize()
	
	return (xsize, ysize,zsize)

# A function for removing a file from disk
# adapted so that if you want to remove an img/hed couple it will automatically remove both
def remove_file( file_name ):
	
	if ( os.path.exists(file_name) ):
		
		parts = file_name.split('.')
		
		file_tag = parts[len(parts)-1]
			
		if ( file_tag == 'hed' or file_tag == 'img' ):
			# get everything that isn't the tag
			name = ''
			for i in range(0,len(parts)-1):
				name = name + parts[i] + '.'
				
			os.remove(name+'hed')
			os.remove(name+'img')
		else:
			os.remove(file_name)
		return True
		
	else:
		print "Warning, attempt to remove file (%s) that does not exist. No action taken." %file_name
		return False

# A function for checking if a file exists
# basically wraps os.path.exists, but when an img or hed file is the argument, it
# checks for the existence of both images
def file_exists( file_name ):
	
	if ( os.path.exists(file_name) ):
		
		parts = file_name.split('.')
		file_tag = parts[len(parts)-1]
		
		# get everything that isn't the tag
		name = ''
		for i in range(0,len(parts)-1):
			name = name + parts[i] + '.'

		if ( file_tag == 'hed' ):
			if ( not os.path.exists(name+'img') ):
				print "Warning - %s does not exist" %(name+'img')
				return False
			else: return True;
		elif (file_tag == 'img'):
			if (not os.path.exists(name+'hed')):
				print "Warning - %s does not exist" %(name+'hed')
				return False
			else: return True;
		else:
			return True
		
	else:
		return False

# a function for testing whether a type of Averager, Aligner, Comparitor, Projector, Reconstructor etc
# can be created from the command line string. Returns false if there are problems
# examples
# if not check_eman2_type(options.simaligncmp,Cmps,"Comparitor") : exit(1)
# if not check_eman2_type(options.simalign,Aligners,"Aligner"): exit(1)
def check_eman2_type(modoptstring, object, objectname, verbose=True):
	if modoptstring == None:
		print "Error: expecting a string but got python None, was looking for a type of %s" %objectname
		return False
	 
	if modoptstring == "":
		print "Error: expecting a string was not empty, was looking for a type of %s" %objectname
		return False
	
	try:
		p = parsemodopt(modoptstring)
		object.get(p[0], p[1])
	except RuntimeError:
		if (verbose):
			print "Error: the specified %s (%s) does not exist or cannot be constructed" %(objectname, modoptstring)
		return False

	return True


def qplot(img):
	"""This will plot a 1D image using qplot"""
	out=file("/tmp/plt.txt","w")
	for i in range(img.get_xsize()):
		out.write("%d\t%f\n"%(i,img.get_value_at(i,0)))
	out.close()
	os.system("qplot /tmp/plt.txt")

def error_exit(s) :
	"""A quick hack until I can figure out the logging stuff. This function
	should still remain as a shortcut"""
	print s
	exit(1)
	
def test_image(type=0,size=(128,128)):
	"""Returns a simple standard test image
	type=0  scurve
	type=1	gaussian noise, 0 mean, sigma 1
	type=2  square
	type=3  hollow square
	type=4  circular sinewave
	size=(128,128) """
	ret=EMData()
	ret.set_size(*size)
	if type==0 :
		ret.process_inplace("testimage.scurve")
	elif type==1 :
		ret.process_inplace("testimage.noise.gauss")
	elif type==2:
		ret.process_inplace("testimage.squarecube",{"edge_length":size[0]/2})
	elif type==3:
		ret.process_inplace("testimage.squarecube",{"fill":1,"edge_length":size[0]/2})
	elif type==4:
		ret.process_inplace("testimage.sinewave.circular")
	
	return ret

def isosurface(marchingcubes, threshhold, smooth=False):
	"""Return the Isosurface points, triangles, normals(smooth=True), normalsSm(smooth=False)"""
	marchingcubes.set_surface_value(threshhold)
	d = marchingcubes.get_isosurface(smooth)
	return d['points'], d['faces'], d['normals']

# determines if all of the data dimensions are a power of val
# e.g. if ( data_dims_power_of(emdata,2) print "the dimensions of the image are all a power of 2"
def data_dims_power_of(data,val):
	
	test_cases = [data.get_xsize()]
	
	if ( data.get_ndim() >= 2 ):
		test_cases.append(data.get_ysize())
	if ( data.get_ndim == 3):
		test_cases.append(data.get_zsize())

	for i in test_cases:
		x = i
		while ( x > 1 and x % val == 0 ): x /= val
		if x != 1: 
			return False
		
	return True

__doc__ = \
"EMAN classes and routines for image/volume processing in \n\
single particle reconstructions.\n\
\n\
The following classes are defined: \n\
  EMData - the primary class to process electronic microscopy images. \n\
 \n\
  Quaternion - implements mathematical quaternion. \n\
  Region - defines a rectangular 2D/3D region. \n\
  Transform3D - defines a transformation including rotation, translation, and different Euler angles. \n\
  Vec3i - a 3-element integer vector. \n\
  Vec3f - a 3-element floating number vector. \n\
\n\
  EMObject - A wrapper class for int, float, double, string, EMData, XYData, list etc. \n\
  Pixel - defines a pixel's 3D coordinates and its value. \n\
  SimpleCtf - defines EMAN CTF parameter model. \n\
  XYData - implements operations on a series of (x y) data pair. \n\
\n\
  Aligners - Aligner factory. Each Aligner alignes 2D/3D images. \n\
  Averagers - Averager factory. Each Averager averages a set of images. \n\
  Cmps  - Cmp factory. Each Cmp defines a way to do image comparison. \n\
  Processors - Processor factory. Each processor implements an image-processing algorithm. \n\
  Projectors - Projector factory. Each Projector implements an algorithm for 3D image projection. \n\
  Reconstructors - Reconstructor factory. Each Reconstructor implements an algorithm for image reconstruction. \n\
\n\
  EMUtil - Defines utility functions for EMData-related operations. \n\
  TestUtil - Unit test utility functions. \n\
  Util - Generic utility functions. \n\
\n\
  EMNumPy - Defines functions for conversions between EMData and numpy array. \n\
  Log - Log output at different verbose level. \n\
  PointArray - Point array. \n\
\n\
  dump_aligners() - Print out all Aligners and their parameters. \n\
  dump_averagers() - Print out all Averagers and their sparameters. \n\
  dump_cmps() - Print out all Cmps and their parameters. \n\
  dump_processors() - Print out all Processor`s and their parameters. \n\
  dump_projectors() - Print out all Projectors and their parameters. \n\
  dump_reconstructors() - Print out all Reconstructors and their parameters. \n\
  dump_analyzers() - Print out all Analyzers anf their parameters. \n\
"

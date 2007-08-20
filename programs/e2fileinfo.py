#!/usr/bin/env python

#
# Author: Steven Ludtke 07/10/2007 (sludtke@bcm.edu)
# Copyright (c) 2000-2007 Baylor College of Medicine
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

from EMAN2 import *
from optparse import OptionParser
import sys
import re
import os

bfactor_expressions = ["bf", "bfactor", "bfactors", "bfac"]
defocus_expressions = ["df", "def", "defocus"]
ac_expressions = ["ac", "ampc", "ampcon", "ampcont", "ampcontrast", "acon", "acont", "acontrast" ]

def main():
	progname = os.path.basename(sys.argv[0])
	usage = """%prog [options] <image file> ... """

	parser = OptionParser(usage=usage,version=EMANVERSION)

#	parser.add_option("--gui",action="store_true",help="Start the GUI for interactive boxing",default=False)
	parser.add_option("--auto","-A",type="string",action="append",help="Autobox using specified method: circle, ref, grid",default=[])
#	parser.add_option("--threshold","-T",type="float",help="Threshold for keeping particles. 0-4, 0 excludes all, 4 keeps all.",default=2.0)
#	parser.add_option("--maxbad","-M",type="int",help="Maximumum number of unassigned helices",default=2)
#	parser.add_option("--minhelix","-H",type="int",help="Minimum residues in a helix",default=6)
#	parser.add_option("--apix","-P",type="float",help="A/Pixel",default=1.0)
	
	parser.add_option("--getinfo",type="string",help="getinfo from file (either defocus, ac (amplitude contrast), or bfactor)",default="")
	parser.add_option("--remove",type="string",help="getinfo from file (either defocus, ac (amplitude contrast), or bfactor)",default="")
	
	(options, args) = parser.parse_args()
	if len(args)<1 : parser.error("Input image required")

	logid=E2init(sys.argv)

	if ( options.remove != "" ):
		a = parsemodopt_logical( options.remove )
		fileinfo_remove(args[0], a )
		E2end(logid)
		return
	if ( options.getinfo != "" ):
		fileinfo_output(args[0],options.getinfo)
	else:
		fileinfo(args[0])
	
	E2end(logid)

def fileinfo_remove(filename, info):
	
	if ( len(info) != 3 ):
		print "ERROR - logical expression must be a single expression"
		print "Could not process the following: "
		print info
		exit(1)
		
	if ( info[1] not in ["==", "<=", ">=", "!=", "~=", "<", ">"] ):
		print "ERROR: could not extract logical expression"
		print "Must be one of \"==\", \"<=\", \">=\", \"<\", \">\" "
		print info
		exit(1)
		
	if ( info[0] not in bfactor_expressions and info[0]  not in defocus_expressions and info[0]  not in ac_expressions ):
		print "ERROR: left expression %s was not in the following" %info[0]
		print bfactor_expressions
		print defocus_expressions
		print ac_expressions
		exit(1)
		
	n=EMUtil.get_image_count(filename)
	t=EMUtil.get_imagetype_name(EMUtil.get_image_type(filename))
	
	#os.unlink("cleaned.hed")
	#os.unlink("cleaned.img")

	total_removed = 0

	for i in xrange(0,n):
		d=EMData()
		d.read_image(filename,i,True)
	
		try:
			expr = d.get_attr("IMAGIC.label")
		except RuntimeError:
			print "ERROR: the image has no \"IMAGIC.label\" attribute"
			exit(1)
			
		#print expr
		vals = re.findall("\S*[\w*]", expr)
		
		if ( len(vals) < 4 ):
			print "ERROR: the CTF params were inconsistent with what was expected"
			print "I am examining image number %d, and its ctf params are as follows:" %(i+1)
			print vals
			exit(1)
			
		if ( info[0] in defocus_expressions ):
			f = re.findall("\d.*\d*", vals[0])
			score = f[0]
		if ( info[0] in bfactor_expressions ):
			score = vals[1]
		if ( info[0] in ac_expressions ):
			score = vals[3]
		
		score = float(score)
		comparison_value = float(info[2])
		
		
		write_image = True
		if ( info[1] == "==" ):
			if ( score == comparison_value ):
				write_image = False
		if ( info[1] == "!=" or info[1] == "~="):
			if ( score != comparison_value ):
				write_image = False
		if ( info[1] == ">=" ):
			if ( score >= comparison_value ):
				write_image = False
		if ( info[1] == "<=" ):
			if ( score <= comparison_value ):
				write_image = False
		if ( info[1] == ">" ):
			if ( score > comparison_value ):
				write_image = False
		if ( info[1] == "<" ):
			if ( score < comparison_value ):
				write_image = False
				
		if write_image:
			dd=EMData()
			# now read the image data as well as the header
			dd.read_image(filename,i)
			dd.write_image("cleaned.img", -1 )
		else:
			total_removed += 1
	
	print "Of a total of %d images %d were removed" %(n,total_removed)

def fileinfo_output(filename, infotype):
	
	if ( infotype not in defocus_expressions and infotype not in bfactor_expressions and infotype not in ac_expressions ):
		print "Error, infotype %s must be in the following sets:" %infotype
		print bfactor_expressions
		print defocus_expressions
		print ac_expressions
		return
	
	#l=[len(i) for i in filenames]
	#l=max(l)
	
	n=EMUtil.get_image_count(filename)
	t=EMUtil.get_imagetype_name(EMUtil.get_image_type(filename))

	for i in xrange(0,n):
		d=EMData()
		d.read_image(filename,i,True)
	
		try:
			expr = d.get_attr("IMAGIC.label")
		except RuntimeError:
			print "ERROR: the image has no \"IMAGIC.label\" attribute"
			exit(1)
			
					#print expr
		vals = re.findall("\S*[\w*]", expr)
		
		if ( infotype in defocus_expressions ):
			f = re.findall("\d.*\d*", vals[0])
			defocus = f[0]
			print "%f" %float(defocus)
		if ( infotype in bfactor_expressions ):
			envelope = vals[1]
			print "%f" %float(envelope)
		if ( infotype in ac_expressions ):
			ac = vals[3]
			print "%f" %float(ac)

def fileinfo(filenames):
	if isinstance(filenames,str) : filenames=[filenames]
	
	l=[len(i) for i in filenames]
	l=max(l)
	
	for i in filenames:
		n=EMUtil.get_image_count(i)
		t=EMUtil.get_imagetype_name(EMUtil.get_image_type(i))
		d=EMData()
		d.read_image(i,0,True)
		if d.get_zsize()==1:
			s="%%-%ds%%s\t%%d\t%%d x %%d"%(l+2)
			print s%(i,t,n,d.get_xsize(),d.get_ysize())
		else:
			s="%%-%ds%%s\t%%d\t%%d x %%d x %%d"%(l+2)
			print s%(i,t,n,d.get_xsize(),d.get_ysize(),d.get_zsize())
		
# If executed as a program
if __name__ == '__main__':
	main()	

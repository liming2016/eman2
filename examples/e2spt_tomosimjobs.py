#!/usr/bin/env python

#
# Author: Jesus Galaz, 02/21/2012 - using code and concepts drawn from Jesus Galaz's scripts
# Copyright (c) 2011 Baylor College of Medicine
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
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  2111-1307 USA
#
#

from optparse import OptionParser
from EMAN2 import *
from sys import argv
import EMAN2
import heapq
import operator
import random
import numpy
import colorsys

from mpl_toolkits.mplot3d import Axes3D
import numpy as np
import matplotlib.pyplot as plt

def main():
	progname = os.path.basename(sys.argv[0])
	usage = """prog <output> [options]

	This program takes in a model in .hdf format, calls e2spt_simulation.py to generate a simulated set of subtomograms from it,
	and characterizes the ability of EMAN2's e2classaverage3d.py to align the particles under varying Single Particle Tomography
	parameters.
	"""
			
	parser = EMArgumentParser(usage=usage,version=EMANVERSION)
	
	#parser = OptionParser(usage=usage,version=EMANVERSION)
	
	parser.add_argument("--path",type=str,default=None,help="Directory to store results in. The default is a numbered series of directories containing the prefix 'sptsimjob'; for example, sptsimjob_02 will be the directory by default if 'sptsimjob_01' already exists.")
	
	parser.add_argument("--snrlowerlimit", type=float,default=0.0,help="Minimum weight for noise compared to singal.")
	parser.add_argument("--snrupperlimit", type=float,default=1.0,help="Maximum weight for noise compared to singal.")

	parser.add_argument("--snrchange", type=float,default=1.0,help="""Step to vary snr from one run to another. 
										For example, if this parameter is set to 2.0, snr will be tested from --snrlowerlimit (for example, 0.0), increasing by --snrchange, 0.0,2.0,4.0... up to --snrupperlimit.""")

	parser.add_argument("--tiltrangelowerlimit", type=int,default=60,help="""Minimum value for imaging range (at a value of 90, there's no missing wedge. 
											60 would mean the data will be simulated, as if it came from a tomogram that was reconstructed from a til series
											collected from -60deg to 60deg)""")
	parser.add_argument("--tiltrangeupperlimit", type=int,default=61,help="""Maximum value to simulate the imaging range. Simulations will be run starting at --tiltrangelowerlimit, and will increase
											by --tiltrangestep, until the last simulation is done at --tiltrangeupperlimit.""")
	parser.add_argument("--tiltrangechange", type=int,default=1,help="Amount (in degrees) to decrease the size of the missing wedge from one run to another.")	
	
	
	parser.add_argument("--tiltsteplowerlimit", type=int,default=1,help="""Within each tiltrange simulated, you can simulate individual pictures taken with different tilt steps.
										For example, if you collect images from -60deg to 60deg with a 2deg tilt step, the tilt series will have 61 images.
										If, on the other hand, the tilt step was 4deg, the tilt series will only have 31 images.
										--tiltstepupperlimit is the largest step size you want to simulate.""")
	parser.add_argument("--tiltstepupperlimit", type=int,default=2,help="""Within each tiltrange simulated, you can simulate individual pictures taken with different tilt steps.
										For example, if you collect images from -60deg to 60deg with a 2deg tilt step, the tilt series will have 61 images.
										If, on the other hand, the tilt step was 4deg, the tilt series will only have 31 images.
										--tiltstepupperlimit is the largest step size you want to simulate.""")
	parser.add_argument("--tiltstepchange", type=int,default=1,help="""Increase in size of tilt step from one run to another. 
											Jobs will be run using --tiltstepstep as the first value, and then adding that value on subsequent runs until --tiltsteplimit is reached""")
											
	parser.add_argument("--nsliceslowerlimit", type=int,default=0,help="Lowest number of slices to divide the tiltrange in. If on and --nslicesupperlimit is ALSO on (any number other than zero), this will turn off all tiltstep parameters.")	

	parser.add_argument("--nslicesupperlimit", type=int,default=0,help="Largest number of slices to divide the tiltrange in. If on and --nsliceslowerlimit is ALSO on (values other than zero), this will turn off all tiltstep parameters.")	

	parser.add_argument("--nsliceschange", type=int,default=1,help="Change with which the nslices parameter in e2spt_simulation.py will be varied. Will only work if --nslicesupperlimit and --nsliceslowerlimit are different than zero.")
	
	"""
	Parameters to be passed on to e2spt_simulation.py
	"""
	parser.add_argument("--input", type=str, help="""The name of the input volume from which simulated subtomograms will be generated. 
							The output will be in HDF format, since volume stack support is required. The input CAN be PDB, MRC or and HDF stack. 
							If the input file is PDB or MRC, a version of the supplied model will be written out in HDF format.
							If the input file is a stack, simulatd subvolumes will be generated from each model in the stack and written to different output stacks.
							For example, if the input file contains models A and B, two output stacks with simulated subvolumes will be generated.""", default=None)
				
	parser.add_argument("--filter",type=str,help="""A filter (as in a processor from e2proc3d.py) apply to the model before generating simulated particles from it.
							Type 'e2help.py processors' at the command line and find the options availbale from the processors list)""",default=None)
	
	parser.add_argument("--shrink", type=int,default=1,help="Optionally shrink the input volume before the simulation if you want binned/down-sampled subtomograms.")
	parser.add_argument("--verbose", "-v", dest="verbose", action="store", metavar="n",type=int, default=0, help="verbose level [0-9], higner number means higher level of verboseness")
	
	parser.add_argument("--nptcls", type=int,default=10,help="Number of simulated subtomograms tu generate per referece.")
	parser.add_argument("--tx", type=int,default=None,help="""Maximum number of pixels to randomly translate each subtomogram in X. The random translation will be picked between -txrange and +txrange. 
								     Default value is set by --transrange, but --txrange will overwrite it if specified.""")
	parser.add_argument("--ty", type=int,default=None,help="""Maximum number of pixels to randomly translate each subtomogram in Y. The random translation will be picked between -tyrange and +tyrange.
								     Default value is set by --transrange, but --txrange will overwrite it if specified.""")
	parser.add_argument("--tz", type=int,default=None,help="""Maximum number of pixels to randomly translate each subtomogram in Z. The random translation will be picked between -tzrange and +tzrange.
								     Default value is set by --transrange, but --txrange will overwrite it if specified.""")
	parser.add_argument("--transrange", type=int,default=4,help="""Maximum number of pixels to randomly translate each subtomogram in all X, Y and Z. 
									The random translation will be picked between -transrage and +transrange; --txrange, --tyrange and --tzrange overwrite --transrange for each specified direction.""")
	
	parser.add_argument("--applyctf", action="store_true",default=False,help="If on, it applies ctf to the projections in the simulated tilt series based on defocus, cs, and voltage parameters.")

	parser.add_argument("--defocus", type=int,default=3,help="Intended defocus at the tilt axis (in microns) for the simulated tilt series.")
	parser.add_argument("--voltage", type=int,default=200,help="Voltage of the microscope, used to simulate the ctf added to the subtomograms.")
	parser.add_argument("--cs", type=int,default=2,help="Cs of the microscope, used to simulate the ctf added to the subtomograms.")

	parser.add_argument("--gridholesize", type=int,default=2,help="""Size of the carbon hole for the simulated grid (this will determine shifts in defocus for each particle at 
									each tilt step, depending on the position of the particle respect to the tilt axis, which is assigned randomly.""")
	parser.add_argument("--saverandstack", action="store_true",default=False,help="Save the stack of randomly oriented particles, before subtomogram simulation (before the missing wedge and noise are added).")
	parser.add_argument("--saveprjs", action="store_true",default=False,help="Save the projections (the 'tilt series') for each simulated subtomogram.")

	parser.add_argument("--reconstructor", type=str,default="fourier",help="""The reconstructor to use to reconstruct the tilt series into a tomogram. Type 'e2help.py reconstructors' at the command line
											to see all options and parameters available.""")

	parser.add_argument("--pad", type=int,default=0,help="""If on, it will increase the box size of the model BEFORE generating projections and doing 3D reconstruction of simulated sutomograms.""")								
	
	parser.add_argument("--finalboxsize", type=int,default=0,help="""The final box size to clip the subtomograms to.""")								

	parser.add_argument("--snr",type=int,help="Weighing noise factor for noise added to the image. Only words if --addnoise is on.",default=5)
	parser.add_argument("--addnoise",action="store_true",default=False,help="If on, it adds random noise to the particles")
	
	parser.add_argument("--sym",type=str,default='c1',help="If your particle is symmetrical, you should randomize it's orientation withing the asymmetric unit only. Thus, provide the symmetry.")

	parser.add_argument("--notrandomize",action="store_true",default=False,help="This will prevent the simulated particles from being rotated and translated into random orientations.")
	parser.add_argument("--simref",action="store_true",default=False,help="This will make a simulated particle in the same orientation as the original input (or reference).")
	parser.add_argument("--ppid", type=int, help="Set the PID of the parent process, used for cross platform PPID",default=-1)
	parser.add_argument("--negativecontrast",action="store_true",default=False,help="This will make the simulated particles be like real EM data before contrast reversal. Otherwise, 'white protein' (positive density values) will be used.")

	parser.add_argument("--testalignment",action="store_true",default=False,help="This will run e2spt_classaverage.py to test the alignment of the particles against the simulated reference.")

	parser.add_argument("--quicktest",action="store_true",default=False,help="This will run e2spt_classaverage.py with minimal parameters to quickly test the program.")
	parser.add_argument("--plotonly",type=str,default='',help="""Text files to be plotted, with information in the correct format. To enter multiple files, separate them with commas: file1,file2,etc...
								Each file must contain lines with the following values:
								tr= ts= snr= angular_error= translational_error=""")
	
	"""
	Parameters to be passed on to e2spt_classaverage.py
	"""
	parser.add_argument("--raligncmp",type=str,default='ccc',help="Comparator to use for missing wedge compensation during fine alignment.")
	parser.add_argument("--aligncmp",type=str,default='ccc',help="Comparator to use for missing wedge compensation during coarse alignment.")
	parser.add_argument("--parallel",type=str,default='thread:7',help="Parallelization to use.")

	(options, args) = parser.parse_args()	
	
	logger = E2init(sys.argv, options.ppid)
	
	'''
	Make the directory where to create the database where the results will be stored
	'''
	
	#if options.path and ("/" in options.path or "#" in options.path) :
	#	print "Path specifier should be the name of a subdirectory to use in the current directory. Neither '/' or '#' can be included. "
	#	sys.exit(1)
		
	#if options.path and options.path[:4].lower()!="bdb:": 
	#	options.path="bdb:"+options.path

	#if not options.path: 
	#	#options.path="bdb:"+numbered_path("sptavsa",True)
	#	options.path = "sptsim_01"
	
	
	#if options.path and ("/" in options.path or "#" in options.path) :
	#	print "Path specifier should be the name of a subdirectory to use in the current directory. Neither '/' or '#' can be included. "
	#	sys.exit(1)

	if not options.path: 
		#options.path="bdb:"+numbered_path("sptavsa",True)
		options.path = "sptsimjob_01"
	
	rootpath = os.getcwd()
	
	files=os.listdir(rootpath)
	print "right before while loop"
	while options.path in files:
		print "in while loop, options.path is", options.path
		#path = options.path
		if '_' not in options.path:
			print "I will add the number"
			options.path = options.path + '_00'
		else:
			jobtag=''
			components=options.path.split('_')
			if components[-1].isdigit():
				components[-1] = str(int(components[-1])+1).zfill(2)
			else:
				components.append('00')
						
			options.path = '_'.join(components)
			#options.path = path
			print "The new options.path is", options.path

	if options.path not in files:
		
		print "I will make the path", options.path
		os.system('mkdir ' + options.path)	
	
	if not options.plotonly:
		#if options.testalignment:	
		#	resultsdir = 'results_ali_errors'
		#	os.system('cd ' + options.path + ' && mkdir ' + resultsdir)
	
	
		snrl = options.snrlowerlimit
		snru = options.snrupperlimit
		snrch = options.snrchange

		tiltrangel = options.tiltrangelowerlimit
		tiltrangeu = options.tiltrangeupperlimit
		tiltrangech = options.tiltrangechange

		tiltstepl = options.tiltsteplowerlimit
		tiltstepu = options.tiltstepupperlimit
		tiltstepch = options.tiltstepchange
	
		if options.nsliceschange and options.nsliceslowerlimit and options.nslicesupperlimit:
			tiltstepl = options.nsliceslowerlimit
			tiltstepu = options.nslicesupperlimit
			tiltstepch = options.nsliceschange
	
		if tiltstepl == 0:
			print "ERROR! You cannot start with a tilt step of 0. The minimum tiltstep is 1, thus, the lower limit for this parameter, tiltsteplowerlimit, must be at least 1."
	
	
	
		nrefs = EMUtil.get_image_count(options.input)
		
		tiltrange=tiltrangel
		while tiltrange <tiltrangeu:
			print "tiltrage is", tiltrange

			tiltstep=tiltstepl
			#if options.nsliceschange and options.nsliceslowerlimit and options.nslicesupperlimit:
			#	tiltstep = options.nsliceslowerlimit


			while tiltstep < tiltstepu:
				tiltsteptag = str(tiltstep).zfill(2)

				if options.nsliceschange and options.nsliceslowerlimit and options.nslicesupperlimit:
					print "The number of slices is", tiltstep
					tiltsteptag = str( round(2.0 * tiltrange / tiltstep,1) ).zfill(4)
				else:
					print "The tilt step is", tiltstep


				snr=snrl
				while snr < snru:
					print "Snr is", snr

					#rootpath = os.getcwd()

					for d in range(nrefs):
						modeltag = ''
						subpath = rootpath + '/' + options.path + '/' +'TR' + str(tiltrange).zfill(2) + '_TS' + tiltsteptag + '_SNR' + str(snr).zfill(2)
						
						print '\n.....\n.......\n.....\n......\n.. subpath is %s .......\n.......\n.......\n' %(subpath)
						print '\n.....\n.......\n.....\n......\n.. subpath is %s .......\n.......\n.......\n' %(subpath)

						inputdata = options.input
						print '\n.....\n.......\n.....\n......\n.. inputdata is %s .......\n.......\n.......\n' %(inputdata)

						if nrefs > 1:
							modeltag = 'model' + str(d).zfill(2)
							subpath += '_' + modeltag

							model = EMData(options.input,d)
							newname = rootpath + '/' + options.path + '/' + inputdata.split('/')[-1].replace('.hdf','_' + modeltag + '.hdf')
							model.write_image(newname,0)

							#inputdata = newname.split('/')[-1] #UPDATE

						subtomos =  subpath.split('/')[-1] + '.hdf'

						jobcmd = 'e2spt_simulation.py --input=' + inputdata + ' --output=' + subtomos + ' --snr=' + str(snr) + ' --nptcls=' + str(options.nptcls) + ' --tiltstep=' + str(tiltstep) + ' --tiltrange=' + str(tiltrange) + ' --transrange=' + str(options.transrange) + ' --pad=' + str(options.pad) + ' --shrink=' + str(options.shrink) + ' --finalboxsize=' + str(options.finalboxsize)

						if options.nsliceschange and options.nsliceslowerlimit and options.nslicesupperlimit:
							print "\n\n\n$$$$$$$$$$$$$$\nYou hvae provided the number of slices\n$$$$$$$$\n\n\n",tiltstep
							jobcmd = 'e2spt_simulation.py --input=' + inputdata + ' --output=' + subtomos + ' --snr=' + str(snr) + ' --nptcls=' + str(options.nptcls) + ' --nslices=' + str(tiltstep) + ' --tiltrange=' + str(tiltrange) + ' --transrange=' + str(options.transrange) + ' --pad=' + str(options.pad) + ' --shrink=' + str(options.shrink) + ' --finalboxsize=' + str(options.finalboxsize)

						if options.simref:
							jobcmd += ' --simref'
						if options.addnoise:
							jobcmd += ' --addnoise'
						if options.saveprjs:
							jobcmd += ' --saveprjs'
						if options.negativecontrast:
							jobcmd += ' --negativecontrast'

						jobcmd += ' --path=' + subpath.split('/')[-1]				

						cmd = 'cd ' + options.path + ' && ' + jobcmd

						resultsfiles=[]

						if options.testalignment:

							#modeldir = ''
							#if nrefs > 1:
							#	modeldir = '/model' + str(d).zfill(2)

							#cmd = cmd + ' && cd ' + rootpath + '/' + options.path + '/' + subpath #UPDATE
							cmd = cmd + ' && cd ' + subpath

							#subtomos = options.input.split('/')[-1].replace('.hdf','_sptsimMODEL_randst_n' + str(options.nptcls) + '_' + subpath + '_subtomos.hdf')

							print "\nRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRR\nRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRRR\nSubtomos name will be\n", subtomos

							ref = inputdata.split('/')[-1].replace('.hdf','_sptsimMODEL_SIM.hdf')

							#if nrefs > 1:
							#	modd = 'model' + str(d).zfill(2)
							#	ref = options.input.split('/')[-1].replace('.hdf','_sptsimMODELS_' + modd + '.hdf')

							output=subtomos.replace('.hdf', '_avg.hdf')
							#print "\n\n$$$$$$$$$$$$$$$$$$$$$$\nRef name is\n$$$$$$$$$$$$$$$$$$$\n", ref

							print "\n\%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%noutput name is\n", output

							alipath1=output.split('/')[-1].replace('_avg.hdf','_ali')
							alipath2= subpath + '/' + output.replace('_avg.hdf','_ali')
							print "\n##################################\nAlipath1 for results will be\n", alipath1
							print "\n##################################\nAlipath2 for results will be\n", alipath2

							alicmd = " && e2spt_classaverage.py --path=" + alipath1 + " --input=" + subtomos.replace('.hdf','_ptcls.hdf') + " --output=" + output + " --ref=" + ref + " --npeakstorefine=4 -v 0 --mask=mask.sharp:outer_radius=-4 --lowpass=filter.lowpass.gauss:cutoff_freq=.02 --align=rotate_translate_3d:search=" + str(options.transrange) + ":delta=12:dphi=12:verbose=0 --parallel=" + options.parallel + " --ralign=refine_3d_grid:delta=12:range=12:search=2 --averager=mean.tomo --aligncmp=" + options.aligncmp + " --raligncmp=" + options.raligncmp + " --shrink=2 --savesteps --saveali --normproc=normalize"

							if options.quicktest:
								alicmd = " && e2spt_classaverage.py --path=" + alipath1 + " --input=" + subtomos.replace('.hdf','_ptcls.hdf') + " --output=" + output + " --ref=" + ref + " -v 0 --mask=mask.sharp:outer_radius=-4 --lowpass=filter.lowpass.gauss:cutoff_freq=.02 --align=rotate_symmetry_3d:sym=c1:verbose=0 --parallel=" + options.parallel + " --ralign=None --averager=mean.tomo --aligncmp=" + options.aligncmp + " --raligncmp=" + options.raligncmp + " --shrink=3 --savesteps --saveali --normproc=normalize"

							aliptcls = output.replace('_avg.hdf','_ptcls_ali.hdf')

							#print "\n\aliptcls name is\n", aliptcls

							extractcmd = " && cd " + alipath2 + " && e2proc3d.py bdb:class_ptcl " + aliptcls

							resultsfile=aliptcls.replace('_ptcls_ali.hdf','_ali_error.txt')
							
							print "\n@@@@@@@\n@@@@@@@\n@@@@@@@@@\n@@@@@@@ Results file is %s \n@@@@@@@\n@@@@@@@\n@@@@@@@@@\n@@@@@@@" %(resultsfile)

							solutioncmd = " && e2spt_transformdistance.py --input=" + aliptcls + ' --output=' + resultsfile

							rfilecmd =  ' && mv ' + resultsfile + ' ' +  rootpath + '/' + options.path

							cmd = cmd + alicmd + extractcmd + solutioncmd + rfilecmd

						print "\n\n\n*********************The command to execute is \n %s \n*********************\n" %(cmd)

						os.system(cmd)

					snr += snrch

				tiltstep += tiltstepch

			tiltrange += tiltrangech

		if nrefs > 1:
			for i in range(nrefs):

				modname = 'model' + str(i).zfill(2)
				#print "\nI will make this moddir", modname
				cmdd='cd ' + options.path + ' && mkdir ' + modname + ' && mv *' + modname + '* ' + modname
				#print "\nBy executing this command", cmdd
				os.system(cmdd)

			for i in range(nrefs):
				modname = 'model' + str(i).zfill(2)

				resultsdir = rootpath + '/' + options.path + '/' + modname + '/results_ali_error_' + modname
				#print "\n\n\n\n*******************\nResults dir is\n", resultsdir

				os.system('mkdir ' +  resultsdir + ' && cd ' + options.path + '/' + modname + ' && mv *error.txt ' + resultsdir)

		else:
			print "\n\n***************\nThere was only one reference\n************\n\n"
			
			resultsdir = rootpath + '/' + options.path + '/results_ali_error'
			os.system('mkdir ' + resultsdir + ' && cd ' + options.path + ' && mv *error.txt ' + resultsdir)
		
			
		resultsdir = rootpath + '/' + options.path + '/results_ali_error' 	
		for i in range(nrefs):
			if nrefs > 1:
				modname = 'model' + str(i).zfill(2)
				resultsdir = rootpath + '/' + options.path + '/' + modname + '/results_ali_error_' + modname
	
		
			resfiles = []
			ang_errors = []
			trans_errors = []
		
			snrs = []
			trs = []
			tss = []
		
			twoD_tr_ts_points = []
			twoD_snr_tr_points = []	
			twoD_snr_ts_points = []
			
			threeD_points = []
		
			findir = os.listdir(resultsdir)
			for f in findir:
				if 'error.txt' in f:
					resfiles.append(f)
			
			resfiles.sort()
			for ff in resfiles:
				tr = float(ff.split('TR')[-1].split('_')[0])
				trs.append(tr)
	
				snr = float(ff.split('SNR')[-1].split('_')[0])
				snrs.append(snr)
				
				ts = float(ff.split('TS')[-1].split('_')[0])
				tss.append(ts)
				
				#3dpoints.append([tr,snr,ts])
			
				
				resultsfilelocation = resultsdir + '/' + ff
				#print "\n\n%%%%%%%%%%%%\nThe results file is here\n%%%%%%%%%%%%%%%%%\n\n", resultsfilelocation
				
				fff = open(resultsfilelocation,'r')
				lines = fff.readlines()
				
				ang = float( lines[0].split('=')[-1].replace('\n','') )
				ang_errors.append(ang)
				
				trans = float( lines[1].split('=')[-1].replace('\n','') )
				trans_errors.append(trans)
				
				threeD_points.append({'tilt range':tr,'tilt step':ts,'noise level':snr,'angular_error':ang,'translational_error':trans})
				twoD_tr_ts_points.append({'tilt range':tr,'tilt step':ts,'angular_error':ang,'translational_error':trans})
				twoD_snr_tr_points.append({'tilt range':tr,'noise level':snr,'angular_error':ang,'translational_error':trans})
				twoD_snr_ts_points.append({'tilt step':ts,'noise level':snr,'angular_error':ang,'translational_error':trans})
				
			if len(set(snrs)) == 1: 
				if len(set(trs)) == 1:
					oneD_plot(tss,ang_errors,resultsdir+'/angular_error.png','tilt step')
					oneD_plot(tss,trans_errors,resultsdir+'/translational_error.png','tilt step')
				
				if len(set(tss)) == 1:
					oneD_plot(trs,ang_errors,resultsdir+'/angular_error.png','tilt range')
					oneD_plot(trs,trans_errors,resultsdir+'/translational_error.png','tilt range')
				
			if len(set(trs)) == 1: 
				if len(set(tss)) == 1:
					oneD_plot(snrs,ang_errors,resultsdir+'/angular_error.png','noise level')
					oneD_plot(snrs,trans_errors,resultsdir+'/translational_error.png','noise level')
		
			if len(set(snrs)) == 1 and len(set(trs)) > 1 and len(set(tss)) > 1:
				twoD_plot(twoD_tr_ts_points,val1='tilt range',val2='tilt step',location=resultsdir +'/')
			
			if len(set(trs)) == 1 and len(set(snrs)) > 1 and len(set(tss)) > 1:
				twoD_plot(twoD_snr_ts_points,val1='noise level',val2='tilt step',location=resultsdir +'/')
			
			if len(set(tss)) == 1 and len(set(trs)) > 1 and len(set(snrs)) > 1:
				twoD_plot(twoD_snr_tr_points,val1='noise level',val2='tilt range',location=resultsdir +'/')
			
			if len(set(tss)) > 1 and len(set(trs)) > 1 and len(set(snrs)) > 1:
				threeD_plot(threeD_points,resultsdir +'/')
			
	elif options.plotonly:
		files=options.plotonly.split(',')
		print "\n\nI'm in PLOTONLY \n\n"
		print "\n\nAnd these are the files", files
		print "\n\n"
		d=0
		resultsdir = rootpath + '/' + options.path
		
		for ff in files:
			print "\n\nI'm analyzing file %d\n\n" %(d)	
			if len(files) > 1:
				modname = 'file' + str(d).zfill(2) + 'plots'
				resultsdir = rootpath + '/' + options.path + '/' + modname
				os.system('mkdir ' + resultsdir)
				
				print "\n\nSupposedly I made this results dir %s\n\n" %(resultsdir)
			else:
				print "\n\nThere's only one file therefore resultsdir is %s\n\n" %(resultsdir)
				print "\n\nSee, files are", files
			
			#resfiles = []
			ang_errors = []
			trans_errors = []
		
			snrs = []
			trs = []
			tss = []
		
			twoD_tr_ts_points = []
			twoD_snr_tr_points = []	
			twoD_snr_ts_points = []
			
			threeD_points = []
			
			fff = open(ff,'r')
			lines = fff.readlines()
			
			#findir = os.listdir(resultsdir)
			#for f in findir:
			#	if 'error.txt' in f:
			#		resfiles.append(f)
			
			#resfiles.sort()
			for line in lines:
				tr = float( line.split('tr=')[-1].split(' ')[0] )
				trs.append(tr)
	
				snr = float( line.split('snr=')[-1].split(' ')[0] )
				snrs.append(snr)
				
				ts = float( line.split('ts=')[-1].split(' ')[0] )
				tss.append(ts)
				
				#threeD_points.append( [tr,snr,ts] )
				
				ang = float( line.split('angular_error=')[-1].split(' ')[0] )
				ang_errors.append(ang)
				
				trans = float( line.split('translational_error=')[-1].split(' ')[0] )
				trans_errors.append(trans)
				
				threeD_points.append({'tilt range':tr,'tilt step':ts,'noise level':snr,'angular_error':ang,'translational_error':trans})
				twoD_tr_ts_points.append({'tilt range':tr,'tilt step':ts,'angular_error':ang,'translational_error':trans})
				twoD_snr_tr_points.append({'tilt range':tr,'noise level':snr,'angular_error':ang,'translational_error':trans})
				twoD_snr_ts_points.append({'tilt step':ts,'noise level':snr,'angular_error':ang,'translational_error':trans})
				
			if len(set(snrs)) == 1: 
				if len(set(trs)) == 1:
					oneD_plot(tss,ang_errors,resultsdir+'/angular_error_varTS_' + str(d).zfill(len(files)) + '.png','tilt step')
					oneD_plot(tss,trans_errors,resultsdir+'/translational_error_varTS_' + str(d).zfill(len(files)) + '.png','tilt step')
				
				if len(set(tss)) == 1:
					oneD_plot(trs,ang_errors,resultsdir+'/angular_error_varTR_' + str(d).zfill(len(files)) + '.png','tilt range')
					oneD_plot(trs,trans_errors,resultsdir+'/translational_error_varTR_' + str(d).zfill(len(files)) + '.png','tilt range')
				
			if len(set(trs)) == 1: 
				if len(set(tss)) == 1:
					oneD_plot(snrs,ang_errors,resultsdir+'/angular_error_varSNR_' + str(d).zfill(len(files)) + '.png','noise level')
					oneD_plot(snrs,trans_errors,resultsdir+'/translational_error_varSNR_' + str(d).zfill(len(files)) + '.png','noise level')
		
			if len(set(snrs)) == 1 and len(set(trs)) > 1 and len(set(tss)) > 1:
				twoD_plot(twoD_tr_ts_points,val1='tilt range',val2='tilt step',location=resultsdir +'/')
			
			if len(set(trs)) == 1 and len(set(snrs)) > 1 and len(set(tss)) > 1:
				twoD_plot(twoD_snr_ts_points,val1='noise level',val2='tilt step',location=resultsdir +'/')
			
			if len(set(tss)) == 1 and len(set(trs)) > 1 and len(set(snrs)) > 1:
				twoD_plot(twoD_snr_tr_points,val1='noise level',val2='tilt range',location=resultsdir +'/')
			
			if len(set(tss)) > 1 and len(set(trs)) > 1 and len(set(snrs)) > 1:
				threeD_plot(threeD_points,resultsdir +'/')
		
			d=+1
				
	E2end(logger)

	return()


def color(value):
	color =	colorsys.hsv_to_rgb( float(value) / 180.0 / (1.1), 1, 1)
	return(color)


def oneD_plot(points,errors,name,concept):
	
	title=name.split('/')[-1].replace('.png','').replace('_',' ')
	#plt.title(title)
	plt.xlabel(concept)
	plt.ylabel(title)
	#plt.xlim([min(points)-min(points)*0.1,max(points)+max(points)*0.1])
	plt.xlim( [0,max(points)+max(points)*0.1] )
	plt.ylim( [0,max(errors)+max(errors)*0.1] )
	plt.plot(points,errors,color='b',linewidth=3)
	plt.savefig(name,bbox_inches=0)
	plt.clf()
	
	return()
	

def twoD_plot(points,val1,val2,location):
	
	finalpoints = []
	ang_errors = []
	trans_errors = [] 
	x=[]
	y=[]
	for p in points:
		finalpoints.append([ p[val1],p[val2] ])
		x.append(p[val1])
		y.append(p[val2])
		ang_errors.append(p['angular_error'])
		trans_errors.append(p['translational_error'])
	
	plotname1 = location + 'angular_errors_2d_' + '_'.join(val1.split(' ')) + '.png'
	print "\n\n########\nI will save the plot inside 2d_plot to\n########\n\n", plotname1

	plt.title("Angular error")
	plt.xlabel(val1)
	plt.ylabel(val2)
	plt.xlim([min(x)-min(x)*0.1,max(x)+max(x)*0.1])
	plt.ylim([min(y)-min(y)*0.1,max(y)+max(y)*0.1])
	for i in range(len(finalpoints)):
		plt.plot(*zip(*[finalpoints[i]]),marker='o',markersize=4,color=color(ang_errors[i]))	
	plt.savefig(plotname1,bbox_inches=0)
	#plt.clf()
	
	'''
	plotname2 = 'translational_errors_2d_' + '_'.join(val1.split(' ')) + '.png'
	plt.title("Translational error")
	plt.xlabel(val1)
	plt.ylabel(val2)
	for i in range(len(finalpoints)):
		plt.plot(*zip(*[finalpoints[i]]),marker='o',markersize=2,color=color(trans_errors[i]))
	plt.savefig(plotname2)
	#plt.clf()
	'''
	return()
	
	
def threeD_plot(points,location):
	
	finalpoints = []
	ang_errors = []
	trans_errors = []
	x=[]
	y=[]
	z=[] 
	for p in points:
		x.append(p['tilt range'])			
		y.append(p['noise level'])
		z.append(p['tilt step'])
	
		finalpoints.append([ p['tilt range'],p['noise level'],p['tilt step'] ])
		ang_errors.append(p['angular_error'])
		trans_errors.append(p['translational_error'])
	
	plotname1 = location + 'angular_errors_3d.png'
	
	print "\n\n#########\nI will save the plot inside 3d_plot to\n###########\n\n", plotname1
	
	fig = plt.figure()
	ax = fig.gca(projection='3d')
	
	plt.title("Angular error")
	xLabel = ax.set_xlabel('tilt range')
	yLabel = ax.set_ylabel('noise level')
	zLabel = ax.set_zlabel('tilt step')
	
	ax.set_xlim3d(min(x)-min(x)*0.1,max(x)+max(x)*0.1) 
	ax.set_ylim3d(min(y)-min(y)*0.1,max(x)+max(y)*0.1)
	ax.set_zlim3d(min(z)-min(z)*0.1,max(z)+max(z)*0.1)                              
	
	ax.xaxis.labelpad = 30
	ax.yaxis.labelpad = 30

	#ax.dist = 15
	for i in range(len(finalpoints)):
		ax.plot(*zip(*[finalpoints[i]]),marker='o',markersize=4, color=color(ang_errors[i]) )
	plt.savefig(plotname1,bbox_inches=0)
	print "\n\n**********\nI HAVE saved the plot inside 3d_plot to\n********\n\n", plotname1

	#plt.clf()
	
	
	'''
	plotname2 = 'translational_errors_3d.png'
	plt.title("Angular error")
	
	xLabel = ax.set_xlabel('tilt range')
	yLabel = ax.set_ylabel('noise level')
	zLabel = ax.set_zlabel('tilt step')
	
	fig = plt.figure()
	ax = fig.gca(projection='3d')
	for i in range(len(finalpoints)):
		ax.plot(*zip(*[finalpoints[i]]),marker='o',color=color(trans_errors[i]) )
	plt.savefig(plotname2)
	#plt.clf()
	'''
	return()	
	
	
if __name__ == "__main__":
    main()

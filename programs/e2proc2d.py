#!/bin/env python

# $Id$

from EMAN2 import *
from optparse import OptionParser
import sys
import os.path
import math
import random

# todo: average_nimg

def read_listfile(listfile, excludefile, nimg):
    imagelist = None
    infile = None
    exclude = 0
    
    if listfile:
        infile = listfile
    elif excludefile:
        infile = excludefile
        exclude = 1
        
    if infile:
        try:
            lfp = open(infile, "rb")
        except IOError:
            print "Error: couldn't read list file '%s'" % infile
            sys.exit(1)
        
        if exclude:
            imagelist = [1] * nimg
        else:
            imagelist = [0] * nimg

        imagelines = lfp.readlines()
        for line in imagelines:
            if line[0] != "#":
                n = int(line)
                if n >= 0 and n < nimg:
                    if options.exclude:
                        imagelist[n] = 0
                    else:
                        imagelist[n] = 1
    return imagelist



def main():
    progname = os.path.basename(sys.argv[0])
    usage = progname + " options inputfile outputfile"

    parser = OptionParser(usage)

    parser.add_option("--first", type="int", help="first image")
    parser.add_option("--last", type="int", help="last image")
    parser.add_option("--exclude", type="string", help="")
    parser.add_option("--list", type="string", help="")
    
    parser.add_option("--apix", type="float", help="")
    parser.add_option("--average", action="store_true", help="")
    parser.add_option("--inplace", action="store_true", help="inplace ")
    parser.add_option("--verbose", type="int", help="verbose level [1-5]")

    parser.add_option("--plt", type="string", help="")
    parser.add_option("--split", type="int", help="")
    
    parser.add_option("--ctfsplit", action="store_true", help="")
    parser.add_option("--mraprep",  action="store_true", help="")

    parser.add_option("--norefs", action="store_true", help="")

    parser.add_option("--outtype", type="string", help="")
    parser.add_option("--radon",  action="store_true", help="")
    parser.add_option("--rfp",  action="store_true", help="")
    # check
    parser.add_option("--setsfpairs",  action="store_true", help="")    

    # the following needs append
    parser.add_option("--calcsf", type="string", nargs=2, help="")    
    parser.add_option("--clip", type="float", nargs=2, help="2D clip")

    parser.add_option("--fftavg", type="string", help="")
    parser.add_option("--filter", type="string", action="append", help="filter name")
    parser.add_option("--interlv", type="string", help="")
    
    parser.add_option("--meanshrink", type="int", help="")
    parser.add_option("--shrink", type="int", help="shrink factor")
       
    parser.add_option("--scale", type="float", help="scale")
    parser.add_option("--selfcl", type="int", nargs=2, help="")
 

    optionlist = []
    for arg1 in sys.argv[1:]:
        if arg1[0] == "-":
            optionlist.append(arg1.lstrip("-"))

    (options, args) = parser.parse_args()

    print options
    print args
    
    if len(args) != 2:
        print "usage: " + usage
        print "Please run '" + progname + " -h' for detailed options"
        sys.exit(1)
    
    infile = args[0]
    outfile = args[1]

    average = None
    fftavg = None
    
    n0 = 0
    n1 = -1

    if options.first:
        n0 = options.first
    if options.last:
        n1 = options.last

    sfout_n = 0
    sfout = None
    sf_amwid = 0

    if options.calcsf:
        sfout_n = int(options.calcsf[0])
        sfout = options.calcsf[1]
        sf_amwid = 2 * math.pi / sfout_n
        
    MAXMICROCTF = 1000
    defocus_val = [0] * MAXMICROCTF
    bfactor_val = [0] * MAXMICROCTF

    pltfp = None
    if options.plt:
        pltfp = open(options.plt, "wb")
    
    if options.verbose:
        Log.set_log_level(options.verbose)
    
    d = EMData()
    nimg = EMUtil.get_image_count(infile)
    if nimg <= n1 or n1 < 0:
        n1 = nimg - 1

    ld = EMData()
    print "nimg = ", nimg

    imagelist = read_listfile(options.list, options.exclude, nimg)
        
    for i in range(n0, n1+1):
        if imagelist and (not imagelist[i]):
            continue

        if options.split and options.split > 1:
            outfile = outfile[:-4] + ".%02d.img" % (i % split)

        d.read_image(infile, i)

        if pltfp:
            r = d.get_rotation()
            pi2d = 180/math.pi
            pltfp.write("%f,%f,%f \n" % (r.eman_phi() * pi2d,
                                         r.eman_alt() * pi2d,
                                         r.eman_az() * pi2d))
            continue
        
        nx = d.get_xsize()
        ny = d.get_ysize()
        
        sigma = d.get_sigma()
        if sigma == 0:
            print "Warning: sigma = 0 for image " + i
            continue

        for option1 in optionlist:
            print "option: " + option1

            if option1 == "norefs" and d.get_average_nimg() <= 0:
                continue
            
            elif option1 == "ctfsplit":

                if i == n0 or (not EMUtil.is_same_ctf(d, ld)):
                    ctf = d.get_ctf()
            
                    for j in range(1, options.ctfsplit):
                        if defocus_val[j] == ctf.get_defocus() and bfactor_val[j] == ctf.get_bfactor():
                            break
                    if options.ctfsplit <= j:
                        options.ctfsplit = j + 1
                        print "New CTF at " + i
                
                    defocus_val[j] = ctf.get_defocus()
                    bfactor_val[j] = ctf.get_bfactor()
                    outfile = outfile + ".%02d.img" % j
                    ld = d.copy(False, False)
            
            # run the filters
        
            elif option1 == "rfp":
                e = d.make_rotational_footprint()
                e.append_image("rfp.hed")

            elif option1 == "scale" and options.scale != 1.0:
                old_r = d.get_rotation()
                d.set_ralign_params(0, 0, 0)
                d.set_talign_params(0, 0, 0)
                d.rotate_translate(options.scale)
                d.set_ralign_params(old_r)
            
            elif option1 == "clip":
                clipx = options.clip[0]
                clipy = options.clip[1]                    
                e = d.get_clip(Region(nx-clipx)/2, (ny-clipy)/2, clipx, clipy)
                d = e
            
            elif option1 == "shrink" and options.shrink > 1:
                d.median_shrink(options.shrink)

            elif option1 == "meanshrink" and options.meanshrink > 1:
                d.mean_shrink(options.meanshrink)
        
            elif option1 == "selfcl":
                scl = options.selfcl[0] / 2
                sclmd = options.selfcl[1]
                sc = EMData()
            
                if sclmd == 0:
                    sc.common_lines_real(d, d, scl, true)
                else:
                    e = d.copy()
                    e.filter("Phase180")
                
                    if sclmd == 1:
                        sc.common_lines(e, e, sclmd, scl, true)
                        sc.filter("LinearXform", Dict("shift", EMObject(-90.0), "scale", EMObject(-1.0)))		
                    elif sclmd == 2:
                        sc.common_lines(e, e, sclmd, scl, true)
                    else:
                        print "Error: invalid common-line mode '" + sclmd + "'"
                        sys.exit(1)
            elif option1 == "radon":
                r = d.do_radon()
                d = r
            
            elif option1 == "average":
                if not average:
                    average = d.copy(False, False)
                else:
                    average.add(d)
                continue

            elif option1 == "fftavg":
                if not fftavg:
                    fftavg = EMData()
                    fftavg.set_size(nx+2, ny)
                    fftavg.set_complex(1)
                    fftavg.to_zero()
                d.filter("EdgeMeanMask")
                d.filter("StdNormalize")
                df = d.do_fft()
                df.mult(df.get_ysize())
                fftavg.add_incoherent(df)
                d.gimme_fft
                continue

            elif option1 == "calcsf":
                dataf = d.do_fft()
                d.gimme_fft()
                curve = dataf.calc_radial_dist(ny, 0, 0.5)
                outfile2 = sfout
                
                if n1 != 0:
                    outfile2 = sfout + ".%03d" % (i+100)
                    
                sf_dx = 1.0 / (apix * 2.0 * ny)
                Util.save_data(0, sf_dx, curve, outfile2)
	    
                if sfout_n > 0:
                    for j in range(0, sfout_n):
                        curve = dataf.calc_radial_dist(ny, 0, 0.5, j * sf_amwid, sf_amwid)                    
                        outfile2 = os.path.basename(sfout) + "-" + str(j) + "-" + str(sfout_n) + ".pwr"
                        if n1 != 0:
                            outfile2 = outfile2 + ".%03d" % (i+100)
                        Util.save_data(0, sf_dx, curve, outfile2)
         
            elif option1 == "interlv":
                d.read_image(options.interlv, i)
                d.append_image(outfile, IMAGIC)
            
            elif option1 in ["o", "outtype"]:
                if options.outtype in ["mrc", "pif", "png", "pgm"]:
                    if n1 != 0:
                        outfile = "%03d." % (i + 100) + outfile
                    
                if options.outtype == "mrc":
                    d.write_image(outfile, 0, MRC)
                
                elif options.outtype == "spidersingle":
                    if n1 != 0:
                        spiderformat = "%s%%0%dd.spi" % (outfile, int(log10(i))+1)
                        outfile = spiderformat % i
                    d.write_image(outfile, 0, SINGLE_SPIDER)

                elif options.outtype == "hdf":
                    d.append_image(outfile,  HDF)
                
                elif options.outtype == "em":
                    d.write_image(outfile, 0, EM)
                
                elif options.outtype == "pif":
                    d.write_image(outfile, 0, PIF)
                
                elif options.outtype == "png":
                    d.write_image(outfile, 0, PNG)
                
                elif options.outtype == "pgm":
                    d.write_image(outfile, 0, PGM)

                elif options.outtype == "spider":
                    d.write_image(outfile, 0, SPIDER)
                
                else:
                    if options.inplace:
                        d.write_image(outfile, i)
                    elif options.mraprep:
                        nf = outfile + "%04d" % i + ".lst"
                        d.write_image(nf, 0, LST)
                    else:
                        d.append_image(outfile, IMAGIC)
    #end of image loop

    if average:
        average.filter("StdNormalize");
	average.append_image(outfile);

    if options.fftavg:
        ffgavg.mult(1.0 / sqrt(n1 - n0 + 1))
        fftavg.write_image(options.fftavg, 0, MRC)
    
    n_outimg = EMUtil.get_image_count(args[1])
    print str(n_outimg) + " images"
    
    
if __name__ == "__main__":
    main()
    


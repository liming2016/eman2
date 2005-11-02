#!/usr/bin/python

# how to deal with unknown symmetry?
# transform3d doesn't support tetra in all its funcs
# deal with thr, hard, keep and not including some slices?
# should pad be a multiplier or should it be in pixels?
# resmap doesn't work
# need to see about SNR
# how can you save the norms? need to access tmp_data in Reconstructor class
# reverse_gridding uses complex images?

from EMAN2 import *
from optparse import OptionParser
import os
import sys
import math

def main():

    (options, files) = load_args()
    options.input_file = files[0]
    if (options.goodbad):
        try:
            os.unlink("3dgood.hed")
            os.unlink("3dbad.hed")
            os.unlink("3dgood.img")
            os.unlink("3dbad.img")
        except:
            pass

    if not(options.quite):
        print "Reading Data ..."
    images=EMData().read_images(files[0],[], options.lowmem)
    if len(images)<3 :
        sys.stderr.write("Found %d image(s): need at least 3\n" % len(images))
        exit(1)
    
    if options.recon_type=="fourier": 
        output=fourier_reconstruction(images, options)
    elif options.recon_type=="back_projection":
        output=back_projection_reconstruction(images, options)
    elif options.recon_type=="pawel_back_projection":      
        output=pawel_back_projection_reconstruction(images, options)
    elif options.recon_type=="reverse_gridding":
        output=reverse_gridding_reconstructor(images, options) 
    elif options.recon_type=="wiener_fourier":
        output=wiener_fourier_reconstructor(images, options)

    else:
        # this point should never be reached
        sys.stderr.write("%s reconstuctor is not supported" % option.recon_type)
        exit(1)
        
    if (options.filename==""):
        output.write_image("threed.mrc")
        if not(options.quite):
            print "Output File: threed.mrc"
    else:
        output.write_image(options.filename)
        if not(options.quite):
            print "Output File: "+options.filename

#-----------------------------------------
def load_args():
    # options that should work
    parser=OptionParser(usage="%prog <input file> [options]", version="%prog 2.0a")
    parser.add_option("--out", dest="filename", default="", help="Output 3D MRC file")
    parser.add_option("--lowmem", action="store_true", dest="lowmem", default=False,
                      help="Read in images only when needed instead of preloading all in memory")
    parser.add_option("--sym", dest="sym", default="UNKNOWN", help="Set the symmetry; if no value is given then the model is assumed to have no symmetry.\nChoices are: i, c, d, t, icos, or oct")
    parser.add_option("--pad", type=int, dest="pad", default=0, help="To reduce Fourier artifacts, the model is typically padded by ~25%")
    parser.add_option("--mode", type=int, dest="mode", default=2, help="Specifies the interpolation size (1 to 6), 2 is the default")
    parser.add_option("--recon", dest="recon_type", default="fourier", help="Reconstructor to use")
    parser.add_option("--quite", dest="quite", default=False, action="store_true",
                      help="Quite output")

    # options that don't work
    parser.add_option("--snrfile", dest="snrfile", default="", help="Use a SNR file (as generated by classalignall) for proper 3D Wiener filtration")
    parser.add_option("--goodbad", action="store_true", dest="goodbad", default=False, help="Saves the used and unused class averages in 2 files")
    parser.add_option("--log", action="store_true", dest="log", default=False, help="Averages the log of the projections")
    parser.add_option("--inorm", action="store_true", dest="inorm", default=False, help="This will use a special weighting scheme to compensate for poor SNR sampling on the unit sphere")
    parser.add_option("--fftmerge", dest="fftmerge", default="", help="Fourier model to merge with real model")
    parser.add_option("--savenorm", action="store_true", dest="savenorm", default=False, help="Saves the normalization map to norm.mrc")
    parser.add_option("--hard", type=float, dest="hard", default=0, help="This specifies how well the class averages must match the model to be included, 25 is typical")
    parser.add_option("--noweight", action="store_true", dest="noweight", default=False,
                      help="Normally the class averages are weighted by the number of raw particles used, this disables that")
    parser.add_option("--mask", type=float, dest="mask", default=-1, help="Real-space mask radius")
    parser.add_option("--apix", type=float, dest="apix", default=-1, help="Set the sampling (angstrom/pixel)")
    parser.add_option("--keep", type=float, dest="sigm", default=3.0, help="An alternative to 'hard'")
    parser.add_option("--resmap", dest="resmap", default="", help="Generates a 'resolution map' in another 3D MRC file")

    (opt,args)=parser.parse_args()

    # Make sure the reconstructor type is valid
    try:
        Reconstructors.get(opt.recon_type)
    except RuntimeError:
        sys.stderr.write("ERROR: '%s' is not a valid reconstuctor type - use one of the following:\n" % opt.recon_type)
        dump_reconstructors()
        exit(1)
    
    # Make sure the symmetry is valid
    opt.sym=opt.sym.lower()
    if opt.sym.rstrip("0123456789") not in ["i","c","d","t","icos","oct"]:
        sys.stderr.write("WARNING: '%s' is an unsupported symmetry type - assuming no symmetry\n" % (opt.sym))
        opt.sym=""      #needed??
    elif (opt.sym[0] in ["c","d"]):
        if (opt.sym.__len__()<2) or not(opt.sym[1].isdigit()):
            sys.stderr.write("WARNING: '%s' must be follwed by a number - assuming 1 axis of symmetry\n" % opt.sym[0])
            opt.sym=opt.sym[0]+"1"
    else:
        opt.sym=opt.sym.rstrip("0123456789")
        
    # Make sure a valid mode number is used
    if opt.mode>6:
        sys.stderr.write("WARNING: %d > 6 for mode - using value 6\n" % (opt.mode))
        opt.mode=6
    if opt.mode<1:
        sys.stderr.write("WARNING: %d < 1 for mode - using value 1\n" % (opt.mode))
        opt.mode=1
        
    if len(args) <1:
        parser.error("incorrect number of arguments")
    return (opt,args)


#-----------------------------------------
# Not finished
def wiener_fourier_reconstructor(images, options):
    recon=Reconstructors.get("wiener_fourier",{"mode":options.mode,
                                               "padratio":1, # isn't right
                                               "size":images[0].get_xsize(),
                                               "snr":[] #isn't right
                                               })


#-----------------------------------------
# Doesn't work / not finished
# "npad" needs to be added to "Reverse_gridding_constructor::get_param_types()"
# maybe add ('s to insert_slice check #2; "!=" is evaled after the "||"
# where is vnx assigned to anything?
def reverse_gridding_reconstructor(images, options):
    if not(options.quite):
        print "Setting up the reconstructor"
    recon=Reconstructors.get("reverse_gridding",{"weight":1.0,   # options.noweight, 
                                                 "size":images[0].get_xsize(),
                                                 "npad":1.0})
    recon.setup()

    for i in xrange(len(images)):
        d=images[i]
        d.process("eman1.normalize")
#        d.do_fft_inplace()
        recon.insert_slice(d, Transform3D(d.get_attr("euler_az"),
                                          d.get_attr("euler_alt"), #**2,
                                          d.get_attr("euler_phi")))

        if not(options.quite):
            sys.stdout.write( "%2d/%d  %3d\t%5.1f  %5.1f  %5.1f\t\t%6.2g %6.2g\n" %
                              (i+1,len(images),d.get_attr("IMAGIC.imgnum"),
                               d.get_attr("euler_alt")*180.0/math.pi,
                               d.get_attr("euler_az")*180.0/math.pi,
                               d.get_attr("euler_phi")*180.0/math.pi,
                               d.get_attr("maximum"),d.get_attr("minimum")))
        
    
    output = recon.finish()
    return output


#-----------------------------------------  should work
def pawel_back_projection_reconstruction(images, options):
    if not(options.quite):
        print "Initializing the reconstructor"
    if (options.pad == 0):
        options.pad = 1;
    recon=Reconstructors.get("pawel_back_projection" ,{"npad":options.pad,
                                                       "size":images[0].get_xsize(),
                                                       "symmetry":options.sym})
    recon.setup()

    for i in xrange(len(images)):
        if (options.lowmem):
            d=EMData().read_images(options.input_file, [i])[0]
        else:
            d=images[i]
        d.process("eman1.normalize")           #is this needed? so other normalization?
        recon.insert_slice(d, Transform3D(d.get_attr("euler_az"),
                                          d.get_attr("euler_alt"),
                                          d.get_attr("euler_phi")))
        
        if not(options.quite):
            sys.stdout.write( "%2d/%d  %3d\t%5.1f  %5.1f  %5.1f\t\t%6.2g %6.2g\n" %
                              (i+1,len(images),d.get_attr("IMAGIC.imgnum"),
                               d.get_attr("euler_alt")*180.0/math.pi,
                               d.get_attr("euler_az")*180.0/math.pi,
                               d.get_attr("euler_phi")*180.0/math.pi,
                               d.get_attr("maximum"),d.get_attr("minimum")))
        
    output=recon.finish()

    # need to apply symmetry??

    return output


#----------------------------------------- doesn't work
def back_projection_reconstruction(images, options):
    if not(options.quite):
        print "Initializing the reconstructor"
    recon=Reconstructors.get("back_projection",{"weight":1.0,   # options.noweight,    this ain't right
                                                "size":images[0].get_xsize()})
    recon.setup()
    # skipping the normalizing 

    for i in xrange(len(images)):
        if (options.lowmem):
            d=EMData().read_images(options.input_file, [i])[0]
        else:
            d=images[i]

        d.process("eman1.normalize")

#        t = Transform3D(d.get_attr("euler_az"), d.get_attr("euler_alt"), d.get_attr("euler_phi"))
#        t.transpose();
#        recon.insert_slice(d, t)

        recon.insert_slice(d, Transform3D(d.get_attr("euler_az"),
                                          d.get_attr("euler_alt"), #**2,
                                          d.get_attr("euler_phi")))
        
        if not(options.quite):
            sys.stdout.write( "%2d/%d  %3d\t%5.1f  %5.1f  %5.1f\t\t%6.2g %6.2g\n" %
                              (i+1,len(images),d.get_attr("IMAGIC.imgnum"),
                               d.get_attr("euler_alt")*180.0/math.pi,
                               d.get_attr("euler_az")*180.0/math.pi,
                               d.get_attr("euler_phi")*180.0/math.pi,
                               d.get_attr("maximum"),d.get_attr("minimum")))
        
    output=recon.finish()
    output.process("eman1.normalize")
#    output.process("eman1.math.sqrt")  #right processor?

    # Apply symmetry

    if not(options.sym=="UNKNOWN"):
        print "Applying %s symmetry" % options.sym

    transform=Transform3D(0,0,0)
    d2=output.copy()
    for csym in xrange(Transform3D.get_nsym(options.sym)):
        t=transform.get_sym(options.sym, csym)                    
        print repr(i)+" "+repr(t.get_rotation())
        d2.rotate(t)   #options.sym, csym))
        output.add(d2)
    output.div(1.0*Transform3D.get_nsym(options.sym))
        



    # merging steps   
    if (options.fftmerge):
        print "Merging Models"
        ny = out.get_ysize()

        d0=EMData().read_images(options.fftmerge,[0])
        f0=d0.do_fft()
        f1=output.do_fft()
	
        for k in xrange(-ny/2,ny/2):
            g=k
            for j in xrange(-ny/2,ny/2):
                for i in xrange(ny/2+1):
                    r=(k**2+j**2+i**2)**.5
                    if r==0 or r>ny/2:
                        f0.set_value_at(g,0)
                        continue
                    f0.set_value_at(g, f0.get_value_at(g)*r*2/ny+f1.get_value_at(g)*(1.0-r*2/ny))
                    g=g+2

        output2=f0.do_ift()
        output2.write_image(options.fftmerge)
           
    return output


#----------------------------------------- should work
def fourier_reconstruction(images, options):
    if not(options.quite):
        print "Initializing the reconstructor ..."
    recon=Reconstructors.get("fourier",{"mode":options.mode,
                                        "dlog":options.log,
                                        "weight":1.0,   # options.noweight,    this ain't right
                                        "size":images[0].get_xsize()})
    recon.setup()
    
    if not(options.quite):
        print "Transforming Slices"
    dataf=[]
    for i in xrange(len(images)):
        d=images[i]

        num_img=d.get_attr("IMAGIC.imgnum")   #will this work for all formats? probably not
        if (num_img<0 or num_img>1000000):
            continue                            
        if (num_img==0): num_img=1
        if (options.lowmem):
            d.unum4=i
            dataf=dataf+[d]
        else:
            d.process("eman1.normalize")
            d.process("eman1.mask.ringmean",{"ring_width":options.mask})

            d.transform=Transform3D(EULER_EMAN,d.get_attr("euler_az"),
                                    d.get_attr("euler_alt"),d.get_attr("euler_phi"))

            d.process("eman1.xform.phaseorigin")

            if options.pad>0:
                d=d.pad_fft(options.pad)
         
            f=d.do_fft()                                 

            f.process("eman1.xform.fourierorigin")
            f.transform=d.transform
            f.unum4=i
            dataf=dataf+[f]
    SNR=[]
    if(options.snrfile):
        for i in xrange(0,len(dataf)):
            d=dataf[i]
            tmp=EMData()
            try:
                tmp.read_image(options.snrfile,d.unum4)
            except:
                sys.stderr.write("Error reading SNR data from %s\n"%options.snrfile)
                exit(1)
                #            SNR[0:]=[tmp.get_data()]  python won't call funcs that return float*
                SNR=SNR+[tmp]

    if(options.lowmem):
        d=EMData()

    if not(options.quite):
        print "Adding Slices"
    
    for j in xrange(0,1):     #,4):     change back when the thr issue solved
        if (options.hard>0): thr=options.hard*(1+(3-j)/3.0)
    
        for i in xrange(0,len(dataf)):
            if(options.lowmem):
                d=EMData().read_images(options.input_file, [i])[0]

                d.process("eman1.normalize")
                d.process("eman1.mask.ringmean",{"ring_width":options.mask})

                d.transform=Transform3D(EULER_EMAN,d.get_attr("euler_az"),
                                        d.get_attr("euler_alt"),d.get_attr("euler_phi"))

                d.process("eman1.xform.phaseorigin")
                    
                if options.pad>0:
                    d=d.pad_fft(options.pad)
         
                f=d.do_fft()                                 

                f.process("eman1.xform.fourierorigin")
                f.transform=d.transform
                f.unum4=i
                    
                d=f
            else:
                d=dataf[i]

            if (d.get_attr("IMAGIC.imgnum")<=0):
                continue
            if (options.noweight):
                d.set_attr("IMAGIC.imgnum",1)
            if (j==3 and options.log):
                d.process("eman1.math.log")

            if not(options.quite):
                sys.stdout.write( "%2d/%d  %3d\t%5.1f  %5.1f  %5.1f\t\t%6.2f %6.2f\n" %
                                  (i+1,len(dataf),d.get_attr("IMAGIC.imgnum"),
                                   d.get_attr("euler_alt")*180.0/math.pi,
                                   d.get_attr("euler_az")*180.0/math.pi,
                                   d.get_attr("euler_phi")*180.0/math.pi,
                                   d.get_attr("maximum"),d.get_attr("minimum")))

            if (d.get_attr("IMAGIC.imgnum")>0):
                for csym in range(0, Transform3D.get_nsym(options.sym)):
                    trans=d.transform.get_sym(options.sym, csym)                    
                    recon.insert_slice(d,trans)

            if (options.goodbad and d.get_attr("IMAGIC.count")>0):
                f=d.do_ift()
                if g:
                    pass  #Should be writing to 3dgood
                else:
                    pass #should be writing to 3dbad"

    if (options.goodbad):
        print "print log msgs"

    if not(options.quite):
        print "Starting Reconstruction"
    output=recon.finish()

    output.process("eman1.xform.fourierorigin")
    output=output.do_ift()
    output.process("eman1.xform.phaseorigin")
    output.process("eman1.normalize")
    if options.pad:
        output.set_attr("is_fftpad",1)  #why isn't this passed along?
        output=output.pad_fft(options.pad)
        
    if not(options.quite):        
        print "Finished Reconstruction"

    if(options.savenorm):   # need to alter reconstructor class to get access to this
        nm=EMData()
        nm.set_size(out2.get_xsize(),out2.get_ysize(), out2.get_zsize())
        for i in xrange(0,out2.get_xsize()*out2.get_ysize()*out2.get_zsize(),2):
            nm.set_value_at_fast(i/2,out2.get_value_at(i,0,0))
        nm.write_image("norm.mrc")
        for i in xrange(0,out2.get_xsize()*out2.get_ysize()*out2.get_zsize(),2):
            nm.set_value_at_fast(i/2,math.hypot(out2.get_value_at(i,0,0),out2.get_value_at(i+1,0,0)))
        nm.write_image("map.mrc")
                    
    if(options.log):
        output.process("eman1.math.exp")
              
    if(options.resmap): #doesn't work
        out=EMData()
        ny2=output.get_ysize()
        out.set_size(ny2,ny2,ny2)
        out.to_zero()
        for i in xrange(0,ny2):
            for j in xrange(0,ny2):
                for k in xrange(ny2/2,ny2):
                    sys.stdout.write("i=%g   j=%g   k=%g []=%g\n"%(i,j,k,(k-ny2/2)*2+j*(ny2+2)+i*(ny2+2)*ny2))
                    #                   try:
                    out.set_value_at_fast(k+j*ny2+i*ny2*ny2,
                                          (output.get_value_at((k-ny2/2)*2+j*(ny2+2)+i*(ny2+2)*ny2))**.5)
                    if (k<>ny2/2 and i<>0 and j<>0):
                        out.set_value_at_fast((ny2-k)+(ny2-j)*ny2+(ny2-i)*ny2*ny2,
                                              (output.get_value_at((k-ny2/2)*2+j*(ny2+2)+i*(ny2+2)*ny2))**.5)
                        #                  except ValueError:
                        #                     print repr((k-ny2/2)*2+j*(ny2+2)+i*(ny2+2)*ny2)+" < 0"
        out.write_image(options.resmap)
                                            
                                            # LOG message: LOG(Ref,resmap,LOG_INFILE,NULL)
        
    if(SNR):  # doesn't work
        out=EMData()
        for i in xrange(0,ny2*ny2*(ny2+2),2):
            temp=1./(1.+(1./output.get_value_at(i)))
            out.set_value_at_fast(i,temp)
            out.set_value_at_fast(i+1,temp)
        out.write_image("filter3d.mrc")

    output.process("eman1.mask.ringmean",{"ring_width":options.mask})
    return output


    
if __name__=="__main__":
    main()
    

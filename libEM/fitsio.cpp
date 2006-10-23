/**
 * $Id$
 */

/*
 * Author: Steven Ludtke, 10/21/2006 (sludtke@bcm.edu)
 * Copyright (c) 2000-2006 Baylor College of Medicine
 * 
 * This software is issued under a joint BSD/GNU license. You may use the
 * source code in this file under either license. However, note that the
 * complete EMAN2 and SPARX software packages have some GPL dependencies,
 * so you are responsible for compliance with the licenses of these packages
 * if you opt to use BSD licensing. The warranty disclaimer below holds
 * in either instance.
 * 
 * This complete copyright notice must be included in any revised version of the
 * source code. Additional authorship citations may be added, but existing
 * author citations must be preserved.
 * 
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 * 
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 * 
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
 * 
 * */

#include "fitsio.h"
#include "portable_fileio.h"
#include "geometry.h"
#include "util.h"
#include "ctf.h"

using namespace EMAN;

FitsIO::FitsIO(const string & fits_filename, IOMode rw)
:	filename(fits_filename), rw_mode(rw)
{
	is_big_endian = ByteOrder::is_host_big_endian();
	is_new_file = false;
	initialized = false;
	fitsfile=0;
}

FitsIO::~FitsIO()
{
	if (fitsfile) {
		fclose(fitsfile);
		fitsfile = 0;
	}
}

void FitsIO::init()
{
	ENTERFUNC;
	
	if (initialized) {
		return;
	}
	
	initialized = true;
	fitsfile = sfopen(filename, rw_mode, &is_new_file);

	EXITFUNC;
}


bool FitsIO::is_image_big_endian()
{
	init();
	return is_big_endian;
}

bool FitsIO::is_valid(const void *first_block, off_t file_size)
{
	ENTERFUNC;
	
	if (!first_block) {
		return false;
	}

	if (strncmp("SIMPLE  ",(const char *)first_block,8)==0) return true;

	EXITFUNC;
	return false;
}

int FitsIO::read_header(Dict & dict, int image_index, const Region * area, bool )
{
	ENTERFUNC;

//	dict["apix_x"] = mrch.xlen / (mrch.nx - 1);
//	dict["apix_y"] = mrch.ylen / (mrch.ny - 1);
	init();

	if (area) throw ImageReadException(filename,"Area reading not supported for FITS format");

	dict["nx"]=1;
	dict["ny"]=1;
	dict["nz"]=1;

	char s[81],lbl[9],val[80];
	int dim=0;
	s[80]=0;
	rewind(fitsfile);
	for (fread(s,80,1,fitsfile); strncmp("END",s,3); fread(s,80,1,fitsfile)) {
		sscanf(s,"%8s = %[^/]",lbl,val);
//		printf("%s,%s\n",lbl,val);
		if (strncmp("SIMPLE  ",s,8)==0) continue;
		else if (strncmp("END     ",s,8)==0) break;
//		else if (strncmp("BITPIX  ",s,8)==0)
		else if (strncmp("NAXIS   ",s,8)==0) dim=atoi(val);
		else if (strncmp("NAXIS",s,5)==0) {
			if (s[5]=='1') dict["nx"]=atoi(val);
			if (s[5]=='2') dict["ny"]=atoi(val);
			if (s[5]=='3') dict["nz"]=atoi(val);
		}
		else {
			dict[(string)"FITS."+lbl]=val;
		}
	}

	dstart=((ftell(fitsfile)-1)/2880+1)*2880;

	int xlen = 0, ylen = 0, zlen = 0;
	dtype=atoi(dict["FITS.BITPIX"]);
	EMUtil::get_region_dims(area, dict["nx"], &xlen, dict["ny"], &ylen, dict["nz"], &zlen);

	dict["nx"] = nx=xlen;
	dict["ny"] = ny=ylen;
	dict["nz"] = nz=zlen;

	EXITFUNC;
	return 0;
}

int FitsIO::write_header(const Dict & dict, int image_index, const Region* area,
						EMUtil::EMDataType, bool)
{
	ENTERFUNC;
	check_write_access(rw_mode, image_index, 1);

	EXITFUNC;
	return 0;
}

int FitsIO::read_data(float *rdata, int image_index, const Region * area, bool )
{
	ENTERFUNC;
	int i;

	check_read_access(image_index, rdata);

	portable_fseek(fitsfile, dstart, SEEK_SET);
	char *cdata=(char *)rdata;
	short *sdata=(short *)rdata;
	int *idata=(int *)idata;
	double *ddata;

	switch (dtype) {
	case 8:
		fread(cdata,nx,ny*nz,fitsfile);
		for (i=nx*ny*nz-1; i>=0; i--) rdata[i]=cdata[i];
		break;
	case 16:
		fread(cdata,nx,ny*nz*2,fitsfile);
		if (!ByteOrder::is_host_big_endian()) ByteOrder::swap_bytes((short*) sdata, nx*ny*nz);
		for (i=nx*ny*nz-1; i>=0; i--) rdata[i]=sdata[i];
		break;
	case 32:
		fread(cdata,nx,ny*nz*4,fitsfile);
		if (!ByteOrder::is_host_big_endian()) ByteOrder::swap_bytes((int*) rdata, nx*ny*nz);
		for (i=0; i<nx*ny*nz; i++) rdata[i]=idata[i];
		break;
	case -32:
		fread(cdata,nx*4,ny*nz,fitsfile);
		if (!ByteOrder::is_host_big_endian()) ByteOrder::swap_bytes((float*) rdata, nx*ny*nz);
		break;
	case -64:
		ddata=(double *)malloc(nx*ny*nz*8);
		fread(ddata,nx,ny*nz*8,fitsfile);
		if (!ByteOrder::is_host_big_endian()) ByteOrder::swap_bytes((double*) ddata, nx*ny*nz);
		for (i=0; i<nx*ny*nz; i++) rdata[i]=ddata[i];
		free(ddata);
		break;
	}

	EXITFUNC;
	return 0;
}

int FitsIO::write_data(float *data, int image_index, const Region* area,
					  EMUtil::EMDataType, bool)
{
	ENTERFUNC;

	check_write_access(rw_mode, image_index, 1, data);
//	check_region(area, FloatSize(mrch.nx, mrch.ny, mrch.nz), is_new_file);
	

	EXITFUNC;
	return 0;
}


bool FitsIO::is_complex_mode()
{
	init();
	return false;
}

void FitsIO::flush()
{
	fflush(fitsfile);
}

int FitsIO::read_ctf(Ctf & ctf, int)
{
	ENTERFUNC;
	init();
	EXITFUNC;
	return 0;
}

void FitsIO::write_ctf(const Ctf & ctf, int)
{
	ENTERFUNC;
	init();
	
	EXITFUNC;
}

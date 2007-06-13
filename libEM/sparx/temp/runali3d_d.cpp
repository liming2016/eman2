#include "mpi.h"
#include "stdlib.h"

// include EMAN2
#include "emdata.h"
#include "assert.h"

#include "ali3d_d_mpi.h"
#include "alignoptions.h"

int ReadVandBcast(MPI_Comm comm, EMData *volume, char *volfname);
int ReadStackandDist(MPI_Comm comm, EMData ***expimages, char *stackfname);
int setpart(MPI_Comm comm, int nima, int *psize, int *nbase);

int main(int argc, char *argv[])
{
    MPI_Comm comm = MPI_COMM_WORLD;
    int ncpus, mypid, ierr;
    int nloc; 
    double t0;

    MPI_Status mpistatus;
    MPI_Init(&argc,&argv);
    MPI_Comm_size(comm,&ncpus);
    MPI_Comm_rank(comm,&mypid);
    printf("mypid = %d, ncpus = %d\n", mypid, ncpus);
    char  volfname[100], optionsfname[100], stackfname[100],voutfname[100];
    voutfname[0] = 0; // default to empty string
    EMData **expimages;

    // parse the command line and set filenames	
    if (argc < 3) {
      if (mypid == 0) {
          printf("Not enough arguments to the command...\n");
          printf("Usage: runali3d_d -data=<imagestack> ");
          printf("-model=<initial 3D volume> ");
          printf("-out=<output filename base string> "); 
	  printf("-options=<options filename>\n");
      }
      ierr = MPI_Finalize();
      exit(1);
    }
    int ia=0;
    bool have_options = false;
    while (ia < argc) {
       if ( !strncmp(argv[ia],"-data",5) ) {
          strcpy(stackfname,&argv[ia][6]);
       }
       else if ( !strncmp(argv[ia],"-model",6) ) {
          strcpy(volfname,&argv[ia][7]);
       }
       else if ( !strncmp(argv[ia],"-out",4) ) {
          strcpy(voutfname,&argv[ia][5]);
       }
       else if ( !strncmp(argv[ia],"-options",8) ) {
	   strcpy(optionsfname,&argv[ia][9]);
	   have_options = true;
       }
       ia++;
    }

    // read and broadcast the initial model
    t0 = MPI_Wtime();
    EMData *volume = new EMData();
    ierr = ReadVandBcast(comm, volume, volfname);
    if (mypid == 0) {
       printf("Finished reading and replicating volume\n");
       printf("I/O time for reading volume = %11.3e\n",
              MPI_Wtime() - t0);
    }
    
    // read and distribute a stack of experimental images
    t0 = MPI_Wtime();
    nloc = ReadStackandDist(comm, &expimages, stackfname);
    if (mypid == 0) {
       printf("Finished reading and distributing image stack\n");
       printf("I/O time for reading image stack = %11.3e\n",
              MPI_Wtime() - t0);
    }

    Vec3i volsize;
    Vec3i origin;
    volsize[0] = volume->get_xsize();
    volsize[1] = volume->get_ysize();
    volsize[2] = volume->get_zsize();
    origin[0] = volume->get_xsize()/2 + 1;
    origin[1] = volume->get_ysize()/2 + 1;
    origin[2] = volume->get_zsize()/2 + 1;
    int    ri = volume->get_xsize()/2 - 2;

    float *angleshift = new float[5*nloc];
    
    AlignOptions options(volsize);

    std::ifstream option_stream;
    std::string current_option;
    char option_buffer[100];
    int int_option;
    float float_option;

    int maxiter = 5;
    EMData * mask3D = NULL;
    float * mask_data;
    if ( have_options ) {
	if ( mypid == 0 ) { // read data from the options file
	    option_stream.open(optionsfname);
	    while ( option_stream >> current_option ) {
		if ( current_option == "maskfile" ) {
		    option_stream >> current_option;
		    mask3D = new EMData();
		    mask3D->read_image(current_option);
		    options.set_mask3D(mask3D);
		} 
		else if ( current_option == "inner_ring" ) {
		    option_stream >> int_option;
		    options.set_first_ring(int_option);
		    std::cout << "first_ring = " << int_option << std::endl;
		} 
		else if ( current_option == "outer_ring" ) {
		    option_stream >> int_option;
		    options.set_last_ring(int_option);
		    std::cout << "last_ring = " << int_option << std::endl;
		} 
		else if ( current_option == "rstep" ) {
		    option_stream >> int_option;
		    options.set_rstep(int_option);
		    std::cout << "rstep = " << int_option << std::endl;
		} 
		else if ( current_option == "radius" ) { // perhaps this is the same as outer_ring?
		    option_stream >> int_option;	
		    options.set_ri(int_option);
		    std::cout << "radius = " << int_option << std::endl;
		} 
		else if ( current_option == "x_range" ) {
		    option_stream >> float_option;
		    options.set_xrng(float_option);
		    std::cout << "x_range = " << float_option << std::endl;
		} 
		else if ( current_option == "y_range" ) {
		    option_stream >> float_option;
		    options.set_yrng(float_option);
		    std::cout << "y_range = " << float_option << std::endl;
		}
		else if ( current_option == "translation_step" ) {
		    option_stream >> float_option;
		    options.set_step(float_option);
		    std::cout << "step = " << float_option << std::endl;
		}
		else if ( current_option == "theta_step" ) {
		    option_stream >> float_option;
		    options.set_dtheta(float_option);
		    std::cout << "theta_step = " << float_option << std::endl;
		}
		else if ( current_option == "maxit" ) {
		    option_stream >> int_option;
		    maxiter = int_option;
		    std::cout << "maxit = " << int_option << std::endl;
		}
		else if ( current_option == "CTF" ) {
		    option_stream >> current_option;
		    if ( current_option == "true" ) {
			options.set_CTF(true);
			std::cout << "CTF = true" << std::endl;
		    } 
		    else { // anything else sets it to false
			options.set_CTF(false);
			std::cout << "CTF = false" << std::endl;
		    }
		}
		else if ( current_option == "snr" ) {
		    option_stream >> float_option;
		    options.set_snr(float_option);
		    std::cout << "snr = " << float_option << std::endl;
		}
		else if ( current_option == "ref_a" ) {
		    option_stream >> current_option;
		    if ( current_option == "P" ) {
			options.set_ref_angle_type("P");
		    } 
		    else if ( current_option == "S" ){ // should add support for this
			std::cerr << "Currently only support Penczek-type reference angles..." << std::endl;
			options.set_ref_angle_type("P");
		    }
		    else { // Currently default to "P", will eventually default to "S"
		    }
		}
		else if ( current_option == "symmetry" ) {
		    option_stream >> current_option;
		    options.set_symmetry(current_option);
		    std::cout << "symmetry = " << current_option << std::endl;
		}
		else { // catch-all
		    std::cerr << "Unsupported option " << current_option << "..." << std::endl;
		}
	    }
	    option_stream.close();
	}
	// Then broadcast all the data that was read
	ierr = MPI_Bcast(&mask3D, 1, MPI_INT, 0, comm); // if it's not NULL, need to allocate and bcast its data
	// NOTE: this is sending over the master's address for mask3D ONLY as a test to see if it's NULL or not.
	// DO NOT USE THIS POINTER ON ANY OTHER NODES EXCEPT FOR THIS TEST!
	if ( mask3D != NULL ) {
	    if ( mypid != 0 ) {
		mask3D = new EMData();
	    }
	    mask_data = mask3D->get_data();
	    ierr = MPI_Bcast(mask_data, volsize[0]*volsize[1]*volsize[2], MPI_FLOAT, 0, comm);
	    options.set_mask3D(mask3D);
	}

	int_option = options.get_first_ring();
	ierr = MPI_Bcast(&int_option, 1, MPI_INT, 0, comm);
	options.set_first_ring(int_option);

	int_option = options.get_last_ring();
	ierr = MPI_Bcast(&int_option, 1, MPI_INT, 0, comm);
	options.set_last_ring(int_option);

	int_option = options.get_rstep();
	ierr = MPI_Bcast(&int_option, 1, MPI_INT, 0, comm);
	options.set_rstep(int_option);

	int_option = options.get_ri();
	ierr = MPI_Bcast(&int_option, 1, MPI_INT, 0, comm);
	options.set_ri(int_option);

	float_option = options.get_xrng();
	ierr = MPI_Bcast(&float_option, 1, MPI_FLOAT, 0, comm);
	options.set_xrng(float_option);

	float_option = options.get_yrng();
	ierr = MPI_Bcast(&float_option, 1, MPI_FLOAT, 0, comm);
	options.set_yrng(float_option);

	float_option = options.get_step();
	ierr = MPI_Bcast(&float_option, 1, MPI_FLOAT, 0, comm);
	options.set_step(float_option);

	float_option = options.get_dtheta();
	ierr = MPI_Bcast(&float_option, 1, MPI_FLOAT, 0, comm);
	options.set_dtheta(float_option);

	int_option = options.get_CTF();
	ierr = MPI_Bcast(&int_option, 1, MPI_INT, 0, comm);
	options.set_CTF(int_option);

	float_option = options.get_snr();
	ierr = MPI_Bcast(&float_option, 1, MPI_FLOAT, 0, comm);
	options.set_snr(float_option);

	current_option = options.get_ref_angle_type();
	strcpy(option_buffer, current_option.c_str());
	ierr = MPI_Bcast(option_buffer, current_option.size(), MPI_CHAR, 0, comm);
	options.set_ref_angle_type(option_buffer);

	current_option = options.get_symmetry();
	strcpy(option_buffer, current_option.c_str());
	ierr = MPI_Bcast(option_buffer, current_option.size(), MPI_CHAR, 0, comm);
	options.set_symmetry(option_buffer);
    }
    options.set_have_angles(false);

    try {
       ali3d_d(comm, volume, expimages, angleshift, nloc, options, 
               maxiter, voutfname);
    }
    catch (std::exception const& e) {
	printf("%s\n", e.what());
    }

    EMDeletePtr(volume);
    for ( int i = 0 ; i < nloc; ++i ) {
	EMDeletePtr(expimages[i]);
    }
    EMDeleteArray(expimages);
    EMDeleteArray(angleshift);
    if ( mask3D != NULL ) {
	EMDeletePtr(mask3D);
    }
    ierr = MPI_Finalize();
    return 0;
}


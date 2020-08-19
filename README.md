# CompPsychFlows
Our lab's repository of nipype interfaces and workflows. Obviously inspired by the Poldrack Lab's [NiWorkflows](https://github.com/nipreps/niworkflows).

Currently there is only one commandline script, comppsychflows-mnitobold

## comppsychflows-mnitobold
* Takes as input a subject's bids directory and an fmriprep output
* Produces a working directory with:
  * Head motion corrected bold series
  * MNI template and parcellation transformed to the space of the HMC bold series using the suceptibility distortion correction transformation if available
  * Stats on each ROI for each TR in the bold series

An [example](notebook/example_of_running_mnitobold_on_swarmp.ipynb) of running comppsychflows-mnitobold on the NIH HPC's swarm system is also available.

## set up

The set up process is currently a bit strange. Since I'm running on an HPC, I'm working in a fMRIPrep singularity container and I didn't want to build a new one for comppsychflows, so here's how I've set things up.
1. Create a clone of the base conda environment from inside the container:
  * export TMPDIR=/lscratch/$SLURM_JOB_ID &&     export SINGULARITY_BINDPATH="/gs4,/gs5,/gs6,/gs7,/gs8,/gs9,/gs10,/gs11,/spin1,/scratch,/fdb,/data,/lscratch" &&    mkdir -p $TMPDIR/out &&     mkdir -p $TMPDIR/wrk &&     singularity shell --cleanenv --bind /data/MBDU/nielsond/fmriprep-fix-cli-parser/fmriprep/:/usr/local/miniconda/lib/python3.7/site-packages/fmriprep /data/MBDU/singularity_images/fmriprep_20.1.0.simg
  * Once you're in your singularity shell:
    * conda create -p [path to enviornment where you'll install comppsychflows] --clone base
    * source activate [path to enviornment where you'll install comppsychflows]
    * pip install -e [path to this comppsychflows repo]
  * if you want a notebook so you can play with thing here, start it as well
    * conda install jupyter notebook
    * jupyter notebook --no-browser --port=46469
 2. copy template_run_mnitobold.sh and update the path in there to your path to enviornment where you'll install comppsychflows]
 3. update the command in notebook/example_of_running_mnitobold_on_swarmp.ipynb to point to your run_mnitobold.sh
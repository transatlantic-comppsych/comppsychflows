# CompPsychFlows
Our lab's repository of nipype interfaces and workflows. Obviously inspired by the Poldrack Lab's [NiWorkflows](https://github.com/nipreps/niworkflows).

Currently there is only one commandline script, comppsychflows-mnitobold

## comppsychflows-mnitobold
* Takes as input a subject's bids directory and an fmriprep output
* Produces a working directory with:
  * Head motion corrected bold series
  * MNI template and parcellation transformed to the space of the HMC bold series using the suceptibility distortion correction transformation if available
  * Stats on each ROI for each TR in the bold series

An [example](notebook/example_of_running_mnitobids_on_swarmp.ipynb) of running comppsychflows-mnitobold on the NIH HPC's swarm system is also available.
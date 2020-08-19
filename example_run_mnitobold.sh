#! /bin/bash

echo comppsychflows-mnitobold ${@:1};
source activate /data/MBDU/midla/notebooks/fmriprep_sing_env; comppsychflows-mnitobold ${@:1};


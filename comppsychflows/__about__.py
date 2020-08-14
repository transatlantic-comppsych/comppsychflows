"""
These pipelines are inspired by the Niworkflows package from
the Poldrack lab at Stanford University
(https://nipreps.stanford.edu/). 
They have been developed by NIMH Comp-Psych for use there,
as well as for open-source software distribution.
"""
from datetime import datetime
from ._version import get_versions

__version__ = get_versions()["version"]
del get_versions

__packagename__ = "comppsychflows"
__credits__ = [
    "Dylan Nielson"
]
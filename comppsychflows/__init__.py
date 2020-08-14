"""CompPsych Workflows (comppsychflows) is a selection of image processing workflows."""
import logging

from .__about__ import __version__, __packagename__, __credits__


__all__ = [
    "__version__",
    # "__packagename__",
    # "__copyright__",
    # "__credits__",
    "COMPPSYCHFLOWS_LOG",
]

COMPPSYCHFLOWS_LOG = logging.getLogger(__packagename__)
COMPPSYCHFLOWS_LOG.setLevel(logging.INFO)

try:
    import matplotlib

    matplotlib.use("Agg")
except ImportError:
    pass
from ._version import get_versions
__version__ = get_versions()['version']
del get_versions

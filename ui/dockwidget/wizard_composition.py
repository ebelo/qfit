"""Compatibility re-exports for pre-#805 wizard composition imports.

The canonical shell composition implementation now lives in
``qfit.ui.dockwidget.workflow_composition``.  Keep this module as a stable
wizard-named import path while the dock consolidation continues.
"""

from .workflow_composition import *
from .workflow_composition import __all__

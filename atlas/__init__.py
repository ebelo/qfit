"""Atlas/publish subsystem.

Groups all atlas planning, PDF export, and profile rendering logic into a
single internal package.  External callers should import from this package
rather than from individual submodules.
"""

from .export_controller import AtlasExportController, AtlasExportValidationError
from .export_service import AtlasExportResult, AtlasExportService
from .export_use_case import AtlasExportUseCase, GenerateAtlasPdfCommand, PrepareAtlasPdfExportResult
from .publish_atlas import build_atlas_page_plans, normalize_atlas_page_settings

# export_task is NOT imported here: it has top-level QGIS runtime imports that
# require the QGIS application to be initialised.  Callers that need symbols
# from that module (e.g. BUILTIN_ATLAS_MAP_TARGET_ASPECT_RATIO) must import
# directly from qfit.atlas.export_task.

__all__ = [
    "AtlasExportController",
    "AtlasExportValidationError",
    "AtlasExportResult",
    "AtlasExportService",
    "AtlasExportUseCase",
    "GenerateAtlasPdfCommand",
    "PrepareAtlasPdfExportResult",
    "build_atlas_page_plans",
    "normalize_atlas_page_settings",
]

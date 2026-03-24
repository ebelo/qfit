import logging

logger = logging.getLogger(__name__)


class AtlasExportValidationError(Exception):
    """Raised when atlas export inputs are invalid."""


class AtlasExportController:
    """Validates inputs and normalises paths for atlas PDF export."""

    @staticmethod
    def validate_atlas_layer(atlas_layer):
        """Raise :class:`AtlasExportValidationError` if the layer is unusable."""
        if atlas_layer is None:
            raise AtlasExportValidationError(
                "Store and load activity layers first (step 3: Store and load layers)."
            )
        if atlas_layer.featureCount() == 0:
            raise AtlasExportValidationError(
                "The atlas_pages layer has no features. "
                "Fetch activities with geometry and store/load layers first."
            )

    @staticmethod
    def normalize_pdf_path(path):
        """Return *path* with a ``.pdf`` suffix and whether the path was changed."""
        if not path:
            raise AtlasExportValidationError("Enter or browse to an output PDF path.")
        if not path.lower().endswith(".pdf"):
            return f"{path}.pdf", True
        return path, False

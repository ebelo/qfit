"""
GeoPackage I/O helpers for qfit.

This module provides the low-level function that writes a ``QgsVectorLayer``
to a GeoPackage file using QGIS's ``QgsVectorFileWriter``.  It has no
knowledge of layer schemas, builders, or orchestration — it only handles
the disk-write operation.
"""

from qgis.core import (
    QgsCoordinateTransformContext,
    QgsProject,
    QgsVectorFileWriter,
)


def write_layer_to_gpkg(layer, output_path, layer_name, overwrite_file):
    """Write *layer* as a named layer inside *output_path* (a GeoPackage file).

    Parameters
    ----------
    layer:
        A ``QgsVectorLayer`` (typically memory-backed) to persist.
    output_path:
        Absolute path to the ``.gpkg`` file to write into.
    layer_name:
        Name used for the layer/table inside the GeoPackage.
    overwrite_file:
        When ``True`` the entire GeoPackage file is recreated
        (``CreateOrOverwriteFile``); when ``False`` only the named layer is
        replaced (``CreateOrOverwriteLayer``).

    Raises
    ------
    RuntimeError
        If ``QgsVectorFileWriter`` reports any error.
    """
    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = "GPKG"
    options.layerName = layer_name
    options.fileEncoding = "UTF-8"
    options.actionOnExistingFile = (
        QgsVectorFileWriter.CreateOrOverwriteFile
        if overwrite_file
        else QgsVectorFileWriter.CreateOrOverwriteLayer
    )

    result = QgsVectorFileWriter.writeAsVectorFormatV3(
        layer,
        output_path,
        QgsProject.instance().transformContext() if QgsProject.instance() else QgsCoordinateTransformContext(),
        options,
    )
    if result[0] != QgsVectorFileWriter.NoError:
        raise RuntimeError(
            "Failed to write layer '{name}' to {path}: {result}".format(
                name=layer_name,
                path=output_path,
                result=result,
            )
        )

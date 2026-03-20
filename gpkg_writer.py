class GeoPackageWriter:
    """Minimal scaffold for future GeoPackage export."""

    def __init__(self, output_path=None):
        self.output_path = output_path

    def write_activities(self, activities):
        raise NotImplementedError("GeoPackage writing is not implemented yet")

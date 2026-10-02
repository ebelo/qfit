"""Anonymous synthetic routes; never read the user's activity database."""


def sparse_heatmap_routes(count=457):
    """Separated cell-centred routes: 4,113 legacy candidates, 457 outputs.

    Use 32-cell tiles to keep the integration fixture cheap. Production retains
    its 256-cell tiles and identical cell size/smoothing kernel.
    """
    from osgeo import osr
    metric = osr.SpatialReference()
    metric.ImportFromEPSG(32632)
    geographic = osr.SpatialReference()
    geographic.ImportFromEPSG(4326)
    for crs in (metric, geographic):
        crs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    transform = osr.CoordinateTransformation(metric, geographic)
    routes = []
    for index in range(count):
        x = (1250 + 3 * (index % 23)) * 320 + 165
        y = (15937 + 3 * (index // 23)) * 320 + 165
        routes.append([transform.TransformPoint(x, y)[:2], transform.TransformPoint(x + 1, y + 1)[:2]])
    return routes


def write_route_heatmap_fixture(path, routes=None):
    from osgeo import ogr, osr
    if routes is None:
        routes = [
            [(7.34, 46.23), (7.35, 46.24), (7.36, 46.24), (7.37, 46.25)],
            [(7.34, 46.23), (7.35, 46.24), (7.36, 46.24), (7.37, 46.25)],
            [(7.35, 46.24), (7.35, 46.25), (7.34, 46.26)],
        ]
    crs = osr.SpatialReference()
    crs.ImportFromEPSG(4326)
    crs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    dataset = ogr.GetDriverByName("GPKG").CreateDataSource(str(path))
    layer = dataset.CreateLayer("activity_tracks", crs, ogr.wkbLineString)
    for name, kind in [("source", ogr.OFTString), ("source_activity_id", ogr.OFTString),
                       ("name", ogr.OFTString), ("activity_type", ogr.OFTString), ("sport_type", ogr.OFTString),
                       ("start_date", ogr.OFTString), ("distance_m", ogr.OFTReal), ("geometry_source", ogr.OFTString)]:
        layer.CreateField(ogr.FieldDefn(name, kind))
    for index, points in enumerate(routes):
        feature = ogr.Feature(layer.GetLayerDefn())
        for name, value in {"source": "synthetic", "source_activity_id": str(index), "name": f"Synthetic route {index}",
                            "activity_type": "Ride" if index % 2 == 0 else "Run", "sport_type": "Ride" if index % 2 == 0 else "Run",
                            "start_date": "2026-05-01T10:00:00", "distance_m": 5000, "geometry_source": "stream"}.items():
            feature.SetField(name, value)
        geometry = ogr.Geometry(ogr.wkbLineString)
        for point in points:
            geometry.AddPoint_2D(*point)
        feature.SetGeometry(geometry)
        layer.CreateFeature(feature)
    layer = None
    dataset = None
    return str(path)

# -*- coding: utf-8 -*-

# FLO-2D Preprocessor tools for QGIS
# Copyright © 2016 Lutra Consulting for FLO-2D

# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version

import math
from osgeo import gdal
from qgis.core import QgsGeometry, QgsPoint, QgsSpatialIndex, QgsRasterLayer, QgsRaster
from utils import is_number


def build_grid(boundary, cell_size):
    """
    Generator which creates grid with given cell size and inside given boundary layer.
    """
    half_size = cell_size * 0.5
    biter = boundary.getFeatures()
    feature = next(biter)
    fgeom = feature.geometry()
    bbox = fgeom.boundingBox()
    xmin = math.floor(bbox.xMinimum())
    xmax = math.ceil(bbox.xMaximum())
    ymax = math.ceil(bbox.yMaximum())
    ymin = math.floor(bbox.yMinimum())
    cols = int(math.ceil(abs(xmax - xmin) / cell_size))
    rows = int(math.ceil(abs(ymax - ymin) / cell_size))
    x = xmin + half_size
    y = ymax - half_size
    for col in xrange(cols):
        y_tmp = y
        for row in xrange(rows):
            if fgeom.contains(QgsPoint(x, y_tmp)):
                poly = (
                    x - half_size, y_tmp - half_size,
                    x + half_size, y_tmp - half_size,
                    x + half_size, y_tmp + half_size,
                    x - half_size, y_tmp + half_size,
                    x - half_size, y_tmp - half_size
                )
                yield poly
            else:
                pass
            y_tmp -= cell_size
        x += cell_size


def poly2grid(grid, polygons, value_column):
    """
    Generator for assigning values from any polygon layer to target grid layer.
    """
    polys = polygons.selectedFeatures() if polygons.selectedFeatureCount() > 0 else polygons.getFeatures()
    allfeatures = {feature.id(): feature for feature in polys}
    index = QgsSpatialIndex()
    map(index.insertFeature, allfeatures.itervalues())
    for feat in grid.getFeatures():
        geom = feat.geometry()
        centroid = geom.centroid()
        fids = index.intersects(centroid.boundingBox())
        for fid in fids:
            f = allfeatures[fid]
            isin = f.geometry().contains(centroid)
            if isin is True:
                yield (f[value_column], feat.id())
            else:
                pass


def calculate_arfwrf(grid, areas):
    """
    Generator which calculates ARF and WRF values based on polygons representing blocked areas.
    """
    sides = (
        (lambda x, y, square_half, octa_half: (x - octa_half, y + square_half, x + octa_half, y + square_half)),
        (lambda x, y, square_half, octa_half: (x + square_half, y + octa_half, x + square_half, y - octa_half)),
        (lambda x, y, square_half, octa_half: (x + octa_half, y - square_half, x - octa_half, y - square_half)),
        (lambda x, y, square_half, octa_half: (x - square_half, y - octa_half, x - square_half, y + octa_half)),
        (lambda x, y, square_half, octa_half: (x + octa_half, y + square_half, x + square_half, y + octa_half)),
        (lambda x, y, square_half, octa_half: (x + square_half, y - octa_half, x + octa_half, y - square_half)),
        (lambda x, y, square_half, octa_half: (x - octa_half, y - square_half, x - square_half, y - octa_half)),
        (lambda x, y, square_half, octa_half: (x - square_half, y + octa_half, x - octa_half, y + square_half))
    )
    area_polys = areas.selectedFeatures() if areas.selectedFeatureCount() > 0 else areas.getFeatures()
    allfeatures = {feature.id(): feature for feature in area_polys}
    index = QgsSpatialIndex()
    map(index.insertFeature, allfeatures.itervalues())
    features = grid.getFeatures()
    first = next(features)
    grid_area = first.geometry().area()
    grid_side = math.sqrt(grid_area)
    octagon_side = grid_side / 2.414
    half_square = grid_side * 0.5
    half_octagon = octagon_side * 0.5
    full_wrf = (1,) * 8
    for feat in grid.getFeatures():
        geom = feat.geometry()
        fids = index.intersects(geom.boundingBox())
        for fid in fids:
            f = allfeatures[fid]
            fgeom = f.geometry()
            inter = fgeom.intersects(geom)
            if inter is True:
                areas_intersection = fgeom.intersection(geom)
                arf = round(areas_intersection.area() / grid_area, 2)
                centroid = geom.centroid()
                centroid_wkt = centroid.exportToWkt()
                if arf > 0.95:
                    yield (centroid_wkt, feat.id(), 1) + full_wrf
                    continue
                else:
                    pass
                grid_center = centroid.asPoint()
                wrf_sides = (f(grid_center.x(), grid_center.y(), half_square, half_octagon) for f in sides)
                wrf_geoms = (QgsGeometry.fromPolyline([QgsPoint(x1, y1), QgsPoint(x2, y2)]) for x1, y1, x2, y2 in wrf_sides)
                wrf = (round(line.intersection(fgeom).length() / octagon_side, 2) for line in wrf_geoms)
                yield (centroid_wkt, feat.id(), arf) + tuple(wrf)
            else:
                pass


def square_grid(gutils, boundary):
    """
    Function for calculating and writing square grid into 'grid' table.
    """
    del_qry = 'DELETE FROM grid;'
    cellsize = gutils.execute('''SELECT value FROM cont WHERE name = "CELLSIZE";''').fetchone()[0]
    update_cellsize = 'UPDATE user_model_boundary SET cell_size = ?;'
    insert_qry = '''INSERT INTO grid (geom) VALUES (AsGPB(ST_GeomFromText('POLYGON(({} {}, {} {}, {} {}, {} {}, {} {}))')));'''
    gutils.execute(update_cellsize, (cellsize,))
    cellsize = float(cellsize)
    polygons = build_grid(boundary, cellsize)
    cur = gutils.con.cursor()
    cur.execute(del_qry)
    c = 0
    for poly in polygons:
        cur.execute(insert_qry.format(*poly))
        c += 1
    gutils.con.commit()
    return c


def update_roughness(gutils, grid, roughness, column_name):
    """
    Updating roughness values inside 'grid' table
    """
    qry = 'UPDATE grid SET n_value=? WHERE fid=?;'
    gutils.con.executemany(qry, poly2grid(grid, roughness, column_name))
    gutils.con.commit()


def evaluate_arfwrf(gutils, grid, areas):
    """
    Calculating and inserting ARF and WRF values into 'blocked_cells' table
    """
    del_cells = 'DELETE FROM blocked_cells;'
    qry_cells = '''INSERT INTO blocked_cells (geom, area_fid, grid_fid, arf, wrf1, wrf2, wrf3, wrf4, wrf5, wrf6, wrf7, wrf8) VALUES (AsGPB(ST_GeomFromText('{}')),?,?,?,?,?,?,?,?,?,?,?);'''
    gutils.execute(del_cells)
    cur = gutils.con.cursor()
    for i, row in enumerate(calculate_arfwrf(grid, areas), 1):
        point = row[0]
        gpb_qry = qry_cells.format(point)
        cur.execute(gpb_qry, (i,) + row[1:])
    gutils.con.commit()


def raster2grid(grid, out_raster, src_raster, options):
    """
    Generator for resampling and probing raster data within 'grid' features
    """
    new = gdal.Warp(out_raster, src_raster, options=options)
    del new
    probe_raster = QgsRasterLayer(out_raster)
    # if probe_raster.dataProvider().srcHasNoDataValue(1):
    #     nodata = probe_raster.dataProvider().srcNoDataValue(1)
    # else:
    nodata = -9999.

    for feat in grid.getFeatures():
        center = feat.geometry().centroid().asPoint()
        ident = probe_raster.dataProvider().identify(center, QgsRaster.IdentifyFormatValue)
        if ident.isValid():
            val = ident.results()[1]
            if not is_number(val):
                val = nodata
            else:
                pass
            yield (round(val, 3), feat.id())
    del probe_raster


def grid_has_empty_elev(gutils):
    qry = '''SELECT fid FROM grid WHERE elevation = -9999;'''
    res = gutils.execute(qry)
    try:
        id = res.next()
        return True
    except StopIteration:
        return False


def get_intersecting_grid_elems(gutils, table_name, table_fids=None, use_center=False, switch=False):
    """
    Get a list of grid elements fids that intersect the given tables features.
    Optionally, users can specify a list of table_fids to be checked.
    """
    grid_geom = 'ST_Centroid(GeomFromGPB(g.geom))' if use_center is True else 'GeomFromGPB(g.geom)'
    qry = '''
        SELECT l.fid, g.fid FROM grid AS g, {} AS l
        WHERE ST_Intersects(GeomFromGPB(l.geom), {})
        '''.format(table_name, grid_geom)
    if table_fids:
        qry += 'AND l.fid IN ({}) '.format(', '.join(str(f) for f in table_fids))
    qry += '''ORDER BY l.fid, g.fid;'''
    res = gutils.execute(qry).fetchall()
    if switch is True:
        first, second = 1, 0
    else:
        first, second = 0, 1
    grid_elems = [(row[first], row[second]) for row in res]
    return grid_elems

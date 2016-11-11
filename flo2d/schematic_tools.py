# -*- coding: utf-8 -*-

# FLO-2D Preprocessor tools for QGIS
# Copyright © 2016 Lutra Consulting for FLO-2D

# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version

from operator import itemgetter
from collections import defaultdict
from math import pi
from PyQt4.QtCore import QPyNullVariant
from qgis.core import QGis, QgsSpatialIndex, QgsFeatureRequest, QgsVector, QgsGeometry, QgsPoint
from grid_tools import fid_from_grid


def get_intervals(line_feature, point_layer, col_value, buffer_size):
    """
    Function which calculates intervals and assigning values based on intersection between line and snapped points.
    Points are selected by line buffer and filtered by the distance from the line feature.
    """
    points = point_layer.getFeatures()
    lgeom = line_feature.geometry()
    tot_len = lgeom.length()
    buf = lgeom.buffer(buffer_size, 5)
    positions = {}
    for feat in points:
        pnt = feat.geometry()
        if buf.contains(pnt):
            pass
        else:
            continue
        pos = lgeom.lineLocatePoint(pnt) / tot_len
        val = feat[col_value]
        closest = lgeom.distance(pnt)
        if pos not in positions or closest < positions[pos][-1]:
            positions.values()
            positions[pos] = (pos, val, closest)
        else:
            pass
    snapped = (i[:-1] for i in sorted(positions.values(), key=itemgetter(0)))
    intervals = []
    try:
        start_distance, start_value = next(snapped)
        end_distance, end_value = next(snapped)
        while True:
            delta_distance = end_distance - start_distance
            delta_value = end_value - start_value
            interval = (start_distance, end_distance, delta_distance, start_value, end_value, delta_value)
            intervals.append(interval)
            start_distance, start_value = end_distance, end_value
            end_distance, end_value = next(snapped)
    except StopIteration:
        return intervals


def interpolate_along_line(line_feature, sampling_layer, intervals, id_col='fid', join_col='user_line_fid'):
    """
    Generator for interpolating values of sampling features centroids snapped to interpolation line.
    Line intervals list needs to be calculated first and derived as a generator parameter.
    """
    start, end = intervals[0], intervals[-1]
    lgeom = line_feature.geometry()
    lid = line_feature[id_col]
    tot_len = lgeom.length()
    fs = sampling_layer.getFeatures()
    sc = [(lgeom.lineLocatePoint(f.geometry().centroid()) / tot_len, f[id_col]) for f in fs if f[join_col] == lid]
    sc.sort()
    inter_iter = iter(intervals)
    snapped_iter = iter(sc)
    try:
        start_distance, end_distance, delta_distance, start_value, end_value, delta_value = next(inter_iter)
        position, fid = next(snapped_iter)
        while True:
            if start_distance < position < end_distance:
                segment_distance = position - start_distance
                coef = segment_distance / delta_distance
                value = start_value + delta_value * coef
                yield (value, fid)
            elif position == start_distance:
                yield (start_value, fid)
            elif position == end_distance:
                yield (end_value, fid)
            elif position < start[0]:
                yield (start[3], fid)
            elif position > end[1]:
                yield (start[4], fid)
            else:
                start_distance, end_distance, delta_distance, start_value, end_value, delta_value = next(inter_iter)
                continue
            position, fid = next(snapped_iter)
    except StopIteration:
        return


def polys2levees(line_feature, poly_lyr, levees_lyr, value_col, correct_val, id_col='fid', join_col='user_line_fid'):
    """
    Generator for assigning elevation values from polygons to levees.
    Levee sides centroids are snapped to the user levee line feature and next tested for intersecting with polygons.
    """
    lgeom = line_feature.geometry()
    lid = line_feature[id_col]
    polys = poly_lyr.getFeatures()
    allfeatures = {feature.id(): feature for feature in polys}
    index = QgsSpatialIndex()
    map(index.insertFeature, allfeatures.itervalues())
    fids = index.intersects(lgeom.boundingBox())
    sel_polys = [allfeatures[fid] for fid in fids if allfeatures[fid].geometry().intersects(lgeom)]
    for feat in levees_lyr.getFeatures():
        if feat[join_col] == lid:
            pass
        else:
            continue
        levcrest = feat['levcrest']
        center = feat.geometry().centroid()
        pos = lgeom.lineLocatePoint(center)
        pnt = lgeom.interpolate(pos)
        for poly in sel_polys:
            if poly.geometry().contains(pnt):
                abs_val, cor = poly[value_col], poly[correct_val]
                if not isinstance(abs_val, QPyNullVariant) and not isinstance(cor, QPyNullVariant):
                    poly_val = abs_val + cor
                elif not isinstance(abs_val, QPyNullVariant) and isinstance(cor, QPyNullVariant):
                    poly_val = abs_val
                elif isinstance(abs_val, QPyNullVariant) and not isinstance(cor, QPyNullVariant):
                    poly_val = cor + levcrest
                else:
                    continue
                yield (poly_val, feat[id_col])
                break
            else:
                pass


def bresenham_line(x1, y1, x2, y2):
    """
    Bresenham's Line Algorithm.
    Returns a list of [x,y] tuples. Works with integer coordinates.
    Based on impl from http://www.roguebasin.com/index.php?title=Bresenham%27s_Line_Algorithm
    """

    # Determine how steep the line is
    is_steep = abs(y2 - y1) > abs(x2 - x1)

    # Rotate line
    if is_steep:
        x1, y1 = y1, x1
        x2, y2 = y2, x2

    # Swap start and end points if necessary and store swap state
    swapped = False
    if x1 > x2:
        x1, x2 = x2, x1
        y1, y2 = y2, y1
        swapped = True

    # Calculate differentials
    dx = x2 - x1
    dy = y2 - y1

    # Calculate error
    error = int(dx / 2.0)
    ystep = 1 if y1 < y2 else -1

    # Iterate over bounding box generating points between start and end
    y = y1
    points = []
    for x in range(x1, x2 + 1):
        coord = (y, x) if is_steep else (x, y)
        points.append(coord)
        error -= abs(dy)
        if error < 0:
            y += ystep
            error += dx

    # Reverse the list if the coordinates were swapped
    if swapped:
        points.reverse()
    return points


def snap_line(x1, y1, x2, y2, cell_size, offset_x, offset_y):
    """
    Take line from (x1,y1) to (x2,y2) and generate list of cell coordinates
    covered by the line within the given grid.
    """

    def float_to_int_coords(x, y):
        xt = int(round((x + offset_x) / float(cell_size)))
        yt = int(round((y + offset_y) / float(cell_size)))
        return xt, yt

    def int_to_float_coords(xt, yt):
        x = xt * cell_size - offset_x
        y = yt * cell_size - offset_y
        return x, y

    xt1, yt1 = float_to_int_coords(x1, y1)
    xt2, yt2 = float_to_int_coords(x2, y2)

    points = bresenham_line(xt1, yt1, xt2, yt2)

    return [int_to_float_coords(x, y) for x, y in points]


def schematize_lines(line_layer, cell_size, offset_x, offset_y):
    """
    Generator for finding grid centroids coordinates for each schematized line segment.
    Calculations are done using Bresenham's Line Algorithm.
    """
    lines = line_layer.getFeatures()
    for line in lines:
        segment = []
        try:
            vertices = line.geometry().asPolyline()
            iver = iter(vertices)
            x1, y1 = next(iver)
            x2, y2 = next(iver)
            segment += [x for x in snap_line(x1, y1, x2, y2, cell_size, offset_x, offset_y)]
            while True:
                x1, y1 = x2, y2
                x2, y2 = next(iver)
                segment += [x for x in snap_line(x1, y1, x2, y2, cell_size, offset_x, offset_y)][1:]
        except StopIteration:
            yield segment


def populate_directions(coords, grids):
    """
    Function for populating streets directions inside each grid cell.
    """
    try:
        start, end = (0, 0)
        igrids = iter(grids)
        x1, y1 = next(igrids)
        x2, y2 = next(igrids)
        while True:
            if x1 == x2 and y1 < y2:
                start = 1
                end = 3
            elif x1 < x2 and y1 == y2:
                start = 2
                end = 4
            elif x1 == x2 and y1 > y2:
                start = 3
                end = 1
            elif x1 > x2 and y1 == y2:
                start = 4
                end = 2
            elif x1 < x2 and y1 < y2:
                start = 5
                end = 7
            elif x1 < x2 and y1 > y2:
                start = 6
                end = 8
            elif x1 > x2 and y1 > y2:
                start = 7
                end = 5
            elif x1 > x2 and y1 < y2:
                start = 8
                end = 6
            else:
                pass
            coords[(x1, y1)].add(start)
            coords[(x2, y2)].add(end)
            x1, y1 = x2, y2
            x2, y2 = next(igrids)
    except StopIteration:
        return


def calculate_offset(gutils, cell_size):
    """
    Finding offset of grid squares centers which is formed after switching from float to integers.
    Rounding to integers is needed for Bresenham's Line Algorithm.
    """
    geom = gutils.single_centroid('1').strip('POINT()').split()
    x, y = float(geom[0]), float(geom[1])
    x_offset = round(x / cell_size) * cell_size - x
    y_offset = round(y / cell_size) * cell_size - y
    return x_offset, y_offset


def schematize_channels(gutils, line_layer, cell_size):
    """
    Calculating and writing schematized channels into the 'chan' table.
    """
    x_offset, y_offset = calculate_offset(gutils, cell_size)
    segments = schematize_lines(line_layer, cell_size, x_offset, y_offset)
    del_sql = '''DELETE FROM chan WHERE user_line_fid IS NOT NULL;'''
    insert_sql = '''INSERT INTO chan (geom, user_line_fid) VALUES (AsGPB(ST_GeomFromText('LINESTRING({0})')), ?)'''
    gutils.execute(del_sql)
    cursor = gutils.con.cursor()
    seen = set()
    for i, line in enumerate(segments, 1):
        vertices = ','.join(('{0} {1}'.format(*xy) for xy in line if xy not in seen and not seen.add(xy)))
        cursor.execute(insert_sql.format(vertices), (i,))
    gutils.con.commit()


def schematize_streets(gutils, line_layer, cell_size):
    """
    Calculating and writing schematized streets into the 'street_seg' table.
    """
    x_offset, y_offset = calculate_offset(gutils, cell_size)
    segments = schematize_lines(line_layer, cell_size, x_offset, y_offset)
    coords = defaultdict(set)
    for grids in segments:
        populate_directions(coords, grids)
    functions = {
        1: (lambda x, y, shift: (x, y + shift)),
        2: (lambda x, y, shift: (x + shift, y)),
        3: (lambda x, y, shift: (x, y - shift)),
        4: (lambda x, y, shift: (x - shift, y)),
        5: (lambda x, y, shift: (x + shift, y + shift)),
        6: (lambda x, y, shift: (x + shift, y - shift)),
        7: (lambda x, y, shift: (x - shift, y - shift)),
        8: (lambda x, y, shift: (x - shift, y + shift))
    }
    del_sql = '''DELETE FROM {0};'''
    insert_elem_sql = '''INSERT INTO street_elems (seg_fid, istdir) VALUES (?,?)'''
    insert_sql = '''INSERT INTO street_seg (geom) VALUES (AsGPB(ST_GeomFromText('MULTILINESTRING({0})')))'''
    gpb_part = '''({0} {1}, {2} {3})'''
    half_cell = cell_size * 0.5
    gutils.execute(del_sql.format('street_seg'))
    gutils.execute(del_sql.format('street_elems'))
    cursor = gutils.con.cursor()
    for i, (xy, directions) in enumerate(coords.iteritems(), 1):
        x1, y1 = xy
        xy_dir = []
        for d in directions:
            cursor.execute(insert_elem_sql, (i, d))
            xy_dir.append(functions[d](x1, y1, half_cell))
        multiline = ','.join((gpb_part.format(x1, y1, x2, y2) for x2, y2 in xy_dir))
        gpb_insert = insert_sql.format(multiline)
        cursor.execute(gpb_insert)
    gutils.con.commit()
    fid_grid = fid_from_grid(gutils, 'street_seg', grid_center=True, switch=True)
    grid_sql = '''UPDATE street_seg SET igridn = ? WHERE fid = ?;'''
    gutils.execute_many(grid_sql, fid_grid)


def levee_grid_isect_pts(levee_fid, grid_fid, levee_lyr, grid_lyr, with_centroid=True):
    lfeat = levee_lyr.getFeatures(QgsFeatureRequest(levee_fid)).next()
    gfeat = grid_lyr.getFeatures(QgsFeatureRequest(grid_fid)).next()
    grid_centroid = gfeat.geometry().centroid().asPoint()
    lg_isect = gfeat.geometry().intersection(lfeat.geometry())
    pts = []
    if lg_isect.isMultipart():
        for part in lg_isect.asMultiPolyline():
            p1 = part[0]
            p2 = part[-1]
            pts.append((p1, p2))
    else:
        p1 = lg_isect.asPolyline()[0]
        p2 = lg_isect.asPolyline()[-1]
        pts.append((p1, p2))
    if with_centroid:
        return pts, grid_centroid
    else:
        return pts, None


def levee_schematic(lid_gid_elev, levee_lyr, grid_lyr):
    schem_lines = {}
    gids = []
    nv = QgsVector(0, 1)
    # for each line crossing a grid element
    for lid, gid, elev in lid_gid_elev:
        pts, c = levee_grid_isect_pts(lid, gid, levee_lyr, grid_lyr)
        if gid not in gids:
            schem_lines[gid] = {}
            schem_lines[gid]['lines'] = {}
            schem_lines[gid]['centroid'] = c
            schem_lines[gid]['elev'] = elev
            gids.append(gid)
        else:
            pass
        sides = []
        # for each entry and leaving point pair
        for pts_pair in pts:
            p1, p2 = pts_pair
            c_p1 = p1 - c
            c_p2 = p2 - c
            a = c_p1.angle(c_p2)
            a = 2 * pi + a if a < 0 else a
            # drawing direction (is it clockwise?)
            cw = a >= pi
            c_p1_a = c_p1.angle(nv)
            c_p1_a = 2 * pi + c_p1_a if c_p1_a < 0 else c_p1_a
            c_p2_a = c_p2.angle(nv)
            c_p2_a = 2 * pi + c_p2_a if c_p2_a < 0 else c_p2_a
            # nearest octagon nodes
            n1 = int(c_p1_a / (pi / 4)) % 8
            n2 = int(c_p2_a / (pi / 4)) % 8
            # if entry and leaving octagon node are identical, skip the pair (no levee seg)
            if n1 == n2:
                continue
            else:
                pass
            # starting and ending octagon side for current pts pair
            s1 = (n1 + 1 if cw else n1) % 8
            s2 = (n2 if cw else n2 + 1) % 8
            # add sides from s1 to s2 for creating the segments
            sides.append(s2)
            while s1 != s2:
                sides.insert(0, s1)
                s1 = (s1 + 1 if cw else s1 - 1) % 8
        sides = set(sides)
        schem_lines[gid]['lines'][lid] = sides
    return schem_lines


def generate_schematic_levees(gutils, levee_lyr, grid_lyr):
    # octagon nodes to sides map
    octagon_levee_dirs = {0: 1, 1: 5, 2: 2, 3: 6, 4: 3, 5: 7, 6: 4, 7: 8}
    levee_dir_pts = {
        1: (lambda x, y, square_half, octa_half: (x - octa_half, y + square_half, x + octa_half, y + square_half)),
        2: (lambda x, y, square_half, octa_half: (x + square_half, y + octa_half, x + square_half, y - octa_half)),
        3: (lambda x, y, square_half, octa_half: (x + octa_half, y - square_half, x - octa_half, y - square_half)),
        4: (lambda x, y, square_half, octa_half: (x - square_half, y - octa_half, x - square_half, y + octa_half)),
        5: (lambda x, y, square_half, octa_half: (x + octa_half, y + square_half, x + square_half, y + octa_half)),
        6: (lambda x, y, square_half, octa_half: (x + square_half, y - octa_half, x + octa_half, y - square_half)),
        7: (lambda x, y, square_half, octa_half: (x - octa_half, y - square_half, x - square_half, y - octa_half)),
        8: (lambda x, y, square_half, octa_half: (x - square_half, y + octa_half, x - octa_half, y + square_half))
    }
    lid_gid_elev = fid_from_grid(gutils, 'user_levee_lines', None, False, False, 'elevation')
    cell_size = float(gutils.get_cont_par('CELLSIZE'))
    scale = 0.9
    # square half
    sh = cell_size * 0.5 * scale
    # octagon half
    oh = sh / 2.414
    schem_lines = levee_schematic(lid_gid_elev, levee_lyr, grid_lyr)

    del_sql = '''DELETE FROM levee_data WHERE user_line_fid IS NOT NULL;'''
    ins_sql = '''INSERT INTO levee_data (grid_fid, ldir, levcrest, user_line_fid, geom)
                 VALUES (?,?,?,?, AsGPB(ST_GeomFromText(?)));'''

    # create levee segments for distinct levee directions in each grid element
    grid_levee_seg = {}
    data = []
    for gid, gdata in schem_lines.iteritems():
        elev = gdata['elev']
        grid_levee_seg[gid] = {}
        grid_levee_seg[gid]['sides'] = {}
        grid_levee_seg[gid]['centroid'] = gdata['centroid']
        for lid, sides in gdata['lines'].iteritems():
            for side in sides:
                if side not in grid_levee_seg[gid]['sides'].keys():
                    grid_levee_seg[gid]['sides'][side] = lid
                    ldir = octagon_levee_dirs[side]
                    c = gdata['centroid']
                    data.append((
                        gid,
                        ldir,
                        elev,
                        lid,
                        'LINESTRING({0} {1}, {2} {3})'.format(*levee_dir_pts[ldir](c.x(), c.y(), sh, oh))
                    ))
    gutils.con.execute(del_sql)
    gutils.con.executemany(ins_sql, data)
    gutils.con.commit()


def perp2side(vec, side, tol):
    # octagon sides normal vectors
    nvec = {
        0: QgsVector(0, 1), 1: QgsVector(1, 1), 2: QgsVector(1, 0), 3: QgsVector(1, -1),
        4: QgsVector(0, -1), 5: QgsVector(-1, -1), 6: QgsVector(-1, 0), 7: QgsVector(-1, 1)
    }
    tol = tol * pi / 180
    if abs(nvec[side].angle(vec)) <= tol or abs(nvec[side].rotateBy(pi).angle(vec)) <= tol:
        return True
    else:
        return False


def find_banks(domain_feature, centerline_fature, xs_lyr):
    xs_feats = xs_lyr.getFeatures()
    allfeatures = {feature.id(): feature for feature in xs_feats}
    index = QgsSpatialIndex()
    map(index.insertFeature, allfeatures.itervalues())
    geom = domain_feature.geometry()
    centerline = centerline_fature.geometry()
    fids = index.intersects(geom.boundingBox())
    cross_sections = [allfeatures[fid] for fid in fids if allfeatures[fid].geometry().intersects(geom)]
    # Trimming centerline
    trimmed_centerline = geom.intersection(centerline).asPolyline()
    # Converting domain polygon to polyline
    envelope = geom.convertToType(QGis.Line)
    # Splitting domain polyline by center line
    splitted = envelope.splitGeometry(centerline.asPolyline(), 0)[1]
    trimmed_envelope = envelope.asPolyline()
    s1 = splitted[0].asPolyline()
    if len(splitted) == 2:
        s2 = splitted[1].asPolyline()
        s2 += trimmed_envelope
    else:
        s2 = trimmed_envelope
    if trimmed_envelope[-1] == s1[0]:
        s1.reverse()
    else:
        s2.reverse()
    # Determine which lines represents left and right
    x0, y0 = trimmed_centerline[0]
    x1, y1 = trimmed_centerline[1]
    x2, y2 = s2[1]
    con = (x1 - x0)*(y2 - y0) - (x2 - x0)*(y1 - y0)
    geom1 = QgsGeometry.fromPolyline(s1)
    geom2 = QgsGeometry.fromPolyline(s2)
    if con > 0:
        right = geom1
        left = geom2
    elif con < 0:
        right = geom2
        left = geom1
    else:
        return

    # Finding bank stations
    for xs in cross_sections:
        xs_geom = xs.geometry()
        xs_trimmed = xs_geom.intersection(geom).asPolyline()
        start = QgsGeometry.fromPoint(QgsPoint(*xs_trimmed[0]))
        end = QgsGeometry.fromPoint(QgsPoint(*xs_trimmed[-1]))
        left_bank = left.nearestPoint(start)
        right_bank = right.nearestPoint(end)
        yield left_bank, right_bank

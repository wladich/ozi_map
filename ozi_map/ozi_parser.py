# Устаревший файл, преобразующий структуру из ozi_reader в более понятную структуру, которая использовалась
# в каком-то старом проекте

from .attr_dict import AttrDict
from copy import deepcopy
import os
import pyproj
from . import ozi_reader
from glob import glob
import math
__all__= ['parse_ozi_map']


datums = {
    'wgs84': '+datum=WGS84',
    'sk42': '+ellps=krass +towgs84=23.9,-141.3,-80.9,0,-0.37,-0.85,-0.12 +no_defs'
    #'sk42': '+ellps=krass +no_defs'
    }
datum_map = {
    # http://www.hemanavigator.com.au/Products/TopographicalGPS/OziExplorer/tabid/69/Default.aspx
    'WGS 84': datums['wgs84'],
    'Pulkovo 1942 (1)': datums['sk42'],
    'Pulkovo 1942 (2)': datums['sk42'],
    'Pulkovo 1942': datums['sk42']
    }

datum_names_map = {
    'WGS 84': 'wgs84',
    'Pulkovo 1942 (1)': 'sk42',
    'Pulkovo 1942 (2)': 'sk42',
    'Pulkovo 1942': 'sk42'
    }
proj_map = {
    'Latitude/Longitude':
        ('+proj=latlong',),
    'Transverse Mercator':
        ('+proj=tmerc +units=m',
        ('+lat_0=', 'lat_origin'),
        ('+lon_0=', 'lon_origin'),
        ('+k=', 'k_factor'),
        ('+x_0=', 'false_easting'),
        ('+y_0=', 'false_northing'))}



def make_converter(s_srs, d_srs):
    proj_src = pyproj.Proj(s_srs)
    proj_dest = pyproj.Proj(d_srs)
    def converter(*args):
        if len(args) == 2 and isinstance(args[0], float) and isinstance(args[1], float):
            return pyproj.transform(proj_src, proj_dest, *args)
        elif len(args) == 1 and hasattr(args[0], '__len__'):
            points = list(zip(*args[0]))
            points = pyproj.transform(proj_src, proj_dest, *points)
            return list(zip(*points))
        else:
            raise TypeError()
    return converter

def find_file_ci(path, file_name):
    pattern = ''.join(['[%s%s]' % (c.upper(), c.lower()) for c in file_name])
    files = glob(os.path.join(path, pattern))
    if files:
        if len(files) > 1:
            raise Exception('Ambigios file name "%s"' % file_name)
        return files[0]
    else:
        return os.path.join(path, file_name)


def parse_ozi_map(map_file_name, cutline_type = None):
    """cutline_type can be 'projected', 'latlon' or None"""
    ozi_map = ozi_reader.read_map(open(map_file_name).readlines())
    ozi_dir = os.path.split(os.path.abspath(map_file_name))[0]

    image_name = find_file_ci(ozi_dir, ozi_map.file_name)
    if not image_name:
        raise Exception('File "%s" not found.' % image_name)
    map_srs = get_srs_as_proj4(ozi_map.datum, ozi_map.projection)
    map_ll_srs = get_ozi_ll_srs(ozi_map.datum, ozi_map.projection)
    gcps = convert_ozi_gcps(ozi_map.gcps, map_srs, map_ll_srs)
    geotransform = gcps_to_geotransform(gcps)
    units_per_pixel = get_resolution(geotransform)
    if cutline_type and len(ozi_map.cutline) > 2:
        cutline_projected = {'projected': True, 'latlon': False}[cutline_type]
        if cutline_projected:
            cutline_points = convert_cutline(ozi_map.cutline, map_srs, map_ll_srs)
            cutline_srs = map_srs
            cutline_units_per_pixel = units_per_pixel
        else:
            cutline_points = convert_cutline(ozi_map.cutline)
            cutline_srs = map_ll_srs
            cutline_units_per_pixel = get_resolution(geotransform, map_srs, map_ll_srs)
        cutline = AttrDict(points = cutline_points, srs = cutline_srs, units_per_pixel = cutline_units_per_pixel)
    else:
        cutline = None

    result = AttrDict()
    result.image_name = image_name
    result.map_srs = map_srs
    result.gcps = gcps
    result.units_per_pixel = units_per_pixel
    result.cutline = cutline
    result.geotransform = geotransform
    result.datum = datum_names_map[ozi_map.datum]
    result.projection = ozi_map.projection
    result.inv_geotransform = gcps_to_geotransform([AttrDict(pixel = g.ref, ref = g.pixel) for g in gcps ])
    return result


def get_resolution(geotransform, s_srs = None, t_srs = None):
    p0 = (geotransform[0], geotransform[3])
    p1 = (geotransform[0] + geotransform[1], geotransform[3] + geotransform[4])
    p2 = (geotransform[0] + geotransform[2], geotransform[3] + geotransform[5])
    if s_srs and t_srs:
        convert = make_converter(s_srs, t_srs)
        p0, p1, p2 = convert([p0, p1, p2])
    dx = math.sqrt((p1[0] - p0[0])**2 + (p1[1] - p0[1])**2)
    dy = math.sqrt((p2[0] - p0[0])**2 + (p2[1] - p0[1])**2)
    return max(dx, dy)


def get_srs_as_proj4(ozi_datum_string, ozi_projection):
    try:
        srs = [datum_map[ozi_datum_string]]
        proj_params = proj_map[ozi_projection.name]
    except KeyError as e:
        raise Exception("Unsupported datum or projection: '%s'" % (e.message))
    srs.append(proj_params[0])
    for proj_param, ozi_param in proj_params[1:]:
        try:
            srs.append('%s%s' % (proj_param, ozi_projection.get(ozi_param)))
        except KeyError:
            raise Exception('Projection parameters not fully defined')
    return ' '.join(srs)

def get_ozi_ll_srs(ozi_datum_string, ozi_projection):
    tmp_projection = deepcopy(ozi_projection)
    tmp_projection.name = 'Latitude/Longitude'
    srs_string = get_srs_as_proj4(ozi_datum_string, tmp_projection)
    return srs_string

def convert_ozi_gcps(ozi_gcps, proj_srs, ll_srs):
    ll_to_proj = make_converter(ll_srs, proj_srs)
    gcps = []
    for ozi_gcp in ozi_gcps:
        if ozi_gcp.type == 'proj':
            gcp_ref = ozi_gcp.ref
        else:
            x, y = ll_to_proj(ozi_gcp.ref.x, ozi_gcp.ref.y)
            gcp_ref = AttrDict(x = x, y = y)
        gcp = AttrDict(pixel = ozi_gcp.pixel, ref = gcp_ref)
        gcps.append(gcp)
    return gcps

def convert_cutline(points, proj_srs = None, ll_srs = None):
    if points:
        if proj_srs and ll_srs:
            ll_to_proj = make_converter(ll_srs, proj_srs)
            points = ll_to_proj(points)
        else:
            points = points[:]
        points.append(points[0])
    return points

def gcps_to_geotransform(gcps):
    gcps_n = len(gcps)
    if gcps_n < 2:
        raise ValueError('gcps_to_geotransform: at least 2 gcps are required')
    geotransform = [0] * 6
    if gcps_n == 2:
        if gcps[1].pixel.x == gcps[0].pixel.x or gcps[1].pixel.y == gcps[0].pixel.y:
            raise ValueError('gcps_to_geotransform: 2 gcps must not lie on horizontal or vertical line')
        geotransform[1] = (gcps[1].ref.x - gcps[0].ref.x) / (gcps[1].pixel.x - gcps[0].pixel.x);
        geotransform[2] = 0.0;
        geotransform[4] = 0.0;
        geotransform[5] = (gcps[1].ref.y - gcps[0].ref.y) / (gcps[1].pixel.y - gcps[0].pixel.y);
        geotransform[0] = gcps[0].ref.x - gcps[0].pixel.x * geotransform[1] \
            - gcps[0].pixel.y * geotransform[2]
        geotransform[3] = gcps[0].ref.y - gcps[0].pixel.x * geotransform[4] \
            - gcps[0].pixel.y * geotransform[5]
        return geotransform

    sum_x = sum_y = sum_xy = sum_xx = sum_yy = 0.0
    sum_Lon = sum_Lonx = sum_Lony = 0.0
    sum_Lat = sum_Latx = sum_Laty = 0.0
    for gcp in gcps:
        sum_x += gcp.pixel.x
        sum_y += gcp.pixel.y
        sum_xy += gcp.pixel.x * gcp.pixel.y
        sum_xx += gcp.pixel.x * gcp.pixel.x
        sum_yy += gcp.pixel.y * gcp.pixel.y
        sum_Lon += gcp.ref.x
        sum_Lonx += gcp.ref.x * gcp.pixel.x
        sum_Lony += gcp.ref.x * gcp.pixel.y
        sum_Lat += gcp.ref.y
        sum_Latx += gcp.ref.y * gcp.pixel.x
        sum_Laty += gcp.ref.y * gcp.pixel.y

    divisor = gcps_n * (sum_xx * sum_yy - sum_xy * sum_xy) + \
        2 * sum_x * sum_y * sum_xy - sum_y * sum_y * sum_xx - sum_x * sum_x * sum_yy

    if divisor == 0.0:
        raise ValueError('gcps_to_geotransform: can''t calculate geotransform for given gcps')

    geotransform[0] = (sum_Lon * (sum_xx * sum_yy - sum_xy * sum_xy) \
                           + sum_Lonx * (sum_y * sum_xy - sum_x *  sum_yy) \
                           + sum_Lony * (sum_x * sum_xy - sum_y * sum_xx)) \
                           / divisor
    geotransform[3] = (sum_Lat * (sum_xx * sum_yy - sum_xy * sum_xy) \
                           + sum_Latx * (sum_y * sum_xy - sum_x *  sum_yy) \
                           + sum_Laty * (sum_x * sum_xy - sum_y * sum_xx)) \
                           / divisor
    geotransform[1] = (sum_Lon * (sum_y * sum_xy - sum_x * sum_yy) \
                           + sum_Lonx * (gcps_n  * sum_yy - sum_y * sum_y) \
                           + sum_Lony * (sum_x * sum_y - sum_xy * gcps_n )) \
                           / divisor
    geotransform[2] = (sum_Lon * (sum_x * sum_xy - sum_y * sum_xx) \
                           + sum_Lonx * (sum_x * sum_y - gcps_n  * sum_xy) \
                           + sum_Lony * (gcps_n  * sum_xx - sum_x * sum_x)) \
                           / divisor
    geotransform[4] = (sum_Lat * (sum_y * sum_xy - sum_x * sum_yy) \
                           + sum_Latx * (gcps_n  * sum_yy - sum_y * sum_y) \
                           + sum_Laty * (sum_x * sum_y - sum_xy * gcps_n )) \
                           / divisor
    geotransform[5] = (sum_Lat * (sum_x * sum_xy - sum_y * sum_xx) \
                           + sum_Latx * (sum_x * sum_y - gcps_n  * sum_xy) \
                           + sum_Laty * (gcps_n  * sum_xx - sum_x * sum_x)) \
                           / divisor
    return geotransform

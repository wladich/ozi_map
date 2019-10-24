# -*- coding: utf-8 -*-
import argparse
import os
from ozi_map import ozi_reader
from maprec import Maprecord
import pyproj


def find_image_file(ozi_image_filename, base_dir):
    ozi_image_filename = ozi_image_filename.split('\\')[-1].lower()
    path = None
    for fn in os.listdir(base_dir):
        if os.path.isfile(os.path.join(base_dir, fn)) and fn.lower() == ozi_image_filename:
            if path is not None:
                raise Exception('Ambigios file name "%s"' % fn)
            path = os.path.abspath(os.path.join(base_dir, fn))
    if path is None:
        raise Exception('Image "%s" not found' % ozi_image_filename)
    return path


def get_srs_as_proj4(ozi_datum_string, ozi_projection=None):
    datums = {
        'wgs84': '+datum=WGS84',
        'sk42': '+ellps=krass +towgs84=23.9,-141.3,-80.9,0,-0.37,-0.85,-0.12 +no_defs'
        }
    datum_map = {
        # http://www.hemanavigator.com.au/Products/TopographicalGPS/OziExplorer/tabid/69/Default.aspx
        'WGS 84': datums['wgs84'],
        'Pulkovo 1942 (1)': datums['sk42'],
        'Pulkovo 1942 (2)': datums['sk42'],
        'Pulkovo 1942': datums['sk42']
        }
    proj_map = {
        'Latitude/Longitude': ('+proj=latlong',),
        'Transverse Mercator': (
            '+proj=tmerc +units=m',
            ('+lat_0=', 'lat_origin'),
            ('+lon_0=', 'lon_origin'),
            ('+k=', 'k_factor'),
            ('+x_0=', 'false_easting'),
            ('+y_0=', 'false_northing')),
        'Lambert Conformal Conic': (
            '+proj=lcc +units=m',
            ('+lat_0=', 'lat_origin'),
            ('+lon_0=', 'lon_origin'),
            ('+lat_1=', 'lat1'),
            ('+lat_2=', 'lat2'),
        ),
        'Mercator': (
            '+proj=merc',
            ('+lon_0=', 'lon_origin'),
            ('+k=', 'k_factor'),
            ('+x_0=', 'false_easting'),
            ('+y_0=', 'false_northing'),
        )
    }
    try:
        srs = [datum_map[ozi_datum_string]]
    except KeyError as e:
        raise Exception("Unsupported datum: '%s'" % (e.message))
    if ozi_projection is None:
        proj_params = ('+proj=latlong',)
    else:
        try:
            proj_params = proj_map[ozi_projection.name]
        except KeyError as e:
            raise Exception("Unsupported projection: '%s'" % (e.message))
    srs.append(proj_params[0])
    for proj_param, ozi_param in proj_params[1:]:
        try:
            value = ozi_projection.get(ozi_param)
            if value is not None:
                srs.append('%s%s' % (proj_param, value))
        except KeyError:
            raise Exception('Projection parameters not fully defined')
    return ' '.join(srs)


def convert_gcps(ozi_gcps):
    gcps = []
    for ozi_gcp in ozi_gcps:
        gcp = {
            'pixel': {'x': ozi_gcp['pixel']['x'], 'y': ozi_gcp['pixel']['y']},
            'ground': {'x': ozi_gcp['ref']['x'], 'y': ozi_gcp['ref']['y']},
            'is_projected': ozi_gcp.type == 'proj'
        }
        gcps.append(gcp)
    return gcps


def convert_cutline(ozi_cutline):
    return [{'x': x, 'y': y} for x, y in ozi_cutline]


def get_maprecord_from_ozi_file(ozi_map_file, cutline_type='latlon'):
    maprecord = {}
    ozi_map = ozi_reader.read_ozi_map(open(ozi_map_file))
    try:
        maprecord['image_path'] = find_image_file(ozi_map.file_name, os.path.dirname(ozi_map_file) or '.')
    except Exception as e:
        raise Exception('Error in "%s": %s' % (ozi_map_file, e))
    maprecord['srs'] = get_srs_as_proj4(ozi_map.datum, ozi_map.projection)
    maprecord['gcps'] = convert_gcps(ozi_map.gcps)

    if cutline_type == 'raw':
        cutline_srs = 'RAW'
        cutline_points = ozi_map['cutline_pixels']
    elif cutline_type == 'latlon':
        cutline_srs = get_srs_as_proj4(ozi_map.datum)
        cutline_points = ozi_map.cutline
    elif cutline_type == 'proj':
        proj_str = get_srs_as_proj4(ozi_map.datum, ozi_map.projection)
        proj = pyproj.Proj(proj_str)
        cutline_srs = proj_str
        cutline_points = proj(*zip(*ozi_map.cutline))
        cutline_points = zip(*cutline_points)
    else:
        raise Exception()

    maprecord['cutline'] = {
        'srs': cutline_srs,
        'points': convert_cutline(cutline_points)
        }
    return maprecord


def parse_command_line():
    parser = argparse.ArgumentParser()
    parser.add_argument('in_file', metavar='ozi_file.map')
    parser.add_argument('out_file', metavar='output.maprec')
    parser.add_argument('--abs-path', action='store_true', help='Write absolute path to image file')
    parser.add_argument('--cutline', required=False, choices=['raw', 'latlon', 'proj'], default='latlon')
    return parser.parse_args()


def main():
    args = parse_command_line()
    maprecord = get_maprecord_from_ozi_file(args.in_file, args.cutline)
    maprecord = Maprecord(args.in_file, maprecord)
    maprecord.write(args.out_file, image_path_relative=not args.abs_path)


if __name__ == '__main__':
    main()

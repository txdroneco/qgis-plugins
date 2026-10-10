# -*- coding: utf-8 -*-
"""
ImageMapper - DJI Drone Image Location Plotter
QGIS 4.0 Plugin

Reads EXIF/XMP metadata from drone images and plots
their locations on a map with colorized icons.
"""


def classFactory(iface):
    from .image_mapper import ImageMapper
    return ImageMapper(iface)

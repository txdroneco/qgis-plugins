# -*- coding: utf-8 -*-
"""
Symbology renderers for altitude gradient and RTK category colorization.
"""

from qgis.core import (
    QgsCategorizedSymbolRenderer,
    QgsGraduatedSymbolRenderer,
    QgsGradientColorRamp,
    QgsLineSymbol,
    QgsMarkerSymbol,
    QgsRendererCategory,
    QgsRendererRange,
    QgsSimpleLineSymbolLayer,
    QgsSimpleMarkerSymbolLayer,
    QgsSymbol,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor


def apply_altitude_renderer(
    layer,
    field: str = "rel_altitude",
    num_classes: int = 7,
):
    """
    Apply a graduated color ramp renderer based on altitude.

    Colors range from blue (low) through green/yellow to red (high).
    """
    # Get min/max from the layer
    idx = layer.fields().indexFromName(field)
    if idx < 0:
        return

    min_val = layer.minimumValue(idx)
    max_val = layer.maximumValue(idx)

    if min_val is None or max_val is None:
        return

    min_val = float(min_val)
    max_val = float(max_val)

    if min_val == max_val:
        max_val = min_val + 1.0

    # Blue -> Cyan -> Green -> Yellow -> Red
    color_ramp = QgsGradientColorRamp(
        QColor(0, 0, 255),    # blue (low)
        QColor(255, 0, 0),    # red (high)
    )
    # Add intermediate stops
    color_ramp.setStops([
        QgsGradientColorRamp.StopInfo(0.25, QColor(0, 200, 255)),   # cyan
        QgsGradientColorRamp.StopInfo(0.5, QColor(0, 200, 0)),      # green
        QgsGradientColorRamp.StopInfo(0.75, QColor(255, 200, 0)),   # yellow
    ])

    # Create ranges
    ranges = []
    step = (max_val - min_val) / num_classes

    for i in range(num_classes):
        lower = min_val + i * step
        upper = min_val + (i + 1) * step
        fraction = (i + 0.5) / num_classes
        color = color_ramp.color(fraction)

        symbol = QgsMarkerSymbol.createSimple({
            "name": "circle",
            "size": "3",
            "outline_color": "black",
            "outline_width": "0.4",
        })
        symbol.setColor(color)

        label = f"{lower:.1f} - {upper:.1f}"
        range_item = QgsRendererRange(lower, upper, symbol, label)
        ranges.append(range_item)

    renderer = QgsGraduatedSymbolRenderer(field, ranges)
    layer.setRenderer(renderer)
    layer.triggerRepaint()


def apply_rtk_renderer(layer):
    """
    Apply a categorized renderer based on RTK flag status.

    - Fixed (50): Green circle
    - Float (16): Yellow/orange triangle
    - None (0): Red diamond
    - Unknown: Gray square
    """
    categories = []

    # RTK Fixed = Green circle
    fixed_symbol = QgsMarkerSymbol.createSimple({
        "name": "circle",
        "size": "3.5",
        "outline_color": "black",
        "outline_width": "0.4",
    })
    fixed_symbol.setColor(QColor(46, 204, 113))
    categories.append(QgsRendererCategory(50, fixed_symbol, "RTK Fixed"))

    # RTK Float = Yellow/orange triangle
    float_symbol = QgsMarkerSymbol.createSimple({
        "name": "triangle",
        "size": "3.5",
        "outline_color": "black",
        "outline_width": "0.4",
    })
    float_symbol.setColor(QColor(241, 196, 15))
    categories.append(QgsRendererCategory(16, float_symbol, "RTK Float"))

    # No RTK = Red diamond
    none_symbol = QgsMarkerSymbol.createSimple({
        "name": "diamond",
        "size": "3.5",
        "outline_color": "black",
        "outline_width": "0.4",
    })
    none_symbol.setColor(QColor(231, 76, 60))
    categories.append(QgsRendererCategory(0, none_symbol, "No RTK"))

    # Unknown = Gray square
    unknown_symbol = QgsMarkerSymbol.createSimple({
        "name": "square",
        "size": "3",
        "outline_color": "black",
        "outline_width": "0.4",
    })
    unknown_symbol.setColor(QColor(149, 165, 166))
    categories.append(QgsRendererCategory(None, unknown_symbol, "Unknown"))

    renderer = QgsCategorizedSymbolRenderer("rtk_flag", categories)
    layer.setRenderer(renderer)
    layer.triggerRepaint()


def apply_single_color_renderer(layer, color: QColor = None):
    """Apply a simple single-color marker renderer."""
    if color is None:
        color = QColor(52, 152, 219)  # Blue

    symbol = QgsMarkerSymbol.createSimple({
        "name": "circle",
        "size": "3",
        "outline_color": "black",
        "outline_width": "0.4",
    })
    symbol.setColor(color)
    layer.renderer().setSymbol(symbol)
    layer.triggerRepaint()


def apply_flight_path_style(layer):
    """Style the flight path line layer with dashed blue line and arrows."""
    symbol = QgsLineSymbol.createSimple({
        "color": "#3388ff",
        "width": "0.8",
        "line_style": "dash",
        "capstyle": "round",
        "joinstyle": "round",
    })
    layer.renderer().setSymbol(symbol)
    layer.triggerRepaint()

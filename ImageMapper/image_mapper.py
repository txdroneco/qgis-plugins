# -*- coding: utf-8 -*-
"""
ImageMapper - Main plugin class.

Manages the plugin lifecycle, toolbar actions, and coordinates
between the dialog, layer builder, symbology, and map tools.
"""

import os

from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import QMessageBox

from qgis.core import QgsProject

from .image_mapper_dialog import ImageMapperDialog
from .layer_builder import add_layers_to_project, build_layers
from .map_tool import ImagePreviewMapTool
from .symbology import (
    apply_altitude_renderer,
    apply_flight_path_style,
    apply_rtk_renderer,
    apply_single_color_renderer,
)


class ImageMapper:
    """QGIS Plugin: Plot DJI drone image locations on a map."""

    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.actions = []
        self.menu_name = "&ImageMapper"
        self.toolbar = None
        self.preview_tool = None
        self.preview_action = None
        self.point_layer = None

    def initGui(self):
        """Called when the plugin is loaded. Set up UI elements."""
        self.toolbar = self.iface.addToolBar("ImageMapper")
        self.toolbar.setObjectName("ImageMapperToolbar")

        # Main action: open dialog
        icon_path = os.path.join(self.plugin_dir, "icon.svg")
        run_action = QAction(
            QIcon(icon_path),
            "Plot Drone Images",
            self.iface.mainWindow(),
        )
        run_action.triggered.connect(self.run)
        run_action.setStatusTip("Plot drone image locations from EXIF/XMP metadata")

        self.toolbar.addAction(run_action)
        self.iface.addPluginToRasterMenu(self.menu_name, run_action)
        self.actions.append(run_action)

        # Preview toggle action
        self.preview_action = QAction(
            QIcon.fromTheme("camera-photo"),
            "Toggle Image Preview Tool",
            self.iface.mainWindow(),
        )
        self.preview_action.setCheckable(True)
        self.preview_action.setEnabled(False)
        self.preview_action.toggled.connect(self._toggle_preview_tool)
        self.preview_action.setStatusTip(
            "Click map points to preview drone images"
        )

        self.toolbar.addAction(self.preview_action)
        self.iface.addPluginToRasterMenu(self.menu_name, self.preview_action)
        self.actions.append(self.preview_action)

    def unload(self):
        """Called when the plugin is unloaded. Clean up UI elements."""
        for action in self.actions:
            self.iface.removePluginRasterMenu(self.menu_name, action)
            self.iface.removeToolBarIcon(action)

        if self.toolbar:
            del self.toolbar

        if self.preview_tool:
            self.preview_tool = None

        self.actions = []

    def run(self):
        """Open the dialog and process images."""
        dialog = ImageMapperDialog(self.iface.mainWindow())

        if dialog.exec() != ImageMapperDialog.DialogCode.Accepted:
            return

        results = dialog.scan_results
        if not results:
            return

        # Build layers
        point_layer, line_layer = build_layers(
            image_metadata_list=results,
            point_layer_name=dialog.point_name_edit.text().strip() or "Drone Images",
            line_layer_name=dialog.line_name_edit.text().strip() or "Flight Path",
            gap_threshold_seconds=dialog.gap_threshold,
            create_flight_path=dialog.create_flight_path,
        )

        # Apply symbology
        mode = dialog.colorization_mode
        if mode == "altitude":
            apply_altitude_renderer(
                point_layer,
                field=dialog.altitude_field,
                num_classes=dialog.num_classes,
            )
        elif mode == "rtk":
            apply_rtk_renderer(point_layer)
        else:
            apply_single_color_renderer(point_layer)

        if line_layer:
            apply_flight_path_style(line_layer)

        # Add to project
        add_layers_to_project(point_layer, line_layer)
        self.point_layer = point_layer

        # Zoom to extent
        canvas = self.iface.mapCanvas()
        extent = point_layer.extent()
        extent.grow(extent.width() * 0.1 or 0.001)
        canvas.setExtent(extent)
        canvas.refresh()

        # Enable preview tool
        if dialog.enable_preview:
            self.preview_action.setEnabled(True)
            self.preview_tool = ImagePreviewMapTool(canvas, point_layer)

        # Status message
        msg = f"Plotted {point_layer.featureCount()} images"
        if line_layer:
            msg += f" with {line_layer.featureCount()} flight path segment(s)"
        self.iface.messageBar().pushSuccess("ImageMapper", msg)

    def _toggle_preview_tool(self, checked: bool):
        """Toggle the image preview map tool on/off."""
        if checked and self.preview_tool:
            self.iface.mapCanvas().setMapTool(self.preview_tool)
        else:
            self.iface.mapCanvas().unsetMapTool(self.preview_tool)

# -*- coding: utf-8 -*-
"""
Custom map tool for click-to-preview on drone image points.
"""

from qgis.core import QgsFeature, QgsVectorLayer
from qgis.gui import QgsMapCanvas, QgsMapToolIdentifyFeature

from .thumbnail_dialog import ThumbnailDialog


class ImagePreviewMapTool(QgsMapToolIdentifyFeature):
    """Map tool that opens a thumbnail preview when clicking an image point."""

    def __init__(self, canvas: QgsMapCanvas, layer: QgsVectorLayer):
        super().__init__(canvas, layer)
        self._layer = layer
        self._dialog = None
        self.featureIdentified.connect(self._on_feature_identified)

    def _on_feature_identified(self, feature: QgsFeature):
        """Handle identified feature by opening thumbnail dialog."""
        filepath = feature.attribute("filepath")
        if not filepath:
            return

        # Collect attributes into a dict for the dialog
        attrs = {}
        for field in feature.fields():
            name = field.name()
            val = feature.attribute(name)
            if val is not None:
                attrs[name] = val

        # Close previous dialog if open
        if self._dialog and self._dialog.isVisible():
            self._dialog.close()

        self._dialog = ThumbnailDialog(
            filepath=filepath,
            attributes=attrs,
            parent=self.canvas().window(),
        )
        self._dialog.show()

    def update_layer(self, layer: QgsVectorLayer):
        """Update the target layer for identification."""
        self._layer = layer
        self.setLayer(layer)

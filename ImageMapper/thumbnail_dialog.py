# -*- coding: utf-8 -*-
"""
Thumbnail preview dialog for viewing drone images and metadata.
"""

import os

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
)


class ThumbnailDialog(QDialog):
    """Dialog showing a thumbnail preview and key metadata for a drone image."""

    MAX_THUMBNAIL_SIZE = 800

    def __init__(self, filepath: str, attributes: dict = None, parent=None):
        super().__init__(parent)

        self.filepath = filepath
        self.attributes = attributes or {}

        self.setWindowTitle(os.path.basename(filepath))
        self.setMinimumSize(500, 400)
        self.resize(700, 550)

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Image area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        pixmap = QPixmap(self.filepath)
        if not pixmap.isNull():
            scaled = pixmap.scaled(
                self.MAX_THUMBNAIL_SIZE,
                self.MAX_THUMBNAIL_SIZE,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.image_label.setPixmap(scaled)
        else:
            self.image_label.setText("Unable to load image")

        scroll.setWidget(self.image_label)
        layout.addWidget(scroll, stretch=3)

        # Metadata panel
        info_text = self._format_metadata()
        self.info_label = QLabel(info_text)
        self.info_label.setWordWrap(True)
        self.info_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.info_label.setStyleSheet(
            "QLabel { background-color: #f0f0f0; padding: 8px; "
            "border-radius: 4px; font-family: monospace; font-size: 11px; }"
        )
        layout.addWidget(self.info_label, stretch=1)

    def _format_metadata(self) -> str:
        """Format attribute dictionary into a readable metadata string."""
        lines = []
        attr = self.attributes

        if attr.get("filename"):
            lines.append(f"<b>File:</b> {attr['filename']}")

        if attr.get("timestamp"):
            lines.append(f"<b>Time:</b> {attr['timestamp']}")

        alt_parts = []
        if attr.get("abs_altitude") is not None:
            alt_parts.append(f"Abs: {attr['abs_altitude']:.1f}m")
        if attr.get("rel_altitude") is not None:
            alt_parts.append(f"Rel: {attr['rel_altitude']:.1f}m")
        if alt_parts:
            lines.append(f"<b>Altitude:</b> {' | '.join(alt_parts)}")

        if attr.get("rtk_status"):
            rtk_line = f"<b>RTK:</b> {attr['rtk_status']}"
            if attr.get("rtk_flag") is not None:
                rtk_line += f" (flag={attr['rtk_flag']})"
            lines.append(rtk_line)

        gimbal_parts = []
        for axis in ("gimbal_pitch", "gimbal_yaw", "gimbal_roll"):
            val = attr.get(axis)
            if val is not None:
                label = axis.replace("gimbal_", "").capitalize()
                gimbal_parts.append(f"{label}: {val:.1f}")
        if gimbal_parts:
            lines.append(f"<b>Gimbal:</b> {' | '.join(gimbal_parts)}")

        if attr.get("camera_model"):
            camera = attr.get("camera_make", "")
            if camera:
                camera += " "
            camera += attr["camera_model"]
            lines.append(f"<b>Camera:</b> {camera}")

        return "<br>".join(lines) if lines else "No metadata available"

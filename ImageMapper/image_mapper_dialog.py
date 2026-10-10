# -*- coding: utf-8 -*-
"""
Main dialog for ImageMapper plugin configuration and execution.
"""

import os

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
)

from qgis.core import QgsApplication, QgsTask

from .metadata_reader import scan_folder


class ScanTask(QgsTask):
    """Background task for scanning image folders."""

    def __init__(self, folder: str, recursive: bool):
        super().__init__("Scanning drone images", QgsTask.Flag.CanCancel)
        self.folder = folder
        self.recursive = recursive
        self.results = []
        self.error_msg = ""
        self.total_found = 0

    def run(self):
        try:
            # Count files first for progress
            import glob as _glob
            extensions = (
                "*.jpg", "*.jpeg", "*.tif", "*.tiff", "*.dng",
                "*.JPG", "*.JPEG", "*.TIF", "*.TIFF", "*.DNG",
            )
            all_files = []
            for ext in extensions:
                if self.recursive:
                    pattern = os.path.join(self.folder, "**", ext)
                    all_files.extend(_glob.glob(pattern, recursive=True))
                else:
                    pattern = os.path.join(self.folder, ext)
                    all_files.extend(_glob.glob(pattern))

            all_files = sorted(set(all_files))
            self.total_found = len(all_files)

            if self.total_found == 0:
                return True

            from .metadata_reader import read_image_metadata
            from datetime import datetime

            for i, filepath in enumerate(all_files):
                if self.isCanceled():
                    return False

                meta = read_image_metadata(filepath)
                if meta and meta.has_valid_coords:
                    self.results.append(meta)

                self.setProgress((i + 1) / self.total_found * 100)

            # Sort by timestamp
            self.results.sort(key=lambda m: m.timestamp or datetime.max)
            return True

        except Exception as e:
            self.error_msg = str(e)
            return False

    def cancel(self):
        super().cancel()


class ImageMapperDialog(QDialog):
    """Main configuration dialog for the ImageMapper plugin."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ImageMapper - Drone Image Plotter")
        self.setMinimumWidth(500)
        self.scan_task = None
        self.scan_results = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # --- Folder selection ---
        folder_group = QGroupBox("Image Folder")
        folder_layout = QVBoxLayout(folder_group)

        row = QHBoxLayout()
        self.folder_edit = QLineEdit()
        self.folder_edit.setPlaceholderText("Select folder containing drone images...")
        row.addWidget(self.folder_edit)

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_folder)
        row.addWidget(browse_btn)
        folder_layout.addLayout(row)

        self.recursive_check = QCheckBox("Include subfolders")
        folder_layout.addWidget(self.recursive_check)

        layout.addWidget(folder_group)

        # --- Layer names ---
        names_group = QGroupBox("Layer Names")
        names_layout = QVBoxLayout(names_group)

        row = QHBoxLayout()
        row.addWidget(QLabel("Points:"))
        self.point_name_edit = QLineEdit("Drone Images")
        row.addWidget(self.point_name_edit)
        names_layout.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("Flight Path:"))
        self.line_name_edit = QLineEdit("Flight Path")
        row.addWidget(self.line_name_edit)
        names_layout.addLayout(row)

        layout.addWidget(names_group)

        # --- Colorization ---
        color_group = QGroupBox("Colorization")
        color_layout = QVBoxLayout(color_group)

        self.color_button_group = QButtonGroup(self)
        self.radio_altitude = QRadioButton("Altitude Gradient")
        self.radio_rtk = QRadioButton("RTK Status Categories")
        self.radio_single = QRadioButton("Single Color")
        self.radio_altitude.setChecked(True)

        self.color_button_group.addButton(self.radio_altitude, 0)
        self.color_button_group.addButton(self.radio_rtk, 1)
        self.color_button_group.addButton(self.radio_single, 2)

        color_layout.addWidget(self.radio_altitude)

        # Altitude options
        alt_row = QHBoxLayout()
        alt_row.addSpacing(24)
        alt_row.addWidget(QLabel("Field:"))
        self.altitude_field_combo = QComboBox()
        self.altitude_field_combo.addItems(["rel_altitude", "abs_altitude"])
        alt_row.addWidget(self.altitude_field_combo)
        alt_row.addWidget(QLabel("Classes:"))
        self.num_classes_spin = QSpinBox()
        self.num_classes_spin.setRange(3, 20)
        self.num_classes_spin.setValue(7)
        alt_row.addWidget(self.num_classes_spin)
        alt_row.addStretch()
        color_layout.addLayout(alt_row)

        color_layout.addWidget(self.radio_rtk)
        color_layout.addWidget(self.radio_single)

        layout.addWidget(color_group)

        # --- Flight path options ---
        path_group = QGroupBox("Flight Path")
        path_layout = QVBoxLayout(path_group)

        self.flight_path_check = QCheckBox("Generate flight path lines")
        self.flight_path_check.setChecked(True)
        path_layout.addWidget(self.flight_path_check)

        gap_row = QHBoxLayout()
        gap_row.addSpacing(24)
        gap_row.addWidget(QLabel("Gap threshold (seconds):"))
        self.gap_spin = QSpinBox()
        self.gap_spin.setRange(5, 300)
        self.gap_spin.setValue(30)
        gap_row.addWidget(self.gap_spin)
        gap_row.addStretch()
        path_layout.addLayout(gap_row)

        layout.addWidget(path_group)

        # --- Preview option ---
        self.preview_check = QCheckBox("Enable click-to-preview (thumbnail popup)")
        self.preview_check.setChecked(True)
        layout.addWidget(self.preview_check)

        # --- Progress ---
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #666;")
        layout.addWidget(self.status_label)

        # --- Buttons ---
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self._on_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def _browse_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select Drone Image Folder", "",
            QFileDialog.Option.ShowDirsOnly,
        )
        if folder:
            self.folder_edit.setText(folder)

    def _on_accept(self):
        """Start scanning when OK is clicked."""
        folder = self.folder_edit.text().strip()
        if not folder or not os.path.isdir(folder):
            self.status_label.setText("Please select a valid folder.")
            self.status_label.setStyleSheet("color: red;")
            return

        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setText("Scanning images...")
        self.status_label.setStyleSheet("color: #666;")
        self.button_box.setEnabled(False)

        self.scan_task = ScanTask(folder, self.recursive_check.isChecked())
        self.scan_task.progressChanged.connect(self._on_progress)
        self.scan_task.taskCompleted.connect(self._on_scan_complete)
        self.scan_task.taskTerminated.connect(self._on_scan_failed)

        QgsApplication.taskManager().addTask(self.scan_task)

    def _on_progress(self, progress):
        self.progress_bar.setValue(int(progress))

    def _on_scan_complete(self):
        self.scan_results = self.scan_task.results
        count = len(self.scan_results)
        total = self.scan_task.total_found

        self.status_label.setText(
            f"Found {count} geotagged images out of {total} total."
        )
        self.status_label.setStyleSheet("color: green;")
        self.progress_bar.setValue(100)
        self.button_box.setEnabled(True)

        if count > 0:
            self.accept()
        else:
            self.status_label.setText(
                f"No geotagged images found in {total} files. "
                "Ensure images have GPS data."
            )
            self.status_label.setStyleSheet("color: orange;")

    def _on_scan_failed(self):
        self.status_label.setText(
            f"Scan failed: {self.scan_task.error_msg or 'Unknown error'}"
        )
        self.status_label.setStyleSheet("color: red;")
        self.progress_bar.setVisible(False)
        self.button_box.setEnabled(True)

    @property
    def colorization_mode(self) -> str:
        """Return 'altitude', 'rtk', or 'single'."""
        checked_id = self.color_button_group.checkedId()
        return {0: "altitude", 1: "rtk", 2: "single"}.get(checked_id, "altitude")

    @property
    def altitude_field(self) -> str:
        return self.altitude_field_combo.currentText()

    @property
    def num_classes(self) -> int:
        return self.num_classes_spin.value()

    @property
    def create_flight_path(self) -> bool:
        return self.flight_path_check.isChecked()

    @property
    def gap_threshold(self) -> float:
        return float(self.gap_spin.value())

    @property
    def enable_preview(self) -> bool:
        return self.preview_check.isChecked()

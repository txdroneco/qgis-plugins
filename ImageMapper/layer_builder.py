# -*- coding: utf-8 -*-
"""
Creates point and flight path vector layers from image metadata.
"""

from datetime import timedelta

from qgis.core import (
    QgsField,
    QgsFeature,
    QgsGeometry,
    QgsPointXY,
    QgsProject,
    QgsVectorLayer,
)
from PyQt6.QtCore import QVariant


def _create_point_layer(name: str) -> QgsVectorLayer:
    """Create a memory point layer with all attribute fields."""
    layer = QgsVectorLayer("Point?crs=EPSG:4326", name, "memory")
    dp = layer.dataProvider()

    fields = [
        QgsField("filename", QVariant.Type.String),
        QgsField("filepath", QVariant.Type.String),
        QgsField("timestamp", QVariant.Type.DateTime),
        QgsField("abs_altitude", QVariant.Type.Double),
        QgsField("rel_altitude", QVariant.Type.Double),
        QgsField("rtk_flag", QVariant.Type.Int),
        QgsField("rtk_status", QVariant.Type.String),
        QgsField("rtk_std_lon", QVariant.Type.Double),
        QgsField("rtk_std_lat", QVariant.Type.Double),
        QgsField("rtk_std_alt", QVariant.Type.Double),
        QgsField("gimbal_pitch", QVariant.Type.Double),
        QgsField("gimbal_yaw", QVariant.Type.Double),
        QgsField("gimbal_roll", QVariant.Type.Double),
        QgsField("flight_pitch", QVariant.Type.Double),
        QgsField("flight_yaw", QVariant.Type.Double),
        QgsField("flight_roll", QVariant.Type.Double),
        QgsField("camera_make", QVariant.Type.String),
        QgsField("camera_model", QVariant.Type.String),
        QgsField("sort_order", QVariant.Type.Int),
    ]
    dp.addAttributes(fields)
    layer.updateFields()

    return layer


def _create_line_layer(name: str) -> QgsVectorLayer:
    """Create a memory line layer for flight paths."""
    layer = QgsVectorLayer("LineString?crs=EPSG:4326", name, "memory")
    dp = layer.dataProvider()

    fields = [
        QgsField("segment_id", QVariant.Type.Int),
        QgsField("start_time", QVariant.Type.DateTime),
        QgsField("end_time", QVariant.Type.DateTime),
        QgsField("point_count", QVariant.Type.Int),
    ]
    dp.addAttributes(fields)
    layer.updateFields()

    return layer


def build_layers(
    image_metadata_list: list,
    point_layer_name: str = "Drone Images",
    line_layer_name: str = "Flight Path",
    gap_threshold_seconds: float = 30.0,
    create_flight_path: bool = True,
) -> tuple:
    """
    Build point and flight path layers from image metadata.

    Args:
        image_metadata_list: List of ImageMetadata objects, sorted by timestamp.
        point_layer_name: Name for the point layer.
        line_layer_name: Name for the flight path layer.
        gap_threshold_seconds: Max seconds between consecutive images
            before splitting the flight path into a new segment.
        create_flight_path: Whether to create a flight path line layer.

    Returns:
        Tuple of (point_layer, line_layer_or_None).
    """
    # --- Point layer ---
    point_layer = _create_point_layer(point_layer_name)
    dp = point_layer.dataProvider()

    features = []
    for idx, meta in enumerate(image_metadata_list):
        feat = QgsFeature(point_layer.fields())
        feat.setGeometry(QgsGeometry.fromPointXY(
            QgsPointXY(meta.longitude, meta.latitude)
        ))
        feat.setAttribute("filename", meta.filename)
        feat.setAttribute("filepath", meta.filepath)
        if meta.timestamp:
            feat.setAttribute("timestamp", meta.timestamp.isoformat())
        feat.setAttribute("abs_altitude", meta.abs_altitude)
        feat.setAttribute("rel_altitude", meta.rel_altitude)
        feat.setAttribute("rtk_flag", meta.rtk_flag)
        feat.setAttribute("rtk_status", meta.rtk_status)
        feat.setAttribute("rtk_std_lon", meta.rtk_std_lon)
        feat.setAttribute("rtk_std_lat", meta.rtk_std_lat)
        feat.setAttribute("rtk_std_alt", meta.rtk_std_alt)
        feat.setAttribute("gimbal_pitch", meta.gimbal_pitch)
        feat.setAttribute("gimbal_yaw", meta.gimbal_yaw)
        feat.setAttribute("gimbal_roll", meta.gimbal_roll)
        feat.setAttribute("flight_pitch", meta.flight_pitch)
        feat.setAttribute("flight_yaw", meta.flight_yaw)
        feat.setAttribute("flight_roll", meta.flight_roll)
        feat.setAttribute("camera_make", meta.camera_make)
        feat.setAttribute("camera_model", meta.camera_model)
        feat.setAttribute("sort_order", idx)
        features.append(feat)

    dp.addFeatures(features)
    point_layer.updateExtents()

    # --- Flight path layer ---
    line_layer = None
    if create_flight_path and len(image_metadata_list) >= 2:
        line_layer = _create_line_layer(line_layer_name)
        line_dp = line_layer.dataProvider()

        # Build segments, splitting at time gaps
        segments = []
        current_segment = [image_metadata_list[0]]
        threshold = timedelta(seconds=gap_threshold_seconds)

        for i in range(1, len(image_metadata_list)):
            prev = image_metadata_list[i - 1]
            curr = image_metadata_list[i]

            if prev.timestamp and curr.timestamp:
                gap = curr.timestamp - prev.timestamp
                if gap > threshold:
                    segments.append(current_segment)
                    current_segment = [curr]
                    continue

            current_segment.append(curr)

        segments.append(current_segment)

        # Create line features for each segment
        line_features = []
        for seg_idx, segment in enumerate(segments):
            if len(segment) < 2:
                continue

            points = [
                QgsPointXY(m.longitude, m.latitude) for m in segment
            ]
            feat = QgsFeature(line_layer.fields())
            feat.setGeometry(QgsGeometry.fromPolylineXY(points))
            feat.setAttribute("segment_id", seg_idx + 1)
            if segment[0].timestamp:
                feat.setAttribute("start_time", segment[0].timestamp.isoformat())
            if segment[-1].timestamp:
                feat.setAttribute("end_time", segment[-1].timestamp.isoformat())
            feat.setAttribute("point_count", len(segment))
            line_features.append(feat)

        if line_features:
            line_dp.addFeatures(line_features)
            line_layer.updateExtents()
        else:
            line_layer = None

    return point_layer, line_layer


def add_layers_to_project(point_layer, line_layer=None):
    """Add layers to the QGIS project, with flight path below points."""
    project = QgsProject.instance()

    if line_layer:
        project.addMapLayer(line_layer)
    project.addMapLayer(point_layer)

# -*- coding: utf-8 -*-
"""
EXIF/XMP metadata extraction for DJI drone images.
Uses GDAL (always available in QGIS) with fallback to raw XMP parsing.
"""

import os
import re
import glob
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from xml.etree import ElementTree

from osgeo import gdal

# Suppress GDAL error messages for non-image files
gdal.UseExceptions()

DJI_NS = "http://www.dji.com/drone-dji/1.0/"
RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"

IMAGE_EXTENSIONS = (
    "*.jpg", "*.jpeg", "*.tif", "*.tiff", "*.dng",
    "*.JPG", "*.JPEG", "*.TIF", "*.TIFF", "*.DNG",
)

RTK_STATUS_MAP = {
    0: "None",
    16: "Float",
    50: "Fixed",
}


@dataclass
class ImageMetadata:
    filepath: str = ""
    filename: str = ""
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    abs_altitude: Optional[float] = None
    rel_altitude: Optional[float] = None
    rtk_flag: Optional[int] = None
    rtk_std_lon: Optional[float] = None
    rtk_std_lat: Optional[float] = None
    rtk_std_alt: Optional[float] = None
    timestamp: Optional[datetime] = None
    gimbal_pitch: Optional[float] = None
    gimbal_yaw: Optional[float] = None
    gimbal_roll: Optional[float] = None
    flight_pitch: Optional[float] = None
    flight_yaw: Optional[float] = None
    flight_roll: Optional[float] = None
    camera_make: Optional[str] = None
    camera_model: Optional[str] = None

    @property
    def has_valid_coords(self) -> bool:
        return self.latitude is not None and self.longitude is not None

    @property
    def rtk_status(self) -> str:
        if self.rtk_flag is None:
            return "Unknown"
        return RTK_STATUS_MAP.get(self.rtk_flag, f"Code {self.rtk_flag}")


def _safe_float(value: str) -> Optional[float]:
    """Safely convert a string to float."""
    if value is None:
        return None
    try:
        # Handle DJI format: sometimes prefixed with +/-
        return float(value.strip().lstrip("+"))
    except (ValueError, AttributeError):
        return None


def _safe_int(value: str) -> Optional[int]:
    """Safely convert a string to int."""
    if value is None:
        return None
    try:
        return int(float(value.strip()))
    except (ValueError, AttributeError):
        return None


def _parse_exif_gps_coord(coord_str: str, ref_str: str) -> Optional[float]:
    """Parse EXIF GPS coordinate from DMS string like '(32) (51) (12.345)'."""
    if not coord_str:
        return None
    try:
        # GDAL returns EXIF GPS as "(deg) (min) (sec)"
        parts = re.findall(r"\(([\d.]+)\)", coord_str)
        if len(parts) == 3:
            deg = float(parts[0])
            minutes = float(parts[1])
            sec = float(parts[2])
            decimal = deg + minutes / 60.0 + sec / 3600.0
            if ref_str and ref_str.strip() in ("S", "W"):
                decimal = -decimal
            return decimal
    except (ValueError, IndexError):
        pass
    return None


def _parse_exif_timestamp(date_str: str) -> Optional[datetime]:
    """Parse EXIF DateTimeOriginal format: '2024:01:15 14:30:00'."""
    if not date_str:
        return None
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    return None


def _extract_xmp_from_bytes(filepath: str) -> Optional[str]:
    """Fallback: extract XMP XML directly from file bytes."""
    try:
        with open(filepath, "rb") as f:
            data = f.read()
        start_marker = b"<x:xmpmeta"
        end_marker = b"</x:xmpmeta>"
        start = data.find(start_marker)
        if start == -1:
            return None
        end = data.find(end_marker, start)
        if end == -1:
            return None
        return data[start : end + len(end_marker)].decode("utf-8", errors="replace")
    except (IOError, OSError):
        return None


def _parse_dji_xmp(xmp_xml: str) -> dict:
    """Parse DJI-specific fields from XMP XML."""
    result = {}
    if not xmp_xml:
        return result

    try:
        root = ElementTree.fromstring(xmp_xml)
    except ElementTree.ParseError:
        return result

    # Search all rdf:Description elements for DJI namespace attributes
    for desc in root.iter():
        for attr_name, attr_value in desc.attrib.items():
            # Match attributes like {http://www.dji.com/drone-dji/1.0/}AbsoluteAltitude
            # or plain drone-dji:AbsoluteAltitude
            if DJI_NS in attr_name:
                key = attr_name.replace(f"{{{DJI_NS}}}", "")
                result[key] = attr_value
            elif attr_name.startswith("drone-dji:"):
                key = attr_name.replace("drone-dji:", "")
                result[key] = attr_value

    return result


def read_image_metadata(filepath: str) -> Optional[ImageMetadata]:
    """
    Read EXIF and DJI XMP metadata from an image file.

    Returns ImageMetadata if readable, None if the file cannot be opened.
    """
    meta = ImageMetadata(
        filepath=filepath,
        filename=os.path.basename(filepath),
    )

    try:
        ds = gdal.Open(filepath, gdal.GA_ReadOnly)
    except Exception:
        return None

    if ds is None:
        return None

    # --- Read standard EXIF ---
    exif = ds.GetMetadata("EXIF") or {}

    # GPS from EXIF
    exif_lat = _parse_exif_gps_coord(
        exif.get("EXIF_GPSLatitude", ""),
        exif.get("EXIF_GPSLatitudeRef", ""),
    )
    exif_lon = _parse_exif_gps_coord(
        exif.get("EXIF_GPSLongitude", ""),
        exif.get("EXIF_GPSLongitudeRef", ""),
    )
    exif_alt = _safe_float(exif.get("EXIF_GPSAltitude", ""))

    # Timestamp
    meta.timestamp = _parse_exif_timestamp(
        exif.get("EXIF_DateTimeOriginal", exif.get("EXIF_DateTime", ""))
    )

    # Camera info
    meta.camera_make = exif.get("EXIF_Make", "").strip() or None
    meta.camera_model = exif.get("EXIF_Model", "").strip() or None

    # --- Read DJI XMP metadata ---
    xmp_xml = None
    xmp_list = ds.GetMetadata("xml:XMP")
    if xmp_list:
        xmp_xml = xmp_list[0] if isinstance(xmp_list, (list, tuple)) else xmp_list

    # Fallback to raw byte extraction
    if not xmp_xml:
        xmp_xml = _extract_xmp_from_bytes(filepath)

    dji = _parse_dji_xmp(xmp_xml)

    # Close GDAL dataset
    ds = None

    # --- Populate DJI fields ---
    meta.abs_altitude = _safe_float(dji.get("AbsoluteAltitude"))
    meta.rel_altitude = _safe_float(dji.get("RelativeAltitude"))
    meta.rtk_flag = _safe_int(dji.get("RtkFlag"))
    meta.rtk_std_lon = _safe_float(dji.get("RtkStdLon"))
    meta.rtk_std_lat = _safe_float(dji.get("RtkStdLat"))
    meta.rtk_std_alt = _safe_float(dji.get("RtkStdHgt"))

    # Gimbal angles
    meta.gimbal_pitch = _safe_float(dji.get("GimbalPitchDegree"))
    meta.gimbal_yaw = _safe_float(dji.get("GimbalYawDegree"))
    meta.gimbal_roll = _safe_float(dji.get("GimbalRollDegree"))

    # Flight angles
    meta.flight_pitch = _safe_float(dji.get("FlightPitchDegree"))
    meta.flight_yaw = _safe_float(dji.get("FlightYawDegree"))
    meta.flight_roll = _safe_float(dji.get("FlightRollDegree"))

    # --- Resolve coordinates (DJI XMP > EXIF GPS) ---
    dji_lat = _safe_float(dji.get("GpsLatitude"))
    dji_lon = _safe_float(dji.get("GpsLongitude"))

    if dji_lat is not None and dji_lon is not None:
        meta.latitude = dji_lat
        meta.longitude = dji_lon
    elif exif_lat is not None and exif_lon is not None:
        meta.latitude = exif_lat
        meta.longitude = exif_lon

    # Use EXIF altitude as fallback for absolute altitude
    if meta.abs_altitude is None and exif_alt is not None:
        meta.abs_altitude = exif_alt

    return meta


def scan_folder(folder: str, recursive: bool = False) -> list:
    """
    Scan a folder for image files and extract metadata.

    Returns a list of ImageMetadata sorted by timestamp,
    filtered to only images with valid GPS coordinates.
    """
    image_files = []
    for ext in IMAGE_EXTENSIONS:
        if recursive:
            pattern = os.path.join(folder, "**", ext)
            image_files.extend(glob.glob(pattern, recursive=True))
        else:
            pattern = os.path.join(folder, ext)
            image_files.extend(glob.glob(pattern))

    # Deduplicate (case-insensitive patterns may overlap)
    image_files = sorted(set(image_files))

    results = []
    for filepath in image_files:
        meta = read_image_metadata(filepath)
        if meta and meta.has_valid_coords:
            results.append(meta)

    # Sort by timestamp (images without timestamp go to the end)
    results.sort(key=lambda m: m.timestamp or datetime.max)

    return results

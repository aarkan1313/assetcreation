"""Inspect LAS/LAZ headers without decompressing point data.

This does not read points, but it tells us the point format, standard dimensions,
RGB capability, scales, bounds, and point count from the public LAS header.
"""
from __future__ import annotations

import json
import struct
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POINT_ROOT = ROOT / "opentopo" / "raw" / "pointcloud"


POINT_FORMAT_DIMENSIONS = {
    0: ["X", "Y", "Z", "intensity", "return_number", "classification", "scan_angle", "user_data", "point_source_id"],
    1: ["X", "Y", "Z", "intensity", "return_number", "classification", "scan_angle", "user_data", "point_source_id", "gps_time"],
    2: ["X", "Y", "Z", "intensity", "return_number", "classification", "scan_angle", "user_data", "point_source_id", "red", "green", "blue"],
    3: ["X", "Y", "Z", "intensity", "return_number", "classification", "scan_angle", "user_data", "point_source_id", "gps_time", "red", "green", "blue"],
    4: ["X", "Y", "Z", "intensity", "return_number", "classification", "scan_angle", "user_data", "point_source_id", "gps_time", "wave_packet"],
    5: ["X", "Y", "Z", "intensity", "return_number", "classification", "scan_angle", "user_data", "point_source_id", "gps_time", "red", "green", "blue", "wave_packet"],
    6: ["X", "Y", "Z", "intensity", "return_number", "classification", "scan_angle", "user_data", "point_source_id", "gps_time", "scanner_channel"],
    7: ["X", "Y", "Z", "intensity", "return_number", "classification", "scan_angle", "user_data", "point_source_id", "gps_time", "scanner_channel", "red", "green", "blue"],
    8: ["X", "Y", "Z", "intensity", "return_number", "classification", "scan_angle", "user_data", "point_source_id", "gps_time", "scanner_channel", "red", "green", "blue", "nir"],
    9: ["X", "Y", "Z", "intensity", "return_number", "classification", "scan_angle", "user_data", "point_source_id", "gps_time", "scanner_channel", "wave_packet"],
    10: ["X", "Y", "Z", "intensity", "return_number", "classification", "scan_angle", "user_data", "point_source_id", "gps_time", "scanner_channel", "red", "green", "blue", "nir", "wave_packet"],
}


def clean_ascii(raw: bytes) -> str:
    return raw.split(b"\x00", 1)[0].decode("ascii", errors="replace").strip()


def inspect(path: Path) -> dict:
    data = path.read_bytes()[:4096]
    if data[:4] != b"LASF":
        raise ValueError(f"{path} is not a LAS/LAZ file")

    version_major = data[24]
    version_minor = data[25]
    system_identifier = clean_ascii(data[26:58])
    generating_software = clean_ascii(data[58:90])
    creation_day, creation_year = struct.unpack_from("<HH", data, 90)
    header_size = struct.unpack_from("<H", data, 94)[0]
    offset_to_point_data = struct.unpack_from("<I", data, 96)[0]
    vlr_count = struct.unpack_from("<I", data, 100)[0]
    point_format_raw = data[104]
    point_format = point_format_raw & 0x3F
    compressed = bool(point_format_raw & 0x80)
    point_record_length = struct.unpack_from("<H", data, 105)[0]
    legacy_point_count = struct.unpack_from("<I", data, 107)[0]
    legacy_by_return = list(struct.unpack_from("<5I", data, 111))
    scale_x, scale_y, scale_z = struct.unpack_from("<3d", data, 131)
    offset_x, offset_y, offset_z = struct.unpack_from("<3d", data, 155)
    max_x, min_x, max_y, min_y, max_z, min_z = struct.unpack_from("<6d", data, 179)

    point_count = legacy_point_count
    by_return = legacy_by_return
    if version_major == 1 and version_minor >= 4 and len(data) >= 375:
        point_count_14 = struct.unpack_from("<Q", data, 247)[0]
        if point_count_14:
            point_count = point_count_14
            by_return = list(struct.unpack_from("<15Q", data, 255))

    vlrs = []
    pos = header_size
    full_header = path.read_bytes()[:offset_to_point_data]
    for _ in range(vlr_count):
        if pos + 54 > len(full_header):
            break
        reserved, user_id_raw, record_id, length_after_header, desc_raw = struct.unpack_from("<H16sHH32s", full_header, pos)
        pos += 54
        user_id = clean_ascii(user_id_raw)
        description = clean_ascii(desc_raw)
        vlrs.append({
            "user_id": user_id,
            "record_id": record_id,
            "length": length_after_header,
            "description": description,
        })
        pos += length_after_header

    dims = POINT_FORMAT_DIMENSIONS.get(point_format, [])
    return {
        "path": str(path),
        "bytes": path.stat().st_size,
        "version": f"{version_major}.{version_minor}",
        "system_identifier": system_identifier,
        "generating_software": generating_software,
        "creation_day": creation_day,
        "creation_year": creation_year,
        "header_size": header_size,
        "offset_to_point_data": offset_to_point_data,
        "vlr_count": vlr_count,
        "point_format_raw": point_format_raw,
        "point_format": point_format,
        "compressed_laz": compressed,
        "point_record_length": point_record_length,
        "point_count": point_count,
        "points_by_return": by_return,
        "scale": {"x": scale_x, "y": scale_y, "z": scale_z},
        "offset": {"x": offset_x, "y": offset_y, "z": offset_z},
        "bounds": {"min_x": min_x, "max_x": max_x, "min_y": min_y, "max_y": max_y, "min_z": min_z, "max_z": max_z},
        "standard_dimensions": dims,
        "has_rgb": all(d in dims for d in ["red", "green", "blue"]),
        "has_nir": "nir" in dims,
        "has_gps_time": "gps_time" in dims,
        "has_classification": "classification" in dims,
        "has_intensity": "intensity" in dims,
        "vlrs": vlrs,
    }


def main() -> int:
    rows = [inspect(path) for path in sorted(POINT_ROOT.rglob("*.laz"))]
    out = ROOT / "opentopo" / "processed" / "comparison" / "laz_headers.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    for row in rows:
        print(f"{Path(row['path']).name}: format={row['point_format']} points={row['point_count']} rgb={row['has_rgb']} class={row['has_classification']} intensity={row['has_intensity']}")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Fresh OpenTopography REST client.
Auth: OPENTOPOGRAPHY_API_KEY env var (User-scope on Windows).
Endpoint: https://portal.opentopography.org/API/globaldem
Datasets: COP30 / SRTMGL1 / AW3D30 / USGS1m / GEBCO."""
from __future__ import annotations
import io
import os
import numpy as np
import requests
from PIL import Image

API_BASE = "https://portal.opentopography.org/API/globaldem"


def build_url(dataset: str, bbox: tuple[float, float, float, float], api_key: str) -> str:
    w, s, e, n = bbox
    return (f"{API_BASE}?demtype={dataset}"
            f"&south={s}&north={n}&west={w}&east={e}"
            f"&outputFormat=GTiff&API_Key={api_key}")


def _parse_geotiff(content: bytes) -> np.ndarray:
    """Parse GeoTIFF bytes to 2D float32 elevation array.
    Uses Pillow's native TIFF reader; OT global DEMs are single-band float."""
    img = Image.open(io.BytesIO(content))
    arr = np.asarray(img, dtype=np.float32)
    if arr.ndim != 2:
        raise ValueError(f"unexpected DEM shape from OT: {arr.shape}")
    return arr


def fetch_dem(dataset: str, bbox: tuple[float, float, float, float],
              api_key: str | None = None, timeout: float = 60.0) -> np.ndarray:
    key = api_key or os.environ.get("OPENTOPOGRAPHY_API_KEY")
    if not key:
        raise RuntimeError(
            "OPENTOPOGRAPHY_API_KEY not set. In PowerShell:\n"
            '  $env:OPENTOPOGRAPHY_API_KEY = '
            '[Environment]::GetEnvironmentVariable("OPENTOPOGRAPHY_API_KEY","User")'
        )
    url = build_url(dataset, bbox, key)
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return _parse_geotiff(resp.content)

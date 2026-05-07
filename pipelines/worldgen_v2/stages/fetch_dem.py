"""Stage 1: fetch a DEM from OpenTopography, resample to quality size,
write 16-bit height_16.png and dem_meta.json into the job output dir."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from PIL import Image
from pipelines.worldgen_v2 import paths, dem_math, ot_client, presets
from pipelines.worldgen_v2.job_schema import Job


def run(job: Job) -> None:
    out = paths.job_output_dir(job.id)
    quality = presets.load_quality(job.quality)

    arr = ot_client.fetch_dem(dataset=job.dem.dataset, bbox=job.dem.bbox)
    arr_resampled = dem_math.resample_to_size(arr, quality.dem_size)
    u16, lo, hi = dem_math.normalize_to_uint16(arr_resampled)

    Image.fromarray(u16, mode="I;16").save(out / "height_16.png")

    span_x_m, span_z_m = dem_math.bbox_span_meters(job.dem.bbox)
    meta = {
        "bbox": list(job.dem.bbox),
        "span_x_m": span_x_m,
        "span_z_m": span_z_m,
        "elev_min_m": lo,
        "elev_max_m": hi,
        "source": f"OT/{job.dem.dataset}",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
    (out / "dem_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"[fetch_dem] wrote {out / 'height_16.png'} ({u16.shape}) elev {lo:.1f}..{hi:.1f}m")

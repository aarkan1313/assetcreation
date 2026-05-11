"""Drive OrchestratorCaptureDriver.gd from the world3 orchestrator.

Writes a JSON capture request to Godot's user:// directory, then invokes the
regular (non-mono) Godot binary with the parameterized capture driver scene.

Used by:
  - world3/jobs/stages.json render_captures_* stages
  - world3_make.py orchestrator (Phase E.3+)

Usage:
  python world3/pipeline/run_orchestrator_capture.py \
      --bundle-dir res://toporeview/procedural_desert_canyon_rock_m10 \
      --material   res://textures/wgv3/terrain_blend_desert.tres \
      --mode iso \
      --output res://docs/captures/review/foo_iso.png \
      [--macro-albedo res://...] [--macro-mask res://...] \
      [--warmup-frames 60] [--viewport-size 1600,1000] \
      [--start-x 60.0] [--start-z 120.0] \
      [--chunk-size 120.0] [--chunk-resolution 4.0]

Exit codes:
  0 success
  1 invalid args or Godot run failed
  2 capture PNG was not produced
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORLD3 = Path(__file__).resolve().parents[1]
GODOT_BIN = Path(r"C:/Godot/Godot_v4.5-stable_win64.exe")
USER_DATA = Path(os.environ["APPDATA"]) / "Godot" / "app_userdata" / "world3"
REQUEST_FILENAME = "orchestrator_capture_request.json"
DRIVER_SCENE = "res://scenes/review/orchestrator_capture_driver.tscn"
STYLE_PACK_DIR = WORLD3 / "jobs" / "style_packs"


def _load_style_pack(name: str) -> dict:
    """Load a style pack JSON. Returns the parsed dict or raises."""
    path = STYLE_PACK_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"style pack not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise ValueError(f"style pack {name} has schema_version != 1")
    if data.get("id") != name:
        raise ValueError(f"style pack file {path.name} declares id={data.get('id')!r}")
    return data


def _parse_pair(value: str, kind: str) -> list[int | float]:
    parts = value.split(",")
    if len(parts) != 2:
        raise argparse.ArgumentTypeError(f"{kind} must be 'a,b', got '{value}'")
    if kind == "viewport":
        return [int(parts[0]), int(parts[1])]
    return [float(parts[0]), float(parts[1])]


def _resolve_log_dir() -> Path:
    log_dir = Path("D:/tmp")
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def _res_to_disk(res_path: str) -> Path:
    if not res_path.startswith("res://"):
        raise ValueError(f"expected res:// path, got '{res_path}'")
    return WORLD3 / res_path[len("res://"):]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    ap.add_argument("--bundle-dir", required=True, help="res:// path to the bundle directory")
    ap.add_argument("--material", required=True, help="res:// path to the terrain_blend .tres")
    ap.add_argument("--mode", required=True, choices=["close", "medium", "iso", "topdown"])
    ap.add_argument("--output", required=True, help="res:// path for the output PNG")
    ap.add_argument("--macro-albedo", default="", help="res:// override (optional)")
    ap.add_argument("--macro-mask", default="", help="res:// override (optional)")
    ap.add_argument("--tour-profile", default="standard")
    ap.add_argument("--warmup-frames", type=int, default=60)
    ap.add_argument("--viewport-size", default="1600,1000",
                    type=lambda v: _parse_pair(v, "viewport"))
    ap.add_argument("--start-x", type=float, default=64.0)
    ap.add_argument("--start-z", type=float, default=128.0)
    ap.add_argument("--chunk-size", type=float, default=256.0)
    ap.add_argument("--chunk-resolution", type=float, default=8.0)
    ap.add_argument("--godot-bin", type=Path, default=GODOT_BIN,
                    help=f"Godot binary path (default {GODOT_BIN})")
    ap.add_argument("--timeout-sec", type=int, default=180)
    ap.add_argument("--style-pack", default="photoreal",
                    help="Style pack id under world3/jobs/style_packs/; default 'photoreal'")
    args = ap.parse_args()

    style_pack = _load_style_pack(args.style_pack)

    if not args.godot_bin.exists():
        print(f"ERROR: Godot binary not found at {args.godot_bin}", file=sys.stderr)
        return 1

    USER_DATA.mkdir(parents=True, exist_ok=True)
    request_path = USER_DATA / REQUEST_FILENAME
    request = {
        "bundle_dir": args.bundle_dir,
        "material": args.material,
        "mode": args.mode,
        "output": args.output,
        "tour_profile": args.tour_profile,
        "warmup_frames": args.warmup_frames,
        "viewport_size": args.viewport_size,
        "start_x_m": args.start_x,
        "start_z_m": args.start_z,
        "chunk_size_m": args.chunk_size,
        "chunk_resolution_m": args.chunk_resolution,
    }
    if args.macro_albedo:
        request["macro_albedo"] = args.macro_albedo
    if args.macro_mask:
        request["macro_mask"] = args.macro_mask

    # Phase E.5: inject style pack render overrides. The driver applies any
    # field present and falls back to the tour's hardcoded defaults otherwise.
    request["style"] = style_pack.get("render", {})
    request["style_pack_id"] = style_pack["id"]
    material_suffix = style_pack.get("material_suffix", "")
    if material_suffix:
        # e.g. "topographic": rewrite res://.../terrain_blend_<kit>_<mode>.tres
        # to res://.../terrain_blend_<kit>_<mode>_<suffix>.tres if such a file exists.
        styled = args.material[: -len(".tres")] + f"_{material_suffix}.tres"
        styled_disk = _res_to_disk(styled)
        if styled_disk.exists():
            request["material"] = styled
        else:
            print(f"WARN: style pack '{style_pack['id']}' requested material_suffix "
                  f"'{material_suffix}' but {styled_disk} does not exist; using base material",
                  file=sys.stderr)

    request_path.write_text(json.dumps(request, indent=2), encoding="utf-8")

    run_id = f"orchestrator_capture_{args.mode}_{uuid.uuid4().hex[:8]}"
    log_path = _resolve_log_dir() / f"{run_id}.log"
    output_disk_path = _res_to_disk(args.output)
    output_disk_path.parent.mkdir(parents=True, exist_ok=True)
    mtime_before = output_disk_path.stat().st_mtime if output_disk_path.exists() else 0.0

    cmd = [
        str(args.godot_bin),
        "--rendering-driver", "opengl3",
        "--path", str(WORLD3),
        "--single-window",
        "--disable-crash-handler",
        "--log-file", str(log_path),
        DRIVER_SCENE,
    ]

    print(f"[run_orchestrator_capture] mode={args.mode} bundle={args.bundle_dir}")
    print(f"[run_orchestrator_capture] log={log_path}")
    t0 = time.time()
    try:
        result = subprocess.run(cmd, timeout=args.timeout_sec, capture_output=True, text=True)
    except subprocess.TimeoutExpired:
        print(f"ERROR: Godot timed out after {args.timeout_sec}s", file=sys.stderr)
        return 1
    elapsed = time.time() - t0
    if result.returncode != 0:
        print(f"ERROR: Godot exit={result.returncode} elapsed={elapsed:.2f}s", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        return 1

    if not output_disk_path.exists() or output_disk_path.stat().st_mtime <= mtime_before:
        print(f"ERROR: capture PNG was not refreshed: {output_disk_path}", file=sys.stderr)
        print(f"       (check log: {log_path})", file=sys.stderr)
        return 2

    size_kb = output_disk_path.stat().st_size / 1024.0
    print(f"[run_orchestrator_capture] OK {output_disk_path} ({size_kb:.0f} KB, {elapsed:.2f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

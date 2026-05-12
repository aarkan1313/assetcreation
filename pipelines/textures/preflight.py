"""Texture pipeline preflight checks.

Verifies that everything `aaa_texture.py` needs is in place BEFORE
queuing any work. Cold-start operators get a clear error per missing
prereq instead of mid-flow "connection refused" surprises.

Added 2026-05-11 (Phase D.4) to close Bucket B gaps surfaced during the
Phase B cold-validation pass:

- B-2: ComfyUI auto-start missing (now: clear error + restart instructions)
- B-4: No preflight check for required model files (now: model file checks)
- B-3: StableMaterials backend invocation undocumented (now: per-backend
  preflight)

Usage:
  python pipelines/textures/preflight.py
  python pipelines/textures/preflight.py --backend chord
  python pipelines/textures/preflight.py --json   # machine-readable

Returns:
  exit 0 if all required checks pass
  exit 1 if any required check fails
  exit 2 on internal error
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

# Repo root: this file lives at pipelines/textures/preflight.py, so two
# levels up is the repo root.
REPO_ROOT = Path(__file__).resolve().parent.parent.parent

DEFAULT_COMFY_URL = "http://127.0.0.1:8188"
COMFY_MODELS_DIR = REPO_ROOT / "animators" / "ComfyUI" / "models"
MESA_VENV_PYTHON = REPO_ROOT / "animators" / "mesa-env" / "venv" / "Scripts" / "python.exe"


def check_python_modules() -> tuple[bool, str]:
    """Verify the python interpreter has the modules aaa_texture needs."""
    required = ["numpy", "PIL", "requests"]
    missing = []
    for mod in required:
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    if missing:
        return (False, "missing: " + ", ".join(missing))
    return (True, f"all present: {', '.join(required)}")


def check_comfyui(url: str = DEFAULT_COMFY_URL, timeout: float = 3.0) -> tuple[bool, str]:
    """Probe ComfyUI's /system_stats endpoint."""
    try:
        req = urllib.request.Request(f"{url}/system_stats")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            sysinfo = data.get("system", {})
            version = sysinfo.get("comfyui_version", "?")
            torch_version = sysinfo.get("pytorch_version", "?")
            return (True, f"ComfyUI {version} (torch {torch_version})")
    except urllib.error.URLError as e:
        return (False, f"connection failed: {e}")
    except Exception as e:
        return (False, f"{type(e).__name__}: {e}")


def check_flux2_klein_4b() -> tuple[bool, str]:
    """Check that the default FLUX 2 klein-4B model file is on disk."""
    target = COMFY_MODELS_DIR / "diffusion_models" / "flux-2-klein-4b.safetensors"
    if target.exists():
        size_gb = target.stat().st_size / 1e9
        return (True, f"{target.name} ({size_gb:.2f} GB)")
    return (False, f"missing: {target}")


def check_stablematerials_venv() -> tuple[bool, str]:
    """StableMaterials runs in animators/mesa-env/venv. Verify the venv
    python exists and has the diffusers module."""
    if not MESA_VENV_PYTHON.exists():
        return (False, f"mesa-env venv python not found: {MESA_VENV_PYTHON}")
    import subprocess
    try:
        result = subprocess.run(
            [str(MESA_VENV_PYTHON), "-c", "import diffusers; print(diffusers.__version__)"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0:
            return (True, f"mesa-env venv (diffusers {result.stdout.strip()})")
        return (False, f"mesa-env venv missing diffusers: {result.stderr.strip()[:120]}")
    except subprocess.TimeoutExpired:
        return (False, "mesa-env venv probe timed out")
    except Exception as e:
        return (False, f"{type(e).__name__}: {e}")


def check_chord_node() -> tuple[bool, str]:
    """CHORD opt-in PBR backend. Lives as a ComfyUI custom node."""
    target = COMFY_MODELS_DIR.parent / "custom_nodes" / "ComfyUI-Chord"
    if not target.exists():
        return (False, f"ComfyUI-Chord custom node not found at {target}")
    chord_model = COMFY_MODELS_DIR / "checkpoints" / "chord_v1.safetensors"
    if not chord_model.exists():
        return (False, f"chord_v1.safetensors not found at {chord_model}")
    return (True, f"ComfyUI-Chord + chord_v1 ({chord_model.stat().st_size / 1e9:.2f} GB)")


def check_comfyui_gguf_node() -> tuple[bool, str]:
    """ComfyUI-GGUF custom node — needed for any quantized .gguf model
    in the diversity_compare bakeoff (auraflow, sd35, klein-9B Q8, etc.)."""
    target = COMFY_MODELS_DIR.parent / "custom_nodes" / "ComfyUI-GGUF"
    if not target.exists():
        return (False, f"ComfyUI-GGUF custom node not found at {target}")
    return (True, "ComfyUI-GGUF custom node")


CHECKS = [
    ("python_modules",      check_python_modules,        "always",        "Python deps (numpy, PIL, requests)"),
    ("comfyui_server",      check_comfyui,               "always",        "ComfyUI server at 127.0.0.1:8188"),
    ("flux2_klein_4b",      check_flux2_klein_4b,        "always",        "FLUX 2 klein-4B model file"),
    ("stablematerials",     check_stablematerials_venv,  "backend=sm",    "StableMaterials backend (mesa-env venv)"),
    ("chord_node",          check_chord_node,            "backend=chord", "CHORD opt-in backend (ComfyUI-Chord + chord_v1)"),
    ("gguf_node",           check_comfyui_gguf_node,     "always",        "ComfyUI-GGUF custom node (for diversity_compare quants)"),
]


def applies(when: str, backend: str | None) -> bool:
    if when == "always":
        return True
    if when == "backend=sm":
        return backend in (None, "sm")  # SM is default
    if when == "backend=chord":
        return backend in ("chord", "chord_sm_rough")
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    ap.add_argument("--backend", default=None,
                    help="restrict checks to a single backend "
                         "(sm | chord | chord_sm_rough | derive). Default: check all.")
    ap.add_argument("--comfy-url", default=DEFAULT_COMFY_URL)
    ap.add_argument("--json", action="store_true",
                    help="emit machine-readable JSON result and exit")
    args = ap.parse_args()

    results = []
    any_required_failed = False
    for check_id, fn, when, label in CHECKS:
        if not applies(when, args.backend):
            continue
        if check_id == "comfyui_server":
            ok, detail = fn(args.comfy_url)
        else:
            ok, detail = fn()
        results.append({"id": check_id, "ok": ok, "label": label, "detail": detail, "when": when})
        if not ok:
            any_required_failed = True

    if args.json:
        print(json.dumps({"ok": not any_required_failed, "checks": results}, indent=2))
        return 0 if not any_required_failed else 1

    # Human-friendly output
    print("=== Texture pipeline preflight ===\n")
    for r in results:
        sym = "OK  " if r["ok"] else "FAIL"
        print(f"  [{sym}] {r['label']}")
        print(f"         {r['detail']}")
    print()

    if any_required_failed:
        print("=== One or more required checks failed. ===")
        # Provide specific repair hints per common failure
        for r in results:
            if r["ok"]:
                continue
            if r["id"] == "comfyui_server":
                print()
                print("  ComfyUI is not running. Start it with:")
                print(f"    cd {REPO_ROOT}/animators/ComfyUI")
                print("    python main.py --listen 127.0.0.1 --port 8188")
                print("  Wait ~30 sec for model loading before retrying.")
            elif r["id"] == "stablematerials":
                print()
                print("  StableMaterials backend requires the mesa-env venv with diffusers.")
                print(f"  Expected: {MESA_VENV_PYTHON}")
                print("  If missing, see pipelines/textures/stablematerials_image2pbr.py")
                print("  for setup instructions.")
            elif r["id"] == "flux2_klein_4b":
                print()
                print("  Download FLUX.2-klein-4B from black-forest-labs/FLUX.2-klein-4B and")
                print(f"  place at: {COMFY_MODELS_DIR}/diffusion_models/flux-2-klein-4b.safetensors")
        return 1

    print("=== All checks passed. ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())

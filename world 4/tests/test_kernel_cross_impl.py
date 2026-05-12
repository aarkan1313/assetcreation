"""Cross-implementation test: Python NoiseStackKernel vs GDScript NoiseStackKernel.

GDScript dumps its output to a JSON file via KernelDump.gd; this test
loads it and asserts the Python impl produces the same numeric output
at every sample point.
"""
from __future__ import annotations
import json
import subprocess
from pathlib import Path

from kernels.noise_stack import NoiseStackKernel


GODOT_EXE = r"C:/Godot/Godot_v4.5-stable_win64.exe"
W4_GODOT_PROJECT = Path(r"D:/assets/world 4/the world 4")
DUMP_SCRIPT = "scripts/kernels/KernelDump.gd"

MAX_ABS_DELTA = 1e-4


def _run_godot_dump(out_path: Path) -> None:
    cmd = [
        GODOT_EXE,
        "--headless",
        "--path", str(W4_GODOT_PROJECT),
        "-s", DUMP_SCRIPT,
        "--",
        "--out", str(out_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise RuntimeError(
            f"KernelDump exited {result.returncode}:\nSTDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}")


def test_python_matches_godot(tmp_path: Path):
    dump_path = tmp_path / "cross_impl_dump.json"
    _run_godot_dump(dump_path)

    data = json.loads(dump_path.read_text(encoding="utf-8"))
    assert data["kernel"] == "noise_stack"
    py_kernel = NoiseStackKernel()
    seed = int(data["world_seed"])
    params = data["params"]

    max_delta = 0.0
    bad_samples = []
    for row in data["samples"]:
        for s in row:
            py_h = py_kernel.height(float(s["x"]), float(s["z"]), seed, params)
            delta = abs(py_h - float(s["h"]))
            max_delta = max(max_delta, delta)
            if delta > MAX_ABS_DELTA:
                bad_samples.append({
                    "x": s["x"], "z": s["z"],
                    "py": py_h, "godot": s["h"],
                    "delta": delta,
                })
                if len(bad_samples) >= 5:
                    break
        if len(bad_samples) >= 5:
            break

    assert not bad_samples, (
        f"Python/GDScript NoiseStackKernel disagree (max delta {max_delta}):\n"
        + "\n".join(repr(b) for b in bad_samples)
    )
    print(f"cross-impl agreement: max delta = {max_delta:.6e}")

"""Cross-implementation test: Python QualityTiers vs GDScript QualityTiers.

Same pattern as test_kernel_cross_impl.py — run the GDScript-side
dumper headless, load its output, and assert the Python resolver
produces the same value for every key, every tier.
"""
from __future__ import annotations
import json
import subprocess
from pathlib import Path

from quality_tiers import resolve, KNOWN_KEYS


GODOT_EXE = r"C:/Godot/Godot_v4.5-stable_win64.exe"
W4_GODOT_PROJECT = Path(r"D:/assets/world 4/the world 4")
DUMP_SCRIPT = "scripts/QualityTiersDump.gd"


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
            f"QualityTiersDump exited {result.returncode}:\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}")


def test_python_matches_godot(tmp_path: Path):
    dump_path = tmp_path / "qt_dump.json"
    _run_godot_dump(dump_path)

    data = json.loads(dump_path.read_text(encoding="utf-8"))
    resolved = data["resolved"]
    assert set(resolved.keys()) == {"low", "medium", "high", "ultra"}

    mismatches = []
    type_mismatches = []
    for tier_name, godot_dict in resolved.items():
        py_dict = resolve(tier_name)
        for key in KNOWN_KEYS:
            g = godot_dict.get(key)
            p = py_dict.get(key)
            if g != p:
                mismatches.append({
                    "tier": tier_name, "key": key,
                    "godot": g, "python": p,
                })
            # Type check: int vs float must agree exactly. Godot's
            # JSON.parse_string returns all numbers as float; the
            # GDScript resolver coerces int-typed keys back to int.
            # If that coercion drifts, downstream consumers break
            # (range() can't take float, etc).
            if type(g) is not type(p):
                type_mismatches.append({
                    "tier": tier_name, "key": key,
                    "godot_type": type(g).__name__,
                    "python_type": type(p).__name__,
                    "godot_value": g, "python_value": p,
                })
        assert godot_dict.get("_tier") == tier_name
        assert py_dict.get("_tier") == tier_name

    assert not mismatches, (
        "Python/GDScript QualityTiers value mismatch:\n"
        + "\n".join(repr(m) for m in mismatches)
    )
    assert not type_mismatches, (
        "Python/GDScript QualityTiers type mismatch:\n"
        + "\n".join(repr(m) for m in type_mismatches)
    )

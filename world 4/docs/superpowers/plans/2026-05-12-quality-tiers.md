# Quality Tiers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a Low/Medium/High/Ultra quality-tier system used by both the GDScript runtime and Python pipeline, with `high` (3060-class) as default and the resolver positioned for a Phase-2 custom-overrides layer.

**Architecture:** Single JSON file (`the world 4/config/quality_tiers.json`) is the source of truth. A Python resolver (`pipeline/quality_tiers.py`) and a GDScript resolver (`scripts/QualityTiers.gd`) both load it; consumers call a typed getter and never branch on the tier string. The current tier is read from `ProjectSettings("world/quality_tier")` (GDScript) or a `--quality-tier` CLI arg / env var (Python). A cross-impl pytest verifies both sides resolve the same values, the same pattern as the NoiseStackKernel cross-impl test that landed in Stage 1.

**Tech Stack:**
- Python 3.12 + pytest for the pipeline resolver and cross-impl test
- GDScript 2 (Godot 4.5) for the runtime resolver
- Godot SceneTree script (`-s` headless) for dumping GDScript-resolved values to JSON, mirroring `KernelDump.gd`
- No new third-party deps

---

## File Structure

**New files:**
- `the world 4/config/quality_tiers.json` — the tier table. Source of truth.
- `pipeline/quality_tiers.py` — Python resolver. ~60 LOC. Loads JSON, returns a dict, supports a `--quality-tier` override.
- `the world 4/scripts/QualityTiers.gd` — GDScript resolver. ~50 LOC. Loads JSON, caches the resolved tier for the session, falls back gracefully on bad input.
- `the world 4/scripts/QualityTiersDump.gd` — headless SceneTree script that resolves each tier via GDScript and writes the values to a JSON file. ~30 LOC. Mirrors `KernelDump.gd`'s structure.
- `tests/test_quality_tiers.py` — Python unit tests for the resolver (schema, defaults, unknown-tier fallback).
- `tests/test_quality_tiers_cross_impl.py` — runs `QualityTiersDump.gd` and asserts every key/value matches the Python resolver's output for every tier.

**Modified files:**
- `the world 4/project.godot` — register the `world/quality_tier` ProjectSettings key with default `"high"`. One line append.

**Boundary discipline:** the resolver is the only thing that knows about tier strings. Stage 3+ consumers will read named values (`cfg["ring_grid_n"]`) and never reference `"low"` / `"high"` etc. This is what keeps Phase 2 (custom overrides) a one-file change later.

---

## Task 1: Author the JSON config

**Files:**
- Create: `the world 4/config/quality_tiers.json`

- [ ] **Step 1: Create the config dir + JSON file via Python helper**

Use the Python helper pattern (Windows Write tool produces UTF-16 — memory `write_tool_utf16_on_windows.md`):

```bash
"C:/Program Files/Python312/python.exe" -c "
import json, os
target = r'D:/assets/world 4/config'
os.makedirs(target, exist_ok=True)
cfg = {
    'schema_version': 1,
    'default_tier': 'high',
    'tiers': {
        'low': {
            'ring_count': 3,
            'ring_grid_n': 64,
            'ring_grid_step_base_m': 4.0,
            'heightmap_format_inner': 'RF',
            'heightmap_format_outer': 'RH',
            'collision_rings': 1,
            'splat_texture_array_size': 1024,
            'splat_resolution_per_ring_m': 4.0,
            'shadow_quality': 'off',
            'update_interval_s': 0.10,
        },
        'medium': {
            'ring_count': 4,
            'ring_grid_n': 96,
            'ring_grid_step_base_m': 2.0,
            'heightmap_format_inner': 'RF',
            'heightmap_format_outer': 'RH',
            'collision_rings': 1,
            'splat_texture_array_size': 2048,
            'splat_resolution_per_ring_m': 2.0,
            'shadow_quality': 'low',
            'update_interval_s': 0.07,
        },
        'high': {
            'ring_count': 4,
            'ring_grid_n': 128,
            'ring_grid_step_base_m': 2.0,
            'heightmap_format_inner': 'RF',
            'heightmap_format_outer': 'RH',
            'collision_rings': 2,
            'splat_texture_array_size': 4096,
            'splat_resolution_per_ring_m': 1.0,
            'shadow_quality': 'high',
            'update_interval_s': 0.05,
        },
        'ultra': {
            'ring_count': 4,
            'ring_grid_n': 256,
            'ring_grid_step_base_m': 2.0,
            'heightmap_format_inner': 'RF',
            'heightmap_format_outer': 'RF',
            'collision_rings': 2,
            'splat_texture_array_size': 4096,
            'splat_resolution_per_ring_m': 0.5,
            'shadow_quality': 'high',
            'update_interval_s': 0.05,
        },
    },
}
out_path = os.path.join(target, 'quality_tiers.json')
open(out_path, 'w', encoding='utf-8', newline='\n').write(json.dumps(cfg, indent=2) + '\n')
print('wrote', out_path)
"
```

Expected output: `wrote D:/assets/world 4/config/quality_tiers.json`

- [ ] **Step 2: Verify the JSON parses + has expected shape**

```bash
"C:/Program Files/Python312/python.exe" -c "
import json
cfg = json.loads(open(r'D:/assets/world 4/config/quality_tiers.json', encoding='utf-8').read())
assert cfg['schema_version'] == 1
assert cfg['default_tier'] == 'high'
assert set(cfg['tiers'].keys()) == {'low', 'medium', 'high', 'ultra'}
assert cfg['tiers']['high']['ring_grid_n'] == 128
assert cfg['tiers']['ultra']['ring_grid_n'] == 256
print('OK')
"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git -C "D:/assets" add "world 4/config/quality_tiers.json"
git -C "D:/assets" commit -m "quality-tiers: 1. JSON source of truth (Low/Medium/High/Ultra)"
```

---

## Task 2: Python resolver (test-first)

**Files:**
- Create: `tests/test_quality_tiers.py`
- Create: `pipeline/quality_tiers.py`

- [ ] **Step 1: Write the failing test file**

Use the Write tool to create `tests/test_quality_tiers.py`:

```python
"""Tests for pipeline.quality_tiers."""
from __future__ import annotations
import pytest

from quality_tiers import (
    QualityTiersError,
    get_config_path,
    load_config,
    resolve,
    KNOWN_KEYS,
)


def test_load_config_returns_expected_shape():
    cfg = load_config()
    assert cfg["schema_version"] == 1
    assert cfg["default_tier"] == "high"
    assert set(cfg["tiers"].keys()) == {"low", "medium", "high", "ultra"}


def test_every_tier_has_every_known_key():
    cfg = load_config()
    for tier_name, tier_dict in cfg["tiers"].items():
        missing = [k for k in KNOWN_KEYS if k not in tier_dict]
        assert not missing, f"tier {tier_name!r} missing keys: {missing!r}"


def test_resolve_high_is_default():
    out = resolve()
    assert out["_tier"] == "high"
    assert out["ring_grid_n"] == 128
    assert out["ring_count"] == 4


def test_resolve_explicit_tier():
    out = resolve("low")
    assert out["_tier"] == "low"
    assert out["ring_grid_n"] == 64
    assert out["ring_count"] == 3
    out2 = resolve("ultra")
    assert out2["_tier"] == "ultra"
    assert out2["ring_grid_n"] == 256


def test_resolve_unknown_tier_raises():
    with pytest.raises(QualityTiersError, match="bogus"):
        resolve("bogus")


def test_resolved_dict_is_independent_copy():
    """Mutating one resolve() result must not poison subsequent calls."""
    a = resolve("high")
    a["ring_grid_n"] = -999
    b = resolve("high")
    assert b["ring_grid_n"] == 128


def test_get_config_path_is_a_real_file():
    p = get_config_path()
    assert p.exists(), f"config not found at {p}"


def test_resolve_values_sane():
    """Sanity ranges so a typo in the JSON doesn't ship silently."""
    for name in ["low", "medium", "high", "ultra"]:
        cfg = resolve(name)
        assert 2 <= cfg["ring_count"] <= 6
        assert 32 <= cfg["ring_grid_n"] <= 512
        assert 0.25 <= cfg["ring_grid_step_base_m"] <= 16.0
        assert cfg["heightmap_format_inner"] in {"RF", "RH"}
        assert cfg["heightmap_format_outer"] in {"RF", "RH"}
        assert 0 <= cfg["collision_rings"] <= cfg["ring_count"]
        assert 256 <= cfg["splat_texture_array_size"] <= 8192
        assert cfg["shadow_quality"] in {"off", "low", "high"}
        assert 0.01 <= cfg["update_interval_s"] <= 1.0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd "D:/assets/world 4" && "C:/Program Files/Python312/python.exe" -m pytest tests/test_quality_tiers.py -v 2>&1 | tail -10
```

Expected: `ModuleNotFoundError: No module named 'quality_tiers'` (collection-time import error).

- [ ] **Step 3: Implement the Python resolver**

Use the Write tool to create `pipeline/quality_tiers.py`:

```python
"""Quality-tier resolver (Python side).

Loads `config/quality_tiers.json` (relative to the W4 Godot project),
returns a typed dict for any of the named tiers, and is the
authoritative source consumed by pipeline tools (asset baking, splat
sizing, etc).

Architecture note: consumers read named keys (cfg["ring_grid_n"]),
never the tier string. This keeps the consumer code Phase-2-ready
(custom overrides land later as a one-file extension here).

CLI usage:
    python -m quality_tiers --tier high   # prints resolved JSON
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


class QualityTiersError(RuntimeError):
    """Raised for unknown tier / malformed config."""


# Keys every tier dict must define. Add to this list when introducing
# a new tier knob (and update the JSON simultaneously — `test_every_tier_has_every_known_key`
# is the safety net).
KNOWN_KEYS = (
    "ring_count",
    "ring_grid_n",
    "ring_grid_step_base_m",
    "heightmap_format_inner",
    "heightmap_format_outer",
    "collision_rings",
    "splat_texture_array_size",
    "splat_resolution_per_ring_m",
    "shadow_quality",
    "update_interval_s",
)


def get_config_path() -> Path:
    """Return the absolute path to quality_tiers.json.

    Resolves relative to this file: `pipeline/quality_tiers.py` →
    `the world 4/config/quality_tiers.json`. Walks up to the W4 root
    so it works regardless of CWD.
    """
    here = Path(__file__).resolve()
    # pipeline/quality_tiers.py -> world 4/pipeline -> world 4
    w4_root = here.parent.parent
    return w4_root / "the world 4" / "config" / "quality_tiers.json"


def load_config() -> dict:
    """Read and parse the JSON config. Raises QualityTiersError on
    missing file or malformed JSON."""
    path = get_config_path()
    if not path.exists():
        raise QualityTiersError(f"config not found at {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise QualityTiersError(f"config malformed: {e}") from e


def resolve(tier: str | None = None) -> dict:
    """Resolve a tier name to its config dict.

    If `tier` is None, uses `default_tier` from the JSON.
    Result is a fresh dict copy with `_tier` set to the resolved name
    so consumers can log / display it.
    """
    cfg = load_config()
    if tier is None:
        tier = cfg.get("default_tier", "high")
    tiers = cfg.get("tiers", {})
    if tier not in tiers:
        raise QualityTiersError(
            f"unknown tier {tier!r}; known: {sorted(tiers.keys())!r}")
    out = dict(tiers[tier])
    out["_tier"] = tier
    return out


def _cli() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", default=None,
                    help="Tier name (low/medium/high/ultra). Default: high.")
    args = ap.parse_args()
    cfg = resolve(args.tier)
    print(json.dumps(cfg, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
```

- [ ] **Step 4: Re-run tests to verify they pass**

```bash
cd "D:/assets/world 4" && "C:/Program Files/Python312/python.exe" -m pytest tests/test_quality_tiers.py -v 2>&1 | tail -15
```

Expected: `8 passed`.

- [ ] **Step 5: Smoke-test the CLI**

```bash
cd "D:/assets/world 4" && "C:/Program Files/Python312/python.exe" -m quality_tiers --tier high 2>&1 | head -20
```

Expected: JSON containing `"_tier": "high"` and `"ring_grid_n": 128`. Note: needs `cd` into `world 4` because pipeline/ isn't on PYTHONPATH globally; alternatively `python pipeline/quality_tiers.py --tier high` works without conftest.

The CLI smoke-test result confirms the module imports correctly outside pytest's `conftest.py` (which prepends `pipeline/`). If `-m` fails with ModuleNotFoundError, run instead:

```bash
"C:/Program Files/Python312/python.exe" "D:/assets/world 4/pipeline/quality_tiers.py" --tier high 2>&1 | head -20
```

That always works.

- [ ] **Step 6: Commit**

```bash
git -C "D:/assets" add "world 4/pipeline/quality_tiers.py" "world 4/tests/test_quality_tiers.py"
git -C "D:/assets" commit -m "quality-tiers: 2. Python resolver + 8 unit tests"
```

---

## Task 3: GDScript resolver

**Files:**
- Create: `the world 4/scripts/QualityTiers.gd`

- [ ] **Step 1: Write `QualityTiers.gd`**

Use the Write tool to create `the world 4/scripts/QualityTiers.gd`:

```gdscript
class_name QualityTiers
extends RefCounted

# Quality-tier resolver (GDScript side).
#
# Loads config/quality_tiers.json, returns a typed Dictionary for any
# named tier, caches the resolved tier for the session.
#
# Consumers call get_current() and read named keys. They MUST NOT
# branch on the tier string — that's what keeps Phase-2 overrides
# a one-file change here.
#
# Reads the active tier from ProjectSettings("world/quality_tier"),
# defaulting to the JSON's `default_tier` if unset.

const CONFIG_PATH := "res://config/quality_tiers.json"
const PROJECT_SETTING_KEY := "world/quality_tier"

static var _cached_resolved: Dictionary = {}


# Public API ----------------------------------------------------------

static func get_current() -> Dictionary:
	if _cached_resolved.is_empty():
		_cached_resolved = _resolve(_current_tier_name())
	return _cached_resolved.duplicate(true)


static func resolve_tier(tier: String) -> Dictionary:
	"""Resolve a specific named tier. Does NOT cache or affect get_current()."""
	return _resolve(tier)


static func clear_cache() -> void:
	"""Force re-read on next get_current(). Test-only."""
	_cached_resolved = {}


# Internals -----------------------------------------------------------

static func _load_config() -> Dictionary:
	var f := FileAccess.open(CONFIG_PATH, FileAccess.READ)
	if f == null:
		push_error("QualityTiers: cannot open " + CONFIG_PATH)
		return {}
	var text := f.get_as_text()
	f.close()
	var parsed: Variant = JSON.parse_string(text)
	if typeof(parsed) != TYPE_DICTIONARY:
		push_error("QualityTiers: config malformed (not a dict)")
		return {}
	return parsed


static func _current_tier_name() -> String:
	var cfg := _load_config()
	var default_tier: String = cfg.get("default_tier", "high")
	var from_project: Variant = ProjectSettings.get_setting(
		PROJECT_SETTING_KEY, "")
	if typeof(from_project) == TYPE_STRING and not (from_project as String).is_empty():
		return from_project
	return default_tier


static func _resolve(tier: String) -> Dictionary:
	var cfg := _load_config()
	var tiers: Dictionary = cfg.get("tiers", {})
	if not tiers.has(tier):
		var fallback: String = cfg.get("default_tier", "high")
		push_error("QualityTiers: unknown tier %s, falling back to %s" % [tier, fallback])
		if not tiers.has(fallback):
			return {}
		tier = fallback
	var out: Dictionary = (tiers[tier] as Dictionary).duplicate(true)
	out["_tier"] = tier
	return out
```

- [ ] **Step 2: Parse-check via --import**

```bash
"C:/Godot/Godot_v4.5-stable_win64.exe" --headless --path "D:/assets/world 4/the world 4" --import 2>&1 | grep -iE "QualityTiers|error|parse" | head -10
```

Expected: no `Parse Error` or `ERROR` lines. The class should appear in the script class index (a `.uid` file is created).

- [ ] **Step 3: Verify uid was generated**

```bash
ls "d:/assets/world 4/the world 4/scripts/QualityTiers.gd.uid"
```

Expected: file exists.

- [ ] **Step 4: Commit**

```bash
git -C "D:/assets" add "world 4/the world 4/scripts/QualityTiers.gd" "world 4/the world 4/scripts/QualityTiers.gd.uid"
git -C "D:/assets" commit -m "quality-tiers: 3. GDScript resolver (caches, falls back gracefully)"
```

---

## Task 4: GDScript dump tool for cross-impl test

**Files:**
- Create: `the world 4/scripts/QualityTiersDump.gd`

- [ ] **Step 1: Write the dump script**

Use the Write tool to create `the world 4/scripts/QualityTiersDump.gd`:

```gdscript
extends SceneTree

# Headless tool: resolves every tier via QualityTiers.gd and writes
# the resulting dict to a JSON file. Consumed by the cross-impl test.
#
# Usage:
#   "C:/Godot/Godot_v4.5-stable_win64.exe" --headless \
#     --path "D:/assets/world 4/the world 4" \
#     -s scripts/QualityTiersDump.gd \
#     -- --out "D:/path/to/dump.json"

func _initialize() -> void:
	var args := OS.get_cmdline_user_args()
	var out_path: String = ""
	for i in range(args.size() - 1):
		if args[i] == "--out":
			out_path = args[i + 1]
			break
	if out_path.is_empty():
		push_error("QualityTiersDump: --out <path> required")
		quit(1)
		return

	var tiers := ["low", "medium", "high", "ultra"]
	var dump := {"schema_version": 1, "resolved": {}}
	for t in tiers:
		dump["resolved"][t] = QualityTiers.resolve_tier(t)

	var f := FileAccess.open(out_path, FileAccess.WRITE)
	if f == null:
		push_error("QualityTiersDump: cannot open " + out_path)
		quit(1)
		return
	f.store_string(JSON.stringify(dump, "  "))
	f.close()
	print("[QualityTiersDump] wrote ", tiers.size(), " tiers to ", out_path)
	quit(0)
```

- [ ] **Step 2: Parse-check + smoke-test**

```bash
"C:/Godot/Godot_v4.5-stable_win64.exe" --headless --path "D:/assets/world 4/the world 4" --import 2>&1 | grep -iE "QualityTiersDump|error|parse" | head -5
```

Expected: no errors.

Run a smoke dump:

```bash
"C:/Godot/Godot_v4.5-stable_win64.exe" --headless --path "D:/assets/world 4/the world 4" -s scripts/QualityTiersDump.gd -- --out "D:/tmp/qt_dump.json" 2>&1 | tail -5
```

Expected: `[QualityTiersDump] wrote 4 tiers to D:/tmp/qt_dump.json`. Verify content:

```bash
"C:/Program Files/Python312/python.exe" -c "
import json
d = json.loads(open(r'D:/tmp/qt_dump.json', encoding='utf-8').read())
assert set(d['resolved'].keys()) == {'low', 'medium', 'high', 'ultra'}
assert d['resolved']['high']['ring_grid_n'] == 128
print('OK')
"
```

Expected: `OK`.

- [ ] **Step 3: Commit**

```bash
git -C "D:/assets" add "world 4/the world 4/scripts/QualityTiersDump.gd" "world 4/the world 4/scripts/QualityTiersDump.gd.uid"
git -C "D:/assets" commit -m "quality-tiers: 4. QualityTiersDump.gd headless tool for cross-impl test"
```

---

## Task 5: Cross-impl test (Python ↔ GDScript)

**Files:**
- Create: `tests/test_quality_tiers_cross_impl.py`

- [ ] **Step 1: Write the failing test**

Use the Write tool to create `tests/test_quality_tiers_cross_impl.py`:

```python
"""Cross-implementation test: Python QualityTiers vs GDScript QualityTiers.

Same pattern as test_kernel_cross_impl.py — run the GDScript-side
dumper headless, load its output, and assert the Python resolver
produces the same value for every key, every tier.
"""
from __future__ import annotations
import json
import subprocess
from pathlib import Path

import pytest

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
        # Also check the _tier label round-trips.
        assert godot_dict.get("_tier") == tier_name
        assert py_dict.get("_tier") == tier_name

    assert not mismatches, (
        "Python/GDScript QualityTiers disagree:\n"
        + "\n".join(repr(m) for m in mismatches)
    )
```

- [ ] **Step 2: Run the test**

```bash
cd "D:/assets/world 4" && "C:/Program Files/Python312/python.exe" -m pytest tests/test_quality_tiers_cross_impl.py -v 2>&1 | tail -10
```

Expected: 1 passed. If it fails, the error message lists every (tier, key) pair that disagrees — most likely cause is a typo between the JSON and one of the resolvers.

- [ ] **Step 3: Commit**

```bash
git -C "D:/assets" add "world 4/tests/test_quality_tiers_cross_impl.py"
git -C "D:/assets" commit -m "quality-tiers: 5. Python/GDScript cross-impl test"
```

---

## Task 6: Register the ProjectSettings key

**Files:**
- Modify: `the world 4/project.godot`

- [ ] **Step 1: Inspect current project.godot to find the right section**

```bash
grep -n "^\[" "d:/assets/world 4/the world 4/project.godot" 2>&1 | head -20
```

This lists section headers. We need to add a `[world]` section (or append to one if it exists). Inspect the current file to decide where the section goes:

```bash
cat "d:/assets/world 4/the world 4/project.godot"
```

- [ ] **Step 2: Add the setting via Python helper**

If `[world]` doesn't already exist, append the section. If it does, add `quality_tier = "high"` inside it.

Use the Python helper to do this safely (preserves UTF-8, doesn't disturb other sections):

```bash
"C:/Program Files/Python312/python.exe" -c "
path = r'D:/assets/world 4/the world 4/project.godot'
text = open(path, encoding='utf-8').read()
addition = '\n[world]\n\nquality_tier=\"high\"\n'
if '[world]' in text:
    print('WARNING: [world] section already exists. Append `quality_tier=\"high\"` manually if not present.')
else:
    open(path, 'w', encoding='utf-8', newline='\n').write(text.rstrip() + '\n' + addition)
    print('appended [world] section with quality_tier=\"high\"')
"
```

Expected: `appended [world] section with quality_tier="high"`.

- [ ] **Step 3: Verify Godot accepts the new setting**

```bash
"C:/Godot/Godot_v4.5-stable_win64.exe" --headless --path "D:/assets/world 4/the world 4" --import 2>&1 | grep -iE "error|parse" | head -5
```

Expected: no errors.

Then confirm `ProjectSettings.get_setting("world/quality_tier")` returns `"high"`. A throwaway dump verifies this:

```bash
"C:/Program Files/Python312/python.exe" -c "
import tempfile, json, subprocess
from pathlib import Path
script = '''extends SceneTree
func _initialize():
	var t = ProjectSettings.get_setting(\"world/quality_tier\", \"NOT_SET\")
	print(\"tier=\" + str(t))
	quit(0)
'''
# Write to a temp file inside the godot project so res:// works.
import os
tmp_script = r'D:/assets/world 4/the world 4/scripts/_qt_probe.gd'
open(tmp_script, 'w', encoding='utf-8', newline='\n').write(script)
r = subprocess.run([
    r'C:/Godot/Godot_v4.5-stable_win64.exe', '--headless',
    '--path', r'D:/assets/world 4/the world 4',
    '-s', 'scripts/_qt_probe.gd'
], capture_output=True, text=True, timeout=30)
print(r.stdout)
print('STDERR:', r.stderr)
os.unlink(tmp_script)
"
```

Expected: stdout contains `tier=high`. If it shows `tier=NOT_SET`, the setting was added to the wrong section — check `project.godot` manually and move it.

- [ ] **Step 4: Commit**

```bash
git -C "D:/assets" add "world 4/the world 4/project.godot"
git -C "D:/assets" commit -m "quality-tiers: 6. register world/quality_tier ProjectSetting (default 'high')"
```

---

## Task 7: Verify the full system end-to-end

**Files:** (no code changes; verification only)

- [ ] **Step 1: Re-run all quality-tier tests**

```bash
cd "D:/assets/world 4" && "C:/Program Files/Python312/python.exe" -m pytest tests/test_quality_tiers.py tests/test_quality_tiers_cross_impl.py -v 2>&1 | tail -20
```

Expected: 9 passed (8 unit + 1 cross-impl).

- [ ] **Step 2: Re-run the full kernel suite to confirm no regression**

```bash
cd "D:/assets/world 4" && "C:/Program Files/Python312/python.exe" -m pytest tests/test_kernel_base.py tests/test_noise_stack_kernel.py tests/test_kernel_composer.py tests/test_kernel_cross_impl.py -v 2>&1 | tail -10
```

Expected: 17 passed (unchanged from Stage 1).

- [ ] **Step 3: Confirm GDScript classes still register without errors**

```bash
"C:/Godot/Godot_v4.5-stable_win64.exe" --headless --path "D:/assets/world 4/the world 4" --import 2>&1 | grep -iE "error|parse|fail" | head -10
```

Expected: no output (no errors).

- [ ] **Step 4 (optional): Smoke a programmatic tier switch**

Verify that changing `ProjectSettings` actually changes the resolved tier. Use a temp probe:

```bash
"C:/Program Files/Python312/python.exe" -c "
import subprocess, os
script = '''extends SceneTree
func _initialize():
	# Override the setting in-memory and check QualityTiers picks it up.
	ProjectSettings.set_setting(\"world/quality_tier\", \"low\")
	QualityTiers.clear_cache()
	var cfg = QualityTiers.get_current()
	print(\"tier=\" + str(cfg[\"_tier\"]) + \" ring_grid_n=\" + str(cfg[\"ring_grid_n\"]))
	quit(0)
'''
tmp_script = r'D:/assets/world 4/the world 4/scripts/_qt_probe2.gd'
open(tmp_script, 'w', encoding='utf-8', newline='\n').write(script)
r = subprocess.run([
    r'C:/Godot/Godot_v4.5-stable_win64.exe', '--headless',
    '--path', r'D:/assets/world 4/the world 4',
    '-s', 'scripts/_qt_probe2.gd'
], capture_output=True, text=True, timeout=30)
print(r.stdout)
print('STDERR:', r.stderr)
os.unlink(tmp_script)
"
```

Expected: stdout contains `tier=low ring_grid_n=64`. Confirms:
1. `QualityTiers.clear_cache()` works (the cache was set to `high` by the prior call).
2. `QualityTiers.get_current()` reads the freshly-set ProjectSetting.
3. The Low tier resolves to the expected values.

- [ ] **Step 5: Commit verification note (optional — only if step 4 surfaced anything noteworthy)**

If everything passed without changes, no commit needed for Task 7. If step 4 revealed a bug worth a fix, fix it and add a commit referencing this task.

---

## Self-review notes

**Spec coverage check:**
- ✅ "Single JSON source of truth" → Task 1
- ✅ "Python resolver, returns dict, supports CLI" → Task 2
- ✅ "GDScript resolver, caches, falls back" → Task 3
- ✅ "ProjectSettings integration, default 'high'" → Task 6
- ✅ "Cross-impl test mirroring kernel pattern" → Tasks 4 + 5
- ✅ "Consumers read named keys, not tier string" → enforced by API shape (no public tier-string accessor in either resolver)
- ✅ "Phase-2 overrides are a one-file extension" → resolver pattern (`_resolve` is private, easy to wrap)

**Placeholder scan:** none. Every step has exact paths, complete code, and exact expected output.

**Type consistency check:** `KNOWN_KEYS` is defined in Python and consumed in `test_quality_tiers.py` + `test_quality_tiers_cross_impl.py`. The GDScript side doesn't define a parallel constant — that's intentional; the cross-impl test is the single mechanism that pins both sides to the JSON shape. Adding a key means: add to JSON (Task 1), add to `KNOWN_KEYS` (Task 2 source), add to every tier dict (JSON). Cross-impl test will fail if you miss any tier.

**Out-of-scope items that came up:**
- A launcher UI for picking the tier at runtime — separate task, not blocking Stage 3+.
- Phase 2 custom-overrides layer — explicitly deferred in the spec; the resolver shape is set up to add it as one new method.

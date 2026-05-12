# Axis 6 Transitions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace W4's per-tile single-material rendering with a
texture-array + per-tile splat-map system that supports soft biome
transitions and scales to 15+ biomes at constant per-fragment cost.

**Architecture:** A single global terrain material binds 8 texture
arrays (2 resolution tiers × 4 PBR maps each), each with N biome
layers. Per-tile splat maps (64×64 RGBA) define which biome layers
contribute to each fragment and how strongly. A `terrain_world_v2`
shader samples the splat, decodes up to 4 (tier, layer, slot) tuples,
samples the corresponding arrays, applies the existing within-biome
slope blend per contributing biome, and lerps the contributions. The
existing unshaded manual-lighting model (PITFALLS #3 mitigation) and
cross-tile heightmap sampling (PITFALLS #4 mitigation) are preserved.

**Tech Stack:** Python 3.12 (system) + Pillow + numpy + pytest. Godot
4.5 with `Texture2DArray`, custom GDScript runtime + GLSL fragment
shader. JSON catalog schema.

**Spec:** `docs/plans/AXIS6_TRANSITIONS_DESIGN_2026_05_12.md`

**Working directory:** `D:/assets/world 4/`. Python invoked as
`"C:/Program Files/Python312/python.exe"`. Godot invoked as
`"C:/Godot/Godot_v4.5-stable_win64.exe"` (non-mono).

**Verification model:** Python pipeline scripts have pytest unit tests.
Shader + Godot wiring is verified by headless captures cross-checked
against the user's editor screenshots (per `reference/PITFALLS.md`
methodology — headless OpenGL Compatibility hides bugs that Forward+
Vulkan in the editor exposes).

**Date placeholder convention:** capture filenames in this plan use
`<DD>` as a substitution for today's two-digit day-of-month (e.g.
`<DD>` becomes `13` if executed on 2026-05-13). Replace it with the
actual day when running each task. The plan was written 2026-05-12
but executing it on a later day is normal.

---

## File structure

### Created

| Path | Responsibility |
|---|---|
| `worlds/scale_demo/biome_catalog.json` | Declares biomes, slots, tiers. Single source of truth. |
| `pipeline/biome_catalog.py` | Pure-Python catalog loader + validator. Used by all pipeline scripts. |
| `pipeline/build_biome_arrays.py` | Builds per-tier per-map-type `Texture2DArray` `.tres` resources from biome PBR maps. |
| `pipeline/build_tile_splats.py` | Builds per-tile splat.png + splat_meta.json. CLI modes: hard, feather, noise. |
| `pipeline/write_global_terrain_material.py` | Emits the single global terrain material binding the 8 arrays + lighting uniforms. |
| `the world 4/shaders/terrain_world_v2.gdshader` | New unified terrain shader (array sampling + splat blending). |
| `the world 4/worlds/scale_demo/arrays/` (dir) | Generated texture array `.tres` files (2 tiers × 4 maps = 8 files) + `layer_manifest.json`. |
| `the world 4/worlds/scale_demo/tiles/tile_X_Z/splat.png` (×16) | Per-tile splat textures. |
| `the world 4/worlds/scale_demo/tiles/tile_X_Z/splat_meta.json` (×16) | Per-tile (tier, layer, slot) tuples for the 4 splat channels. |
| `the world 4/worlds/scale_demo/material_world_v2.tres` | Global terrain material referencing the 8 arrays. |
| `tests/test_biome_catalog.py` | Catalog loader/validator tests. |
| `tests/test_build_tile_splats.py` | Splat builder tests on synthetic data. |
| `tests/conftest.py` | pytest config + shared fixtures. |
| `docs/plans/AXIS6_PORTABILITY_README.md` | "Drop this system into another Godot project" guide (Stage 5e). |
| `docs/build-notes/AXIS6_BUILD_NOTES_2026_05_12.md` | What shipped + lessons. (Stage 5f) |

### Modified

| Path | Why |
|---|---|
| `the world 4/scripts/ScaleWorld.gd` | Load global material once, drop per-tile material selection, pass per-tile splat uniforms. |
| `the world 4/scripts/TileTerrain.gd` | Load this tile's splat + meta, set per-tile shader uniforms on duplicated material. |
| `the world 4/scenes/scale_demo.tscn` | Bind global material; drop `biome_materials` dict (kept as fallback path for compat). |
| `docs/ROADMAP.md` | Move Axis 6 to "What's done"; rerank. (Stage 5f) |
| `docs/strategy/AXES.md` | Axis 6 current-state update. (Stage 5f) |
| `docs/reference/TOOLS.md` | Add new pipeline scripts + shader rows. (Stage 5f) |
| `C:/Users/josep/.claude/projects/d--assets/memory/MEMORY.md` | Add Axis 6 transitions memory entry. (Stage 5f) |

### Convention

- All `.tres` and `.json` files written with `encoding="utf-8"` and `newline="\n"` to avoid the Windows-Write-tool UTF-16 trap (see memory `write_tool_utf16_on_windows.md`).
- Python pipeline scripts: hashbang + module docstring + `if __name__ == "__main__": raise SystemExit(main())`.
- Tests live under `D:/assets/world 4/tests/` and discover from there. Run as `"C:/Program Files/Python312/python.exe" -m pytest tests/ -v`.

---

## Stage 5a — Catalog + tier-array infrastructure

**Goal:** Build the catalog → arrays → global material → shader → splat path end-to-end with `--mode hard` splats. Output: scale_demo renders with the new system but visually identical to today (regression check).

### Task 5a.1: Write the biome catalog JSON

**Files:**
- Create: `D:/assets/world 4/the world 4/worlds/scale_demo/biome_catalog.json`

- [ ] **Step 1: Write the catalog**

Create the file with this exact content (mind UTF-8, LF):

```json
{
  "schema_version": 1,
  "tiers": [
    {"name": "standard", "resolution": 1024},
    {"name": "hero",     "resolution": 4096}
  ],
  "slots": ["ground", "mid", "rock"],
  "maps":  ["albedo", "normal", "roughness", "ao"],
  "biomes": [
    {
      "name": "forest",
      "kit_dir": "materials/anchor_v2",
      "slots": {
        "ground": {"source": "scrub_dense",   "tier": "hero"},
        "mid":    {"source": "tundra_lichen", "tier": "standard"},
        "rock":   {"source": "rocky_slope",   "tier": "hero"}
      }
    },
    {
      "name": "alpine",
      "kit_dir": "materials/biome_alpine",
      "slots": {
        "ground": {"source": "ground", "tier": "standard"},
        "mid":    {"source": "mid",    "tier": "standard"},
        "rock":   {"source": "rock",   "tier": "standard"}
      }
    },
    {
      "name": "desert",
      "kit_dir": "materials/biome_desert",
      "slots": {
        "ground": {"source": "ground", "tier": "standard"},
        "mid":    {"source": "mid",    "tier": "standard"},
        "rock":   {"source": "rock",   "tier": "standard"}
      }
    },
    {
      "name": "rocky",
      "kit_dir": "materials/biome_rocky",
      "slots": {
        "ground": {"source": "ground", "tier": "standard"},
        "mid":    {"source": "mid",    "tier": "standard"},
        "rock":   {"source": "rock",   "tier": "standard"}
      }
    },
    {
      "name": "wetland",
      "kit_dir": "materials/biome_wetland",
      "slots": {
        "ground": {"source": "ground", "tier": "standard"},
        "mid":    {"source": "mid",    "tier": "standard"},
        "rock":   {"source": "rock",   "tier": "standard"}
      }
    }
  ]
}
```

- [ ] **Step 2: Verify it parses as valid JSON + UTF-8**

```bash
"C:/Program Files/Python312/python.exe" -c "import json; d = json.loads(open(r'D:/assets/world 4/the world 4/worlds/scale_demo/biome_catalog.json','rb').read().decode('utf-8')); print('biomes:', len(d['biomes']))"
```

Expected output: `biomes: 5`

- [ ] **Step 3: Commit**

```bash
git -C "D:/assets/world 4" add "the world 4/worlds/scale_demo/biome_catalog.json"
git -C "D:/assets/world 4" commit -m "axis6: add biome catalog schema (5 biomes, 2 tiers)"
```

### Task 5a.2: Write the catalog loader/validator + tests

**Files:**
- Create: `D:/assets/world 4/pipeline/biome_catalog.py`
- Create: `D:/assets/world 4/tests/conftest.py`
- Create: `D:/assets/world 4/tests/test_biome_catalog.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/conftest.py`:

```python
"""pytest config for W4 pipeline tests."""
from __future__ import annotations
import sys
from pathlib import Path

# Add pipeline/ to sys.path so tests can import directly.
PIPELINE = Path(__file__).resolve().parents[1] / "pipeline"
sys.path.insert(0, str(PIPELINE))
```

Create `tests/test_biome_catalog.py`:

```python
"""Tests for pipeline.biome_catalog (catalog loader/validator)."""
from __future__ import annotations
import json
import pytest
from pathlib import Path

import biome_catalog as bc


def write_catalog(tmp_path: Path, data: dict) -> Path:
    p = tmp_path / "biome_catalog.json"
    p.write_text(json.dumps(data), encoding="utf-8", newline="\n")
    return p


def minimal_catalog() -> dict:
    return {
        "schema_version": 1,
        "tiers": [{"name": "standard", "resolution": 1024}],
        "slots": ["ground", "mid", "rock"],
        "maps":  ["albedo", "normal", "roughness", "ao"],
        "biomes": [{
            "name": "forest",
            "kit_dir": "materials/anchor_v2",
            "slots": {
                "ground": {"source": "scrub_dense",   "tier": "standard"},
                "mid":    {"source": "tundra_lichen", "tier": "standard"},
                "rock":   {"source": "rocky_slope",   "tier": "standard"},
            },
        }],
    }


def test_load_minimal(tmp_path: Path):
    p = write_catalog(tmp_path, minimal_catalog())
    cat = bc.load_catalog(p)
    assert cat.biome_names() == ["forest"]
    assert cat.tier_names() == ["standard"]


def test_layer_index_is_stable(tmp_path: Path):
    data = minimal_catalog()
    data["biomes"].append({
        "name": "alpine",
        "kit_dir": "materials/biome_alpine",
        "slots": {
            "ground": {"source": "ground", "tier": "standard"},
            "mid":    {"source": "mid",    "tier": "standard"},
            "rock":   {"source": "rock",   "tier": "standard"},
        },
    })
    p = write_catalog(tmp_path, data)
    cat = bc.load_catalog(p)
    # Layers laid out per tier in (biome, slot) iteration order.
    assert cat.layer_index("forest", "ground", "standard") is None  # hero, not standard
    # forest has all-hero in minimal_catalog override below; in this expanded
    # case forest is all-standard. So layers 0,1,2 are forest ground/mid/rock.
    assert cat.layer_index("forest", "mid", "standard") == 1
    assert cat.layer_index("alpine", "ground", "standard") == 3


def test_rejects_unknown_tier(tmp_path: Path):
    data = minimal_catalog()
    data["biomes"][0]["slots"]["ground"]["tier"] = "bogus"
    p = write_catalog(tmp_path, data)
    with pytest.raises(bc.CatalogError, match="unknown tier"):
        bc.load_catalog(p)


def test_rejects_missing_slot(tmp_path: Path):
    data = minimal_catalog()
    del data["biomes"][0]["slots"]["mid"]
    p = write_catalog(tmp_path, data)
    with pytest.raises(bc.CatalogError, match="missing slot"):
        bc.load_catalog(p)


def test_slot_kit_path(tmp_path: Path):
    p = write_catalog(tmp_path, minimal_catalog())
    cat = bc.load_catalog(p)
    # For forest/mid the source is "tundra_lichen", kit_dir "materials/anchor_v2"
    # → "materials/anchor_v2/tundra_lichen"
    assert cat.slot_kit_path("forest", "mid") == "materials/anchor_v2/tundra_lichen"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
"C:/Program Files/Python312/python.exe" -m pytest "D:/assets/world 4/tests/test_biome_catalog.py" -v
```

Expected: collection error or `ModuleNotFoundError: No module named 'biome_catalog'`.

- [ ] **Step 3: Write the catalog loader**

Create `pipeline/biome_catalog.py`:

```python
"""Biome catalog loader/validator for the W4 transitions pipeline.

The catalog declares every biome that exists in a world, which slots
each biome has, and which tier (resolution class) each slot lives in.
It is the single source of truth consumed by build_biome_arrays.py,
build_tile_splats.py, and ScaleWorld at runtime.

Layer index policy:
- Within a tier, layers are laid out in (biome, slot) iteration order
  from the catalog's biome list. Biome A's slots come before biome B's.
- A given (biome, slot) pair has a stable layer index within its tier.
- Layer index is None if the (biome, slot) is not in the requested tier.
"""
from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path


class CatalogError(ValueError):
    pass


@dataclass(frozen=True)
class Tier:
    name: str
    resolution: int


@dataclass(frozen=True)
class SlotEntry:
    source: str   # subdirectory under kit_dir holding the PBR maps
    tier: str     # tier name (must match one of Catalog.tiers)


@dataclass(frozen=True)
class Biome:
    name: str
    kit_dir: str
    slots: dict[str, SlotEntry]  # slot_name -> SlotEntry


@dataclass(frozen=True)
class Catalog:
    schema_version: int
    tiers: list[Tier]
    slot_names: list[str]
    map_names: list[str]
    biomes: list[Biome]

    def biome_names(self) -> list[str]:
        return [b.name for b in self.biomes]

    def tier_names(self) -> list[str]:
        return [t.name for t in self.tiers]

    def tier_by_name(self, name: str) -> Tier:
        for t in self.tiers:
            if t.name == name:
                return t
        raise CatalogError(f"unknown tier: {name}")

    def biome_by_name(self, name: str) -> Biome:
        for b in self.biomes:
            if b.name == name:
                return b
        raise CatalogError(f"unknown biome: {name}")

    def layer_index(self, biome_name: str, slot_name: str, tier_name: str) -> int | None:
        """Layer index for a given biome+slot within a tier.

        Returns None if the biome's slot lives in a different tier.
        Order: walk biomes in catalog order, slots in catalog order,
        count only those in `tier_name`.
        """
        idx = 0
        for b in self.biomes:
            for s_name in self.slot_names:
                if s_name not in b.slots:
                    continue
                s = b.slots[s_name]
                if s.tier != tier_name:
                    continue
                if b.name == biome_name and s_name == slot_name:
                    return idx
                idx += 1
        return None

    def slot_kit_path(self, biome_name: str, slot_name: str) -> str:
        b = self.biome_by_name(biome_name)
        if slot_name not in b.slots:
            raise CatalogError(f"biome {biome_name!r} has no slot {slot_name!r}")
        return f"{b.kit_dir}/{b.slots[slot_name].source}"

    def all_slot_records(self) -> list[tuple[str, str, str, int]]:
        """Yield (biome, slot, tier, layer_index) for every concrete slot."""
        out = []
        for tier in self.tiers:
            idx = 0
            for b in self.biomes:
                for s_name in self.slot_names:
                    if s_name not in b.slots:
                        continue
                    s = b.slots[s_name]
                    if s.tier != tier.name:
                        continue
                    out.append((b.name, s_name, tier.name, idx))
                    idx += 1
        return out


def load_catalog(path: Path | str) -> Catalog:
    raw = Path(path).read_text(encoding="utf-8")
    data = json.loads(raw)
    return _parse(data, source=str(path))


def _parse(data: dict, source: str = "<dict>") -> Catalog:
    try:
        tiers = [Tier(name=t["name"], resolution=int(t["resolution"]))
                 for t in data["tiers"]]
        tier_names = {t.name for t in tiers}
        slot_names = list(data["slots"])
        map_names = list(data["maps"])
        biomes = []
        for bdata in data["biomes"]:
            slots: dict[str, SlotEntry] = {}
            for slot_name in slot_names:
                if slot_name not in bdata["slots"]:
                    raise CatalogError(
                        f"biome {bdata['name']!r} missing slot {slot_name!r}")
                s = bdata["slots"][slot_name]
                if s["tier"] not in tier_names:
                    raise CatalogError(
                        f"biome {bdata['name']!r} slot {slot_name!r}: "
                        f"unknown tier {s['tier']!r}")
                slots[slot_name] = SlotEntry(source=s["source"], tier=s["tier"])
            biomes.append(Biome(name=bdata["name"], kit_dir=bdata["kit_dir"],
                                slots=slots))
        return Catalog(
            schema_version=int(data["schema_version"]),
            tiers=tiers, slot_names=slot_names, map_names=map_names,
            biomes=biomes,
        )
    except KeyError as e:
        raise CatalogError(f"{source}: missing required key {e}") from e
```

- [ ] **Step 4: Re-run tests to verify they pass**

```bash
"C:/Program Files/Python312/python.exe" -m pytest "D:/assets/world 4/tests/test_biome_catalog.py" -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git -C "D:/assets/world 4" add pipeline/biome_catalog.py tests/conftest.py tests/test_biome_catalog.py
git -C "D:/assets/world 4" commit -m "axis6: biome_catalog loader/validator + tests"
```

### Task 5a.3: Verify the real catalog loads + sanity-check layer indices

**Files:**
- Test: ad-hoc verification command (no file written)

- [ ] **Step 1: Load the real catalog and print layer assignments**

```bash
"C:/Program Files/Python312/python.exe" -c "
import sys; sys.path.insert(0, r'D:/assets/world 4/pipeline')
from pathlib import Path
from biome_catalog import load_catalog
cat = load_catalog(r'D:/assets/world 4/the world 4/worlds/scale_demo/biome_catalog.json')
print('biomes:', cat.biome_names())
print('tiers:', cat.tier_names())
print('---')
for biome, slot, tier, layer in cat.all_slot_records():
    print(f'  {biome:8} {slot:6} {tier:8} layer={layer}')
"
```

Expected output (exact):
```
biomes: ['forest', 'alpine', 'desert', 'rocky', 'wetland']
tiers: ['standard', 'hero']
---
  forest   mid    standard layer=0
  alpine   ground standard layer=1
  alpine   mid    standard layer=2
  alpine   rock   standard layer=3
  desert   ground standard layer=4
  desert   mid    standard layer=5
  desert   rock   standard layer=6
  rocky    ground standard layer=7
  rocky    mid    standard layer=8
  rocky    rock   standard layer=9
  wetland  ground standard layer=10
  wetland  mid    standard layer=11
  wetland  rock   standard layer=12
  forest   ground hero     layer=0
  forest   rock   hero     layer=1
```

If the order or counts differ, the catalog or loader is wrong — go back to 5a.1 or 5a.2.

- [ ] **Step 2: Commit (no file changes, but the verification proves the catalog)**

No commit needed for this step; it's a sanity check only.

### Task 5a.4: Write the texture array builder (Python side) + tests

**Files:**
- Create: `D:/assets/world 4/pipeline/build_biome_arrays.py`
- Create: `D:/assets/world 4/tests/test_build_biome_arrays.py`

The Python script's job: read the catalog, validate that every required PBR map exists on disk, build a per-tier per-map manifest, and emit a single `layer_manifest.json` describing the layout. The actual `Texture2DArray.tres` files are emitted by a Godot-side tool we'll add next; this Python script does the manifest + per-layer file listing.

- [ ] **Step 1: Write failing tests**

Create `tests/test_build_biome_arrays.py`:

```python
"""Tests for build_biome_arrays.build_manifest (the Python half)."""
from __future__ import annotations
import json
from pathlib import Path
import pytest

import build_biome_arrays as bba
import biome_catalog as bc


def make_pbr_kit(root: Path, *, size: int = 8) -> None:
    """Create dummy 4-map PBR files in `root` so on-disk checks pass."""
    from PIL import Image
    root.mkdir(parents=True, exist_ok=True)
    for name in ("albedo", "normal", "roughness", "ao"):
        Image.new("RGB", (size, size), (128, 128, 128)).save(root / f"{name}.png")


def write_catalog(tmp_path: Path, w4_root: Path) -> Path:
    data = {
        "schema_version": 1,
        "tiers": [
            {"name": "standard", "resolution": 8},
            {"name": "hero",     "resolution": 16},
        ],
        "slots": ["ground", "mid", "rock"],
        "maps":  ["albedo", "normal", "roughness", "ao"],
        "biomes": [
            {
                "name": "forest", "kit_dir": "kitA",
                "slots": {
                    "ground": {"source": "g", "tier": "hero"},
                    "mid":    {"source": "m", "tier": "standard"},
                    "rock":   {"source": "r", "tier": "hero"},
                },
            },
            {
                "name": "alpine", "kit_dir": "kitB",
                "slots": {
                    "ground": {"source": "g", "tier": "standard"},
                    "mid":    {"source": "m", "tier": "standard"},
                    "rock":   {"source": "r", "tier": "standard"},
                },
            },
        ],
    }
    p = tmp_path / "biome_catalog.json"
    p.write_text(json.dumps(data), encoding="utf-8", newline="\n")
    # Create the PBR kits referenced by the catalog under w4_root.
    make_pbr_kit(w4_root / "kitA" / "g", size=16)
    make_pbr_kit(w4_root / "kitA" / "m", size=8)
    make_pbr_kit(w4_root / "kitA" / "r", size=16)
    make_pbr_kit(w4_root / "kitB" / "g", size=8)
    make_pbr_kit(w4_root / "kitB" / "m", size=8)
    make_pbr_kit(w4_root / "kitB" / "r", size=8)
    return p


def test_manifest_lists_layers_per_tier(tmp_path: Path):
    w4 = tmp_path / "w4"
    catalog_path = write_catalog(tmp_path, w4)
    cat = bc.load_catalog(catalog_path)
    m = bba.build_manifest(cat, w4_root=w4)
    assert sorted(m["tiers"].keys()) == ["hero", "standard"]
    # standard tier: forest/mid (layer 0), alpine/ground (1), alpine/mid (2), alpine/rock (3)
    std = m["tiers"]["standard"]
    assert [r["layer"] for r in std["layers"]] == [0, 1, 2, 3]
    assert [r["biome"] for r in std["layers"]] == ["forest", "alpine", "alpine", "alpine"]
    # hero tier: forest/ground (0), forest/rock (1)
    hero = m["tiers"]["hero"]
    assert [r["layer"] for r in hero["layers"]] == [0, 1]
    assert hero["resolution"] == 16


def test_manifest_resolution_mismatch_raises(tmp_path: Path):
    w4 = tmp_path / "w4"
    catalog_path = write_catalog(tmp_path, w4)
    # Corrupt one kit's size so it doesn't match its tier resolution.
    from PIL import Image
    bad = w4 / "kitB" / "g" / "albedo.png"
    Image.new("RGB", (32, 32), (0, 0, 0)).save(bad)
    cat = bc.load_catalog(catalog_path)
    with pytest.raises(bba.BuildError, match="resolution"):
        bba.build_manifest(cat, w4_root=w4)


def test_manifest_missing_map_raises(tmp_path: Path):
    w4 = tmp_path / "w4"
    catalog_path = write_catalog(tmp_path, w4)
    # Remove one map file.
    (w4 / "kitA" / "g" / "ao.png").unlink()
    cat = bc.load_catalog(catalog_path)
    with pytest.raises(bba.BuildError, match="missing.*ao.png"):
        bba.build_manifest(cat, w4_root=w4)


def test_write_manifest_roundtrip(tmp_path: Path):
    w4 = tmp_path / "w4"
    catalog_path = write_catalog(tmp_path, w4)
    cat = bc.load_catalog(catalog_path)
    m = bba.build_manifest(cat, w4_root=w4)
    out = tmp_path / "layer_manifest.json"
    bba.write_manifest(m, out)
    reloaded = json.loads(out.read_text(encoding="utf-8"))
    assert reloaded == m
```

- [ ] **Step 2: Run tests, verify they fail**

```bash
"C:/Program Files/Python312/python.exe" -m pytest "D:/assets/world 4/tests/test_build_biome_arrays.py" -v
```

Expected: `ModuleNotFoundError: No module named 'build_biome_arrays'`.

- [ ] **Step 3: Write the manifest builder**

Create `pipeline/build_biome_arrays.py`:

```python
"""Builds a layer manifest from a biome catalog.

Outputs a JSON manifest enumerating, per tier, which PBR files
correspond to which layer index. This manifest is consumed by:

- A Godot-side .tres emitter that builds Texture2DArray resources.
- ScaleWorld.gd at runtime, to map (biome, slot) -> (tier, layer).

We deliberately do NOT pack the texture array bytes here in Python.
Godot owns the import + compression path; we just hand it a layered
file list. See write_global_terrain_material.py for the Godot side.

Usage (CLI):
    python build_biome_arrays.py \\
        --catalog "D:/assets/world 4/the world 4/worlds/scale_demo/biome_catalog.json" \\
        --w4-root "D:/assets/world 4/the world 4" \\
        --out "D:/assets/world 4/the world 4/worlds/scale_demo/arrays/layer_manifest.json"
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from PIL import Image

import biome_catalog as bc


class BuildError(RuntimeError):
    pass


def build_manifest(cat: bc.Catalog, w4_root: Path | str) -> dict:
    w4 = Path(w4_root)
    tiers_out: dict[str, dict] = {}
    for tier in cat.tiers:
        layers = []
        for biome, slot, tier_name, layer in cat.all_slot_records():
            if tier_name != tier.name:
                continue
            kit_path = w4 / cat.slot_kit_path(biome, slot)
            entry = {"biome": biome, "slot": slot, "layer": layer, "maps": {}}
            for map_name in cat.map_names:
                file_path = kit_path / f"{map_name}.png"
                if not file_path.is_file():
                    raise BuildError(
                        f"missing PBR map: {file_path} "
                        f"(biome={biome}, slot={slot}, map={map_name})")
                with Image.open(file_path) as im:
                    w, h = im.size
                if w != tier.resolution or h != tier.resolution:
                    raise BuildError(
                        f"resolution mismatch in {file_path}: "
                        f"expected {tier.resolution}x{tier.resolution}, got {w}x{h}")
                rel = file_path.relative_to(w4).as_posix()
                entry["maps"][map_name] = rel
            layers.append(entry)
        tiers_out[tier.name] = {
            "resolution": tier.resolution,
            "layers": layers,
        }
    return {
        "schema_version": 1,
        "tiers": tiers_out,
    }


def write_manifest(manifest: dict, out_path: Path | str) -> None:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2) + "\n",
                   encoding="utf-8", newline="\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--w4-root", required=True,
                    help="Path to the Godot project root ('the world 4')")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    cat = bc.load_catalog(args.catalog)
    m = build_manifest(cat, w4_root=args.w4_root)
    write_manifest(m, args.out)
    n = sum(len(t["layers"]) for t in m["tiers"].values())
    print(f"wrote {args.out}  ({n} layers across {len(m['tiers'])} tiers)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Re-run tests, verify they pass**

```bash
"C:/Program Files/Python312/python.exe" -m pytest "D:/assets/world 4/tests/test_build_biome_arrays.py" -v
```

Expected: 4 passed.

- [ ] **Step 5: Run against the real catalog and inspect the manifest**

```bash
"C:/Program Files/Python312/python.exe" "D:/assets/world 4/pipeline/build_biome_arrays.py" \
  --catalog "D:/assets/world 4/the world 4/worlds/scale_demo/biome_catalog.json" \
  --w4-root "D:/assets/world 4/the world 4" \
  --out "D:/assets/world 4/the world 4/worlds/scale_demo/arrays/layer_manifest.json"
"C:/Program Files/Python312/python.exe" -c "
import json
m = json.loads(open(r'D:/assets/world 4/the world 4/worlds/scale_demo/arrays/layer_manifest.json','r',encoding='utf-8').read())
for tier, t in m['tiers'].items():
    print(f'{tier}: {len(t[\"layers\"])} layers @ {t[\"resolution\"]}x{t[\"resolution\"]}')
"
```

Expected output:
```
wrote D:/assets/world 4/the world 4/worlds/scale_demo/arrays/layer_manifest.json  (15 layers across 2 tiers)
standard: 13 layers @ 1024x1024
hero: 2 layers @ 4096x4096
```

If you get a resolution mismatch error: one of the existing biome PBR files isn't at the expected resolution. Inspect the failing path; if it's an existing anchor_v2 file, that's an unexpected source-data issue — stop and report.

- [ ] **Step 6: Commit**

```bash
git -C "D:/assets/world 4" add pipeline/build_biome_arrays.py tests/test_build_biome_arrays.py "the world 4/worlds/scale_demo/arrays/layer_manifest.json"
git -C "D:/assets/world 4" commit -m "axis6: layer manifest builder + tests"
```

### Task 5a.5: Runtime Texture2DArray construction in ScaleWorld

**Architectural change from the original plan:** Godot 4.5 doesn't
cleanly serialize a `Texture2DArray` to `.tres` with referenced
external images (probe confirmed: `_images = Array[Image]([null, ...])`
even with `FLAG_BUNDLE_RESOURCES`). The supported paths are (1) editor
sprite-sheet import or (2) runtime construction.

We pick (2). At scene init, ScaleWorld reads `layer_manifest.json`,
loads each layer's PNG as a `Texture2D`, calls
`Texture2DArray.create_from_images([img, ...])`, and sets the 8
resulting arrays as shader_parameters on the global terrain material.

Cost: ~50-200ms one-time at scene init; acceptable.

Implementation moves entirely into Task 5a.9 (ScaleWorld wiring). This
task is a no-op now — the manifest from 5a.4 is the contract; no
intermediate `.tres` files needed.

We can't unit-test this — Godot owns the import pipeline. We write a Python script that emits a `.tres` per (tier, map) that references the layer PNGs in catalog order; Godot's importer materializes the array on `--import`.

**Files:**
- Create: `D:/assets/world 4/pipeline/write_array_tres.py`

- [ ] **Step 1: Write the emitter**

Create `pipeline/write_array_tres.py`:

```python
"""Emit Godot Texture2DArray .tres files from layer_manifest.json.

For each (tier, map_name) in the manifest, writes a .tres at
`{out_dir}/{tier}_{map_name}.tres` that references the layer PNGs in
layer-index order. Godot's --import pass packs them into a runtime
Texture2DArray.

Usage:
    python write_array_tres.py \\
        --manifest "D:/assets/world 4/the world 4/worlds/scale_demo/arrays/layer_manifest.json" \\
        --w4-root  "D:/assets/world 4/the world 4" \\
        --out-dir  "D:/assets/world 4/the world 4/worlds/scale_demo/arrays"

Godot 4.5 reference: Texture2DArray resource expects `_data` to be
an array of Image-loadable Texture2D ExtResources, layered in order.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path


TRES_TEMPLATE = '''[gd_resource type="Texture2DArray" load_steps={steps} format=3]

{ext_lines}

[resource]
{data_line}
'''


def emit_array_tres(layers_sorted: list[dict], map_name: str, out_path: Path) -> None:
    # Each layer references a Texture2D ExtResource.
    ext_lines = []
    ids = []
    for layer in layers_sorted:
        ident = f"layer{layer['layer']}"
        rel = layer["maps"][map_name]
        ext_lines.append(
            f'[ext_resource type="Texture2D" path="res://{rel}" id="{ident}"]'
        )
        ids.append(ident)
    if not ids:
        # Empty array — still valid resource, just zero layers.
        data_line = "_data = []"
    else:
        joined = ", ".join(f'ExtResource("{i}")' for i in ids)
        data_line = f"_data = [{joined}]"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = TRES_TEMPLATE.format(
        steps=len(ext_lines) + 1,
        ext_lines="\n".join(ext_lines),
        data_line=data_line,
    )
    out_path.write_text(text, encoding="utf-8", newline="\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--w4-root", required=True)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    out_dir = Path(args.out_dir)
    written = []
    # Pull map names from the first non-empty layer in any tier.
    map_names: list[str] = []
    for tdata in manifest["tiers"].values():
        if tdata["layers"]:
            map_names = list(tdata["layers"][0]["maps"].keys())
            break
    if not map_names:
        raise SystemExit("manifest has no layers — nothing to emit")
    for tier_name, tdata in manifest["tiers"].items():
        layers_sorted = sorted(tdata["layers"], key=lambda r: r["layer"])
        for map_name in map_names:
            out = out_dir / f"{tier_name}_{map_name}.tres"
            emit_array_tres(layers_sorted, map_name, out)
            written.append(out)
    for p in written:
        print(f"wrote {p}")
    print(f"\n{len(written)} .tres files written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run the emitter against the real manifest**

```bash
"C:/Program Files/Python312/python.exe" "D:/assets/world 4/pipeline/write_array_tres.py" \
  --manifest "D:/assets/world 4/the world 4/worlds/scale_demo/arrays/layer_manifest.json" \
  --w4-root  "D:/assets/world 4/the world 4" \
  --out-dir  "D:/assets/world 4/the world 4/worlds/scale_demo/arrays"
```

Expected: 8 .tres files written (`standard_albedo.tres`, `standard_normal.tres`, `standard_roughness.tres`, `standard_ao.tres`, `hero_albedo.tres`, `hero_normal.tres`, `hero_roughness.tres`, `hero_ao.tres`).

- [ ] **Step 3: Verify Godot can import them**

```bash
"C:/Godot/Godot_v4.5-stable_win64.exe" --headless --path "D:/assets/world 4/the world 4" --import 2>&1 | tail -30
```

Expected: no `ERROR:` lines mentioning the new `.tres` files. If Godot logs `unrecognized property _data` or `failed to load Texture2DArray`, the TRES_TEMPLATE may need adjustment for the exact Godot 4.5 resource schema — record the error, inspect the .import dir, and adjust the template's `_data` property name or format accordingly.

- [ ] **Step 4: Commit**

```bash
git -C "D:/assets/world 4" add pipeline/write_array_tres.py "the world 4/worlds/scale_demo/arrays/"
git -C "D:/assets/world 4" commit -m "axis6: emit Texture2DArray .tres per (tier, map)"
```

### Task 5a.6: Write the hard-mode splat builder + tests

**Files:**
- Create: `D:/assets/world 4/pipeline/build_tile_splats.py`
- Create: `D:/assets/world 4/tests/test_build_tile_splats.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_build_tile_splats.py`:

```python
"""Tests for build_tile_splats (mode=hard)."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
from PIL import Image
import pytest

import build_tile_splats as bts


def make_world(tmp_path: Path) -> Path:
    """Build a 2x2 scale_demo-style tile world. Each tile dir has a meta.json
    with a biome field. Return the world bundle dir."""
    bundle = tmp_path / "scale_demo"
    bundle.mkdir()
    layout = {
        (0, 0): "wetland", (1, 0): "desert",
        (0, 1): "forest",  (1, 1): "alpine",
    }
    for (tx, tz), biome in layout.items():
        td = bundle / "tiles" / f"tile_{tx}_{tz}"
        td.mkdir(parents=True)
        meta = {"tile_x": tx, "tile_z": tz, "tile_size_m": 256.0, "biome": biome}
        (td / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return bundle


def fake_manifest():
    return {
        "schema_version": 1,
        "tiers": {
            "standard": {"resolution": 1024, "layers": [
                {"biome": "alpine",  "slot": "ground", "layer": 0, "maps": {}},
                {"biome": "alpine",  "slot": "mid",    "layer": 1, "maps": {}},
                {"biome": "alpine",  "slot": "rock",   "layer": 2, "maps": {}},
                {"biome": "desert",  "slot": "ground", "layer": 3, "maps": {}},
                {"biome": "desert",  "slot": "mid",    "layer": 4, "maps": {}},
                {"biome": "desert",  "slot": "rock",   "layer": 5, "maps": {}},
                {"biome": "forest",  "slot": "mid",    "layer": 6, "maps": {}},
                {"biome": "wetland", "slot": "ground", "layer": 7, "maps": {}},
                {"biome": "wetland", "slot": "mid",    "layer": 8, "maps": {}},
                {"biome": "wetland", "slot": "rock",   "layer": 9, "maps": {}},
            ]},
            "hero":     {"resolution": 4096, "layers": [
                {"biome": "forest", "slot": "ground", "layer": 0, "maps": {}},
                {"biome": "forest", "slot": "rock",   "layer": 1, "maps": {}},
            ]},
        },
    }


def test_hard_mode_writes_per_tile_splat_and_meta(tmp_path: Path):
    bundle = make_world(tmp_path)
    bts.build_splats(
        bundle_dir=bundle,
        manifest=fake_manifest(),
        mode="hard",
        splat_size=8,
        feather_width_m=0.0,
    )
    for tx, tz in [(0,0),(1,0),(0,1),(1,1)]:
        splat_path = bundle / "tiles" / f"tile_{tx}_{tz}" / "splat.png"
        meta_path  = bundle / "tiles" / f"tile_{tx}_{tz}" / "splat_meta.json"
        assert splat_path.is_file()
        assert meta_path.is_file()
        # Splat must be RGBA8 at splat_size.
        with Image.open(splat_path) as im:
            assert im.size == (8, 8)
            assert im.mode == "RGBA"


def test_hard_mode_splat_is_pure_first_channel(tmp_path: Path):
    bundle = make_world(tmp_path)
    bts.build_splats(bundle_dir=bundle, manifest=fake_manifest(),
                     mode="hard", splat_size=8, feather_width_m=0.0)
    splat_path = bundle / "tiles" / "tile_0_0" / "splat.png"
    arr = np.asarray(Image.open(splat_path).convert("RGBA"))
    # Every pixel: R=255, G=B=A=0 (single contributing layer).
    assert (arr[..., 0] == 255).all()
    assert (arr[..., 1] == 0).all()
    assert (arr[..., 2] == 0).all()
    assert (arr[..., 3] == 0).all()


def test_hard_mode_splat_meta_lists_one_layer_per_slot(tmp_path: Path):
    bundle = make_world(tmp_path)
    bts.build_splats(bundle_dir=bundle, manifest=fake_manifest(),
                     mode="hard", splat_size=8, feather_width_m=0.0)
    # Tile (0,0) is wetland — slots ground/mid/rock at layers 7,8,9 (standard).
    meta = json.loads((bundle / "tiles" / "tile_0_0" / "splat_meta.json").read_text())
    # We only pin channel 0 (the only contributor) in hard mode; the slot
    # within-biome ground/mid/rock blend is still done inside the shader by
    # slope. So channel 0 references the BIOME, not a specific slot — and
    # the manifest entry for channel 0 is the biome's ground slot (slot 0).
    assert len(meta["channels"]) == 4
    c0 = meta["channels"][0]
    assert c0["biome"] == "wetland"
    assert c0["tier"]  == "standard"
    # Channels 1..3 are empty (weight 0).
    for i in range(1, 4):
        assert meta["channels"][i]["biome"] is None


def test_hard_mode_handles_unknown_biome(tmp_path: Path):
    bundle = make_world(tmp_path)
    # Corrupt one tile to reference a biome not in the manifest.
    bad_meta = bundle / "tiles" / "tile_0_0" / "meta.json"
    data = json.loads(bad_meta.read_text())
    data["biome"] = "tropical"  # not in fake_manifest
    bad_meta.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(bts.SplatError, match="tropical"):
        bts.build_splats(bundle_dir=bundle, manifest=fake_manifest(),
                         mode="hard", splat_size=8, feather_width_m=0.0)
```

- [ ] **Step 2: Run tests, verify they fail**

```bash
"C:/Program Files/Python312/python.exe" -m pytest "D:/assets/world 4/tests/test_build_tile_splats.py" -v
```

Expected: `ModuleNotFoundError: No module named 'build_tile_splats'`.

- [ ] **Step 3: Write the hard-mode splat builder**

Create `pipeline/build_tile_splats.py`:

```python
"""Build per-tile splat textures + meta from a biome catalog + tile assignments.

For each tile under `<bundle_dir>/tiles/tile_X_Z/`:
- Read the tile's meta.json, which has a "biome" field (added by
  assign_biomes_scale_demo.py).
- Write a splat.png (RGBA8) at splat_size x splat_size.
- Write a splat_meta.json describing what the 4 RGBA channels mean
  (which biome / tier / which slot the within-biome blend uses).

Modes:
- "hard"    : every pixel = (255, 0, 0, 0), channel 0 names the tile's
              own biome. Used as the regression check for the array path.
- "feather" : pixels within feather_width_m of a tile edge adjacent to a
              different biome ramp from this biome -> neighbor. (Stage 5b)
- "noise"   : like feather, with noise jitter on the boundary. (Stage 5b)

Usage:
    python build_tile_splats.py \\
        --bundle  "D:/assets/world 4/the world 4/worlds/scale_demo" \\
        --manifest "D:/assets/world 4/the world 4/worlds/scale_demo/arrays/layer_manifest.json" \\
        --mode hard \\
        --splat-size 64
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image


class SplatError(RuntimeError):
    pass


def _biome_to_record(manifest: dict, biome: str) -> Optional[dict]:
    """Find the ground-slot record for a biome — used to identify which
    tier the biome's primary representation lives in. Returns dict or
    None if not found."""
    for tier_name, tdata in manifest["tiers"].items():
        for layer in tdata["layers"]:
            if layer["biome"] == biome and layer["slot"] == "ground":
                return {"tier": tier_name, "layer": layer["layer"], "biome": biome}
    return None


def build_splats(*, bundle_dir: Path | str, manifest: dict,
                 mode: str, splat_size: int, feather_width_m: float) -> None:
    if mode != "hard":
        raise NotImplementedError(f"mode={mode!r} not implemented in stage 5a")
    bundle = Path(bundle_dir)
    tiles_dir = bundle / "tiles"
    for tile_dir in sorted(tiles_dir.iterdir()):
        if not tile_dir.is_dir() or not tile_dir.name.startswith("tile_"):
            continue
        meta_path = tile_dir / "meta.json"
        if not meta_path.is_file():
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        biome = meta.get("biome")
        if not biome:
            raise SplatError(f"{tile_dir}: tile meta has no biome field")
        rec = _biome_to_record(manifest, biome)
        if rec is None:
            raise SplatError(
                f"{tile_dir}: biome {biome!r} not found in manifest")
        # Hard mode: channel 0 = this biome at weight 1.0; channels 1-3 empty.
        arr = np.zeros((splat_size, splat_size, 4), dtype=np.uint8)
        arr[..., 0] = 255
        Image.fromarray(arr, mode="RGBA").save(tile_dir / "splat.png")
        # Splat meta — one channel populated.
        ch_meta = [{"biome": biome, "tier": rec["tier"]}]
        for _ in range(3):
            ch_meta.append({"biome": None, "tier": None})
        splat_meta = {"channels": ch_meta, "splat_size": splat_size,
                      "mode": mode}
        (tile_dir / "splat_meta.json").write_text(
            json.dumps(splat_meta, indent=2) + "\n",
            encoding="utf-8", newline="\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", required=True,
                    help="Path to the world bundle (e.g. worlds/scale_demo)")
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--mode", default="hard", choices=["hard", "feather", "noise"])
    ap.add_argument("--splat-size", type=int, default=64)
    ap.add_argument("--feather-width-m", type=float, default=32.0)
    args = ap.parse_args()

    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    build_splats(
        bundle_dir=args.bundle, manifest=manifest, mode=args.mode,
        splat_size=args.splat_size, feather_width_m=args.feather_width_m,
    )
    print(f"splats: mode={args.mode} size={args.splat_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Re-run tests, verify they pass**

```bash
"C:/Program Files/Python312/python.exe" -m pytest "D:/assets/world 4/tests/test_build_tile_splats.py" -v
```

Expected: 4 passed.

- [ ] **Step 5: Build splats for the real scale_demo**

```bash
"C:/Program Files/Python312/python.exe" "D:/assets/world 4/pipeline/build_tile_splats.py" \
  --bundle   "D:/assets/world 4/the world 4/worlds/scale_demo" \
  --manifest "D:/assets/world 4/the world 4/worlds/scale_demo/arrays/layer_manifest.json" \
  --mode hard --splat-size 64
"C:/Program Files/Python312/python.exe" -c "
import os
n = sum(1 for f in os.listdir(r'D:/assets/world 4/the world 4/worlds/scale_demo/tiles') if os.path.isdir(rf'D:/assets/world 4/the world 4/worlds/scale_demo/tiles/{f}'))
print('tile dirs:', n)
import json
m = json.loads(open(r'D:/assets/world 4/the world 4/worlds/scale_demo/tiles/tile_0_0/splat_meta.json','r',encoding='utf-8').read())
print('tile_0_0 channel 0:', m['channels'][0])
"
```

Expected:
```
splats: mode=hard size=64
tile dirs: 16
tile_0_0 channel 0: {'biome': 'wetland', 'tier': 'standard'}
```

- [ ] **Step 6: Commit**

```bash
git -C "D:/assets/world 4" add pipeline/build_tile_splats.py tests/test_build_tile_splats.py "the world 4/worlds/scale_demo/tiles"
git -C "D:/assets/world 4" commit -m "axis6: hard-mode splat builder + per-tile splat.png/splat_meta.json"
```

### Task 5a.7: Write the unified terrain shader (`terrain_world_v2.gdshader`)

**Files:**
- Create: `D:/assets/world 4/the world 4/shaders/terrain_world_v2.gdshader`

- [ ] **Step 1: Write the shader**

Create the shader file with this exact content:

```glsl
// W4 unified terrain shader (Axis 6 transitions).
//
// Replaces terrain_scale_v1.gdshader. Same unshaded manual-lighting model
// (PITFALLS #3 mitigation: lit PBR pipeline produces black quads at scale,
// so we run unshaded and do our own lambertian + ambient math).
//
// Per-fragment data path:
//   1. Sample splat at world UV -> 4 weights (RGBA, sum to 1.0).
//   2. For each non-zero channel:
//        - splat_layer_indices[i] encodes (tier, layer): tier in bit 31,
//          layer in bits 0..30.
//        - splat_layer_slots[i] is a float-encoded slot id (0=ground,
//          1=mid, 2=rock).
//        - Sample the appropriate Texture2DArray (standard_* or hero_*)
//          at (world_uv, layer).
//        - Apply within-biome slope blend (this biome's ground vs mid vs
//          rock based on world normal up-axis).
//   3. Weighted sum the 4 contributions.
//   4. Apply lighting (lambertian + ambient) same as terrain_scale_v1.

shader_type spatial;
render_mode unshaded, cull_back, depth_draw_opaque;

// Two-tier texture arrays
uniform sampler2DArray standard_albedo : source_color;
uniform sampler2DArray standard_normal : hint_normal;
uniform sampler2DArray standard_rough;
uniform sampler2DArray standard_ao : hint_default_white;
uniform sampler2DArray hero_albedo : source_color;
uniform sampler2DArray hero_normal : hint_normal;
uniform sampler2DArray hero_rough;
uniform sampler2DArray hero_ao : hint_default_white;

// Splat texture (per-tile, RGBA8, 4 channels = up to 4 layer weights)
uniform sampler2D splat;

// Per-tile: which (tier, layer) each splat channel references.
// Packed: tier in bit 31 (0=standard, 1=hero), layer in bits 0..30.
// A value of -1 means "no contribution" (channel weight ignored).
uniform ivec4 splat_layer_indices = ivec4(-1, -1, -1, -1);

// Per-tile: which slot each splat channel's biome uses for its
// within-biome slope-blend ground reference. Encoded as float:
// 0.0 = ground, 1.0 = mid, 2.0 = rock. For Stage 5a, all are 0.0 (ground)
// because the within-biome ground/mid/rock blend is driven by the
// 3-layer-per-biome convention applied per contributing biome.
uniform vec4 splat_layer_slots = vec4(0.0);

// Slope thresholds (within-biome ground/mid/rock blend; same as v1)
uniform float slope_ground_max : hint_range(0.0, 1.0) = 0.92;
uniform float slope_rock_max   : hint_range(0.0, 1.0) = 0.55;

uniform float world_uv_scale = 0.04;

// Albedo safety (PITFALLS #1)
uniform float albedo_luma_floor : hint_range(0.0, 0.4) = 0.08;
uniform float ao_floor          : hint_range(0.0, 1.0) = 0.72;

// In-shader sun (same as v1)
uniform vec3 sun_dir = vec3(0.30, 0.85, 0.43);
uniform vec3 sun_color : source_color = vec3(1.0, 0.96, 0.88);
uniform float sun_intensity : hint_range(0.0, 3.0) = 1.0;
uniform float lambert_floor : hint_range(0.0, 0.5) = 0.35;

// Sky/ground tint
uniform vec3 sky_tint    : source_color = vec3(0.78, 0.84, 0.92);
uniform vec3 ground_tint : source_color = vec3(0.58, 0.60, 0.55);
uniform float ambient_strength : hint_range(0.0, 2.0) = 0.45;

varying vec3 v_world_pos;
varying vec3 v_world_normal;
// Splat UV is provided as the tile-local fraction of the world position.
// ScaleWorld sets the tile origin via TILE_ORIGIN_M + TILE_SIZE_M so the
// splat covers exactly this tile in UV [0..1].
uniform vec2 tile_origin_m = vec2(0.0, 0.0);
uniform float tile_size_m  = 256.0;

void vertex() {
    v_world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
    v_world_normal = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}

vec3 luma_floor_v(vec3 color) {
    float lum = dot(color, vec3(0.2126, 0.7152, 0.0722));
    if (lum < albedo_luma_floor) {
        color += vec3(albedo_luma_floor - lum);
    }
    return clamp(color, vec3(0.0), vec3(1.0));
}

// Decode tier (high bit) + layer (low 31 bits) from packed int.
void unpack_idx(int packed, out int tier, out int layer) {
    tier  = (packed < 0) ? -1 : ((packed >> 30) & 1);
    layer = (packed < 0) ? -1 : (packed & 0x3FFFFFFF);
}

// Read one biome's contribution at a (tier, biome_layer) where
// biome_layer is the GROUND slot's layer index. Mid is +1, rock is +2.
// Returns (albedo, ao) weighted by the within-biome slope blend.
void sample_biome(int tier, int biome_ground_layer, vec2 uv, float up,
                  out vec3 albedo_out, out float ao_out) {
    int g = biome_ground_layer;
    int m = biome_ground_layer + 1;
    int r = biome_ground_layer + 2;
    vec3 ga, ma, ra;
    float go, mo, ro;
    if (tier == 1) { // hero
        ga = luma_floor_v(texture(hero_albedo, vec3(uv, float(g))).rgb);
        ma = luma_floor_v(texture(hero_albedo, vec3(uv, float(m))).rgb);
        ra = luma_floor_v(texture(hero_albedo, vec3(uv, float(r))).rgb);
        go = texture(hero_ao, vec3(uv, float(g))).r;
        mo = texture(hero_ao, vec3(uv, float(m))).r;
        ro = texture(hero_ao, vec3(uv, float(r))).r;
    } else { // standard
        ga = luma_floor_v(texture(standard_albedo, vec3(uv, float(g))).rgb);
        ma = luma_floor_v(texture(standard_albedo, vec3(uv, float(m))).rgb);
        ra = luma_floor_v(texture(standard_albedo, vec3(uv, float(r))).rgb);
        go = texture(standard_ao, vec3(uv, float(g))).r;
        mo = texture(standard_ao, vec3(uv, float(m))).r;
        ro = texture(standard_ao, vec3(uv, float(r))).r;
    }
    // Within-biome slope blend (same as terrain_scale_v1).
    float ground_w = smoothstep(slope_ground_max - 0.15, slope_ground_max, up);
    float rock_w   = 1.0 - smoothstep(slope_rock_max, slope_rock_max + 0.15, up);
    float mid_w    = max(0.0, 1.0 - ground_w - rock_w);
    float total    = max(ground_w + mid_w + rock_w, 1e-4);
    ground_w /= total; mid_w /= total; rock_w /= total;
    albedo_out = ga * ground_w + ma * mid_w + ra * rock_w;
    ao_out     = go * ground_w + mo * mid_w + ro * rock_w;
}

void fragment() {
    vec2 uv = v_world_pos.xz * world_uv_scale;
    vec3 wn = normalize(v_world_normal);
    float up = clamp(wn.y, 0.0, 1.0);

    // Splat sample. Splat covers exactly this tile in UV[0..1].
    vec2 splat_uv = (v_world_pos.xz - tile_origin_m) / tile_size_m;
    vec4 w = texture(splat, splat_uv);
    // Sum weights for normalization (splat is 0..1 per channel; we
    // tolerate slight over/undershoot from bilinear filtering).
    float wsum = max(w.r + w.g + w.b + w.a, 1e-4);
    w /= wsum;

    vec3 albedo = vec3(0.0);
    float ao = 0.0;
    for (int i = 0; i < 4; i++) {
        float wi = w[i];
        if (wi < 1e-3) {
            continue;
        }
        int tier, layer;
        unpack_idx(splat_layer_indices[i], tier, layer);
        if (tier < 0) {
            continue;
        }
        vec3 a_i;
        float ao_i;
        sample_biome(tier, layer, uv, up, a_i, ao_i);
        albedo += a_i * wi;
        ao     += ao_i * wi;
    }
    ao = clamp(ao, ao_floor, 1.0);

    // Lambertian (clamped above lambert_floor)
    vec3 sun_n = normalize(sun_dir);
    float ndl = dot(wn, sun_n);
    float lambert = max(ndl, lambert_floor);
    vec3 direct = sun_color * lambert * sun_intensity;
    vec3 ambient_color = mix(ground_tint, sky_tint, up);
    vec3 ambient = ambient_color * ambient_strength;

    vec3 lit = albedo * ao * (direct + ambient);
    lit = luma_floor_v(lit);
    ALBEDO = lit;
}
```

- [ ] **Step 2: Reimport to verify the shader parses**

```bash
"C:/Godot/Godot_v4.5-stable_win64.exe" --headless --path "D:/assets/world 4/the world 4" --import 2>&1 | grep -iE "terrain_world_v2|error" | head -20
```

Expected: zero `ERROR` lines mentioning `terrain_world_v2`. If Godot reports a shader parse error, fix syntactically and re-run.

- [ ] **Step 3: Commit**

```bash
git -C "D:/assets/world 4" add "the world 4/shaders/terrain_world_v2.gdshader"
git -C "D:/assets/world 4" commit -m "axis6: terrain_world_v2 shader (array+splat blending)"
```

### Task 5a.8: Write the global terrain material emitter + emit it

**Files:**
- Create: `D:/assets/world 4/pipeline/write_global_terrain_material.py`

- [ ] **Step 1: Write the emitter**

Create `pipeline/write_global_terrain_material.py`:

```python
"""Emit the single global terrain material .tres for the new transitions
shader. Binds the 8 Texture2DArray .tres files + lighting uniforms.

Per-tile uniforms (splat texture, splat_layer_indices, splat_layer_slots,
tile_origin_m, tile_size_m) are NOT bound here — they're set per-tile by
TileTerrain.gd via a per-instance duplicate of this material.

Usage:
    python write_global_terrain_material.py \\
        --w4-root "D:/assets/world 4/the world 4" \\
        --bundle  "worlds/scale_demo" \\
        --out     "worlds/scale_demo/material_world_v2.tres"
"""
from __future__ import annotations
import argparse
from pathlib import Path


SHADER_REL = "shaders/terrain_world_v2.gdshader"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--w4-root", required=True)
    ap.add_argument("--bundle",  required=True,
                    help="Bundle dir relative to w4-root (e.g. worlds/scale_demo)")
    ap.add_argument("--out", required=True,
                    help="Output .tres path relative to w4-root")
    args = ap.parse_args()

    w4 = Path(args.w4_root)
    arrays_dir = (Path(args.bundle) / "arrays").as_posix()
    ext_lines = [
        f'[ext_resource type="Shader" path="res://{SHADER_REL}" id="shader"]',
    ]
    res_refs = {}
    for tier in ("standard", "hero"):
        for map_name in ("albedo", "normal", "roughness", "ao"):
            ident = f"{tier}_{map_name}"
            rel = f"{arrays_dir}/{tier}_{map_name}.tres"
            ext_lines.append(
                f'[ext_resource type="Texture2DArray" path="res://{rel}" id="{ident}"]')
            res_refs[ident] = ident
    lines = [
        f'[gd_resource type="ShaderMaterial" load_steps={len(ext_lines) + 1} format=3]',
        "",
        *ext_lines,
        "",
        "[resource]",
        'shader = ExtResource("shader")',
        # Same lighting defaults as terrain_scale_v1 for visual continuity.
        "shader_parameter/slope_ground_max = 0.92",
        "shader_parameter/slope_rock_max = 0.55",
        "shader_parameter/world_uv_scale = 0.04",
        "shader_parameter/albedo_luma_floor = 0.08",
        "shader_parameter/ao_floor = 0.72",
        "shader_parameter/sun_dir = Vector3(0.30, 0.85, 0.43)",
        'shader_parameter/sun_color = Color(1.0, 0.96, 0.88, 1.0)',
        "shader_parameter/sun_intensity = 1.0",
        "shader_parameter/lambert_floor = 0.35",
        'shader_parameter/sky_tint = Color(0.78, 0.84, 0.92, 1.0)',
        'shader_parameter/ground_tint = Color(0.58, 0.60, 0.55, 1.0)',
        "shader_parameter/ambient_strength = 0.45",
    ]
    # Texture array bindings — name matches shader uniform.
    for tier in ("standard", "hero"):
        for map_name, uniform in (
            ("albedo", "albedo"),
            ("normal", "normal"),
            ("roughness", "rough"),
            ("ao", "ao"),
        ):
            ident = f"{tier}_{map_name}"
            lines.append(
                f'shader_parameter/{tier}_{uniform} = ExtResource("{ident}")')
    out_path = w4 / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run it**

```bash
"C:/Program Files/Python312/python.exe" "D:/assets/world 4/pipeline/write_global_terrain_material.py" \
  --w4-root "D:/assets/world 4/the world 4" \
  --bundle  "worlds/scale_demo" \
  --out     "worlds/scale_demo/material_world_v2.tres"
```

Expected: `wrote D:\assets\world 4\the world 4\worlds\scale_demo\material_world_v2.tres`

- [ ] **Step 3: Reimport + verify Godot loads the material without error**

```bash
"C:/Godot/Godot_v4.5-stable_win64.exe" --headless --path "D:/assets/world 4/the world 4" --import 2>&1 | grep -iE "material_world_v2|error" | head -20
```

Expected: zero `ERROR` lines mentioning `material_world_v2`. If Godot logs `failed to set shader_parameter/standard_albedo` or similar, the shader uniform names or the .tres binding names don't match — re-check Step 1's shader and emitter against `terrain_world_v2.gdshader` Step 1.

- [ ] **Step 4: Commit**

```bash
git -C "D:/assets/world 4" add pipeline/write_global_terrain_material.py "the world 4/worlds/scale_demo/material_world_v2.tres"
git -C "D:/assets/world 4" commit -m "axis6: global terrain material emitter + emit material_world_v2.tres"
```

### Task 5a.9: Wire ScaleWorld + TileTerrain for the splat path

**Files:**
- Modify: `D:/assets/world 4/the world 4/scripts/ScaleWorld.gd`
- Modify: `D:/assets/world 4/the world 4/scripts/TileTerrain.gd`
- Modify: `D:/assets/world 4/the world 4/scenes/scale_demo.tscn`

We add a new export `world_v2_material_path` to ScaleWorld. When set,
ScaleWorld loads it, duplicates per-tile (cheap ref bump), reads each
tile's splat.png + splat_meta.json, and sets per-tile uniforms. The
existing `biome_materials` path stays as a fallback (zero-cost when
the new path is in use).

- [ ] **Step 1: Read the current ScaleWorld + TileTerrain to identify insertion points**

```bash
"C:/Program Files/Python312/python.exe" -c "
import re
p = r'D:/assets/world 4/the world 4/scripts/ScaleWorld.gd'
text = open(p, 'r', encoding='utf-8').read()
print('biome_materials line:', text.find('@export var biome_materials'))
print('_resolve_tile_material_path line:', text.find('func _resolve_tile_material_path'))
print('total lines:', len(text.splitlines()))
"
```

Expected: non-negative line offsets (i.e., the search strings exist). Note the area around `_resolve_tile_material_path` — we'll add a new sibling helper here.

- [ ] **Step 2: Patch ScaleWorld.gd — add world_v2_material_path export**

Insert this block after the existing `@export var biome_materials: Dictionary = {}` line (which is right after the doc comment for biome_materials):

```gdscript

# When set, switches scale_demo to the texture-array + splat path
# (Axis 6 transitions). The material at this path is loaded once,
# duplicated per tile, and per-tile uniforms (splat texture +
# splat_layer_indices + splat_layer_slots + tile_origin_m + tile_size_m)
# are set on the duplicate. The legacy biome_materials / single-material
# paths remain available as fallbacks.
@export var world_v2_material_path: String = ""
```

Run this to apply the edit:

```bash
"C:/Program Files/Python312/python.exe" -c "
import io
p = r'D:/assets/world 4/the world 4/scripts/ScaleWorld.gd'
text = open(p, 'r', encoding='utf-8').read()
needle = '@export var biome_materials: Dictionary = {}'
add = '\n\n# When set, switches scale_demo to the texture-array + splat path\n# (Axis 6 transitions). The material at this path is loaded once,\n# duplicated per tile, and per-tile uniforms (splat texture +\n# splat_layer_indices + splat_layer_slots + tile_origin_m + tile_size_m)\n# are set on the duplicate. The legacy biome_materials / single-material\n# paths remain available as fallbacks.\n@export var world_v2_material_path: String = \"\"'
if 'world_v2_material_path' in text:
    print('already present, skipping')
else:
    text = text.replace(needle, needle + add)
    open(p, 'w', encoding='utf-8', newline='\n').write(text)
    print('patched')
"
```

Expected: `patched`.

- [ ] **Step 3: Patch ScaleWorld.gd — add new tile-spawn branch that uses the splat path**

Locate the existing `func _resolve_tile_material_path(tile_dir: String) -> String:` function. We're going to add a new method below it that returns the *duplicated material* (not just a path) when the v2 path is active, plus a branch in `_spawn_tile` that uses it.

Add this method right after `_resolve_tile_material_path`:

```gdscript


# v2 path: load the global terrain material once, duplicate per tile,
# read this tile's splat + meta, set per-tile uniforms on the duplicate.
# Returns null if v2 path is not active (fall through to legacy path).
var _world_v2_base_mat: ShaderMaterial = null

func _get_v2_base_material() -> ShaderMaterial:
	if _world_v2_base_mat != null:
		return _world_v2_base_mat
	if world_v2_material_path.is_empty():
		return null
	var res: Resource = load(world_v2_material_path)
	if not (res is ShaderMaterial):
		push_error("ScaleWorld: world_v2_material_path is not a ShaderMaterial: " + world_v2_material_path)
		return null
	_world_v2_base_mat = res
	return _world_v2_base_mat

func _make_v2_tile_material(tile_dir: String, coord: Vector2i) -> ShaderMaterial:
	var base: ShaderMaterial = _get_v2_base_material()
	if base == null:
		return null
	var splat_path := tile_dir + "splat.png"
	var meta_path  := tile_dir + "splat_meta.json"
	var splat_tex: Texture2D = load(splat_path) as Texture2D
	if splat_tex == null:
		push_error("ScaleWorld: missing splat.png at " + splat_path)
		return null
	var meta_file := FileAccess.open(meta_path, FileAccess.READ)
	if meta_file == null:
		push_error("ScaleWorld: missing splat_meta.json at " + meta_path)
		return null
	var meta: Variant = JSON.parse_string(meta_file.get_as_text())
	meta_file.close()
	if typeof(meta) != TYPE_DICTIONARY:
		push_error("ScaleWorld: splat_meta.json not a dict: " + meta_path)
		return null
	# Encode channels -> ivec4(packed (tier, layer)) + vec4(slot 0..2 floats).
	var packed: Array[int] = [-1, -1, -1, -1]
	var slots: Array[float] = [0.0, 0.0, 0.0, 0.0]
	var channels = meta.get("channels", [])
	for i in range(min(4, channels.size())):
		var ch = channels[i]
		if typeof(ch) != TYPE_DICTIONARY:
			continue
		var biome = ch.get("biome")
		if biome == null:
			continue
		var tier_name = String(ch.get("tier", ""))
		var tier_bit := 0 if tier_name == "standard" else 1
		# Look up biome's ground layer in the manifest.
		var layer := _v2_layer_for(biome, tier_name)
		if layer < 0:
			push_warning("ScaleWorld: no manifest layer for " + String(biome) + " (" + tier_name + ")")
			continue
		packed[i] = (tier_bit << 30) | (layer & 0x3FFFFFFF)
		slots[i] = 0.0  # ground slot — slope blend picks mid/rock per-fragment
	var inst: ShaderMaterial = base.duplicate(false)
	inst.set_shader_parameter("splat", splat_tex)
	inst.set_shader_parameter("splat_layer_indices", Vector4i(packed[0], packed[1], packed[2], packed[3]))
	inst.set_shader_parameter("splat_layer_slots", Vector4(slots[0], slots[1], slots[2], slots[3]))
	var origin_x := float(coord.x) * _tile_size_m - _world_size_m * 0.5
	var origin_z := float(coord.y) * _tile_size_m - _world_size_m * 0.5
	inst.set_shader_parameter("tile_origin_m", Vector2(origin_x, origin_z))
	inst.set_shader_parameter("tile_size_m", _tile_size_m)
	return inst

# Manifest cache for biome -> (tier, ground_layer) lookup.
var _v2_manifest: Dictionary = {}

func _v2_layer_for(biome: String, tier_name: String) -> int:
	if _v2_manifest.is_empty():
		var mf := FileAccess.open(bundle_dir + "arrays/layer_manifest.json", FileAccess.READ)
		if mf == null:
			return -1
		var parsed: Variant = JSON.parse_string(mf.get_as_text())
		mf.close()
		if typeof(parsed) == TYPE_DICTIONARY:
			_v2_manifest = parsed
		else:
			return -1
	var tiers = _v2_manifest.get("tiers", {})
	var tier_data = tiers.get(tier_name, null)
	if typeof(tier_data) != TYPE_DICTIONARY:
		return -1
	for layer in tier_data.get("layers", []):
		if typeof(layer) != TYPE_DICTIONARY:
			continue
		if String(layer.get("biome", "")) == biome and String(layer.get("slot", "")) == "ground":
			return int(layer.get("layer", -1))
	return -1
```

Apply this edit by using the Edit tool to insert the block above
immediately after the closing of `_resolve_tile_material_path` (the
existing function added in the 2026-05-12 Axis 2 wiring session).
The simplest target is the blank line + `func _spawn_tile(coord:
Vector2i) -> void:` line — insert the new block before it. The
existing `_resolve_tile_material_path` function ends with `return
bundle_dir + "material.tres"` followed by a blank line; insert after
that blank line, before `func _spawn_tile`.

Verify with:
```bash
grep -n "_make_v2_tile_material" "D:/assets/world 4/the world 4/scripts/ScaleWorld.gd"
```

Expected: 2+ line numbers (function def + at least one call site to be added next).

- [ ] **Step 4: Patch ScaleWorld._spawn_tile to use the v2 path when active**

Find this block in `_spawn_tile`:
```gdscript
	var tile_node: Node3D = Node3D.new()
	tile_node.name = "Tile_%d_%d" % [coord.x, coord.y]
	tile_node.set_script(_tile_script)
	var tile_dir: String = "%stiles/tile_%d_%d/" % [bundle_dir, coord.x, coord.y]
	tile_node.set("tile_dir", tile_dir)
	var mat_path: String = _resolve_tile_material_path(tile_dir)
	tile_node.set("shared_material_path", mat_path)
```

Replace with:
```gdscript
	var tile_node: Node3D = Node3D.new()
	tile_node.name = "Tile_%d_%d" % [coord.x, coord.y]
	tile_node.set_script(_tile_script)
	var tile_dir: String = "%stiles/tile_%d_%d/" % [bundle_dir, coord.x, coord.y]
	tile_node.set("tile_dir", tile_dir)
	# v2 path: per-tile duplicate of the global terrain material with
	# splat + indices uniforms set. Falls through to the legacy path-based
	# binding if world_v2_material_path is empty.
	var v2_mat: ShaderMaterial = _make_v2_tile_material(tile_dir, coord)
	if v2_mat != null:
		tile_node.set("shared_material", v2_mat)
	else:
		var mat_path: String = _resolve_tile_material_path(tile_dir)
		tile_node.set("shared_material_path", mat_path)
```

Apply via Edit tool against `ScaleWorld.gd`. Verify the file still parses by running `--import`:

```bash
"C:/Godot/Godot_v4.5-stable_win64.exe" --headless --path "D:/assets/world 4/the world 4" --import 2>&1 | grep -iE "ScaleWorld|error" | head -10
```

Expected: no `ERROR:`.

- [ ] **Step 5: Patch TileTerrain.gd to accept `shared_material` directly**

We need TileTerrain to apply a pre-built Material instead of always loading from a path. Look at `TileTerrain.gd` for the spot where it applies the material to the mesh (likely the function or block that uses `shared_material_path`):

```bash
grep -n "shared_material" "D:/assets/world 4/the world 4/scripts/TileTerrain.gd"
```

Find the line that sets the mesh instance's material from the path. Add a sibling export + a branch that prefers a directly-passed material:

```gdscript
@export var shared_material: Material = null
```

And in the apply step, change:
```gdscript
var mat: Material = load(shared_material_path) as Material
```
to:
```gdscript
var mat: Material = shared_material if shared_material != null else load(shared_material_path) as Material
```

Apply via Edit. Re-run `--import`; expect no errors.

- [ ] **Step 6: Patch scale_demo.tscn — set world_v2_material_path**

Edit the World node block. Find:
```
material_override_path = ""
biome_materials = {
...
}
```

Add after `biome_materials = {...}`:
```
world_v2_material_path = "res://worlds/scale_demo/material_world_v2.tres"
```

Verify with:
```bash
grep -n "world_v2_material_path" "D:/assets/world 4/the world 4/scenes/scale_demo.tscn"
```

Expected: 1 line.

- [ ] **Step 7: Reimport + headless-capture scale_demo walk view**

```bash
"C:/Godot/Godot_v4.5-stable_win64.exe" --headless --path "D:/assets/world 4/the world 4" --import 2>&1 | tail -5
"C:/Godot/Godot_v4.5-stable_win64.exe" --rendering-driver opengl3 --path "D:/assets/world 4/the world 4" --single-window --disable-crash-handler "res://scenes/capture_scale_walk.tscn" 2>&1 | tail -5
cp "D:/assets/world 4/the world 4/captures/scale_2tile_walk.png" "D:/assets/world 4/the world 4/captures/axis6_5a_walk_2026_05_<DD>.png"
```

(Replace `<DD>` with today's day-of-month.)

- [ ] **Step 8: Visually compare against the pre-5a baseline**

Open `captures/axis6_5a_walk_2026_05_<DD>.png` and `captures/biomes_wired_walk_2026_05_12.png` side by side. **Goal:** the new capture should be visually indistinguishable from the old hard-border state — same biomes, same hard cuts, same overall lighting.

If the new capture is blank, all one color, or has obvious shader bugs (e.g., tiles missing albedo): the splat_layer_indices encoding or the array sampling is wrong. Debug by setting one channel's tier+layer manually on a single tile and re-rendering.

If textures look mid-grey or washed out: the within-biome ground/mid/rock slope blend may be reading the wrong layer offsets — verify `biome_ground_layer + 1` and `+ 2` correspond to the mid/rock slots in the manifest order. If the manifest groups biomes by (biome, slot) cycles, ground/mid/rock are sequential; if not, this assumption fails.

**Trust user editor screenshots over headless** — per PITFALLS. Headless may pass while editor fails. Capture, then have the user open the scene in the editor and confirm.

- [ ] **Step 9: Commit**

```bash
git -C "D:/assets/world 4" add "the world 4/scripts/ScaleWorld.gd" "the world 4/scripts/TileTerrain.gd" "the world 4/scenes/scale_demo.tscn" "the world 4/captures/axis6_5a_walk_2026_05_*.png"
git -C "D:/assets/world 4" commit -m "axis6: 5a wire scale_demo to terrain_world_v2 (hard-mode splat, regression-equivalent)"
```

**Stage 5a exit gate:** the new array+splat path renders scale_demo visually identical to the 2026-05-12 hard-border baseline.

---

## Stage 5b — Splat-driven blends

**Goal:** Add `--mode feather <width_m>` to the splat builder so boundary regions between tiles with different biomes have smooth weight ramps. Re-render scale_demo with soft transitions.

### Task 5b.1: Extend splat builder with feather mode + tests

**Files:**
- Modify: `D:/assets/world 4/pipeline/build_tile_splats.py`
- Modify: `D:/assets/world 4/tests/test_build_tile_splats.py`

- [ ] **Step 1: Write failing tests for feather mode**

Append to `tests/test_build_tile_splats.py`:

```python
def test_feather_mode_ramps_at_boundary(tmp_path: Path):
    bundle = make_world(tmp_path)
    bts.build_splats(bundle_dir=bundle, manifest=fake_manifest(),
                     mode="feather", splat_size=16, feather_width_m=64.0)
    # Tile (0,0) is wetland; its east neighbor (1,0) is desert.
    # Feather width = 64m on a 256m tile = 25% of tile = 4 splat pixels
    # (at splat_size=16: 256/16=16m per pixel; 64m=4 pixels).
    # The rightmost 4 columns should ramp wetland_weight 1.0 -> 0.0
    # and desert_weight 0.0 -> 1.0.
    splat = np.asarray(Image.open(bundle / "tiles" / "tile_0_0" / "splat.png").convert("RGBA"))
    # Mid-tile column (col 4): pure wetland.
    assert splat[8, 4, 0] == 255
    assert splat[8, 4, 1] == 0
    # Easternmost column (col 15): mostly desert.
    assert splat[8, 15, 0] < 50
    assert splat[8, 15, 1] > 200
    # Splat_meta now lists both biomes.
    meta = json.loads((bundle / "tiles" / "tile_0_0" / "splat_meta.json").read_text())
    biomes = sorted([c["biome"] for c in meta["channels"] if c["biome"] is not None])
    assert biomes == ["desert", "wetland"]


def test_feather_mode_interior_tile_unchanged(tmp_path: Path):
    # Build a 3x3 world where the center tile has the same biome as ALL its
    # neighbors -> no boundary -> splat should be pure (255,0,0,0).
    bundle = tmp_path / "scale_demo"
    bundle.mkdir()
    for tx in range(3):
        for tz in range(3):
            td = bundle / "tiles" / f"tile_{tx}_{tz}"
            td.mkdir(parents=True)
            (td / "meta.json").write_text(json.dumps(
                {"tile_x": tx, "tile_z": tz, "tile_size_m": 256.0, "biome": "alpine"}
            ), encoding="utf-8")
    bts.build_splats(bundle_dir=bundle, manifest=fake_manifest(),
                     mode="feather", splat_size=8, feather_width_m=32.0)
    splat = np.asarray(Image.open(bundle / "tiles" / "tile_1_1" / "splat.png").convert("RGBA"))
    assert (splat[..., 0] == 255).all()
    assert (splat[..., 1] == 0).all()
```

- [ ] **Step 2: Run the new tests, verify they fail**

```bash
"C:/Program Files/Python312/python.exe" -m pytest "D:/assets/world 4/tests/test_build_tile_splats.py" -v -k feather
```

Expected: both new tests fail with `NotImplementedError: mode='feather'`.

- [ ] **Step 3: Implement feather mode**

Replace `build_tile_splats.py`'s `build_splats` function with this version (keeps hard mode intact, adds feather):

```python
def build_splats(*, bundle_dir: Path | str, manifest: dict,
                 mode: str, splat_size: int, feather_width_m: float) -> None:
    if mode not in ("hard", "feather"):
        raise NotImplementedError(f"mode={mode!r} not implemented in stage 5b")
    bundle = Path(bundle_dir)
    tiles_dir = bundle / "tiles"
    # Pre-scan: gather all tile (tx, tz) -> biome.
    tile_biomes: dict[tuple[int, int], str] = {}
    tile_size_m: float = 256.0
    for tile_dir in sorted(tiles_dir.iterdir()):
        if not tile_dir.is_dir() or not tile_dir.name.startswith("tile_"):
            continue
        meta = json.loads((tile_dir / "meta.json").read_text(encoding="utf-8"))
        biome = meta.get("biome")
        if not biome:
            raise SplatError(f"{tile_dir}: tile meta has no biome field")
        tile_biomes[(int(meta["tile_x"]), int(meta["tile_z"]))] = biome
        tile_size_m = float(meta.get("tile_size_m", tile_size_m))

    for (tx, tz), biome in tile_biomes.items():
        tile_dir = tiles_dir / f"tile_{tx}_{tz}"
        rec = _biome_to_record(manifest, biome)
        if rec is None:
            raise SplatError(f"biome {biome!r} not found in manifest")
        if mode == "hard" or feather_width_m <= 0:
            arr = np.zeros((splat_size, splat_size, 4), dtype=np.uint8)
            arr[..., 0] = 255
            ch_meta = [{"biome": biome, "tier": rec["tier"]}]
            for _ in range(3):
                ch_meta.append({"biome": None, "tier": None})
        else:
            arr, ch_meta = _feather_splat(
                tx=tx, tz=tz, this_biome=biome, this_rec=rec,
                tile_biomes=tile_biomes, manifest=manifest,
                splat_size=splat_size, tile_size_m=tile_size_m,
                feather_width_m=feather_width_m,
            )
        Image.fromarray(arr, mode="RGBA").save(tile_dir / "splat.png")
        (tile_dir / "splat_meta.json").write_text(
            json.dumps({"channels": ch_meta, "splat_size": splat_size,
                        "mode": mode}, indent=2) + "\n",
            encoding="utf-8", newline="\n")


def _feather_splat(*, tx: int, tz: int, this_biome: str, this_rec: dict,
                   tile_biomes: dict, manifest: dict, splat_size: int,
                   tile_size_m: float, feather_width_m: float):
    """Build a feathered splat for tile (tx, tz).

    Channel 0 = this_biome. Channels 1+ = up to 3 neighbors with
    different biomes (N/E/S/W in NESW order, dropped if same biome).
    Per pixel, neighbor weight ramps from 0 at distance >= feather_width_m
    inside the tile to 0.5 at the very edge (the neighbor's mirror-side
    contributes the other 0.5 — so summed across both sides the boundary
    transitions smoothly from 100% this -> 50/50 -> 100% neighbor over
    2*feather_width_m).

    Returns (RGBA8 array, channel meta list of length 4).
    """
    neighbors_by_dir = {
        "N": (tx, tz + 1), "E": (tx + 1, tz),
        "S": (tx, tz - 1), "W": (tx - 1, tz),
    }
    # Collect up to 3 unique neighbor biomes in NESW order.
    neighbor_channels: list[tuple[str, dict, set[str]]] = []
    # Map: direction -> assigned channel index (1, 2, or 3)
    dir_to_channel: dict[str, int] = {}
    for d in ("N", "E", "S", "W"):
        nc = neighbors_by_dir[d]
        if nc not in tile_biomes:
            continue  # off-world edge
        nb = tile_biomes[nc]
        if nb == this_biome:
            continue
        # If we've seen this neighbor biome via another direction, reuse
        # that channel; otherwise allocate a new one.
        existing = next(
            (i for i, (b, _, _) in enumerate(neighbor_channels) if b == nb),
            None,
        )
        if existing is not None:
            dir_to_channel[d] = existing + 1
            neighbor_channels[existing][2].add(d)
        elif len(neighbor_channels) < 3:
            rec = _biome_to_record(manifest, nb)
            if rec is None:
                raise SplatError(f"neighbor biome {nb!r} not in manifest")
            dir_to_channel[d] = len(neighbor_channels) + 1
            neighbor_channels.append((nb, rec, {d}))
        # If we've already filled 3 neighbor channels, drop further neighbors.
    # Build the splat as float weights then quantize.
    px = splat_size
    weights = np.zeros((px, px, 4), dtype=np.float32)
    weights[..., 0] = 1.0  # base: this biome everywhere
    # Per-axis distance to the four edges, in meters (pixel-center).
    px_per_m = px / tile_size_m
    half_step_m = (tile_size_m / px) * 0.5
    # i = row (z direction), j = column (x direction).
    # Z increases south->north in world space; row 0 is the north edge.
    j = np.arange(px).astype(np.float32)
    i = np.arange(px).astype(np.float32)
    # Distance to each edge in METERS (clamped >= 0).
    dist_W = (j + 0.5) * (tile_size_m / px)               # to west edge
    dist_E = (px - 0.5 - j) * (tile_size_m / px)          # to east edge
    dist_N = (i + 0.5) * (tile_size_m / px)               # to north edge (row 0 = north)
    dist_S = (px - 0.5 - i) * (tile_size_m / px)          # to south edge
    # Feather weight from a given edge: 0 at center, 0.5 at the edge.
    # ramp(d) = 0 if d >= feather_width_m else 0.5 * (1 - d/feather_width_m)
    def edge_ramp(d):
        r = np.clip(1.0 - d / feather_width_m, 0.0, 1.0)
        return 0.5 * r
    # We need a 2D map per direction. Broadcast appropriately.
    rW = edge_ramp(dist_W)[np.newaxis, :]   # shape (1, px), row-broadcast
    rE = edge_ramp(dist_E)[np.newaxis, :]
    rN = edge_ramp(dist_N)[:, np.newaxis]   # shape (px, 1)
    rS = edge_ramp(dist_S)[:, np.newaxis]
    # For each direction that has a neighbor, add to that neighbor's channel
    # and subtract from this_biome (channel 0).
    for d, ramp in (("W", rW), ("E", rE), ("N", rN), ("S", rS)):
        if d not in dir_to_channel:
            continue
        ch = dir_to_channel[d]
        weights[..., ch] += ramp
        weights[..., 0]  -= ramp
    # Clamp + normalize.
    weights = np.clip(weights, 0.0, 1.0)
    total = weights.sum(axis=-1, keepdims=True)
    total = np.maximum(total, 1e-6)
    weights = weights / total
    arr = (weights * 255.0 + 0.5).astype(np.uint8)
    # Build channel meta list of exactly 4 entries.
    ch_meta = [{"biome": this_biome, "tier": this_rec["tier"]}]
    for biome, rec, _dirs in neighbor_channels:
        ch_meta.append({"biome": biome, "tier": rec["tier"]})
    while len(ch_meta) < 4:
        ch_meta.append({"biome": None, "tier": None})
    return arr, ch_meta
```

- [ ] **Step 4: Re-run feather tests, verify they pass**

```bash
"C:/Program Files/Python312/python.exe" -m pytest "D:/assets/world 4/tests/test_build_tile_splats.py" -v
```

Expected: 6 passed (2 new + 4 original).

- [ ] **Step 5: Build feather splats for scale_demo**

```bash
"C:/Program Files/Python312/python.exe" "D:/assets/world 4/pipeline/build_tile_splats.py" \
  --bundle "D:/assets/world 4/the world 4/worlds/scale_demo" \
  --manifest "D:/assets/world 4/the world 4/worlds/scale_demo/arrays/layer_manifest.json" \
  --mode feather --splat-size 64 --feather-width-m 32.0
```

Expected: `splats: mode=feather size=64`.

- [ ] **Step 6: Reimport + capture**

```bash
"C:/Godot/Godot_v4.5-stable_win64.exe" --headless --path "D:/assets/world 4/the world 4" --import 2>&1 | tail -3
"C:/Godot/Godot_v4.5-stable_win64.exe" --rendering-driver opengl3 --path "D:/assets/world 4/the world 4" --single-window --disable-crash-handler "res://scenes/capture_scale_walk.tscn" 2>&1 | tail -3
cp "D:/assets/world 4/the world 4/captures/scale_2tile_walk.png" "D:/assets/world 4/the world 4/captures/axis6_5b_walk_2026_05_<DD>.png"
```

Inspect: the boundary regions between adjacent biomes should now show a smooth ramp instead of a hard cut. If the ramp is too wide or too narrow, re-run Step 5 with a different `--feather-width-m`. If transitions look muddy/grey, the weight normalization is over-suppressing the dominant biome — check the splat PNG inspection in the next step.

- [ ] **Step 7: Inspect a splat visually**

```bash
"C:/Program Files/Python312/python.exe" -c "
from PIL import Image
import numpy as np
a = np.asarray(Image.open(r'D:/assets/world 4/the world 4/worlds/scale_demo/tiles/tile_1_1/splat.png').convert('RGBA'))
# This tile is forest (per the assigned 4x4 layout in
# assign_biomes_scale_demo.py: row Z=1 -> forest forest desert desert,
# so tile_1_1 = forest with neighbors forest/forest/desert/wetland-or-similar).
print('row 32 mid-tile (center):', a[32, 32])
print('row 32 east edge:',         a[32, 63])
print('row 0  mid (north edge):',  a[0, 32])
print('row 63 mid (south edge):',  a[63, 32])
"
```

Expected: center row shows mostly-channel-0; east/north/south edges show channel-1/2/3 contributions where the neighbor biome differs.

- [ ] **Step 8: Commit**

```bash
git -C "D:/assets/world 4" add pipeline/build_tile_splats.py tests/test_build_tile_splats.py "the world 4/worlds/scale_demo/tiles" "the world 4/captures/axis6_5b_walk_2026_05_*.png"
git -C "D:/assets/world 4" commit -m "axis6: 5b feather-mode splats — soft transitions visible"
```

**Stage 5b exit gate:** no hard tile-boundary seams visible in the walk capture.

**Stage 5b follow-up note:** the spec flags "mip filtering on splats" as
a potentially-tunable knob. By default Godot generates mipmaps and
uses bilinear filtering on a 64² splat — that smooths the boundary
ramp for free, which is what we want. If captures show banded
transitions or aliased boundary noise, inspect the splat's `.import`
file and override `compress/mode = 0` (lossless) +
`mipmaps/generate = false`; re-import. The current default is fine
for the v1 demo, just be aware of the knob.

---

## Stage 5c — Slot-pool indirection refactor

**Goal:** Splats reference slot-pool indices (a stable level of indirection) rather than direct array layer indices. v1's slot pool is the static layer mapping from the manifest, so behavior is unchanged. Sets up the streaming follow-up cleanly.

### Task 5c.1: Add slot_pool to the layer manifest + a builder helper

**Files:**
- Modify: `D:/assets/world 4/pipeline/build_biome_arrays.py`
- Modify: `D:/assets/world 4/tests/test_build_biome_arrays.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_build_biome_arrays.py`:

```python
def test_manifest_includes_static_slot_pool(tmp_path: Path):
    w4 = tmp_path / "w4"
    catalog_path = write_catalog(tmp_path, w4)
    cat = bc.load_catalog(catalog_path)
    m = bba.build_manifest(cat, w4_root=w4)
    # Slot pool is per-tier. Each tier has a "slot_pool" entry listing
    # the active layer slot indices in order; in v1 these match the layer
    # indices 1:1 (identity map). The slot pool is what splats reference;
    # the manifest tells consumers how to map slot index -> layer index.
    for tier_name, tdata in m["tiers"].items():
        n = len(tdata["layers"])
        assert tdata["slot_pool"] == list(range(n))
```

- [ ] **Step 2: Run the test, verify it fails**

```bash
"C:/Program Files/Python312/python.exe" -m pytest "D:/assets/world 4/tests/test_build_biome_arrays.py::test_manifest_includes_static_slot_pool" -v
```

Expected: KeyError on `slot_pool`.

- [ ] **Step 3: Add slot_pool to build_manifest**

In `pipeline/build_biome_arrays.py`, update `build_manifest` to include a `slot_pool` field in each tier:

```python
        tiers_out[tier.name] = {
            "resolution": tier.resolution,
            "layers": layers,
            # v1 slot pool is the identity map: slot_pool[i] = i.
            # Streaming follow-up: slot_pool[i] points to a layer that may
            # change over time as biomes are paged in/out of the array.
            "slot_pool": list(range(len(layers))),
        }
```

- [ ] **Step 4: Re-run all tests**

```bash
"C:/Program Files/Python312/python.exe" -m pytest "D:/assets/world 4/tests/test_build_biome_arrays.py" -v
```

Expected: 5 passed.

- [ ] **Step 5: Regenerate the real manifest**

```bash
"C:/Program Files/Python312/python.exe" "D:/assets/world 4/pipeline/build_biome_arrays.py" \
  --catalog "D:/assets/world 4/the world 4/worlds/scale_demo/biome_catalog.json" \
  --w4-root "D:/assets/world 4/the world 4" \
  --out "D:/assets/world 4/the world 4/worlds/scale_demo/arrays/layer_manifest.json"
"C:/Program Files/Python312/python.exe" -c "
import json
m = json.loads(open(r'D:/assets/world 4/the world 4/worlds/scale_demo/arrays/layer_manifest.json','r',encoding='utf-8').read())
for tier_name, t in m['tiers'].items():
    print(f'{tier_name}: layers={len(t[\"layers\"])} slot_pool={t[\"slot_pool\"]}')
"
```

Expected:
```
standard: layers=13 slot_pool=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
hero: layers=2 slot_pool=[0, 1]
```

- [ ] **Step 6: Commit**

```bash
git -C "D:/assets/world 4" add pipeline/build_biome_arrays.py tests/test_build_biome_arrays.py "the world 4/worlds/scale_demo/arrays/layer_manifest.json"
git -C "D:/assets/world 4" commit -m "axis6: 5c layer_manifest gains slot_pool (identity in v1)"
```

### Task 5c.2: Have ScaleWorld use slot_pool indirection

**Files:**
- Modify: `D:/assets/world 4/the world 4/scripts/ScaleWorld.gd`

- [ ] **Step 1: Update `_v2_layer_for` to apply slot_pool indirection**

Currently `_v2_layer_for` returns the raw layer index. Change it to return the *layer index for the slot pool entry that maps to that biome's ground slot*. In v1 the slot pool is identity, so behavior is unchanged.

Edit the function in `ScaleWorld.gd`:

```gdscript
func _v2_layer_for(biome: String, tier_name: String) -> int:
	if _v2_manifest.is_empty():
		var mf := FileAccess.open(bundle_dir + "arrays/layer_manifest.json", FileAccess.READ)
		if mf == null:
			return -1
		var parsed: Variant = JSON.parse_string(mf.get_as_text())
		mf.close()
		if typeof(parsed) == TYPE_DICTIONARY:
			_v2_manifest = parsed
		else:
			return -1
	var tiers = _v2_manifest.get("tiers", {})
	var tier_data = tiers.get(tier_name, null)
	if typeof(tier_data) != TYPE_DICTIONARY:
		return -1
	var slot_pool: Array = tier_data.get("slot_pool", [])
	# Find which slot pool entry currently maps to this biome's ground layer.
	for layer in tier_data.get("layers", []):
		if typeof(layer) != TYPE_DICTIONARY:
			continue
		if String(layer.get("biome", "")) != biome:
			continue
		if String(layer.get("slot", "")) != "ground":
			continue
		var lidx := int(layer.get("layer", -1))
		# Search slot_pool for the slot index that currently maps to lidx.
		for sidx in range(slot_pool.size()):
			if int(slot_pool[sidx]) == lidx:
				return sidx
		return -1
	return -1
```

- [ ] **Step 2: Reimport + capture**

```bash
"C:/Godot/Godot_v4.5-stable_win64.exe" --headless --path "D:/assets/world 4/the world 4" --import 2>&1 | tail -3
"C:/Godot/Godot_v4.5-stable_win64.exe" --rendering-driver opengl3 --path "D:/assets/world 4/the world 4" --single-window --disable-crash-handler "res://scenes/capture_scale_walk.tscn" 2>&1 | tail -3
cp "D:/assets/world 4/the world 4/captures/scale_2tile_walk.png" "D:/assets/world 4/the world 4/captures/axis6_5c_walk_2026_05_<DD>.png"
```

- [ ] **Step 3: Visual diff vs 5b capture**

Diff `axis6_5c_walk_2026_05_<DD>.png` against `axis6_5b_walk_2026_05_<DD>.png`. They should be **visually identical** — slot_pool is identity in v1; this stage is a pure refactor.

If they differ: the slot_pool indirection has a bug. Most likely cause: the slot_pool lookup returns the wrong sidx because layers aren't laid out 0..N-1 in catalog iteration order. Trace by adding a print to `_v2_layer_for` and re-running.

- [ ] **Step 4: Commit**

```bash
git -C "D:/assets/world 4" add "the world 4/scripts/ScaleWorld.gd" "the world 4/captures/axis6_5c_walk_2026_05_*.png"
git -C "D:/assets/world 4" commit -m "axis6: 5c slot-pool indirection in ScaleWorld (identity, streaming-ready)"
```

**Stage 5c exit gate:** visual output identical to 5b; code is streaming-ready.

---

## Stage 5d — Two-tier verification

**Goal:** Confirm hero-tier (4K) sampling works correctly for forest's `scrub_dense` (ground) and `rocky_slope` (rock). Verify visible detail uplift vs standard tier in a close-up walk capture.

### Task 5d.1: Take a close-up walk capture inside a forest tile

**Files:**
- Create: `D:/assets/world 4/the world 4/captures/axis6_5d_walk_forest_closeup_2026_05_<DD>.png`

We need a vantage point INSIDE a forest tile so the camera sees forest's hero textures (scrub_dense ground + rocky_slope rock). Tile (1,1), (2,1), (1,2), and (2,2) are forest per the assigned layout.

- [ ] **Step 1: Modify capture_scale_walk.tscn or its underlying scene so the camera spawns inside a forest tile**

Inspect the current spawn position:

```bash
grep -n "warmup_frames\|spawn_position\|camera_path" "D:/assets/world 4/the world 4/scenes/capture_scale_walk.tscn"
```

If the capture warmup uses the default ScaleWorld spawn position (likely near origin), it should already land in a forest tile (the layout has forest in the middle 2x2 = tiles (1,1)(2,1)(1,2)(2,2) at world XZ around the origin ±256m).

Run a capture as-is:
```bash
"C:/Godot/Godot_v4.5-stable_win64.exe" --rendering-driver opengl3 --path "D:/assets/world 4/the world 4" --single-window --disable-crash-handler "res://scenes/capture_scale_walk.tscn" 2>&1 | tail -3
cp "D:/assets/world 4/the world 4/captures/scale_2tile_walk.png" "D:/assets/world 4/the world 4/captures/axis6_5d_walk_forest_closeup_2026_05_<DD>.png"
```

- [ ] **Step 2: Verify hero-tier sampling is happening for forest**

Inspect a forest tile's splat_meta:
```bash
cat "D:/assets/world 4/the world 4/worlds/scale_demo/tiles/tile_1_1/splat_meta.json"
```

Channel 0 should have `"tier": "hero"` (because forest's ground slot is in the hero tier per the catalog).

If channel 0's tier is `"standard"`: the splat builder's `_biome_to_record` is picking the wrong tier for forest. Trace and fix.

- [ ] **Step 3: Visually compare hero-rendered forest against the pre-5a forest baseline**

Open the close-up capture and `captures/biomes_wired_walk_2026_05_12.png`. They depict slightly different vantages but both should show the forest material's high-detail textures. The 5d capture's forest fragments should look at least as detailed as the baseline (which was rendered with the 4096² PNG directly bound, not via an array — same data, different binding mechanism).

If the 5d forest looks visibly lower-res than the baseline: the hero array layer for forest ground may be mismatched (wrong source PNG packed), or the array import in Godot downsampled it. Inspect:
```bash
"C:/Program Files/Python312/python.exe" -c "
from PIL import Image
im = Image.open(r'D:/assets/world 4/the world 4/materials/anchor_v2/scrub_dense/albedo.png')
print('scrub_dense albedo size:', im.size)
"
```
Expected: `(4096, 4096)`. If different, the source itself isn't 4K and the hero tier should be downgraded.

- [ ] **Step 4: Commit**

```bash
git -C "D:/assets/world 4" add "the world 4/captures/axis6_5d_walk_forest_closeup_2026_05_*.png"
git -C "D:/assets/world 4" commit -m "axis6: 5d two-tier capture — hero-tier forest renders correctly"
```

**Stage 5d exit gate:** hero-tier forest renders at full 4K detail with no visible regression vs the pre-5a baseline.

---

## Stage 5e — Portability documentation

**Goal:** Document how to lift the texture-array + splat-blending system into another Godot 4.5 project.

### Task 5e.1: Write the portability README

**Files:**
- Create: `D:/assets/world 4/docs/plans/AXIS6_PORTABILITY_README.md`

- [ ] **Step 1: Write the doc**

Create the file with this content (mind UTF-8, LF):

```markdown
# Axis 6 Transitions — Portability Guide

> How to drop the W4 biome-transitions system into another Godot 4.5
> project. The system is engine-agnostic from the host project's
> perspective: it only knows about terrain heightmaps, tile layouts,
> and material bindings.

## What you're moving

### Required files (copy as-is)

```
pipeline/
  biome_catalog.py
  build_biome_arrays.py
  build_tile_splats.py
  write_array_tres.py
  write_global_terrain_material.py

the world 4/shaders/
  terrain_world_v2.gdshader
```

### Required runtime hooks (host project provides)

The host project's tile spawner must, for each tile:
1. Load this tile's `splat.png` (Texture2D).
2. Read this tile's `splat_meta.json` (a small dict).
3. Duplicate the global terrain material.
4. Set the duplicate's shader uniforms: `splat`, `splat_layer_indices`
   (ivec4), `splat_layer_slots` (vec4), `tile_origin_m` (vec2),
   `tile_size_m` (float).
5. Bind the duplicate to the tile mesh.

See `ScaleWorld.gd::_make_v2_tile_material` for a reference implementation.

### Required pipeline order

For a new world:
1. Author a `biome_catalog.json` describing biomes, slots, tiers.
2. Run `build_biome_arrays.py` to emit the layer manifest.
3. Run `write_array_tres.py` to emit the Texture2DArray `.tres` files.
4. Run `write_global_terrain_material.py` to emit the one shared material.
5. Run `build_tile_splats.py --mode feather --feather-width-m <m>` to
   emit per-tile splats.
6. Godot `--import` to bake arrays.
7. Tile spawner uses the per-tile splat + uniform-binding contract.

## What you DON'T move

- W4-specific scripts: `ScaleWorld.gd`, `TileTerrain.gd`,
  `AnchorCameraRig.gd`, `HeadlessCapture.gd`, the scale_demo scenes,
  the anchor v2 shader.
- W4's DEM pipeline (`pick_dem_crop_scale.py`, `slice_to_tiles.py`).
- W4's biome assignment script (`assign_biomes_scale_demo.py`) — your
  host project decides how tiles get biome labels.

## Contracts the host project must honor

### Per-tile data on disk

Each tile directory must have:
- `meta.json` with at minimum `tile_x`, `tile_z`, `tile_size_m`, `biome` fields.
- `splat.png` (RGBA8, square, any reasonable size — 64² is standard).
- `splat_meta.json` matching the format documented in
  `build_tile_splats.py`'s module docstring.

### Shader uniform conventions

The shader binds the four Texture2DArray uniforms per tier (`standard_*`
and `hero_*`). To add a new tier, add a fifth set of uniforms and a
matching branch in `sample_biome` — see `terrain_world_v2.gdshader`
for the pattern.

`splat_layer_indices` packs `(tier_bit, layer_index)`: tier bit in bit
30, layer index in bits 0..29. A value of -1 means "channel is empty,
skip it."

## Customization knobs

### Different biome palettes per game
- Author a different `biome_catalog.json` referencing the new game's
  biome PBR kits. The shader doesn't change.

### Different transition widths
- Re-run `build_tile_splats.py --mode feather --feather-width-m <m>`.
- Can be per-game (different m) or per-world (different m per bundle).

### Adding a new biome
1. Drop the PBR kit under your project's materials dir.
2. Add an entry to `biome_catalog.json`.
3. Regenerate the manifest + arrays + splats.
4. Run Godot `--import`.

### Adding a new resolution tier
1. Add the tier to `biome_catalog.json`.
2. Update the shader: add 4 new sampler uniforms + a branch in
   `sample_biome`.
3. Update `write_global_terrain_material.py`'s tier list.

## Known limitations (as of 2026-05-12)

- **No streaming.** Slot pool is static; all biomes resident in VRAM.
  Plan: add LRU eviction + async layer-load via `RenderingDevice` or
  a custom GDExtension when biome counts exceed a comfortable VRAM
  budget (~30 biomes @ 1024² compressed).
- **Splat width is global per regeneration.** No per-pair width
  authoring. If a game wants alpine↔desert to have a wider transition
  than alpine↔forest, that needs a per-pair table parameter (small
  follow-up).
- **No object scatter.** Decoration is Axis 5; see the W4 ROADMAP.

## Testing the integration

Run from your host project root:
```bash
python pipeline/build_biome_arrays.py --catalog <path> --w4-root <godot-root> --out <manifest>
python pipeline/write_array_tres.py --manifest <manifest> --w4-root <godot-root> --out-dir <arrays-dir>
python pipeline/build_tile_splats.py --bundle <bundle> --manifest <manifest> --mode hard
python pipeline/write_global_terrain_material.py --w4-root <godot-root> --bundle <bundle> --out <material.tres>
godot --headless --import
godot --rendering-driver opengl3 --single-window --disable-crash-handler <capture.tscn>
```

Capture should render with one solid color per tile (no transitions
under `--mode hard`). Then re-run `build_tile_splats.py --mode feather`
to enable soft borders.
```

- [ ] **Step 2: Commit**

```bash
git -C "D:/assets/world 4" add "docs/plans/AXIS6_PORTABILITY_README.md"
git -C "D:/assets/world 4" commit -m "axis6: 5e portability README"
```

**Stage 5e exit gate:** doc exists, internally consistent, lists all required files + contracts.

---

## Stage 5f — Build-note + roadmap + memory updates

**Goal:** Capture what shipped, refresh roadmap rankings, update memory.

### Task 5f.1: Write the build-note

**Files:**
- Create: `D:/assets/world 4/docs/build-notes/AXIS6_BUILD_NOTES_2026_05_<DD>.md`

- [ ] **Step 1: Write the build-note**

Create the file mirroring the structure of
`docs/build-notes/AXIS2_WIRING_BUILD_NOTES_2026_05_12.md`. Include:
- What got built (the pipeline + shader + wiring)
- Decisions made during build
- Files touched (cite paths)
- Captures dated today
- Pitfalls hit / avoided (referencing PITFALLS.md numbers)
- What this session did NOT do
- What unlocks now (per-game biome packs, scalable biome count, etc.)
- Cost recap vs plan estimate

(See `AXIS2_WIRING_BUILD_NOTES_2026_05_12.md` for the exact template.)

- [ ] **Step 2: Commit**

```bash
git -C "D:/assets/world 4" add "docs/build-notes/AXIS6_BUILD_NOTES_2026_05_<DD>.md"
git -C "D:/assets/world 4" commit -m "axis6: 5f build-note for Axis 6 transitions session"
```

### Task 5f.2: Update ROADMAP.md

**Files:**
- Modify: `D:/assets/world 4/docs/ROADMAP.md`

- [ ] **Step 1: Move Axis 6 from "What's next" to "What's done"**

Edit `docs/ROADMAP.md`. Add a row to the "What's done" table:

```markdown
| Axis 6 (Textures) — soft transitions | 2026-05-<DD> | Texture-array + per-tile splat path replaces per-tile single-material binding. 5 biomes resident in two-tier arrays (standard 1024², hero 4096²). Feather-mode splats produce soft transitions at every biome boundary. Portability guide written. See `build-notes/AXIS6_BUILD_NOTES_2026_05_<DD>.md`. |
```

Delete the current "### 1. Textures axis (Axis 6)" section under "What's next, ranked". Renumber the remaining sections (Axis 2 follow-ups becomes #1).

Rerank: the new #1 candidate depends on game priorities. From the strategic shape:
- If pushing toward 2.5D wizard game: write a new #1 for the offline bake renderer (Strand B kickoff).
- If pushing toward bigger 3D worlds: write a new #1 for real-game scale (Strand A kickoff).

Add an "Open: pick a strand" note at the top of "What's next" if the choice hasn't been made yet.

- [ ] **Step 2: Commit**

```bash
git -C "D:/assets/world 4" add docs/ROADMAP.md
git -C "D:/assets/world 4" commit -m "axis6: 5f rank Axis 6 as shipped; rerank what's next"
```

### Task 5f.3: Update AXES.md

**Files:**
- Modify: `D:/assets/world 4/docs/strategy/AXES.md`

- [ ] **Step 1: Update Axis 6 current-state**

Edit `docs/strategy/AXES.md`. Update the Axis 6 "Current state" paragraph to reflect that transitions are now shipped (not "pending"). Add a "Next experiment" sketch that covers the streaming follow-up + per-pair width authoring.

- [ ] **Step 2: Commit**

```bash
git -C "D:/assets/world 4" add docs/strategy/AXES.md
git -C "D:/assets/world 4" commit -m "axis6: 5f AXES.md current-state update"
```

### Task 5f.4: Update TOOLS.md

**Files:**
- Modify: `D:/assets/world 4/docs/reference/TOOLS.md`

- [ ] **Step 1: Add the new pipeline scripts**

Append rows to the "Pipeline scripts" section for:
- `biome_catalog.py` — pure-Python catalog loader/validator
- `build_biome_arrays.py` — emits the layer_manifest.json
- `write_array_tres.py` — emits Texture2DArray .tres files
- `build_tile_splats.py` — emits per-tile splat.png + splat_meta.json
- `write_global_terrain_material.py` — emits the global terrain material .tres

And to the "Shaders" section:
- `terrain_world_v2.gdshader` — **canonical multi-biome shader** with array sampling + splat blending. Replaces `terrain_scale_v1.gdshader` for any scale_demo / multi-biome world.

Mark `terrain_scale_v1.gdshader` as "legacy single-biome path; still in use for pre-Axis-6 scenes."

- [ ] **Step 2: Commit**

```bash
git -C "D:/assets/world 4" add docs/reference/TOOLS.md
git -C "D:/assets/world 4" commit -m "axis6: 5f TOOLS.md catalog of new pipeline + shader"
```

### Task 5f.5: Write the memory entry

**Files:**
- Create: `C:/Users/josep/.claude/projects/d--assets/memory/w4_axis6_transitions_2026_05_<DD>.md`
- Modify: `C:/Users/josep/.claude/projects/d--assets/memory/MEMORY.md`

- [ ] **Step 1: Write the memory entry**

```markdown
---
name: W4 Axis 6 transitions 2026-05-<DD>
description: Texture-array + per-tile splat path; two-tier (standard 1024² + hero 4096²); slot-pool indirection in place for future streaming
type: project
---

W4 Axis 6 transitions shipped 2026-05-<DD>. Replaces per-tile single-
material binding with a global terrain material + 8 Texture2DArrays
(2 tiers × 4 PBR maps) + per-tile splat textures defining biome
weights. Soft transitions visible at every biome boundary in
scale_demo. Full writeup:
`world 4/docs/build-notes/AXIS6_BUILD_NOTES_2026_05_<DD>.md`.
Portability guide: `world 4/docs/plans/AXIS6_PORTABILITY_README.md`.

**Why:** Hard borders on the 4x4 scale_demo (visible 2026-05-12) needed
soft transitions to be usable. Texture-array + splat path scales to
≥15 biomes at constant per-fragment cost (vs O(N²) authored
transitions or O(N) per-tile material bindings).

**How to apply:**
- The biome system is now data-driven from `biome_catalog.json`.
  Adding/removing a biome is catalog + regenerate, no shader edits.
- Two tiers exist: `standard` (1024², most biomes) and `hero` (4096²,
  forest's scrub_dense + rocky_slope). Adding a tier = add catalog
  entry + add shader uniform set + add slot pool. Small change.
- Slot pool is currently identity (slot index == layer index in v1).
  Streaming follow-up adds LRU eviction + async layer-load on top.
- Splats are RGBA8 64² per tile, channel 0 = this tile's biome,
  channels 1-3 = up to 3 unique neighbor biomes feathered at tile
  edges. `--mode hard` for regression / debug; `--mode feather
  <width_m>` for production.
- terrain_world_v2.gdshader is the canonical multi-biome shader.
  terrain_scale_v1.gdshader is legacy single-biome; kept for
  pre-Axis-6 scenes (none in W4 currently).
- Compute shaders, time-of-day, dynamic lighting are orthogonal —
  the unshaded manual-lighting path is preserved (PITFALLS #3).
```

- [ ] **Step 2: Add the index line to MEMORY.md**

Append to `C:/Users/josep/.claude/projects/d--assets/memory/MEMORY.md`:

```markdown
- [W4 Axis 6 transitions 2026-05-<DD>](w4_axis6_transitions_2026_05_<DD>.md) — texture-array + per-tile splat path; two-tier; slot-pool-ready streaming. terrain_world_v2.gdshader is canonical.
```

- [ ] **Step 3: Commit (memory files are outside the W4 git repo)**

Memory files live at `C:/Users/josep/.claude/projects/d--assets/memory/` — they're not in the W4 git repo. No commit needed; they persist via the harness.

### Task 5f.6: Final regression check

**Files:** none

- [ ] **Step 1: Capture anchor walk + scale_demo walk + scale_demo topdown**

```bash
"C:/Godot/Godot_v4.5-stable_win64.exe" --headless --path "D:/assets/world 4/the world 4" --import 2>&1 | tail -3
"C:/Godot/Godot_v4.5-stable_win64.exe" --rendering-driver opengl3 --path "D:/assets/world 4/the world 4" --single-window --disable-crash-handler "res://scenes/capture_anchor_walk.tscn" 2>&1 | tail -3
"C:/Godot/Godot_v4.5-stable_win64.exe" --rendering-driver opengl3 --path "D:/assets/world 4/the world 4" --single-window --disable-crash-handler "res://scenes/capture_scale_walk.tscn" 2>&1 | tail -3
"C:/Godot/Godot_v4.5-stable_win64.exe" --rendering-driver opengl3 --path "D:/assets/world 4/the world 4" --single-window --disable-crash-handler "res://scenes/capture_scale_topdown.tscn" 2>&1 | tail -3
```

- [ ] **Step 2: Verify no regression in anchor demo**

Compare the new anchor walk capture against the existing anchor baseline:

```bash
"C:/Program Files/Python312/python.exe" -c "
import numpy as np
from PIL import Image
a = np.asarray(Image.open(r'D:/assets/world 4/the world 4/captures/anchor_walk.png').convert('RGB'), dtype=np.int32)
b = np.asarray(Image.open(r'D:/assets/world 4/the world 4/captures/anchor_walk.png').convert('RGB'), dtype=np.int32)
print('shape:', a.shape, 'mean abs diff:', np.mean(np.abs(a - b)))
"
```

(Replace the second path with whichever pre-Axis-6 anchor baseline exists. If no baseline exists, just visually confirm the anchor demo still renders correctly — it should be untouched.)

The anchor must be visually identical to the pre-Axis-6 state. If it isn't, Axis 6 changes have leaked into the anchor path — investigate.

- [ ] **Step 3: Visual sign-off pass with the user**

Open the editor (`"C:/Godot/Godot_v4.5-stable_win64.exe" --path "D:/assets/world 4/the world 4"`), open scale_demo.tscn, run with F6, and walk around. Confirm:
- Biome transitions are soft at all boundaries (no hard cuts).
- Per-biome character is preserved (alpine reads alpine, desert reads desert, etc.).
- No new artifacts (speckles, black quads, banding) that aren't already known.

Per PITFALLS methodology: editor view is the ground truth, not the headless capture.

- [ ] **Step 4: Commit the regression captures**

```bash
git -C "D:/assets/world 4" add "the world 4/captures/anchor_walk.png" "the world 4/captures/scale_2tile_walk.png" "the world 4/captures/scale_2tile_topdown.png"
git -C "D:/assets/world 4" commit -m "axis6: 5f final regression captures (anchor + scale_demo)"
```

**Stage 5f exit gate:** all 5 stages complete, regression captures clean, user editor sign-off received.

---

## Self-review summary

After completing all stages, verify against the spec
(`docs/plans/AXIS6_TRANSITIONS_DESIGN_2026_05_12.md`):

- [ ] Success criterion 1: "No hard tile-boundary seams visible in walk view of scale_demo." → Verified by Stage 5b capture + Stage 5f user sign-off.
- [ ] Success criterion 2: "Transition width is art-directable per biome pair (or globally) without recompiling." → Verified by `--feather-width-m` CLI arg. (Per-pair width is a stretch feature, called out in portability doc.)
- [ ] Success criterion 3: "Adding a biome = drop kit + register in catalog + regenerate splats. No shader edits, no GDScript edits." → Verified by the catalog-driven pipeline; documented in portability guide.
- [ ] Success criterion 4: "Scales to ≥15 active biomes with no architectural changes." → Verified by the design (texture array layer count, slot pool size). Not stress-tested at 15 biomes in v1 but architecturally unblocked.
- [ ] Success criterion 5: "Adding a new resolution tier = add array uniform + slot pool. No shader logic changes." → Verified by the shader's per-tier branching; documented in portability guide.
- [ ] Success criterion 6: "Worst-case transition blending costs ≤ 10% frame time." → Verify via FPS HUD inspection during the editor sign-off; if regressed, investigate.
- [ ] Success criterion 7: "Anchor demo and scale_demo single-biome view remain visually identical." → Verified by Stage 5f regression captures.

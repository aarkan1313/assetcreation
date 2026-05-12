# Workflow — debugging terrain artifacts

> When something looks wrong on the terrain. The discipline below has
> resolved every shipped W4 visual bug (see `reference/PITFALLS.md`
> for the full set).

## Step 0: characterize the artifact

Before touching anything, **describe what you see** in exact terms.
Common artifact classes:

- **Black speckles / specks** — random dark pixels.
- **Scan lines** — horizontal or vertical dark stripes.
- **Bands / fingerprints** — periodic patterns at tile boundaries.
- **Dark seams** — straight lines at known geometry edges.
- **Z-fight pepper** — salt-and-pepper noise at overlap regions.
- **Cliffs / discontinuities** — height jumps at boundaries.
- **Flat / shadeless regions** — areas missing lighting.

Match the description against `reference/PITFALLS.md` first. If it
matches a known class, jump to the fix recipe there.

## Step 1: headless vs editor

Confirm whether the artifact shows in both:

- **Headless capture** (`HeadlessCapture.gd` → PNG): reproducible,
  easy to share.
- **Editor F6**: catches things headless hides (Vulkan vs OpenGL
  driver differences — PITFALLS #6b is the canonical example).

If editor-only: the artifact is probably driver-specific. Run a
walk-around with WASD to see if it's view-angle-dependent (skirt
gap), texel-grid-dependent (filter mismatch), or tile-boundary-dependent
(per-tile splat).

## Step 2: isolate the change

If the artifact appeared in the last N commits:

```bash
git log --oneline -10
git diff <last-known-good>..HEAD -- "world 4/the world 4/shaders/" "world 4/the world 4/scripts/"
```

If the artifact has always been there: probably architectural. Look
in `PITFALLS.md` for the matching class.

## Step 3: change one thing at a time

The cardinal rule from PITFALLS. The user has burned hours on this
before. **Do not** change two suspected fixes in one iteration.

Iteration loop:

1. Form a hypothesis.
2. Make the smallest change that tests it.
3. Re-capture headless + editor.
4. If fixed → great, find the WHY before claiming victory. If not →
   revert and try a different hypothesis.

## Step 4: document the diagnosis

Once fixed:

- **Add a PITFALLS entry** if the bug class is new. Format: symptom →
  root cause → fix. See existing entries for tone.
- **Update STATE.md** "Known pitfalls" count.
- **In the commit message**, name the symptom + the root cause. Future
  you will grep this when the same class of bug returns.

## Diagnostic toolkit

### Save the heightmap

For displacement bugs, dump the actual height values:

```python
"C:/Program Files/Python312/python.exe" "D:/assets/world 4/pipeline/build_kernel_preview.py" \
  --catalog "D:/assets/world 4/the world 4/worlds/<world>/biome_catalog.json" \
  --out "D:/tmp/preview" --resolution 512 --extent-m 4096 --seed 42
```

Inspect `D:/tmp/preview/height.png` (grayscale heightmap) and
`biome_dominant.png` (biome partition).

### Headless dump from GDScript

For runtime-state bugs (ring positions, snap math), the
`KernelDump.gd` and `QualityTiersDump.gd` patterns work:

1. Write a SceneTree script `scripts/_debug_dump.gd` that
   `extends SceneTree`, computes the suspect state, prints / writes
   it to a JSON file, and `quit(0)`.
2. Run headless: `Godot --headless -s scripts/_debug_dump.gd -- --out "D:/tmp/dump.json"`.
3. Inspect the JSON.

### Save intermediate textures from a shader

Add a `DEBUG_OUTPUT` uniform to the shader. When set, output the
suspect intermediate as ALBEDO. Re-capture. Revert before commit.

### Visualize ring layout

The topdown capture shows ring partitions clearly. If rings overlap
or gap, it's immediately visible. Walk view masks layout bugs.

## Cross-references

- Canonical pitfall list: `reference/PITFALLS.md`
- Workflow for capturing: `verifying-visual-change.md`
- Examples of past debugging sagas: `historical/`

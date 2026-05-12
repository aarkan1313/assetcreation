# Workflow — working with quality tiers

> The quality-tier system (shipped 2026-05-12) controls every
> performance-sensitive knob in W4. New subsystems consume tier values
> via a resolver call; they never branch on the tier string.

## The contract

- **Source of truth:** `the world 4/config/quality_tiers.json`. Four
  tiers: `low`, `medium`, `high` (default), `ultra`.
- **GDScript consumers** call `QualityTiers.get_current()` → typed
  Dictionary. Read named keys.
- **Python consumers** call `quality_tiers.resolve()` → typed dict. Same
  shape.
- **Cross-impl test** (`tests/test_quality_tiers_cross_impl.py`) pins
  both sides to identical values + types.

The tier is read once at startup from
`ProjectSettings("world/quality_tier")` (default `high`). Changing the
tier requires a scene reload — there's no hot-reload yet.

## Adding a new knob

When you add a feature that has a perf trade-off (e.g. shadow cascade
count, foliage density), put it in the tier system instead of hardcoding
a default:

1. **Add the knob to all 4 tiers** in `config/quality_tiers.json`. Pick
   reasonable values across the range — Low gets the cheap version,
   Ultra gets the expensive one.
2. **Add the key to `KNOWN_KEYS`** in `pipeline/quality_tiers.py`. The
   `test_every_tier_has_every_known_key` test will fail if you miss a
   tier in step 1.
3. **If the value is int-typed in GDScript**, add it to `_INT_KEYS` in
   `scripts/QualityTiers.gd`. Godot's JSON parser returns all numbers
   as float; the resolver coerces ints back. Forgetting this means
   `range(cfg["my_int_key"])` crashes.
4. **Add a sanity range** to `test_resolve_values_sane` in
   `tests/test_quality_tiers.py` — pin the value to a plausible interval
   so a typo in the JSON fails CI.
5. **Run the full test suite**:
   ```bash
   cd "world 4" && python -m pytest tests/test_quality_tiers.py tests/test_quality_tiers_cross_impl.py -v
   ```
   Both must pass before you start consuming the knob.

## Consuming a knob (GDScript)

```gdscript
func _ready() -> void:
    var qt: Dictionary = QualityTiers.get_current()
    var ring_count: int = qt["ring_count"]       # already coerced to int
    var update_s: float = qt["update_interval_s"]
    # ... use the values, never the tier string
```

**Do not** do:
```gdscript
if qt["_tier"] == "low":     # ❌ defeats Phase 2 overrides
    ring_count = 3
```

Instead, **always read the named value**. If you need a tier-specific
behavior that doesn't fit a single knob, add a new knob (see "Adding a
new knob" above).

## Consuming a knob (Python pipeline)

```python
from quality_tiers import resolve

cfg = resolve()                      # default tier (high)
# or: cfg = resolve("low")           # explicit
size = cfg["splat_texture_array_size"]
```

For CLI tools, accept `--quality-tier` as an arg:

```python
ap.add_argument("--quality-tier", default=None)
args = ap.parse_args()
cfg = resolve(args.quality_tier)
```

## Phase 2 — custom overrides (not yet shipped)

The architecture is set up to add a custom-overrides layer as a
one-file change. When that ships:

```gdscript
QualityTiers.apply_overrides({"ring_grid_n": 192})   # not yet implemented
```

Consumers don't change — they keep reading `qt["ring_grid_n"]` and
get `192` instead of the tier default.

If you find yourself wanting overrides before they ship, that's a
signal to prioritize Phase 2. Don't work around it by reading the tier
string and branching.

## Common mistakes

- **Adding a knob to the JSON but forgetting `KNOWN_KEYS`**: silent
  failure mode. The `test_every_tier_has_every_known_key` test catches
  *missing* tier values but not missing `KNOWN_KEYS` entries. Manual
  discipline.
- **Float-typing what should be int**: see step 3 above.
- **Hardcoding the tier string in consumer code**: defeats Phase 2.
  Always go through the resolver.
- **Reading the resolver in a hot loop**: `get_current()` is cached
  after first call, but read it once at `_ready` time and cache the
  result locally. Cheap, but explicit caching documents intent.

## Cross-references

- Spec: `superpowers/specs/2026-05-12-quality-tiers-design.md`
- Plan: `superpowers/plans/2026-05-12-quality-tiers.md`
- GDScript resolver: `the world 4/scripts/QualityTiers.gd`
- Python resolver: `pipeline/quality_tiers.py`
- JSON source: `the world 4/config/quality_tiers.json`
- Tests: `tests/test_quality_tiers.py`, `tests/test_quality_tiers_cross_impl.py`

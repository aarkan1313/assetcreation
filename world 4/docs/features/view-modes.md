# Feature — View Modes

> Three view treatments (walk / iso / topdown) over the same world,
> swapped at runtime by hotkey 1/2/3. Each gets its own shader, its own
> material binding, and its own loaded-tile radius.
>
> For the underlying world pipeline see `world-pipeline.md`.

## What this feature is

Walk, iso, and topdown are three ways to look at the same scale_demo
world. Same geometry, same texture catalog, but each rendered with a
shader tuned for its viewing distance and aesthetic.

| Mode | Hotkey | Camera | Shader | Radius |
|---|---|---|---|---|
| Walk | 1 | Perspective, eye-level (~1.8 m), 70° FOV | `terrain_scale_v1.gdshader` | 1 tile (3×3) — streaming |
| Iso | 2 | Perspective, 30° iso angle, ~700 m distance | `terrain_view_iso.gdshader` | 8 tiles — whole world |
| Topdown | 3 | Orthographic, straight down | `terrain_view_topdown.gdshader` | 8 tiles — whole world |

Hotkey 1/2/3 swaps:
1. The active `Camera3D` (built by `AnchorCameraRig._setup_cameras`)
2. The per-tile `material_override` (via `ScaleWorld.set_view_mode`)
3. The loaded-tile radius (so iso/topdown load the whole world,
   walk uses the narrow streaming radius)
4. The mouse-capture state (walk = captured, others = visible)
5. The HUD hint text

## Shader differences

All three shaders share:
- `render_mode unshaded, cull_back, depth_draw_opaque` (Pitfall #3)
- 3-slot slope-blended albedo pipeline (ground / mid / rock)
- `luma_floor` + `ao_floor` guardrails (Pitfall #1)
- World-XZ UV from `v_world_pos` for cross-tile continuity

What differs per view:

### Walk — `terrain_scale_v1.gdshader`
The baseline. Manual lambertian with sun + ambient + lambert_floor (0.35).
`sun_intensity = 1.0`, `ambient_strength = 0.45`. Designed for eye-level
viewing where slope cues read as terrain detail.

### Iso — `terrain_view_iso.gdshader`
Flatter lighting for 2.5D viewing.
- `lambert_floor` raised 0.35 → 0.55 (no black shadows on dark side)
- `sun_intensity` dropped 1.0 → 0.5 (highlights don't dominate)
- `ambient_strength` raised 0.45 → 0.65 (silhouette has body)
- `form_light_strength = 0.18` — brightens upward-facing fragments
  to push hill shapes forward

### Topdown — `terrain_view_topdown.gdshader`
Cartographic hillshade replaces lambertian.
- No `sun_dir`/`lambert_floor` — those uniforms aren't in the shader
- `hillshade_dir = (-0.45, 0.78, 0.43)` — upper-left virtual sun
- `hillshade_min/max = 0.55/1.20` — clamps so dark side is readable
  and bright side has slight overshoot
- `sepia_amount = 0.25` mixes 25% toward `(0.96, 0.88, 0.74)` — warm
  topographic-map palette
- `saturation = 1.10` — slight saturation gain to keep the sepia from
  reading muddy

## Per-view radius bumps

Walk wants narrow streaming radius (3×3 = 9 tiles loaded) because the
player is at eye-level and only sees nearby terrain. Iso and topdown
want the whole world loaded because the player is surveying.

`ScaleWorld.set_view_mode(mode_name)` does:
1. Look up the view's `view_radius_*` export
2. If specified (≥0), update `view_radius_tiles` and call `_repage(true)`
3. Synchronously drain the spawn queue so the new tiles are visible
   before the next frame

Default radii (`scale_demo.tscn`):
- `view_radius_walk = 1` (3×3 = 9 tiles)
- `view_radius_iso = 8` (effectively whole world for 4×4 grid)
- `view_radius_topdown = 8`

## Controls

| Action | Walk | Iso | Topdown |
|---|---|---|---|
| Pan | WASD (camera-local) | WASD (world XZ) | WASD (world XZ) |
| Sprint | Shift = 4× | Shift = 3× × 4× base | Shift = 3× × 8× base |
| Rotate camera | Mouse-look | — | — |
| Zoom | Q/E vertical | — | Scroll wheel (orthographic size) |
| Release mouse | Esc | (already free) | (already free) |
| Re-capture mouse | F | — | — |

Walk velocity = `walk_speed` (default 12 m/s). Iso pans at `walk_speed × 4`,
topdown at `walk_speed × 8` — surveys faster than walking.

## How to add a new view mode

1. **Write a new shader** following the pattern in
   `terrain_view_iso.gdshader` — `unshaded`, same 3-slot albedo pipeline,
   own lighting math.
2. **Add a `.tres` binding** via `pipeline/write_material_tres_views.py`
   (extend the script to emit your new material).
3. **Add a `Camera3D`** + `_setup_cameras` configuration in
   `AnchorCameraRig.gd`.
4. **Add a `CameraMode` enum entry** + hotkey in `_unhandled_input`.
5. **Add a `_process_<mode>` function** for that camera's movement.
6. **Add `view_material_<mode>` + `view_radius_<mode>`** exports in
   `ScaleWorld.gd`.
7. **Update `ScaleWorld.set_view_mode`'s match block** to dispatch.
8. **Update `AnchorCameraRig._set_mode`'s match block** to send the
   mode name.
9. **Wire the new exports in `scale_demo.tscn`.**

That's ~9 touch points for a clean addition. The plumbing is the
expensive part; the shader itself is a copy-and-tune from one of the
existing three.

## What's not in this feature yet

See `strategy/WISHLIST.md` "Axis 4 (View) follow-ups":
- Topdown contour lines (every N meters)
- Iso silhouette outline (edge detect for hill silhouettes)
- Per-view env tonemap (currently FILMIC for all)
- Headless topdown framing edge case (L-shaped crop in OpenGL captures)
- True multi-scale zoom (Crimson Desert style) — stretch goal

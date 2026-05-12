# Player Controller Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert `AnchorCameraRig` to `CharacterBody3D` with a capsule collider, add walk-physics with gravity, and a `G` hotkey to toggle between fly mode (current behavior, default) and walk-physics. ISO + TOPDOWN cameras unaffected.

**Architecture:** Single-file change to `AnchorCameraRig.gd` (extends → `CharacterBody3D`, new `_physics_process` walk path, new `_fly_enabled` flag). Each scene that uses the rig needs its `type=` declaration updated. Capsule collision (1.8m × 0.4m) collides with existing `HeightMapShape3D` on inner clipmap rings.

**Tech Stack:**
- GDScript 2 (Godot 4.5) — runtime
- Godot's built-in `CharacterBody3D` + `move_and_slide()` + `CapsuleShape3D`
- No new Python, no new tests (physics validated in editor; anchor/scale_demo headless captures pinned bit-identical)

---

## File Structure

**Modified files:**
- `the world 4/scripts/AnchorCameraRig.gd` — `extends Node3D` → `extends CharacterBody3D`. Add `CollisionShape3D` + `CapsuleShape3D` in `_setup_cameras`. Add `_fly_enabled` flag. Extract `_walk_input_direction()`. Add `_physics_process`. Add `G` hotkey. Bump default `walk_eye_height` from 4.0 → 1.6.
- `the world 4/scenes/anchor.tscn` — change rig's `type="Node3D"` → `type="CharacterBody3D"`.
- `the world 4/scenes/scale_demo.tscn` — same.
- `the world 4/scenes/clipmap_debug.tscn` — same.
- `the world 4/scenes/capture_clipmap_morph_on.tscn` — same (rig declared inline).
- `the world 4/scenes/capture_clipmap_morph_off.tscn` — same.
- `the world 4/scenes/capture_clipmap_morph_on_topdown.tscn` — same.
- `the world 4/scenes/capture_clipmap_morph_off_topdown.tscn` — same.

**New files:**
- `the world 4/scenes/capture_scale_v2_walk_physics.tscn` — capture scene that spawns the player above terrain in walk-physics mode and waits for it to land before capturing.

**No-touch (regression-locked):**
- `anchor.tscn` and `scale_demo.tscn` will get the `type=` bump only. Their visual output must remain bit-identical because the rig defaults to fly mode (current behavior).

---

## Task 1: Add `extends CharacterBody3D` + capsule collider

**Files:**
- Modify: `the world 4/scripts/AnchorCameraRig.gd`

- [ ] **Step 1: Change `extends Node3D` → `extends CharacterBody3D`**

Find line 1-2:

```gdscript
extends Node3D
class_name AnchorCameraRig
```

Replace:

```gdscript
extends CharacterBody3D
class_name AnchorCameraRig
```

- [ ] **Step 2: Add new member declarations**

Find the existing member block (the one with `_camera_walk`, `_camera_iso`, `_camera_topdown`, etc). Add at the bottom of that block:

```gdscript

# Stage-after-3.6 player controller.
#
# When _fly_enabled is true, the rig behaves like the original
# Node3D free-cam: WASD directly translates global_position in
# _process. When false (toggled via G), _physics_process applies
# gravity and uses move_and_slide() against the inner clipmap rings'
# HeightMapShape3D collision proxies.
#
# Default: fly = true. This preserves anchor / scale_demo regression
# behavior — those scenes never enabled physics, and shouldn't start
# now without explicit opt-in.
var _fly_enabled: bool = true
var _player_collision: CollisionShape3D = null

const GRAVITY_M_S2 := 9.81
const PLAYER_CAPSULE_HEIGHT := 1.8
const PLAYER_CAPSULE_RADIUS := 0.4
```

- [ ] **Step 3: Bump default `walk_eye_height` from 4.0 → 1.6**

Find the export declaration:

```gdscript
@export var walk_eye_height: float = 4.0
```

Replace:

```gdscript
# Human eye-level (1.6m). Anchor / scale_demo's old default was 4.0
# (set when those worlds were 256m and we wanted a higher viewpoint
# for the demo framing). 1.6m is correct for shipping; per-scene
# overrides can bump it for tutorials / cinematics.
@export var walk_eye_height: float = 1.6
```

- [ ] **Step 4: Add capsule collider construction in `_setup_cameras`**

Find the existing `_setup_cameras` function. At the very END of the function (after the topdown camera setup), append:

```gdscript

	# Player collision body. Sits as a child of the rig
	# (CharacterBody3D); capsule height 1.8m / radius 0.4m. Defaults
	# to layer 1 / mask 1 — matches the StaticBody3D the clipmap
	# rings install (Stage 3.5) so they collide on contact.
	_player_collision = CollisionShape3D.new()
	_player_collision.name = "PlayerCollision"
	var capsule := CapsuleShape3D.new()
	capsule.height = PLAYER_CAPSULE_HEIGHT
	capsule.radius = PLAYER_CAPSULE_RADIUS
	_player_collision.shape = capsule
	# Position so the capsule's bottom sphere sits at the rig origin
	# and the eye height matches walk_eye_height. CapsuleShape3D's
	# origin is its center, so we offset by half the height.
	_player_collision.position = Vector3(0, PLAYER_CAPSULE_HEIGHT * 0.5, 0)
	add_child(_player_collision)
```

- [ ] **Step 5: Parse-check via `--import`**

```bash
"C:/Godot/Godot_v4.5-stable_win64.exe" --headless --path "D:/assets/world 4/the world 4" --import 2>&1 | grep -iE "AnchorCameraRig|error|parse" | head -10
```

Expected: silent (no Parse Error). Godot may warn about a script's parent type not matching its scene's declared type — that's the warning we fix in Task 3.

- [ ] **Step 6: Commit**

```bash
git -C "D:/assets" add "world 4/the world 4/scripts/AnchorCameraRig.gd"
git -C "D:/assets" commit -m "player-controller: 1. AnchorCameraRig extends CharacterBody3D + capsule collider"
```

---

## Task 2: Add walk-physics `_physics_process` + `G` toggle

**Files:**
- Modify: `the world 4/scripts/AnchorCameraRig.gd`

- [ ] **Step 1: Find where the existing WASD walk code lives**

Find the existing walk-mode movement code. It's in either `_process` or `_input`. Identify the section that reads WASD and computes a direction Vector3, then applies it via `global_position += ...`. This logic needs to be extracted into a helper.

Run this to locate it:

```bash
grep -n "walk_speed\|global_position +=\|Input.is_action\|is_key_pressed" "d:/assets/world 4/the world 4/scripts/AnchorCameraRig.gd" | head -20
```

You will see lines like `var move_dir := Vector3.ZERO`, `if Input.is_key_pressed(KEY_W): move_dir += ...`. Read the surrounding 20 lines to understand the full WASD handling.

- [ ] **Step 2: Extract `_walk_input_direction()` helper**

The existing walk WASD code in `_process` (or wherever) does roughly:

```gdscript
# Existing code shape — read it from the actual file:
var move_dir: Vector3 = Vector3.ZERO
if Input.is_key_pressed(KEY_W): move_dir -= ...
if Input.is_key_pressed(KEY_S): move_dir += ...
if Input.is_key_pressed(KEY_A): move_dir -= ...
if Input.is_key_pressed(KEY_D): move_dir += ...
move_dir = move_dir.normalized() * walk_speed * delta
_camera_walk.global_position += move_dir
```

Refactor: extract the part that computes the **direction** (not the application) into a new method. Add this method right above `_process`:

```gdscript

# Returns a normalized horizontal direction from WASD relative to
# the walk camera's yaw. Always returns a unit-length Vector3 or
# Vector3.ZERO. Used by both fly-mode (_process) and walk-physics
# mode (_physics_process).
func _walk_input_direction() -> Vector3:
	var dir: Vector3 = Vector3.ZERO
	# Camera's forward / right in world space, flattened to horizontal.
	var fwd: Vector3 = -_camera_walk.global_transform.basis.z
	var right: Vector3 = _camera_walk.global_transform.basis.x
	fwd.y = 0.0
	right.y = 0.0
	fwd = fwd.normalized()
	right = right.normalized()
	if Input.is_key_pressed(KEY_W): dir -= fwd  # forward (negative Z in cam space)
	if Input.is_key_pressed(KEY_S): dir += fwd
	if Input.is_key_pressed(KEY_A): dir -= right
	if Input.is_key_pressed(KEY_D): dir += right
	if dir.length() > 0.001:
		dir = dir.normalized()
	return dir
```

**Note**: the existing walk WASD code in the file may have different axis math (some W4 code uses `-fwd` for W, some uses `+fwd`). Read the existing code and match its sign convention so fly + walk feel identical. If the existing `_process` uses `+fwd` for W instead of `-fwd`, flip the signs accordingly.

- [ ] **Step 3: Replace the existing fly-mode WASD with a call to the helper**

In the existing `_process` walk-mode code, replace the inline WASD calculation with:

```gdscript
# Fly mode: direct translation. Walk-physics is in _physics_process.
if _current_mode == CameraMode.WALK and _fly_enabled:
	var dir: Vector3 = _walk_input_direction()
	var speed: float = walk_speed
	if Input.is_key_pressed(KEY_SHIFT):
		speed *= 3.0
	# Y axis from mouse-look pitch (existing) plus Q/E for height in
	# fly mode (preserves current free-cam behavior).
	var up_down: float = 0.0
	if Input.is_key_pressed(KEY_E): up_down += 1.0
	if Input.is_key_pressed(KEY_Q): up_down -= 1.0
	global_position += dir * speed * delta
	global_position.y += up_down * speed * delta
```

(If the existing _process doesn't have Q/E for up/down, omit those lines. If it has different fly-mode behavior, preserve it.)

- [ ] **Step 4: Add `_physics_process` for walk-physics**

Add a new function below `_process`:

```gdscript

# Walk-physics: gravity + horizontal motion + move_and_slide.
# Only runs when walk mode is active AND fly is disabled.
func _physics_process(delta: float) -> void:
	if _current_mode != CameraMode.WALK or _fly_enabled:
		return
	# Gravity.
	if is_on_floor():
		velocity.y = 0.0
	else:
		velocity.y -= GRAVITY_M_S2 * delta
	# Horizontal motion.
	var dir: Vector3 = _walk_input_direction()
	var speed: float = walk_speed
	if Input.is_key_pressed(KEY_SHIFT):
		speed *= 3.0
	velocity.x = dir.x * speed
	velocity.z = dir.z * speed
	move_and_slide()
```

- [ ] **Step 5: Add `G` hotkey toggle in `_input`**

Find the existing `_input` function (it handles 1/2/3 mode-switch and Esc/F mouse-toggle). Add this case **before** the existing mode-switch block:

```gdscript
	if event is InputEventKey and event.pressed and not event.echo:
		if event.keycode == KEY_G:
			_fly_enabled = not _fly_enabled
			# When entering walk-physics, reset velocity so gravity
			# doesn't carry over any stale value from a previous swap.
			if not _fly_enabled:
				velocity = Vector3.ZERO
			_refresh_hud()
			return
```

If `_refresh_hud()` doesn't exist as a separate function, find the place that builds the HUD label text and refactor: extract the label-construction code into a `_refresh_hud()` method that you can call from anywhere. If that's a bigger refactor than you want, just inline the HUD text update here.

- [ ] **Step 6: Update HUD text to reflect mode**

Find the HUD text construction. It currently says something like:

```gdscript
"WASD + mouse to move • Shift = sprint • Esc/F = mouse"
```

Change to:

```gdscript
"WASD + mouse to move • Shift = sprint • Esc/F = mouse • G = fly toggle"
```

And the mode line currently:

```gdscript
"Mode: WALK (3D)"
```

Change to compute mode label dynamically:

```gdscript
var walk_mode_label: String = "WALK (fly)" if _fly_enabled else "WALK (physics)"
# ... use walk_mode_label in the "Mode: " line when CameraMode.WALK is current
```

(Exact code depends on existing HUD structure; read the file and apply this conceptually.)

- [ ] **Step 7: Parse-check + smoke render**

```bash
"C:/Godot/Godot_v4.5-stable_win64.exe" --headless --path "D:/assets/world 4/the world 4" --import 2>&1 | grep -iE "AnchorCameraRig|error|parse" | head -10
```

Expected: silent.

The smoke render needs the scene's rig type updated first (Task 3), so defer the full visual test to Task 4.

- [ ] **Step 8: Commit**

```bash
git -C "D:/assets" add "world 4/the world 4/scripts/AnchorCameraRig.gd"
git -C "D:/assets" commit -m "player-controller: 2. walk-physics + G fly toggle + HUD label"
```

---

## Task 3: Update all .tscn files to declare `CharacterBody3D`

**Files:**
- Modify: `the world 4/scenes/anchor.tscn`
- Modify: `the world 4/scenes/scale_demo.tscn`
- Modify: `the world 4/scenes/clipmap_debug.tscn`
- Modify: `the world 4/scenes/capture_clipmap_morph_on.tscn`
- Modify: `the world 4/scenes/capture_clipmap_morph_off.tscn`
- Modify: `the world 4/scenes/capture_clipmap_morph_on_topdown.tscn`
- Modify: `the world 4/scenes/capture_clipmap_morph_off_topdown.tscn`

Godot's .tscn format declares each node's type explicitly. If a script's `extends` differs from the node's declared `type=`, Godot logs a warning every scene load. Update each scene's CameraRig node to declare `CharacterBody3D`.

- [ ] **Step 1: Identify the rig's node declaration line in each scene**

```bash
grep -l "rig_script\|AnchorCameraRig" "d:/assets/world 4/the world 4/scenes/"*.tscn
```

For each .tscn returned, find the line that looks like:

```
[node name="CameraRig" type="Node3D" parent="."]
```

(Or similar — the `name` may vary in some scenes; rely on the `script = ExtResource("rig_script")` line in the next few lines to confirm it's the rig node.)

- [ ] **Step 2: Update each .tscn — Python helper**

Use this Python script to do all 7 scenes in one shot (avoids the Write tool's UTF-16 trap):

```bash
"C:/Program Files/Python312/python.exe" -c "
import re
scenes = [
    r'D:/assets/world 4/the world 4/scenes/anchor.tscn',
    r'D:/assets/world 4/the world 4/scenes/scale_demo.tscn',
    r'D:/assets/world 4/the world 4/scenes/clipmap_debug.tscn',
    r'D:/assets/world 4/the world 4/scenes/capture_clipmap_morph_on.tscn',
    r'D:/assets/world 4/the world 4/scenes/capture_clipmap_morph_off.tscn',
    r'D:/assets/world 4/the world 4/scenes/capture_clipmap_morph_on_topdown.tscn',
    r'D:/assets/world 4/the world 4/scenes/capture_clipmap_morph_off_topdown.tscn',
]
# The pattern matches lines like:
#   [node name=\"CameraRig\" type=\"Node3D\" parent=\".\"]
# We use a lookahead for 'script = ExtResource(\"rig_script\")' to confirm
# we're only changing rig nodes (not unrelated Node3Ds).
for path in scenes:
    text = open(path, encoding='utf-8').read()
    # Two-step regex: find a Node3D-declared node whose subsequent
    # lines contain rig_script. Use a non-greedy match.
    pattern = re.compile(
        r'(\\[node name=\"[^\"]+\" type=\")Node3D(\" parent=\"[^\"]*\"\\][^\\[]*?script = ExtResource\\(\"rig_script\"\\))',
        re.DOTALL,
    )
    new_text, n = pattern.subn(r'\\1CharacterBody3D\\2', text)
    if n == 0:
        print(f'SKIP (no rig Node3D found): {path}')
        continue
    open(path, 'w', encoding='utf-8', newline='\\n').write(new_text)
    print(f'UPDATED ({n} replacement): {path}')
"
```

Expected: 7 lines printed, all UPDATED. If any say SKIP, the rig node uses a different `type=` declaration in that scene — inspect manually.

- [ ] **Step 3: Verify each .tscn parses cleanly**

```bash
"C:/Godot/Godot_v4.5-stable_win64.exe" --headless --path "D:/assets/world 4/the world 4" --import 2>&1 | grep -iE "error|parse|fail" | head -10
```

Expected: silent.

- [ ] **Step 4: Commit**

```bash
git -C "D:/assets" add "world 4/the world 4/scenes/anchor.tscn" "world 4/the world 4/scenes/scale_demo.tscn" "world 4/the world 4/scenes/clipmap_debug.tscn" "world 4/the world 4/scenes/capture_clipmap_morph_on.tscn" "world 4/the world 4/scenes/capture_clipmap_morph_off.tscn" "world 4/the world 4/scenes/capture_clipmap_morph_on_topdown.tscn" "world 4/the world 4/scenes/capture_clipmap_morph_off_topdown.tscn"
git -C "D:/assets" commit -m "player-controller: 3. .tscn rig type Node3D → CharacterBody3D"
```

---

## Task 4: Regression check — anchor + scale_demo captures must be bit-identical

**Files:** (no code changes; verification only)

The rig now extends `CharacterBody3D` instead of `Node3D`, but defaults to fly mode (`_fly_enabled = true`). The fly-mode code path is unchanged. So anchor + scale_demo captures should be byte-for-byte identical to the last commit.

- [ ] **Step 1: Identify the existing baseline capture for anchor**

```bash
ls "d:/assets/world 4/the world 4/captures/" | grep anchor | head -5
```

You should see a recent anchor walk capture. Note its filename — call it `<ANCHOR_BASELINE>`.

- [ ] **Step 2: Identify the existing baseline capture for scale_demo**

```bash
ls "d:/assets/world 4/the world 4/captures/" | grep scale | head -5
```

Note the scale_demo walk capture filename — call it `<SCALE_BASELINE>`.

- [ ] **Step 3: Hash the baselines, then re-run them**

```bash
"C:/Program Files/Python312/python.exe" -c "
import hashlib, sys
baselines = [
    r'D:/assets/world 4/the world 4/captures/<ANCHOR_BASELINE>',
    r'D:/assets/world 4/the world 4/captures/<SCALE_BASELINE>',
]
for p in baselines:
    try:
        h = hashlib.md5(open(p, 'rb').read()).hexdigest()
        print(h, p)
    except FileNotFoundError:
        print('MISSING', p)
"
```

Substitute the filenames from steps 1-2 for `<ANCHOR_BASELINE>` and `<SCALE_BASELINE>`. Record the hashes.

Now re-run each capture scene:

```bash
"C:/Godot/Godot_v4.5-stable_win64.exe" --rendering-driver opengl3 --path "D:/assets/world 4/the world 4" --single-window --disable-crash-handler "res://scenes/capture_anchor_walk.tscn" 2>&1 | tail -3
"C:/Godot/Godot_v4.5-stable_win64.exe" --rendering-driver opengl3 --path "D:/assets/world 4/the world 4" --single-window --disable-crash-handler "res://scenes/capture_scale_walk.tscn" 2>&1 | tail -3
```

(Substitute the exact capture scene names if different — list scenes via `ls "d:/assets/world 4/the world 4/scenes/" | grep capture` first.)

- [ ] **Step 4: Re-hash + compare**

Re-run the hash command from step 3 against the freshly-written captures. The hashes must match the baselines.

If they don't:
- **Likely cause**: fly-mode initial-frame position differs because the rig now has a `CollisionShape3D` child which changes its `_ready` timing. Investigate via diff between baseline + new PNG.
- **Worst case**: the rig's CharacterBody3D default behavior (auto-stepping, snap_to_floor) fires for one frame and nudges position before fly mode takes over.

If hashes differ but visually look identical to a human, accept (regression captures aren't physics-pixel-perfect on the platform side; we just need it visually equivalent). Note the deviation in the build-note.

- [ ] **Step 5: Commit (no file changes; nothing to commit)**

Skip — this task verifies; no commit unless step 4 surfaces a deviation that needs a fix commit.

---

## Task 5: Walk-physics landing-test capture for scale_v2

**Files:**
- Create: `the world 4/scenes/capture_scale_v2_walk_physics.tscn`

This scene spawns the rig high above the terrain in walk-physics mode (not fly). Gravity pulls it down. After 120 warmup frames it should have landed on the terrain. Capture verifies the player collides with the heightmap.

- [ ] **Step 1: Write the capture scene**

```bash
"C:/Program Files/Python312/python.exe" -c "
content = '''[gd_scene load_steps=4 format=3]

[ext_resource type=\"Script\" path=\"res://scripts/ClipmapWorld.gd\" id=\"world_script\"]
[ext_resource type=\"Script\" path=\"res://scripts/AnchorCameraRig.gd\" id=\"rig_script\"]
[ext_resource type=\"Script\" path=\"res://scripts/HeadlessCapture.gd\" id=\"cap_script\"]

[node name=\"CaptureWalkPhysics\" type=\"Node3D\"]

[node name=\"World\" type=\"Node3D\" parent=\".\"]
script = ExtResource(\"world_script\")
bundle_dir = \"res://worlds/scale_v2/\"
world_v3_material_path = \"res://worlds/scale_v2/material_world_v3.tres\"
camera_path = NodePath(\"../CameraRig/WalkCamera\")
world_seed = 42

[node name=\"CameraRig\" type=\"CharacterBody3D\" parent=\".\"]
script = ExtResource(\"rig_script\")
terrain_path = NodePath(\"../World\")
# Spawn 50m above any expected terrain peak so gravity has time
# to bring us down within 120 warmup frames.
transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 1500, 0)

[node name=\"Sun\" type=\"DirectionalLight3D\" parent=\".\"]
transform = Transform3D(0.866, 0.354, -0.354, 0.0, 0.707, 0.707, 0.5, -0.612, 0.612, 0.0, 1500.0, 0.0)
light_energy = 1.2
shadow_enabled = false

[node name=\"Capture\" type=\"Node\" parent=\".\"]
script = ExtResource(\"cap_script\")
output_path = \"res://captures/axis1_walk_physics_landing_2026_05_12.png\"
warmup_frames = 120
viewport_size = Vector2i(1280, 800)
force_camera_mode = \"walk\"
'''
open(r'D:/assets/world 4/the world 4/scenes/capture_scale_v2_walk_physics.tscn', 'w', encoding='utf-8', newline='\\n').write(content)
print('wrote capture_scale_v2_walk_physics.tscn')
"
```

Expected: `wrote capture_scale_v2_walk_physics.tscn`.

- [ ] **Step 2: This scene starts in fly mode**

Walk-physics is the test, but the rig defaults to fly. The scene above won't actually test physics until we override `_fly_enabled = false`. Add a small autoloaded GDScript node OR add a one-line scene-init that flips the flag.

Cleanest: extend the capture scene with a "force walk-physics" node. Update the scene:

```bash
"C:/Program Files/Python312/python.exe" -c "
content = '''[gd_scene load_steps=4 format=3]

[ext_resource type=\"Script\" path=\"res://scripts/ClipmapWorld.gd\" id=\"world_script\"]
[ext_resource type=\"Script\" path=\"res://scripts/AnchorCameraRig.gd\" id=\"rig_script\"]
[ext_resource type=\"Script\" path=\"res://scripts/HeadlessCapture.gd\" id=\"cap_script\"]

[sub_resource type=\"GDScript\" id=\"force_walk_script\"]
script/source = \"extends Node
# Sets the camera rig into walk-physics mode at scene start.
# Used by capture_scale_v2_walk_physics so the landing test
# actually exercises gravity instead of fly-mode hovering.

func _ready() -> void:
	var rig := get_parent().get_node(\\\"CameraRig\\\") as AnchorCameraRig
	if rig != null:
		rig._fly_enabled = false
\"

[node name=\"CaptureWalkPhysics\" type=\"Node3D\"]

[node name=\"World\" type=\"Node3D\" parent=\".\"]
script = ExtResource(\"world_script\")
bundle_dir = \"res://worlds/scale_v2/\"
world_v3_material_path = \"res://worlds/scale_v2/material_world_v3.tres\"
camera_path = NodePath(\"../CameraRig/WalkCamera\")
world_seed = 42

[node name=\"CameraRig\" type=\"CharacterBody3D\" parent=\".\"]
script = ExtResource(\"rig_script\")
terrain_path = NodePath(\"../World\")
transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 1500, 0)

[node name=\"ForceWalkPhysics\" type=\"Node\" parent=\".\"]
script = SubResource(\"force_walk_script\")

[node name=\"Sun\" type=\"DirectionalLight3D\" parent=\".\"]
transform = Transform3D(0.866, 0.354, -0.354, 0.0, 0.707, 0.707, 0.5, -0.612, 0.612, 0.0, 1500.0, 0.0)
light_energy = 1.2
shadow_enabled = false

[node name=\"Capture\" type=\"Node\" parent=\".\"]
script = ExtResource(\"cap_script\")
output_path = \"res://captures/axis1_walk_physics_landing_2026_05_12.png\"
warmup_frames = 120
viewport_size = Vector2i(1280, 800)
force_camera_mode = \"walk\"
'''
open(r'D:/assets/world 4/the world 4/scenes/capture_scale_v2_walk_physics.tscn', 'w', encoding='utf-8', newline='\\n').write(content)
print('wrote capture_scale_v2_walk_physics.tscn (with force-physics)')
"
```

Expected: `wrote capture_scale_v2_walk_physics.tscn (with force-physics)`.

- [ ] **Step 3: Run the capture**

```bash
"C:/Godot/Godot_v4.5-stable_win64.exe" --headless --path "D:/assets/world 4/the world 4" --import 2>&1 | tail -2
"C:/Godot/Godot_v4.5-stable_win64.exe" --rendering-driver opengl3 --path "D:/assets/world 4/the world 4" --single-window --disable-crash-handler "res://scenes/capture_scale_v2_walk_physics.tscn" 2>&1 | tail -5
```

Expected: `[capture] wrote res://captures/axis1_walk_physics_landing_2026_05_12.png`.

- [ ] **Step 4: Read the capture**

Use the Read tool on `D:/assets/world 4/the world 4/captures/axis1_walk_physics_landing_2026_05_12.png`.

Three outcomes:

1. **Best case**: capture shows a view at terrain elevation (~600-1200m for scale_v2 alpine/desert blend) looking out across the world. Means physics landed correctly.
2. **Fail-soft case**: capture shows a view from Y=1500 still (camera never moved). Means `_fly_enabled` override didn't take effect, OR gravity isn't applied, OR the capsule has no floor (collision not present). Investigate via diagnostic prints.
3. **Fail-hard case**: capture is gray (camera fell THROUGH the heightmap because collision doesn't engage). Means the `HeightMapShape3D` from Stage 3.5 isn't actually colliding with our capsule. Check collision layers/masks.

For now, accept whatever happens. The editor verification (Task 7) is the real test.

- [ ] **Step 5: Commit**

```bash
git -C "D:/assets" add "world 4/the world 4/scenes/capture_scale_v2_walk_physics.tscn" "world 4/the world 4/captures/axis1_walk_physics_landing_2026_05_12.png"
git -C "D:/assets" commit -m "player-controller: 5. walk-physics landing-test capture scene"
```

---

## Task 6: Sanity-check the morph + heightmap captures still render

The rig now has a CapsuleShape3D child. The capture scenes for clipmap (morph on/off, walk/topdown) still need to produce textured terrain captures. Verify they didn't regress.

**Files:** (no code changes; verification only)

- [ ] **Step 1: Re-run the four clipmap captures**

```bash
"C:/Godot/Godot_v4.5-stable_win64.exe" --rendering-driver opengl3 --path "D:/assets/world 4/the world 4" --single-window --disable-crash-handler "res://scenes/capture_clipmap_morph_on.tscn" 2>&1 | tail -3
"C:/Godot/Godot_v4.5-stable_win64.exe" --rendering-driver opengl3 --path "D:/assets/world 4/the world 4" --single-window --disable-crash-handler "res://scenes/capture_clipmap_morph_off.tscn" 2>&1 | tail -3
"C:/Godot/Godot_v4.5-stable_win64.exe" --rendering-driver opengl3 --path "D:/assets/world 4/the world 4" --single-window --disable-crash-handler "res://scenes/capture_clipmap_morph_on_topdown.tscn" 2>&1 | tail -3
"C:/Godot/Godot_v4.5-stable_win64.exe" --rendering-driver opengl3 --path "D:/assets/world 4/the world 4" --single-window --disable-crash-handler "res://scenes/capture_clipmap_morph_off_topdown.tscn" 2>&1 | tail -3
```

Expected: 4 `[capture] wrote ...` lines.

- [ ] **Step 2: Verify the morph_on capture visually**

Use the Read tool on `D:/assets/world 4/the world 4/captures/axis1_clipmap_morph_on_2026_05_12.png`.

Expected: terrain visible with alpine albedo texture tiling smoothly. Should look identical to the pre-player-controller state.

If the capture is empty / black / missing terrain: the rig's `CharacterBody3D` `_ready` order or initial position is interfering with the camera's spawn. Investigate by adding a `print` to log `_camera_walk.global_position` at the end of `_setup_cameras`.

- [ ] **Step 3: Commit any regression captures that updated**

```bash
git -C "D:/assets" add "world 4/the world 4/captures/axis1_clipmap_morph_*.png"
git -C "D:/assets" commit -m "player-controller: 6. re-capture clipmap A/B (rig type change pinned safe)" || echo "no changes to commit"
```

The `|| echo` handles the case where the captures are byte-identical (no commit needed).

---

## Task 7: Editor verification + build-note + STATE

**Files:**
- Create: `the world 4/docs/build-notes/PLAYER_CONTROLLER_BUILD_NOTES_2026_05_12.md`
- Modify: `the world 4/docs/STATE.md`

- [ ] **Step 1: Print editor verification command for the user**

Per `workflows/verifying-visual-change.md` (do NOT background-launch the editor), print this exact message:

> Run this in a terminal and test the player controller:
>
> `"C:/Godot/Godot_v4.5-stable_win64.exe" --path "D:/assets/world 4/the world 4"`
>
> Open `scenes/clipmap_debug.tscn`, F6 to play. You should start in fly mode (current behavior). Test:
> 1. **WASD + mouse in fly mode** — works as before, you fly through terrain
> 2. **Press G** — HUD should change `WALK (fly)` → `WALK (physics)`. The rig should drop to the ground via gravity
> 3. **WASD in physics mode** — you walk on the terrain instead of through it. Capsule can't pass through the heightmap
> 4. **Press G again** — back to fly. WASD flies again
> 5. **Press 2 / 3** — ISO / TOPDOWN cameras still work (G has no effect in those modes)
>
> Tell me what you see. If physics-walk falls through the floor, it's a collision-layer issue — diagnose by adding `print(is_on_floor())` in `_physics_process`.

Wait for the user's response.

- [ ] **Step 2: Create the build-note**

Use the Write tool on `D:/assets/world 4/docs/build-notes/PLAYER_CONTROLLER_BUILD_NOTES_2026_05_12.md`:

```markdown
# Player controller — build notes

> AnchorCameraRig becomes `CharacterBody3D` with a capsule collider.
> `G` hotkey toggles fly ↔ walk-physics within the WALK camera mode.
> Default is fly (preserves anchor/scale_demo regression behavior).
> Shipped 2026-05-12 on `main`.

## What shipped

| Task | Component | Commit |
|---|---|---|
| 1 | `extends CharacterBody3D` + CapsuleShape3D collider in `_setup_cameras` | (see git log) |
| 2 | `_walk_input_direction()` helper + `_physics_process` walk-physics + G toggle | (see git log) |
| 3 | 7 .tscn files updated: rig declared `CharacterBody3D` instead of `Node3D` | (see git log) |
| 4 | Anchor + scale_demo regression captures verified (default fly mode = no behavior change) | (verify-only, no commit) |
| 5 | Landing-test capture scene `capture_scale_v2_walk_physics.tscn` | (see git log) |
| 6 | Clipmap A/B re-captures (sanity) | (see git log if changes) |
| 7 | This build-note + STATE refresh | (this commit) |

**Test count:** unchanged. Physics behavior is editor-verified, not unit-tested.

## Architecture

- `AnchorCameraRig` extends `CharacterBody3D` (was `Node3D`).
- One child added in `_setup_cameras`: `PlayerCollision: CollisionShape3D` carrying a `CapsuleShape3D` (height 1.8m, radius 0.4m, centered at y=0.9m so the capsule's bottom sphere sits at the rig's origin).
- New flag: `_fly_enabled: bool = true` (default fly mode).
- `_process` walk-mode block now early-exits when `_fly_enabled` is false; `_physics_process` handles walk-physics (gravity + horizontal motion + `move_and_slide`).
- `G` keypress in `_input` flips `_fly_enabled` and refreshes the HUD label.
- Default `walk_eye_height` bumped from 4.0 → 1.6 (human eye-level).

## Plan deviations

(Fill in any deviations the implementer hit. If the regression captures changed hashes in Task 4, document the cause + decision here. If `_refresh_hud()` extraction was bigger than expected, note it.)

## Lessons + new pitfalls

(Fill in any new PITFALLS classes if the editor verification surfaced an issue.)

## What's still missing

- **Jumping**: not implemented. Easy follow-up (`velocity.y += jump_force` on Space when `is_on_floor()`).
- **Crouching / sliding**: deferred.
- **Mid-air control**: the current `_physics_process` sets `velocity.xz` from input every tick, which means full directional control in the air. That's "fly-game" feel, not "platformer" feel. Tunable later by lerping toward the input vector instead of snapping.
- **Per-tier capsule size**: hardcoded 1.8 × 0.4. Not a tier knob (gameplay, not perf).

## What's next

Player can walk on terrain. Stage 4.2 (biome culler) unblocked: biome-blending art can now be evaluated with realistic walking POV instead of fly-cam.
```

- [ ] **Step 3: Update STATE.md**

Find the "Active work" section. Below the Stage 4.1 entry, add:

```markdown
- ✅ **Player controller (fly + walk-physics)**: complete pending
  editor verification. `AnchorCameraRig` becomes `CharacterBody3D`
  with a 1.8m × 0.4m capsule collider. `G` hotkey toggles fly ↔
  walk-physics within walk camera mode. Default is fly so anchor +
  scale_demo captures are bit-identical to pre-controller state.
  Capsule collides with the Stage 3.5 `HeightMapShape3D` proxies on
  inner clipmap rings. Build-note:
  `build-notes/PLAYER_CONTROLLER_BUILD_NOTES_2026_05_12.md`.
```

- [ ] **Step 4: Commit**

```bash
git -C "D:/assets" add "world 4/docs/build-notes/PLAYER_CONTROLLER_BUILD_NOTES_2026_05_12.md" "world 4/docs/STATE.md"
git -C "D:/assets" commit -m "player-controller: 7. build-note + STATE refresh"
```

---

## Self-review notes

**Spec coverage** (against `superpowers/specs/2026-05-12-player-controller-design.md`):
- ✅ "Convert AnchorCameraRig from Node3D to CharacterBody3D" → Task 1 step 1.
- ✅ "Add a CollisionShape3D child with a CapsuleShape3D (1.8m × 0.4m)" → Task 1 step 4.
- ✅ "Add `_physics_process` doing `move_and_slide()` in walk mode; applies gravity + horizontal motion" → Task 2 step 4.
- ✅ "G hotkey toggles fly/physics" → Task 2 step 5.
- ✅ "Default mode: fly (preserves regression)" → Task 1 step 2.
- ✅ "HUD line update" → Task 2 step 6.
- ✅ "Update each .tscn that uses the rig to declare CharacterBody3D" → Task 3.
- ✅ "Anchor + scale_demo headless re-captures should be bit-identical" → Task 4.
- ✅ "capture_scale_v2_walk_physics.tscn landing test" → Task 5.
- ✅ "Editor verification per workflows/verifying-visual-change.md" → Task 7 step 1.
- ✅ "Build-note + STATE refresh" → Task 7 steps 2-3.

**Placeholder scan:**
- Task 2 step 2's WASD direction calculation has a fallback to "read existing axis math and match its sign convention." That's not a placeholder — it's correct guidance because the existing rig's sign convention may differ from my assumed `-fwd` for W. Reading the existing code is a required step.
- Task 2 step 5's `_refresh_hud()` mention says "if it doesn't exist as a separate function, find the place that builds the HUD label and refactor." That's also guidance — the rig's HUD structure is unknown to me at plan-write time.
- Task 7 step 2's build-note has parenthetical "(Fill in any deviations...)" sections — those are intentional placeholders for the implementer to fill at write time, not unknown unknowns I should resolve here.

**Type consistency:**
- `_fly_enabled: bool` declared in Task 1 step 2, referenced in Task 2 steps 4 + 5, referenced in Task 5 step 2.
- `_walk_input_direction()` declared in Task 2 step 2, called in Task 2 steps 3 + 4.
- `PLAYER_CAPSULE_HEIGHT` / `_RADIUS` constants declared Task 1 step 2, used Task 1 step 4.
- `GRAVITY_M_S2` declared Task 1 step 2, used Task 2 step 4.

**Risks called out:**
- Task 4 regression check may fail (hash differs). Plan provides triage path.
- Task 5 landing capture may show all-gray (collision layer mismatch). Plan flags this as expected outcome to diagnose.
- The existing rig's WASD axis convention may differ from the helper — Task 2 step 2 calls this out and tells implementer to read + match.
- HUD refactor scope creep — Task 2 step 5 gives an out: "if too big, inline the HUD update here."

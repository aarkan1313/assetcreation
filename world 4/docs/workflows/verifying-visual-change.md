# Workflow — verifying a visual change

> Anything that touches rendering — new shader, new mesh, new
> displacement, new biome — needs both **headless capture** (catches
> regressions automatically) and **editor verification** (catches what
> headless can't show). This workflow is the discipline.

## Why both?

Headless captures via `HeadlessCapture.gd` are scriptable and great for
regression checks. But they hide bugs the editor surfaces — see
`PITFALLS.md` #6 (per-tile splat boundary discontinuity), which passed
every headless capture and only appeared in the editor's Vulkan path.
The Axis 6 world-splat pivot exists because of that one bug.

**Rule (from PITFALLS #6b):** headless captures are smoke tests, not
sign-off. Editor verification is mandatory before claiming a visual
change works.

## Step 1: headless capture

Create a capture scene (or reuse one). Example pattern:

```python
"C:/Program Files/Python312/python.exe" -c "
content = '''[gd_scene load_steps=3 format=3]

[ext_resource type=\"PackedScene\" path=\"res://scenes/<your_scene>.tscn\" id=\"scene\"]
[ext_resource type=\"Script\" path=\"res://scripts/HeadlessCapture.gd\" id=\"cap_script\"]

[node name=\"Capture<Name>\" type=\"Node\"]

[node name=\"Inner\" parent=\".\" instance=ExtResource(\"scene\")]

[node name=\"Capture\" type=\"Node\" parent=\".\"]
script = ExtResource(\"cap_script\")
output_path = \"res://captures/<topic>_<YYYY_MM_DD>.png\"
warmup_frames = 60
viewport_size = Vector2i(1280, 800)
force_camera_mode = \"walk\"
'''
open(r'D:/assets/world 4/the world 4/scenes/capture_<your_scene>.tscn', 'w', encoding='utf-8', newline='\n').write(content)
print('wrote')
"
```

Use the Python helper because the Write tool produces UTF-16 on Windows. (See memory `write_tool_utf16_on_windows.md`.)

Then reimport + run:

```bash
"C:/Godot/Godot_v4.5-stable_win64.exe" --headless --path "D:/assets/world 4/the world 4" --import 2>&1 | tail -3
"C:/Godot/Godot_v4.5-stable_win64.exe" --rendering-driver opengl3 --path "D:/assets/world 4/the world 4" --single-window --disable-crash-handler "res://scenes/capture_<your_scene>.tscn" 2>&1 | tail -10
```

Required flags: `--rendering-driver opengl3` (memory `godot_headless_null_viewport.md`), `--single-window --disable-crash-handler` (memory `godot_binary_and_capture_invocation.md`).

Output: PNG written to `the world 4/captures/<topic>_<YYYY_MM_DD>.png`. View it with the `Read` tool (it renders inline).

## Step 2: walk + topdown captures

For any spatial change (new geometry, new shader, new biome layout),
capture **both** walk and topdown views. Walk shows what the player
sees; topdown shows the spatial layout. Boundary bugs typically only
show in one.

Pattern: duplicate the capture scene, change `force_camera_mode` to
`"topdown"`, and re-run.

## Step 3: editor verification (mandatory)

**Do NOT background-launch the editor from the harness.** See memory
`editor_launch_workflow.md` — background launches fire "completed"
notifications immediately and break the verify-then-iterate loop.

Instead, **print the launch command for the user**:

> "Run this in a terminal and walk around for 30 seconds to verify
> the change:
>
> `"C:/Godot/Godot_v4.5-stable_win64.exe" --path "D:/assets/world 4/the world 4"`
>
> Open `scenes/<your_scene>.tscn`, F6 to play, WASD around. Watch for:
> [list 2-3 specific things — e.g. 'gaps between rings', 'z-fight at
> biome boundaries', 'terrain visibly regenerating as you walk'].
> Tell me what you see."

Wait for the user's verdict. **Do not claim the change is shipped until
they confirm.**

## Step 4: one change at a time

When debugging a visual artifact, change exactly one thing per
iteration. Re-capture (headless + editor). The reason: if the artifact
disappears, you know which change fixed it; if it doesn't, you know it
wasn't that.

This is slow but it's the only debugging discipline that scales. See
`PITFALLS.md` for examples where this discipline (or its absence)
mattered.

## Step 5: regression captures on close

When the feature ships, capture the canonical "shipped" view (walk +
topdown) and check it into `captures/` alongside the build-note. Future
sessions compare against these to detect regressions.

## Checklist

- [ ] Headless capture exists and was rerun after every code change
- [ ] Walk + topdown both captured (for spatial changes)
- [ ] Editor launch command printed to user
- [ ] User verdict received before claiming "shipped"
- [ ] If a bug appeared: changed one thing at a time, re-captured
- [ ] If shipped: regression captures saved to `captures/`
- [ ] Build-note links to the regression captures

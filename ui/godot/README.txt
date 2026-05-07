# UI drop-in for Godot 4.5
Copy this folder to res://ui/. Apply theme.tres to a Control's
'theme' property (or set as the default theme in Project Settings).

Icons are AtlasTexture references into atlas.png. Load any one with:
    var t: Texture2D = load('res://ui/ico_sword_atlas.tres')

9-slice elements (panel/button/frame/healthbar) are StyleBoxTexture
resources auto-wired into Button.styles and Panel.styles by theme.tres.

# Biome ambience drop-in for Godot 4.5
Copy this folder to res://audio/ambience/. Then in your scene:

    var c := preload('res://audio/ambience/BiomeAmbienceController.tscn').instantiate()
    add_child(c)
    c.set_biome('ice_cavern')

The controller cross-fades beds, fires Poisson sweeteners, and
tunes the AmbienceReverb bus per biome preset.

Optional: import bus_layout_ambience_overlay.tres via
Project > Project Settings > Audio > Buses > Load to add the
Ambience + AmbienceReverb buses (idempotent: same Master/SFX/UI/
Voice/Music order as the SFX exporter, plus 2 ambience buses).

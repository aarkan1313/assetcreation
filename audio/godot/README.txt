# audio drop-in for Godot 4.5
Copy this folder to res://audio/. Each sound has a randomizer.tres
that picks one of N WAV variants per .play().

    var s := load('res://audio/sfx/ui_click/randomizer.tres')
    $AudioStreamPlayer.stream = s
    $AudioStreamPlayer.play()

Optional: import bus_layout.tres via Project > Project Settings >
Audio > Buses > Load to apply the recommended bus structure
(Master / SFX / UI / Voice / Ambience / Music).

# game_data drop-in for Godot 4.5
Copy this folder to res://game_data/. The scripts/ subfolder contains
auto-generated Resource classes; resources/<type>s/*.tres are the data
records. Reference any record from GDScript:

    var rec: ItemRecord = load("res://game_data/resources/items/iron_sword_0.tres")
    print(rec.display_name, rec.stats)

All fields use @export so they show in the Inspector.
Regenerate from D:/assets/ with:
    python pipelines/game_data/export_godot.py

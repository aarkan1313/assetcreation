# props drop-in for Godot 4.5 (v2 HLOD)
Copy this folder to res://props/. Each prop is a packed .tscn that
instances its model_lodN.glb chain with explicit VisibilityRange (HLOD).
Auto-LOD is DISABLED per .glb.import — the chain is the chain.

    var s := preload('res://props/barrel_a01/barrel_a01.tscn')
    add_child(s.instantiate())

Scatter (MultiMesh) templates: <id>_multimesh.tscn for scatter_multimesh
props. Each template has one MultiMeshInstance3D per LOD with its own
VisibilityRange; the placement compiler fills the transform array.

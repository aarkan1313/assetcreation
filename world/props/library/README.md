# Prop Library

Generated prop variants live here.

Each prop gets a folder:

```text
world/props/library/<prop_id>/
  prop.json
  qa.json
  model_lod0.glb
  thumbnail.png
```

The CPU-only planning tools can run before these folders exist. Missing folders
are reported as pending generation, not as errors unless `--strict-assets` is
used.


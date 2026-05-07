# Shader Reference Sets

Put curated reference PNG/JPG/WebP images here when you want candidates scored
against a target style.

Example:

```text
art_lab/shaders/reference_sets/
  storm_projectile/
    ref_001.png
    ref_002.png
  occult_portal/
    ref_001.jpg
```

Then run:

```powershell
python "D:\assets\art_lab\tools\shader_reference_score.py" `
  --batch-dir "D:\assets\art_lab\shaders\batches\shader_review_next_001" `
  --reference-set storm_projectile `
  --update-summary
```

Use reference scoring as a second gate after the normal batch review. The normal
score catches broken outputs. The reference score asks whether a surviving
candidate is visually near the target style.

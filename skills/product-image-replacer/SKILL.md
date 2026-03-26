---
name: product-image-replacer
description: Replace the product area inside poster mockups, wireframes, or product prototype images with new product photos and export regenerated images in batch. Use when Codex needs to swap a single main product in existing marketing artwork, especially when the source template lives in a wireframe or mockup folder and replacement images come from a separate input folder.
---

# Product Image Replacer

Use this skill to batch-generate new product posters by reusing an existing template image and swapping only the main product visual.

The default folder convention for this project is:

- `wireframes/`: source mockups or prototype images
- `input_product/`: replacement product images
- `output_product/`: generated images
- `result_product/`: legacy fallback output folder seen in some projects; write there only if the user explicitly asks or the project already depends on it

## Workflow

1. Inspect the template image and confirm it is a "single hero product" layout.
2. Run `scripts/replace_product.py` with the wireframe folder, product folder, and output folder.
3. Let the script auto-detect the replacement region first.
4. If auto-detection is not stable, rerun with `--region x1,y1,x2,y2`.
5. Review at least one generated image before batch delivery.

## Run The Script

Auto-detect the main product area and generate outputs:

```powershell
python scripts/replace_product.py ^
  --wireframes-dir wireframes ^
  --input-dir input_product ^
  --output-dir output_product
```

Force a fixed replacement box when the heuristic misses:

```powershell
python scripts/replace_product.py ^
  --wireframes-dir wireframes ^
  --input-dir input_product ^
  --output-dir output_product ^
  --region 470,250,980,860
```

## Defaults And Assumptions

- Assume the template has one primary product on the right or center-right side.
- Assume the template background is relatively clean, so a white or near-white product background can be removed heuristically.
- Generate one output per `(wireframe, product)` pair.
- Name outputs as `<wireframe-stem>__<product-stem>.png`.
- Prefer PNG output to preserve soft edges.

## Validation Rules

- Confirm `output_product/` exists or let the script create it.
- Confirm every replacement image is visually centered and not cropped.
- If the product sits too high or too low, adjust with `--bottom-padding` and rerun.
- If auto-detection grabs text or decorations, switch to `--region`.

## Resources

- `scripts/replace_product.py`: batch replace the detected product area with new product images
- `references/layout-notes.md`: folder convention, parameter notes, and fallback guidance

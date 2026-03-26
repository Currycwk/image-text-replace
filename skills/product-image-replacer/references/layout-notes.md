# Layout Notes

## Folder Contract

- Read wireframes from `wireframes/`.
- Read source products from `input_product/`.
- Write generated files to `output_product/`.
- Treat `result_product/` as a legacy folder name if the workspace already uses it.

## Heuristic Behavior

- Auto-detect the replacement area from the right side of the template.
- Remove the new product background by comparing image corners against the dominant background color.
- Resize the new product proportionally and align it to the detected region bottom.

## Fallback

Use `--region x1,y1,x2,y2` when:

- the template contains extra decorations on the right side
- the product is centered rather than right-aligned
- the background is not light enough for the heuristic

Use `--bottom-padding` when the new product should sit lower on a shelf or pedestal.

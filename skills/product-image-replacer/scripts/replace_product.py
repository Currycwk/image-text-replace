from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter


SUPPORTED_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


@dataclass
class Box:
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Replace the main product area inside wireframe poster images."
    )
    parser.add_argument("--wireframes-dir", type=Path, default=Path("wireframes"))
    parser.add_argument("--input-dir", type=Path, default=Path("input_product"))
    parser.add_argument("--output-dir", type=Path, default=Path("output_product"))
    parser.add_argument(
        "--region",
        type=str,
        default=None,
        help="Optional override box as x1,y1,x2,y2 in wireframe pixel coordinates.",
    )
    parser.add_argument(
        "--bottom-padding",
        type=float,
        default=0.06,
        help="Extra vertical room below the detected box for products that need to sit lower.",
    )
    parser.add_argument(
        "--white-threshold",
        type=int,
        default=242,
        help="Threshold used for product-region detection in the template.",
    )
    return parser.parse_args()


def list_images(folder: Path) -> list[Path]:
    return sorted(path for path in folder.iterdir() if path.suffix.lower() in SUPPORTED_EXTS)


def parse_region(raw: str) -> Box:
    parts = [int(part.strip()) for part in raw.split(",")]
    if len(parts) != 4:
        raise ValueError("region must be x1,y1,x2,y2")
    left, top, right, bottom = parts
    if left >= right or top >= bottom:
        raise ValueError("region coordinates must define a positive box")
    return Box(left, top, right, bottom)


def find_components(mask: np.ndarray) -> list[tuple[int, int, int, int, int, float]]:
    height, width = mask.shape
    visited = np.zeros_like(mask, dtype=bool)
    components: list[tuple[int, int, int, int, int, float]] = []

    for start_y, start_x in np.argwhere(mask):
        if visited[start_y, start_x]:
            continue

        stack = [(int(start_y), int(start_x))]
        visited[start_y, start_x] = True
        area = 0
        min_x = max_x = int(start_x)
        min_y = max_y = int(start_y)
        sum_x = 0

        while stack:
            y, x = stack.pop()
            area += 1
            sum_x += x
            min_x = min(min_x, x)
            max_x = max(max_x, x)
            min_y = min(min_y, y)
            max_y = max(max_y, y)

            for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                if 0 <= ny < height and 0 <= nx < width and mask[ny, nx] and not visited[ny, nx]:
                    visited[ny, nx] = True
                    stack.append((ny, nx))

        center_x = sum_x / area
        components.append((area, min_x, min_y, max_x, max_y, center_x))

    return components


def detect_product_box(image: Image.Image, white_threshold: int, bottom_padding: float) -> Box:
    rgb = np.asarray(image.convert("RGB"))
    height, width, _ = rgb.shape

    x0 = int(width * 0.5)
    x1 = width
    y0 = int(height * 0.18)
    y1 = int(height * 0.74)

    roi = rgb[y0:y1, x0:x1]
    candidate = np.any(roi < white_threshold, axis=2)
    components = [
        component
        for component in find_components(candidate)
        if component[0] >= 1200
    ]
    if not components:
        raise RuntimeError("auto-detection failed; rerun with --region")

    best = max(components, key=lambda item: item[0] * (1 + item[5] / roi.shape[1]))
    _, left, top, right, bottom, _ = best
    top += y0
    bottom += y0
    left += x0
    right += x0

    pad_x = int((right - left) * 0.08)
    pad_top = int((bottom - top) * 0.06)
    pad_bottom = int((bottom - top) * bottom_padding)

    return Box(
        max(0, left - pad_x),
        max(0, top - pad_top),
        min(width, right + pad_x),
        min(height, bottom + pad_bottom),
    )


def extract_subject(product: Image.Image) -> Image.Image:
    rgba = product.convert("RGBA")
    arr = np.asarray(rgba).astype(np.int16)

    corners = np.vstack(
        [
            arr[0, 0, :3],
            arr[0, -1, :3],
            arr[-1, 0, :3],
            arr[-1, -1, :3],
        ]
    )
    bg = np.median(corners, axis=0)
    diff = np.sqrt(np.sum((arr[:, :, :3] - bg) ** 2, axis=2))

    mask = diff > 22
    alpha = np.where(mask, 255, 0).astype(np.uint8)

    alpha_img = Image.fromarray(alpha, mode="L").filter(ImageFilter.GaussianBlur(radius=1.2))
    rgba.putalpha(alpha_img)

    bbox = rgba.getbbox()
    if not bbox:
        raise RuntimeError("product background removal failed")
    return rgba.crop(bbox)


def paste_product(
    wireframe: Image.Image,
    subject: Image.Image,
    box: Box,
    use_box_clear: bool,
) -> Image.Image:
    canvas = wireframe.convert("RGBA")
    subject = subject.convert("RGBA")

    scale = min(box.width / subject.width, box.height / subject.height)
    new_size = (
        max(1, int(subject.width * scale)),
        max(1, int(subject.height * scale)),
    )
    subject = subject.resize(new_size, Image.Resampling.LANCZOS)

    x = box.left + (box.width - subject.width) // 2
    y = box.bottom - subject.height

    clear_overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    if use_box_clear:
        clear_patch = Image.new("RGBA", (box.width, box.height), (255, 255, 255, 248))
        clear_patch = clear_patch.filter(ImageFilter.GaussianBlur(radius=10))
        clear_overlay.paste(clear_patch, (box.left, box.top), clear_patch)
    else:
        # Fade the original product behind the new subject without leaving a hard rectangle.
        clear_scale = 1.12
        clear_size = (
            max(1, int(subject.width * clear_scale)),
            max(1, int(subject.height * clear_scale)),
        )
        clear_alpha = subject.getchannel("A").resize(clear_size, Image.Resampling.LANCZOS)
        clear_alpha = clear_alpha.filter(ImageFilter.GaussianBlur(radius=14))
        clear_layer = Image.new("RGBA", clear_size, (255, 255, 255, 235))
        clear_layer.putalpha(clear_alpha)
        clear_x = x - (clear_size[0] - subject.width) // 2
        clear_y = y - (clear_size[1] - subject.height) // 2
        clear_overlay.paste(clear_layer, (clear_x, clear_y), clear_layer)
    canvas.alpha_composite(clear_overlay)

    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    shadow_alpha = subject.getchannel("A").filter(ImageFilter.GaussianBlur(radius=10))
    shadow_layer = Image.new("RGBA", subject.size, (0, 0, 0, 65))
    shadow_layer.putalpha(shadow_alpha)
    shadow.paste(shadow_layer, (x + 12, y + 18), shadow_layer)
    canvas.alpha_composite(shadow)
    canvas.paste(subject, (x, y), subject)
    return canvas


def replace_one(wireframe_path: Path, product_path: Path, output_path: Path, args: argparse.Namespace) -> None:
    wireframe = Image.open(wireframe_path)
    product = Image.open(product_path)

    manual_region = args.region is not None
    box = parse_region(args.region) if manual_region else detect_product_box(
        wireframe, args.white_threshold, args.bottom_padding
    )
    subject = extract_subject(product)
    result = paste_product(wireframe, subject, box, use_box_clear=manual_region)
    result.save(output_path)


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    wireframes = list_images(args.wireframes_dir)
    products = list_images(args.input_dir)

    if not wireframes:
        raise SystemExit(f"no wireframe images found in {args.wireframes_dir}")
    if not products:
        raise SystemExit(f"no product images found in {args.input_dir}")

    for wireframe_path in wireframes:
        for product_path in products:
            output_name = f"{wireframe_path.stem}__{product_path.stem}.png"
            output_path = args.output_dir / output_name
            replace_one(wireframe_path, product_path, output_path, args)
            print(f"generated {output_path}")


if __name__ == "__main__":
    main()

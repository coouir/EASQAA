"""`image_stats`: mean brightness and background noise of a region, from the pixels (SPEC §5.2).

Both values are computed on the 8-bit grayscale image. `background_noise` is the standard
deviation of the pixels not covered by a **label** box, whatever box source the run uses
(SPEC §5.3), so the gold answer does not change with the input condition.
`mean_brightness` uses all pixels of the region.
Pixel regions are rectangles: quadrants split at the image half, `[x1, y1, x2, y2]` is
`x1 <= x < x2`, `y1 <= y < y2` after rounding and clipping to the image.
"""

import math

import numpy as np

from sarqa.config import load_config
from sarqa.tools.base import ToolContext, ToolError, tool
from sarqa.tools.geometry import parse_region

DECIMALS = 2


def _rect(reg, size: int) -> tuple[int, int, int, int]:
    half = size // 2
    if reg.kind == "custom":
        x1, y1, x2, y2 = (min(max(math.floor(v + 0.5), 0), size) for v in reg.rect)
        return x1, y1, x2, y2
    return {"full": (0, 0, size, size),
            "top_left": (0, 0, half, half), "top_right": (half, 0, size, half),
            "bottom_left": (0, half, half, size), "bottom_right": (half, half, size, size),
            }[reg.kind]


@tool
def image_stats(ctx: ToolContext, image_id: str, region="full") -> dict:
    if not isinstance(image_id, str):
        raise ToolError("image_id must be a string")
    if image_id not in ctx.label_boxes:
        raise ToolError(f"unknown image_id: {image_id}")
    reg = parse_region(region)
    size = load_config()["tools"]["image_size"]
    x1, y1, x2, y2 = _rect(reg, size)
    if x1 >= x2 or y1 >= y2:
        raise ToolError("region has no pixels inside the image")
    img = ctx.load_image(image_id)
    masked = np.zeros(img.shape, dtype=bool)
    for b in ctx.label_boxes.boxes(image_id):
        masked[b.y1:b.y2, b.x1:b.x2] = True
    patch = img[y1:y2, x1:x2].astype(np.float64)
    background = patch[~masked[y1:y2, x1:x2]]
    noise = round(float(background.std()), DECIMALS) if background.size else None
    return {"region": reg.label, "mean_brightness": round(float(patch.mean()), DECIMALS),
            "background_noise": noise}

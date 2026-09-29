"""Hand-made mini images and contexts shared by the tool and program tests."""

import numpy as np

from sarqa.boxes import BoxProvider
from sarqa.tools.base import ToolContext

# Five 800x800 mini images. Boxes are (x1, y1, x2, y2).
MINI_BOXES = {
    "m1.jpg": [],                                                        # empty sea
    "m2.jpg": [(100, 100, 130, 120)],                                    # one ship, top-left
    "m3.jpg": [(500, 100, 540, 130), (100, 500, 120, 560), (600, 600, 640, 620)],
    "m4.jpg": [(0, 0, 10, 10), (390, 390, 410, 410), (790, 790, 800, 800),
               (200, 600, 260, 640)],
    "m5.jpg": [(10 + 50 * i, 300, 30 + 50 * i, 320) for i in range(15)],  # 15 ships in a row
}
MINI_SCENES = {"m1.jpg": "offshore", "m2.jpg": "offshore", "m3.jpg": "inshore",
               "m4.jpg": "inshore", "m5.jpg": "offshore"}


def mini_image(name: str) -> np.ndarray:
    """Grey 50 everywhere; the pixels inside label boxes are 200."""
    img = np.full((800, 800), 50, dtype=np.uint8)
    for x1, y1, x2, y2 in MINI_BOXES[name]:
        img[y1:y2, x1:x2] = 200
    return img


def mini_context(source: str = "label", table=None) -> ToolContext:
    labels = BoxProvider("label", MINI_BOXES)
    boxes = labels if table is None else BoxProvider(source, table)
    return ToolContext(boxes=boxes, label_boxes=labels, scenes=MINI_SCENES, load_image=mini_image)

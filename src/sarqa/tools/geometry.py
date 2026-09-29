"""Geometry rules of SPEC §5.1. These are the only place the rules live; tests pin them.

- a box belongs to a region by its **centre**; overlap is never used
- quadrant borders: centre x < 400 is left, x >= 400 right; y < 400 top, y >= 400 bottom
- custom region [x1, y1, x2, y2]: x1 <= cx < x2 and y1 <= cy < y2
- near the edge: a box side is within `edge_margin_px` of the image border
- distance: Euclidean distance between box centres, rounded to `distance_decimals`
- length: the box's longer side in px
"""

import math
from dataclasses import dataclass

from sarqa.boxes import Box
from sarqa.config import load_config
from sarqa.tools.base import ToolError

QUADRANTS = ("top_left", "top_right", "bottom_left", "bottom_right")
REGION_NAMES = ("full", *QUADRANTS)


@dataclass(frozen=True)
class Region:
    label: str | list  # as echoed back to the agent: a name or the [x1, y1, x2, y2] list
    kind: str          # "full" | quadrant name | "custom"
    rect: tuple | None = None

    def contains(self, cx: float, cy: float, size: int) -> bool:
        half = size / 2
        if self.kind == "full":
            return True
        if self.kind == "custom":
            x1, y1, x2, y2 = self.rect
            return x1 <= cx < x2 and y1 <= cy < y2
        left, top = cx < half, cy < half
        return (self.kind == "top_left" and left and top) \
            or (self.kind == "top_right" and not left and top) \
            or (self.kind == "bottom_left" and left and not top) \
            or (self.kind == "bottom_right" and not left and not top)


def parse_region(region) -> Region:
    if isinstance(region, str):
        if region not in REGION_NAMES:
            raise ToolError(f"unknown region {region!r}; use one of {list(REGION_NAMES)} "
                            "or [x1, y1, x2, y2]")
        return Region(region, region)
    if isinstance(region, (list, tuple)) and len(region) == 4 \
            and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in region):
        x1, y1, x2, y2 = region
        if not (x1 < x2 and y1 < y2):
            raise ToolError("region [x1, y1, x2, y2] needs x1 < x2 and y1 < y2")
        return Region(list(region), "custom", (x1, y1, x2, y2))
    raise ToolError("region must be a name or a list of four numbers [x1, y1, x2, y2]")


def in_region(box: Box, region: Region) -> bool:
    return region.contains(box.cx, box.cy, load_config()["tools"]["image_size"])


def near_edge(box: Box) -> bool:
    t = load_config()["tools"]
    m, size = t["edge_margin_px"], t["image_size"]
    return box.x1 <= m or box.y1 <= m or size - box.x2 <= m or size - box.y2 <= m


def dist2(a: Box, b: Box) -> float:
    """Squared centre distance. Exact (centres are multiples of 0.5), so ties compare exactly."""
    return (a.cx - b.cx) ** 2 + (a.cy - b.cy) ** 2


def distance_px(a: Box, b: Box) -> float:
    return round(math.sqrt(dist2(a, b)), load_config()["tools"]["distance_decimals"])

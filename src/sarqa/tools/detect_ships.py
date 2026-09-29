"""`detect_ships`: ship boxes of one image, optionally restricted to a region (SPEC §5.2).

No confidence is returned (SPEC §5.3): labels, injected and corrected boxes have none, so showing
scores only for detector boxes would reveal the input source and let the agent filter false
positives by score.
"""

from sarqa.tools.base import ToolContext, tool
from sarqa.tools.geometry import in_region, parse_region


@tool
def detect_ships(ctx: ToolContext, image_id: str, region="full") -> dict:
    boxes = ctx.ship_boxes(image_id)
    reg = parse_region(region)
    ships = [b.as_dict() for b in boxes if in_region(b, reg)]
    return {"region": reg.label, "count": len(ships), "ships": ships}

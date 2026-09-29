"""`spatial_query`: counts, sizes, distances and edge checks from the current box source.

The agent never passes boxes; they come from `ctx.boxes` (SPEC §5.2). Ship ids are those of the
whole image (`s1`, `s2`, ... in (y1, x1) order), whatever the region, so ids stay comparable across
calls. Counts take one region per call (the loop structure of L3 questions).
"""

from sarqa.boxes import Box
from sarqa.config import load_config
from sarqa.tools.base import ToolContext, ToolError, tool
from sarqa.tools.geometry import dist2, distance_px, in_region, near_edge, parse_region

# query -> arguments it accepts besides image_id and query
QUERY_ARGS = {
    "count": {"region"},
    "sizes": {"region"},
    "distance": {"ship_a", "ship_b"},
    "nearest_pair": {"region"},
    "nearest_to": {"ship_a"},
    "edge": {"region", "ship_a"},
}


def _find(boxes: list[Box], ship_id) -> Box:
    for b in boxes:
        if b.id == ship_id:
            return b
    raise ToolError(f"unknown ship id: {ship_id!r}")


def _need(name: str, value):
    if value is None:
        raise ToolError(f"missing required argument {name!r}")
    return value


def _closest(pool: list[Box], pairs) -> tuple[Box, Box]:
    """Closest pair by exact squared distance; ties go to the earlier (a, b) in id order."""
    return min(pairs, key=lambda p: (dist2(p[0], p[1]), pool.index(p[0]), pool.index(p[1])))


@tool
def spatial_query(ctx: ToolContext, image_id: str, query: str, region="full",
                  ship_a: str | None = None, ship_b: str | None = None) -> dict:
    if query not in QUERY_ARGS:
        raise ToolError(f"unknown query {query!r}; use one of {sorted(QUERY_ARGS)}")
    given = {"region": None if region == "full" else region, "ship_a": ship_a, "ship_b": ship_b}
    extra = sorted(k for k, v in given.items() if v is not None and k not in QUERY_ARGS[query])
    if extra:
        raise ToolError(f"query {query!r} does not take {extra}")
    boxes = ctx.ship_boxes(image_id)
    reg = parse_region(region)
    inside = [b for b in boxes if in_region(b, reg)]

    if query == "count":
        return {"query": query, "region": reg.label, "count": len(inside),
                "ship_ids": [b.id for b in inside]}
    if query == "sizes":
        return {"query": query, "region": reg.label, "count": len(inside),
                "ships": [{"id": b.id, "long_side_px": b.long_side} for b in inside],
                "long_side_px": [b.long_side for b in inside]}
    if query == "distance":
        a, b = _find(boxes, _need("ship_a", ship_a)), _find(boxes, _need("ship_b", ship_b))
        return {"query": query, "ship_a": a.id, "ship_b": b.id, "distance_px": distance_px(a, b)}
    if query == "nearest_pair":
        if len(inside) < 2:
            raise ToolError(f"nearest_pair needs at least 2 ships in the region (found {len(inside)})")
        pairs = [(inside[i], inside[j]) for i in range(len(inside)) for j in range(i + 1, len(inside))]
        a, b = _closest(inside, pairs)
        return {"query": query, "region": reg.label, "ship_a": a.id, "ship_b": b.id,
                "distance_px": distance_px(a, b)}
    if query == "nearest_to":
        a = _find(boxes, _need("ship_a", ship_a))
        others = [b for b in boxes if b is not a]
        if not others:
            raise ToolError("nearest_to needs at least 2 ships in the image")
        b = min(others, key=lambda o: (dist2(a, o), boxes.index(o)))
        return {"query": query, "ship_a": a.id, "ship_b": b.id, "distance_px": distance_px(a, b)}
    # query == "edge"
    margin = load_config()["tools"]["edge_margin_px"]
    if ship_a is not None:
        if given["region"] is not None:
            raise ToolError("query 'edge' takes either ship_a or region, not both")
        a = _find(boxes, ship_a)
        return {"query": query, "margin_px": margin, "ship_a": a.id, "near_edge": near_edge(a)}
    near = [b for b in inside if near_edge(b)]
    return {"query": query, "region": reg.label, "margin_px": margin, "count": len(near),
            "ship_ids": [b.id for b in near]}

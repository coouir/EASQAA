"""`get_metadata`: inshore / offshore tag of an image (SPEC §5.2).

HRSID has no per-image resolution (m/px) or sensor field (docs/data_notes.md §6, user decision
§16-1), so the fallback is fixed: the output carries `scene` only, and distance and length
questions are in px. The tag comes from the HRSID inshore/offshore files, never from the boxes,
so it does not change with the box source.
"""

from sarqa.tools.base import ToolContext, ToolError, tool


@tool
def get_metadata(ctx: ToolContext, image_id: str) -> dict:
    if not isinstance(image_id, str):
        raise ToolError("image_id must be a string")
    if image_id not in ctx.scenes:
        raise ToolError(f"unknown image_id: {image_id}")
    return {"scene": ctx.scenes[image_id]}

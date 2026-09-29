"""`get_metadata`: inshore / offshore tag and pixel size of an image (SPEC §5.2).

HRSID has no per-image resolution (m/px) or sensor field (docs/data_notes.md §6, user decision
§16-1), so neither is returned and distance and length questions are in px. The output carries
`scene` and the image's actual `width` and `height` in px (read from the image, not from the
config; this is a size, not a resolution). The tag comes from the HRSID inshore/offshore files,
never from the boxes, so nothing here changes with the box source.
"""

from sarqa.tools.base import ToolContext, ToolError, tool


@tool
def get_metadata(ctx: ToolContext, image_id: str) -> dict:
    if not isinstance(image_id, str):
        raise ToolError("image_id must be a string")
    if image_id not in ctx.scenes:
        raise ToolError(f"unknown image_id: {image_id}")
    height, width = ctx.load_image(image_id).shape[:2]
    return {"scene": ctx.scenes[image_id], "width": int(width), "height": int(height)}

import pytest

from sarqa.boxes import BoxProvider
from sarqa.tools import call_tool
from tools_fixtures import MINI_SCENES, mini_context


def test_scene_and_image_size_but_no_resolution_or_sensor():
    ctx = mini_context()
    assert call_tool(ctx, "get_metadata", {"image_id": "m3.jpg"}) == {
        "scene": "inshore", "width": 800, "height": 800}
    assert call_tool(ctx, "get_metadata", {"image_id": "m1.jpg"}) == {
        "scene": "offshore", "width": 800, "height": 800}


def test_size_is_read_from_the_image_not_the_config():
    import numpy as np

    ctx = mini_context()
    wide = ctx.__class__(ctx.boxes, ctx.label_boxes, ctx.scenes,
                         lambda name: np.zeros((600, 900), dtype=np.uint8))
    assert call_tool(wide, "get_metadata", {"image_id": "m1.jpg"}) == {
        "scene": "offshore", "width": 900, "height": 600}


def test_output_does_not_depend_on_the_box_source():
    ctx = mini_context()
    other = ctx.with_boxes(BoxProvider("injected", {"m3.jpg": []}))
    assert call_tool(other, "get_metadata", {"image_id": "m3.jpg"}) == {
        "scene": "inshore", "width": 800, "height": 800}
    assert call_tool(other, "get_metadata", {"image_id": "m4.jpg"}) == {
        "scene": MINI_SCENES["m4.jpg"], "width": 800, "height": 800}


def test_errors():
    ctx = mini_context()
    assert "unknown image_id" in call_tool(ctx, "get_metadata", {"image_id": "zz.jpg"})["error"]
    assert "must be a string" in call_tool(ctx, "get_metadata", {"image_id": 3})["error"]
    # asking for a resolution is not possible: there is no such argument
    assert "unexpected argument" in call_tool(
        ctx, "get_metadata", {"image_id": "m1.jpg", "field": "resolution"})["error"]


@pytest.mark.data
def test_real_tags_cover_every_image_and_match_hrsid_counts():
    from sarqa.tools import default_context

    ctx = default_context()
    tags = [call_tool(ctx, "get_metadata", {"image_id": n})["scene"] for n in ctx.boxes.image_ids()]
    assert len(tags) == 5604 and tags.count("inshore") == 1031 and tags.count("offshore") == 4573
    sizes = {(m["width"], m["height"]) for m in (
        call_tool(ctx, "get_metadata", {"image_id": n}) for n in ctx.boxes.image_ids()[:200])}
    assert sizes == {(800, 800)}

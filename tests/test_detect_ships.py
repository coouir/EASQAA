import json

from sarqa.boxes import BoxProvider, file_provider
from sarqa.tools import call_tool, render
from tools_fixtures import MINI_BOXES, mini_context

CTX = mini_context()


def d(image, **kw):
    return call_tool(CTX, "detect_ships", {"image_id": image, **kw})


def test_full_image_lists_boxes_with_ids_in_order():
    assert d("m3.jpg") == {"region": "full", "count": 3, "ships": [
        {"id": "s1", "x1": 500, "y1": 100, "x2": 540, "y2": 130},
        {"id": "s2", "x1": 100, "y1": 500, "x2": 120, "y2": 560},
        {"id": "s3", "x1": 600, "y1": 600, "x2": 640, "y2": 620}]}


def test_region_keeps_image_wide_ids():
    out = d("m3.jpg", region="bottom_right")
    assert out["count"] == 1 and out["ships"][0]["id"] == "s3"
    assert d("m3.jpg", region=[0, 400, 400, 800])["ships"][0]["id"] == "s2"


def test_empty_and_fifteen():
    assert d("m1.jpg") == {"region": "full", "count": 0, "ships": []}
    assert d("m5.jpg")["count"] == 15


def test_no_confidence_field_whatever_the_source():
    scored = {"m2.jpg": [(100, 100, 130, 120, 0.99)]}
    out = call_tool(mini_context("detected", scored), "detect_ships", {"image_id": "m2.jpg"})
    assert set(out["ships"][0]) == {"id", "x1", "y1", "x2", "y2"}


def test_output_text_is_identical_across_the_four_sources(tmp_path):
    raw = {"m3.jpg": MINI_BOXES["m3.jpg"]}
    path = tmp_path / "b.json"
    path.write_text(json.dumps(raw))
    scored = {"m3.jpg": [b + (0.97,) for b in raw["m3.jpg"]]}
    providers = [BoxProvider("label", raw), BoxProvider("detected", scored),
                 file_provider("injected", path), file_provider("corrected", path)]
    texts = {render(call_tool(CTX.with_boxes(p), "detect_ships", {"image_id": "m3.jpg"}))
             for p in providers}
    assert len(texts) == 1


def test_errors():
    assert "unknown image_id" in d("zz.jpg")["error"]
    assert "unknown region" in d("m3.jpg", region="edge")["error"]
    assert "missing required" in call_tool(CTX, "detect_ships", {})["error"]

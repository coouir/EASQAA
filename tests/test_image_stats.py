import numpy as np
import pytest

from sarqa.boxes import BoxProvider
from sarqa.tools import call_tool
from sarqa.tools.base import ToolContext
from tools_fixtures import MINI_BOXES, MINI_SCENES, mini_context

CTX = mini_context()


def stats(image, ctx=CTX, **kw):
    return call_tool(ctx, "image_stats", {"image_id": image, **kw})


def test_mean_brightness_by_hand():
    # m2: background 50, one 30x20 ship at 200 -> 50 + 150 * 600 / 640000 = 50.140625
    assert stats("m2.jpg")["mean_brightness"] == 50.14
    assert stats("m1.jpg") == {"region": "full", "mean_brightness": 50.0, "background_noise": 0.0}
    # bottom_left quadrant of m2 has no ship
    assert stats("m2.jpg", region="bottom_left")["mean_brightness"] == 50.0
    # top_left is 400x400 = 160000 px, ship 600 px: 50 + 150 * 600 / 160000 = 50.5625
    assert stats("m2.jpg", region="top_left")["mean_brightness"] == 50.56


def test_custom_region_is_pixel_rectangle():
    out = stats("m2.jpg", region=[100, 100, 130, 120])  # exactly the ship
    assert out["mean_brightness"] == 200.0 and out["background_noise"] is None  # all masked
    assert stats("m2.jpg", region=[100, 100, 101, 101])["mean_brightness"] == 200.0
    assert stats("m1.jpg", region=[-50, -50, 10, 10])["region"] == [-50, -50, 10, 10]  # echoed as given


def test_noise_is_std_of_unmasked_pixels_only():
    checker = np.indices((800, 800)).sum(axis=0) % 2  # 0/1 checkerboard
    img = np.where(checker == 0, 40, 60).astype(np.uint8)  # std 10 everywhere
    for x1, y1, x2, y2 in MINI_BOXES["m2.jpg"]:
        img[y1:y2, x1:x2] = 255
    ctx = ToolContext(boxes=CTX.boxes, label_boxes=CTX.label_boxes, scenes=MINI_SCENES,
                      load_image=lambda name: img)
    assert stats("m2.jpg", ctx)["background_noise"] == 10.0
    assert stats("m2.jpg", ctx, region="top_left")["background_noise"] == 10.0


@pytest.mark.parametrize("source", ["detected", "injected", "corrected"])
def test_independent_of_the_box_source(source):
    """Wrong or missing input boxes must not move the gold value (SPEC §5.3)."""
    other = mini_context(source, {"m2.jpg": [(0, 0, 400, 400)], "m3.jpg": []})
    for image, region in [("m2.jpg", "full"), ("m2.jpg", "top_left"), ("m3.jpg", "full")]:
        assert stats(image, other, region=region) == stats(image, CTX, region=region)
    assert isinstance(other.boxes, BoxProvider) and other.boxes.source == source


def test_errors():
    assert "unknown image_id" in stats("zz.jpg")["error"]
    assert "unknown region" in stats("m1.jpg", region="edge")["error"]
    assert "no pixels" in stats("m1.jpg", region=[900, 900, 950, 950])["error"]
    assert "unexpected argument" in call_tool(CTX, "image_stats", {"image_id": "m1.jpg", "op": "x"})["error"]


@pytest.mark.data
def test_real_image_values_are_sane_and_deterministic():
    from sarqa.tools import default_context

    ctx = default_context()
    name = "P0001_0_800_7200_8000.jpg"
    a = call_tool(ctx, "image_stats", {"image_id": name})
    assert a == call_tool(ctx, "image_stats", {"image_id": name})
    assert 0 < a["mean_brightness"] < 255 and a["background_noise"] > 0

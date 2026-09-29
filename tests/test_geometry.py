import pytest

from sarqa.boxes import Box
from sarqa.tools.base import ToolError
from sarqa.tools.geometry import distance_px, in_region, near_edge, parse_region


def box(x1, y1, x2, y2):
    return Box("s1", x1, y1, x2, y2)


@pytest.mark.parametrize("b,expected", [
    (box(380, 380, 419, 419), "top_left"),      # centre (399.5, 399.5)
    (box(390, 390, 410, 410), "bottom_right"),  # centre exactly (400, 400)
    (box(390, 100, 410, 110), "top_right"),     # cx = 400 -> right
    (box(100, 390, 110, 410), "bottom_left"),   # cy = 400 -> bottom
    (box(389, 100, 410, 110), "top_left"),      # cx = 399.5 -> left
])
def test_quadrant_uses_centre_with_400_going_right_and_down(b, expected):
    hits = [q for q in ("top_left", "top_right", "bottom_left", "bottom_right")
            if in_region(b, parse_region(q))]
    assert hits == [expected]


def test_overlap_is_not_used():
    wide = box(0, 100, 700, 110)  # mostly right of the border, centre x = 350 -> left
    assert in_region(wide, parse_region("top_left")) and not in_region(wide, parse_region("top_right"))


def test_custom_region_is_half_open_on_the_centre():
    r = parse_region([100, 100, 200, 200])
    assert in_region(box(90, 90, 110, 110), r)        # centre (100, 100): inside
    assert not in_region(box(190, 90, 210, 110), r)   # cx = 200: outside
    assert not in_region(box(90, 190, 110, 210), r)   # cy = 200: outside
    assert parse_region([100, 100, 200, 200]).label == [100, 100, 200, 200]


@pytest.mark.parametrize("bad", ["middle", [1, 2, 3], [5, 5, 5, 9], [1, 1, 0, 9], "full ", None,
                                 [True, 0, 5, 5], "[1,2,3,4]"])
def test_bad_regions_raise(bad):
    with pytest.raises(ToolError):
        parse_region(bad)


@pytest.mark.parametrize("b,near", [
    (box(20, 300, 60, 340), True),    # x1 = 20 -> within 20 px
    (box(21, 300, 60, 340), False),
    (box(300, 300, 780, 340), True),  # 800 - x2 = 20
    (box(300, 300, 779, 340), False),
    (box(300, 20, 340, 60), True),    # y1 = 20
    (box(300, 300, 340, 780), True),  # 800 - y2 = 20
    (box(300, 300, 340, 779), False),
    (box(0, 0, 5, 5), True),
])
def test_edge_margin_is_20px_inclusive(b, near):
    assert near_edge(b) is near


def test_distance_is_centre_to_centre_rounded_to_one_decimal():
    a, b = box(0, 0, 10, 10), box(100, 0, 110, 10)
    assert distance_px(a, b) == 100.0
    assert distance_px(box(0, 0, 2, 2), box(3, 4, 5, 6)) == 5.0
    assert distance_px(box(0, 0, 2, 2), box(1, 1, 3, 3)) == 1.4  # sqrt(2) = 1.41421

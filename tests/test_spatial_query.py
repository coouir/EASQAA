import pytest

from sarqa.tools import call_tool
from tools_fixtures import mini_context

CTX = mini_context()


def q(image, query, **kw):
    return call_tool(CTX, "spatial_query", {"image_id": image, "query": query, **kw})


def test_count_full_and_quadrants():
    assert q("m3.jpg", "count")["count"] == 3
    assert q("m3.jpg", "count", region="top_right") == {
        "query": "count", "region": "top_right", "count": 1, "ship_ids": ["s1"]}
    assert q("m3.jpg", "count", region="bottom_left")["ship_ids"] == ["s2"]
    assert q("m3.jpg", "count", region="top_left")["count"] == 0
    # ids are image-wide: the ship in the bottom-right keeps id s3
    assert q("m3.jpg", "count", region="bottom_right")["ship_ids"] == ["s3"]


def test_count_boundary_ship_centre_400_goes_bottom_right():
    counts = {r: q("m4.jpg", "count", region=r)["count"]
              for r in ("top_left", "top_right", "bottom_left", "bottom_right")}
    # (0,0,10,10) TL; (390..410) centre 400 -> BR; (790..800) BR; (200,600,260,640) BL
    assert counts == {"top_left": 1, "top_right": 0, "bottom_left": 1, "bottom_right": 2}


def test_empty_image_and_fifteen_ships():
    assert q("m1.jpg", "count") == {"query": "count", "region": "full", "count": 0, "ship_ids": []}
    s = q("m1.jpg", "sizes")
    assert s["count"] == 0 and s["long_side_px"] == [] and s["ships"] == []
    assert "at least 2" in q("m1.jpg", "nearest_pair")["error"]
    assert q("m5.jpg", "count")["count"] == 15
    assert q("m5.jpg", "sizes")["long_side_px"] == [20] * 15


def test_sizes_are_long_sides_in_id_order():
    out = q("m3.jpg", "sizes")
    assert out["ships"] == [{"id": "s1", "long_side_px": 40}, {"id": "s2", "long_side_px": 60},
                            {"id": "s3", "long_side_px": 40}]
    assert out["long_side_px"] == [40, 60, 40]
    assert q("m3.jpg", "sizes", region="bottom_left")["long_side_px"] == [60]


def test_distance_and_nearest_pair_match_hand_calculation():
    # centres: s1 (520,115), s2 (110,530), s3 (620,610)
    # s1-s3: dx 100, dy 495 -> 505 exactly; s2-s3: dx 510, dy 80 -> 516.2; s1-s2: 583.4
    assert q("m3.jpg", "distance", ship_a="s1", ship_b="s3")["distance_px"] == 505.0
    assert q("m3.jpg", "distance", ship_a="s3", ship_b="s1")["distance_px"] == 505.0
    assert q("m3.jpg", "distance", ship_a="s2", ship_b="s3")["distance_px"] == 516.2
    pair = q("m3.jpg", "nearest_pair")
    assert (pair["ship_a"], pair["ship_b"], pair["distance_px"]) == ("s1", "s3", 505.0)
    near = q("m3.jpg", "nearest_to", ship_a="s2")
    assert (near["ship_b"], near["distance_px"]) == ("s3", 516.2)


def test_nearest_pair_tie_goes_to_lowest_ids():
    # m5: 15 ships 50 px apart -> the first adjacent pair wins the tie
    pair = q("m5.jpg", "nearest_pair")
    assert (pair["ship_a"], pair["ship_b"], pair["distance_px"]) == ("s1", "s2", 50.0)


def test_nearest_pair_within_region():
    # bottom_right holds s2 (centre 400,400) and s4 (795,795): 395 * sqrt(2) = 558.6
    assert q("m4.jpg", "nearest_pair", region="bottom_right")["distance_px"] == 558.6
    assert "at least 2" in q("m4.jpg", "nearest_pair", region="top_left")["error"]


def test_edge_query():
    # m4 ids by (y1, x1): s1 (0,0,10,10), s2 (390..410), s3 (200,600,260,640), s4 (790..800)
    out = q("m4.jpg", "edge")
    assert out == {"query": "edge", "region": "full", "margin_px": 20, "count": 2,
                   "ship_ids": ["s1", "s4"]}
    assert q("m4.jpg", "edge", region="bottom_right")["ship_ids"] == ["s4"]
    assert q("m4.jpg", "edge", ship_a="s2")["near_edge"] is False
    assert q("m4.jpg", "edge", ship_a="s4")["near_edge"] is True


def test_errors_are_text_not_exceptions():
    assert "unknown query" in q("m3.jpg", "area")["error"]
    assert "unknown image_id" in q("zz.jpg", "count")["error"]
    assert "unknown region" in q("m3.jpg", "count", region="middle")["error"]
    assert "missing required argument 'ship_a'" in q("m3.jpg", "distance", ship_b="s1")["error"]
    assert "unknown ship id" in q("m3.jpg", "distance", ship_a="s1", ship_b="s9")["error"]
    assert "does not take" in q("m3.jpg", "distance", ship_a="s1", ship_b="s2", region="top_left")["error"]
    assert "does not take" in q("m3.jpg", "count", ship_a="s1")["error"]
    assert "either ship_a or region" in q("m3.jpg", "edge", ship_a="s1", region="top_left")["error"]
    assert "at least 2" in q("m2.jpg", "nearest_to", ship_a="s1")["error"]


@pytest.mark.parametrize("region", [[0, 0, 400, 400], [400, 0, 800, 400]])
def test_custom_region_count(region):
    assert q("m3.jpg", "count", region=region)["count"] == (0 if region[0] == 0 else 1)

import json

import pytest

from sarqa.boxes import SOURCES, Box, BoxProvider, file_provider, normalize
from tools_fixtures import MINI_BOXES, mini_context


def test_normalize_orders_by_y1_then_x1_and_numbers_ids():
    boxes = normalize([(50, 40, 60, 50), (10, 40, 20, 50), (5, 10, 9, 20)])
    assert [(b.id, b.x1, b.y1) for b in boxes] == [("s1", 5, 10), ("s2", 10, 40), ("s3", 50, 40)]


def test_normalize_rounds_half_up_clamps_and_ignores_score():
    (b,) = normalize([(-3.2, 10.5, 800.7, 799.49, 0.99)])
    assert (b.x1, b.y1, b.x2, b.y2) == (0, 11, 800, 799)


def test_box_geometry():
    b = Box("s1", 10, 20, 30, 70)
    assert (b.cx, b.cy, b.long_side) == (20.0, 45.0, 50)
    assert b.as_dict() == {"id": "s1", "x1": 10, "y1": 20, "x2": 30, "y2": 70}


def test_provider_rejects_unknown_source_and_image():
    with pytest.raises(ValueError):
        BoxProvider("gt", {})
    with pytest.raises(KeyError):
        BoxProvider("label", {}).boxes("nope.jpg")


def test_all_four_sources_give_identical_output_format(tmp_path):
    """Same image, different origin -> tools cannot tell the origin apart (SPEC §5.1)."""
    raw = {"m3.jpg": MINI_BOXES["m3.jpg"]}
    path = tmp_path / "b.json"
    path.write_text(json.dumps({"images": raw}))
    scored = {"m3.jpg": [b + (0.9,) for b in raw["m3.jpg"]]}
    providers = [BoxProvider("label", raw), BoxProvider("detected", scored),
                 file_provider("injected", path), file_provider("corrected", path)]
    assert {p.source for p in providers} == set(SOURCES)
    outs = [[b.as_dict() for b in p.boxes("m3.jpg")] for p in providers]
    assert all(o == outs[0] for o in outs)


def test_file_provider_only_for_injected_and_corrected(tmp_path):
    with pytest.raises(ValueError):
        file_provider("label", tmp_path / "x.json")


def test_with_boxes_swaps_only_the_box_source():
    ctx = mini_context()
    other = BoxProvider("injected", {"m1.jpg": [(1, 2, 3, 4)]})
    swapped = ctx.with_boxes(other)
    assert swapped.boxes.source == "injected" and swapped.label_boxes.source == "label"


@pytest.mark.data
def test_real_label_provider_matches_coco():
    from sarqa.boxes import label_provider

    p = label_provider()
    assert len(p.image_ids()) == 5604
    total = sum(len(p.boxes(n)) for n in p.image_ids())
    assert total == 16951
    boxes = p.boxes("P0001_0_800_7200_8000.jpg")
    assert [b.id for b in boxes] == [f"s{i}" for i in range(1, len(boxes) + 1)]


@pytest.mark.data
def test_real_detected_provider_uses_frozen_threshold():
    from sarqa.boxes import detected_provider

    p = detected_provider("dev")
    assert len(p.image_ids()) == 393

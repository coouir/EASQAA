import json

import pytest

from sarqa.data.scenes import build_scenes, group_id, official_box_mismatch


def _coco(images, anns=()):
    return {"images": [{"id": i, "file_name": n} for i, n in enumerate(images)],
            "annotations": [{"image_id": i, "bbox": b} for i, b in anns]}


@pytest.fixture
def root(tmp_path):
    (tmp_path / "annotations").mkdir()
    (tmp_path / "inshore_offshore").mkdir()
    names = ["P0001_0_800_0_800.jpg", "P0001_600_1400_0_800.jpg", "P0137_1.jpg"]
    dump = lambda p, d: (tmp_path / p).write_text(json.dumps(d))
    dump("annotations/train_test2017.json", _coco(names, [(0, [1, 1, 2, 2]), (2, [3, 3, 4, 4])]))
    dump("annotations/train2017.json", _coco(names[:1], [(0, [1, 1, 2, 2]), (0, [5, 5, 6, 6])]))
    dump("annotations/test2017.json", _coco(names[1:], [(1, [3, 3, 4, 4])]))
    dump("inshore_offshore/inshore.json", _coco(names[:1]))
    dump("inshore_offshore/offshore.json", _coco(names[1:]))
    return tmp_path


def test_group_id():
    assert group_id("P0042") == "G0042"


def test_build_scenes(root):
    s = build_scenes(root)
    assert s["n_images"] == 3 and s["n_groups"] == 2
    assert s["images"]["P0001_0_800_0_800.jpg"]["group"] == "G0001"
    assert s["groups"]["G0001"] == {"n_images": 2, "n_inshore": 1, "origin_unknown": False}
    assert s["groups"]["G0137"]["origin_unknown"] is True
    assert s["methods"]["filename_scene_only"]["n_images"] == 1


def test_official_box_mismatch(root):
    m = official_box_mismatch(root)
    assert [x["file_name"] for x in m] == ["P0001_0_800_0_800.jpg"]
    assert m[0]["n_boxes_label"] == 1 and m[0]["n_boxes_official"] == 2

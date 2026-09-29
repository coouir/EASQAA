from sarqa.data.hrsid import TileName, boxes_by_file, parse_name


def test_parse_regular_tile():
    assert parse_name("P0001_0_800_7200_8000.jpg") == TileName("P0001", (0, 800, 7200, 8000))


def test_parse_tile_without_coordinates():
    assert parse_name("P0137_62.jpg") == TileName("P0137", None)


def test_parse_unknown_name():
    assert parse_name("foo.jpg") is None


def test_boxes_by_file_keeps_empty_images():
    coco = {
        "images": [{"id": 0, "file_name": "a.jpg"}, {"id": 1, "file_name": "b.jpg"}],
        "annotations": [{"image_id": 0, "bbox": [1, 2, 3, 4]}],
    }
    assert boxes_by_file(coco) == {"a.jpg": [(1, 2, 3, 4)], "b.jpg": []}

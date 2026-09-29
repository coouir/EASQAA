"""Loaders for the HRSID COCO-style files (facts confirmed in docs/data_notes.md)."""

import json
import re
from dataclasses import dataclass
from pathlib import Path

# Regular tiles: P<scene>_<x1>_<x2>_<y1>_<y2>.jpg ; the 109 "P0137_<n>.jpg" tiles have no coordinates.
_TILE = re.compile(r"^(P\d{4})_(\d+)_(\d+)_(\d+)_(\d+)\.jpg$")
_PLAIN = re.compile(r"^(P\d{4})_(\d+)\.jpg$")


@dataclass(frozen=True)
class TileName:
    scene: str
    crop: tuple[int, int, int, int] | None  # (x1, x2, y1, y2) in the source scene, if encoded


def parse_name(file_name: str) -> TileName | None:
    m = _TILE.match(file_name)
    if m:
        return TileName(m.group(1), tuple(int(g) for g in m.groups()[1:]))
    m = _PLAIN.match(file_name)
    if m:
        return TileName(m.group(1), None)
    return None


def load_coco(path: str | Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def boxes_by_file(coco: dict) -> dict[str, list[tuple[float, float, float, float]]]:
    """file_name -> list of COCO bboxes (x, y, w, h). Images without boxes map to []."""
    names = {i["id"]: i["file_name"] for i in coco["images"]}
    out: dict[str, list] = {n: [] for n in names.values()}
    for a in coco["annotations"]:
        out[names[a["image_id"]]].append(tuple(a["bbox"]))
    return out


def xywh_to_xyxy(box) -> tuple[float, float, float, float]:
    x, y, w, h = box
    return (float(x), float(y), float(x + w), float(y + h))

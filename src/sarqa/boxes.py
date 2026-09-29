"""Box sources for the tools (SPEC §5.1, §5.3).

Every source (label | detected | injected | corrected) is turned into the same `Box` list here:
integer pixel coordinates clamped to the image, sorted by (y1, x1), ids `s1, s2, ...`. Tools only
ever see `Box` objects, so their output cannot reveal where the boxes came from.
"""

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from sarqa.config import load_config, repo_path

SOURCES = ("label", "detected", "injected", "corrected")


@dataclass(frozen=True)
class Box:
    id: str
    x1: int
    y1: int
    x2: int
    y2: int

    @property
    def cx(self) -> float:
        return (self.x1 + self.x2) / 2

    @property
    def cy(self) -> float:
        return (self.y1 + self.y2) / 2

    @property
    def long_side(self) -> int:
        return max(self.x2 - self.x1, self.y2 - self.y1)

    def as_dict(self) -> dict:
        return {"id": self.id, "x1": self.x1, "y1": self.y1, "x2": self.x2, "y2": self.y2}


def _px(v: float, size: int) -> int:
    return min(max(math.floor(float(v) + 0.5), 0), size)  # round half up, then clamp


def normalize(raw: Sequence[Sequence[float]], size: int | None = None) -> list[Box]:
    """Raw xyxy boxes (extra trailing values such as a score are ignored) -> ordered `Box` list."""
    size = size or load_config()["tools"]["image_size"]
    rows = sorted(
        (_px(b[1], size), _px(b[0], size), _px(b[2], size), _px(b[3], size)) for b in raw)
    return [Box(f"s{i}", x1, y1, x2, y2) for i, (y1, x1, x2, y2) in enumerate(rows, 1)]


class BoxProvider:
    """Boxes per image for one source. `table` maps image id (file name) -> raw xyxy boxes."""

    def __init__(self, source: str, table: Mapping[str, Sequence[Sequence[float]]]):
        if source not in SOURCES:
            raise ValueError(f"unknown box source {source!r}; expected one of {SOURCES}")
        self.source = source
        self._table = table
        self._cache: dict[str, list[Box]] = {}

    def __contains__(self, image_id: str) -> bool:
        return image_id in self._table

    def image_ids(self) -> list[str]:
        return sorted(self._table)

    def boxes(self, image_id: str) -> list[Box]:
        """Normalised boxes of one image. Raises KeyError for an unknown image."""
        if image_id not in self._cache:
            self._cache[image_id] = normalize(self._table[image_id])
        return self._cache[image_id]


def _load_table(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("images", data)


def label_provider() -> BoxProvider:
    """Human label boxes of every HRSID image (`train_test2017.json`, user decision 4)."""
    from sarqa.data.hrsid import boxes_by_file, load_coco, xywh_to_xyxy
    from sarqa.data.scenes import LABEL_FILE

    root = repo_path(load_config()["paths"]["hrsid_root"])
    raw = boxes_by_file(load_coco(root / LABEL_FILE))
    return BoxProvider("label", {n: [xywh_to_xyxy(b) for b in bs] for n, bs in raw.items()})


def detected_provider(split: str) -> BoxProvider:
    """Cached detector output of `dev` or `test` (`data/detections/<split>.json`).

    The cache is already cut at the frozen score threshold; it is applied again here so a cache
    written at a lower threshold still gives the frozen result. Scores are dropped (SPEC §5.3).
    """
    cfg = load_config()
    if split not in ("dev", "test"):
        raise ValueError(f"no detection cache for split {split!r}")
    thr = cfg["detector"]["score_threshold"]
    path = repo_path(cfg["paths"]["detections_dir"]) / f"{split}.json"
    table = {n: [b[:4] for b in bs if len(b) < 5 or b[4] >= thr]
             for n, bs in _load_table(path).items()}
    return BoxProvider("detected", table)


def file_provider(source: str, path: str | Path) -> BoxProvider:
    """Injected or corrected boxes from a JSON file `{image: [[x1, y1, x2, y2], ...]}`
    (optionally wrapped as `{"images": {...}}`)."""
    if source not in ("injected", "corrected"):
        raise ValueError("file_provider is for the injected and corrected sources")
    return BoxProvider(source, _load_table(Path(path)))

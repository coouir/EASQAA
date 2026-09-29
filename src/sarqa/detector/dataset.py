"""HRSID detection dataset restricted to one split of splits/splits.json."""

import json
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torch.utils.data import Dataset

from sarqa.config import load_config, repo_path
from sarqa.data.hrsid import boxes_by_file, load_coco, xywh_to_xyxy
from sarqa.data.scenes import LABEL_FILE


def load_split(split: str, limit: int | None = None) -> tuple[list[str], dict[str, np.ndarray]]:
    """File names of one split (sorted) and their label boxes as float32 xyxy arrays."""
    cfg = load_config()["paths"]
    with open(repo_path(cfg["splits"]), encoding="utf-8") as f:
        images = json.load(f)["images"]
    names = sorted(n for n, m in images.items() if m["split"] == split)
    if limit:
        names = names[:limit]
    coco = load_coco(Path(repo_path(cfg["hrsid_root"])) / LABEL_FILE)
    raw = boxes_by_file(coco)
    boxes = {n: np.array([xywh_to_xyxy(b) for b in raw[n]], dtype=np.float32).reshape(-1, 4)
             for n in names}
    return names, boxes


class HRSIDDetection(Dataset):
    def __init__(self, names: list[str], boxes: dict[str, np.ndarray], train: bool):
        self.root = Path(repo_path(load_config()["paths"]["hrsid_root"])) / "JPEGImages"
        self.names, self.boxes, self.train = names, boxes, train

    def __len__(self) -> int:
        return len(self.names)

    def __getitem__(self, i: int):
        name = self.names[i]
        with Image.open(self.root / name) as im:
            img = torch.from_numpy(np.asarray(im.convert("RGB"), dtype=np.uint8).copy())
        img = img.permute(2, 0, 1).float() / 255.0
        boxes = torch.from_numpy(self.boxes[name]).clone()
        if self.train and torch.rand(1).item() < 0.5:  # horizontal flip is the only augmentation
            img = img.flip(-1)
            w = img.shape[-1]
            boxes[:, [0, 2]] = w - boxes[:, [2, 0]]
        target = {"boxes": boxes, "labels": torch.ones(len(boxes), dtype=torch.int64)}
        return img, target, name


def collate(batch):
    imgs, targets, names = zip(*batch, strict=True)
    return list(imgs), list(targets), list(names)

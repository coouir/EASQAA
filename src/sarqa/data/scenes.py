"""Scene groups: image -> original-scene group (SPEC §4.2 steps 1-3)."""

import json
from collections import Counter, defaultdict
from pathlib import Path

from sarqa.data.hrsid import boxes_by_file, load_coco, parse_name

LABEL_FILE = "annotations/train_test2017.json"  # user decision 4 (2026-09-29)
OFFICIAL_FILES = ("annotations/train2017.json", "annotations/test2017.json")
TAG_FILES = {"inshore": "inshore_offshore/inshore.json", "offshore": "inshore_offshore/offshore.json"}

# Tiles named P<id>_<n>.jpg have no crop coordinates and their id is not one of the 136 scenes.
UNKNOWN_ORIGIN_SCENE = "P0137"


def group_id(scene: str) -> str:
    return "G" + scene[1:]  # P0042 -> G0042


def official_box_mismatch(root: Path) -> list[dict]:
    """Images whose box list differs between the label file and the official train/test files."""
    label = boxes_by_file(load_coco(root / LABEL_FILE))
    ids = {i["file_name"]: i["id"] for i in load_coco(root / LABEL_FILE)["images"]}
    official: dict[str, list] = {}
    for f in OFFICIAL_FILES:
        official.update(boxes_by_file(load_coco(root / f)))
    out = []
    for name in sorted(label):
        if sorted(label[name]) != sorted(official.get(name, [])):
            out.append({"file_name": name, "coco_id": ids[name],
                        "n_boxes_label": len(label[name]), "n_boxes_official": len(official[name])})
    return out


def build_scenes(root: str | Path) -> dict:
    root = Path(root)
    coco = load_coco(root / LABEL_FILE)
    tags: dict[str, str] = {}
    for tag, f in TAG_FILES.items():
        for img in load_coco(root / f)["images"]:
            tags[img["file_name"]] = tag
    names = [i["file_name"] for i in coco["images"]]
    if set(names) != set(tags):
        raise ValueError("tag files and label file cover different images")

    images: dict[str, dict] = {}
    for name in names:
        parsed = parse_name(name)
        if parsed is None:
            raise ValueError(f"unparseable file name: {name}")
        method = "filename_scene_and_crop" if parsed.crop else "filename_scene_only"
        images[name] = {"group": group_id(parsed.scene), "method": method, "tag": tags[name],
                        "crop": list(parsed.crop) if parsed.crop else None}

    stats: dict[str, Counter] = defaultdict(Counter)
    for meta in images.values():
        stats[meta["group"]]["n_images"] += 1
        stats[meta["group"]]["n_inshore"] += meta["tag"] == "inshore"
    groups = {}
    for gid in sorted(stats):
        unknown = gid == group_id(UNKNOWN_ORIGIN_SCENE)
        groups[gid] = {"n_images": stats[gid]["n_images"], "n_inshore": stats[gid]["n_inshore"],
                       "origin_unknown": unknown}
    methods = Counter(m["method"] for m in images.values())
    return {
        "label_file": LABEL_FILE,
        "methods": {k: {"n_images": v, "fraction": round(v / len(images), 4)}
                    for k, v in sorted(methods.items())},
        "n_images": len(images),
        "n_groups": len(groups),
        "groups": groups,
        "images": images,
    }


def write_scenes(root: str | Path, out: str | Path) -> dict:
    scenes = build_scenes(root)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(scenes, f, indent=1, sort_keys=True)
    return scenes

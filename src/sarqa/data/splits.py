"""Group-level stratified split and leakage checks (SPEC §4.2 steps 4-6)."""

import json
import random
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from PIL import Image

from sarqa.data.hrsid import boxes_by_file, load_coco
from sarqa.data.scenes import LABEL_FILE, official_box_mismatch

SPLITS = ("det_train", "det_val", "dev", "test")
# Fractions of scene groups (SPEC §4.2): det_train ~65%, det_val ~10%, evaluation ~25% -> dev 30% / test 70%.
DET_VAL_FRAC, EVAL_FRAC, DEV_FRAC_OF_EVAL = 0.10, 0.25, 0.30
INSHORE_EDGES = (0.0, 0.15, 0.40)  # group inshore-image ratio bins: ==0, (0,.15], (.15,.4], >.4
SEED_CANDIDATES = range(1000)
DHASH_MAX_DIST = 4  # of 64 bits, auxiliary near-duplicate check only
# Featureless sea tiles hash to almost all-zero bits and match each other by accident; only hashes
# with 12..52 set bits carry enough structure to compare.
DHASH_INFORMATIVE_BITS = (12, 52)


def targets(n_groups: int) -> dict[str, int]:
    n_eval = round(EVAL_FRAC * n_groups)
    n_dev = round(DEV_FRAC_OF_EVAL * n_eval)
    n_val = round(DET_VAL_FRAC * n_groups)
    return {"det_train": n_groups - n_val - n_eval, "det_val": n_val, "dev": n_dev,
            "test": n_eval - n_dev}


def stratum(group: dict, size_cut: float) -> str:
    ratio = group["n_inshore"] / group["n_images"]
    r = sum(ratio > e for e in INSHORE_EDGES)  # 0..3
    return f"ins{r}_{'big' if group['n_images'] > size_cut else 'small'}"


def _deck(tgt: dict[str, int]) -> list[str]:
    """Evenly interleaved label sequence with exact counts, so any contiguous run is ~proportional."""
    keyed = [((i + 0.5) / c, k) for k, c in tgt.items() for i in range(c)]
    return [k for _, k in sorted(keyed)]


def assign(strata: dict[str, str], tgt: dict[str, int], seed: int) -> dict[str, str]:
    """group -> split. Groups are ordered by stratum (random within), then dealt from the deck."""
    rng = random.Random(seed)
    order = sorted(strata, key=lambda g: (strata[g], rng.random()))
    deck = _deck(tgt)
    shift = rng.randrange(len(deck))
    deck = deck[shift:] + deck[:shift]
    return dict(zip(order, deck, strict=True))


def imbalance(groups: dict[str, dict], asg: dict[str, str]) -> float:
    """Sum of squared gaps: image share vs group share, and inshore ratio vs overall, per split."""
    n_g = len(asg)
    n_i = sum(groups[g]["n_images"] for g in asg)
    ins_all = sum(groups[g]["n_inshore"] for g in asg) / n_i
    score = 0.0
    for s in SPLITS:
        gs = [g for g in asg if asg[g] == s]
        ni = sum(groups[g]["n_images"] for g in gs)
        score += (ni / n_i - len(gs) / n_g) ** 2
        score += (sum(groups[g]["n_inshore"] for g in gs) / ni - ins_all) ** 2
    return score


def build_splits(root: str | Path, scenes: dict) -> dict:
    root = Path(root)
    groups = {g: v for g, v in scenes["groups"].items() if not v["origin_unknown"]}
    unknown = [g for g, v in scenes["groups"].items() if v["origin_unknown"]]
    sizes = sorted(v["n_images"] for v in groups.values())
    size_cut = sizes[len(sizes) // 2]
    strata = {g: stratum(v, size_cut) for g, v in groups.items()}
    tgt = targets(len(groups))
    seed = min(SEED_CANDIDATES, key=lambda s: imbalance(groups, assign(strata, tgt, s)))
    asg = assign(strata, tgt, seed)
    for g in unknown:
        asg[g] = "det_train"  # user decision 3: origin unknown -> detector training only

    mismatch = {m["file_name"] for m in official_box_mismatch(root)}
    boxes = boxes_by_file(load_coco(root / LABEL_FILE))
    images = {}
    for name, meta in scenes["images"].items():
        split = asg[meta["group"]]
        images[name] = {
            "group": meta["group"], "split": split, "tag": meta["tag"], "n_boxes": len(boxes[name]),
            "official_box_mismatch": name in mismatch,
            "question_eligible": split in ("dev", "test") and name not in mismatch,
        }
    return {
        "seed": seed, "seed_candidates": [SEED_CANDIDATES.start, SEED_CANDIDATES.stop],
        "targets_groups": tgt, "size_cut_images": size_cut, "inshore_edges": list(INSHORE_EDGES),
        "strata": {g: strata.get(g, "excluded_unknown_origin") for g in asg},
        "groups": {g: {"split": asg[g], **scenes["groups"][g]} for g in sorted(asg)},
        "images": images,
    }


def summarize(splits: dict) -> dict:
    out = {}
    for s in SPLITS:
        gs = [g for g, v in splits["groups"].items() if v["split"] == s]
        ims = [m for m in splits["images"].values() if m["split"] == s]
        ins = sum(m["tag"] == "inshore" for m in ims)
        cand = [m for m in ims if m["question_eligible"] and 2 <= m["n_boxes"] <= 15]
        out[s] = {"groups": len(gs), "images": len(ims), "inshore_images": ins,
                  "inshore_ratio": round(ins / len(ims), 4),
                  "question_candidates_2_15_ships": len(cand),
                  "candidate_inshore": sum(m["tag"] == "inshore" for m in cand)}
    return out


def _overlap(a: tuple, b: tuple) -> bool:
    return a[0] < b[1] and b[0] < a[1] and a[2] < b[3] and b[2] < a[3]


def check_overlap(splits: dict, scenes: dict) -> dict:
    """Automatic leakage checks between splits (SPEC §4.2 step 6)."""
    imgs = splits["images"]
    by_group: dict[str, set] = defaultdict(set)
    for m in imgs.values():
        by_group[m["group"]].add(m["split"])
    groups_in_many = sorted(g for g, s in by_group.items() if len(s) > 1)
    scene_sets = {s: {m["group"] for m in imgs.values() if m["split"] == s} for s in SPLITS}
    shared = {f"{a}&{b}": sorted(scene_sets[a] & scene_sets[b])
              for i, a in enumerate(SPLITS) for b in SPLITS[i + 1:] if scene_sets[a] & scene_sets[b]}
    # Tiles of one scene overlap spatially; count overlapping tile pairs that sit in different splits.
    tiles = defaultdict(list)
    for name, meta in scenes["images"].items():
        if meta["crop"]:
            tiles[meta["group"]].append((tuple(meta["crop"]), imgs[name]["split"]))
    cross = Counter()
    for ts in tiles.values():
        for i, (ca, sa) in enumerate(ts):
            for cb, sb in ts[i + 1:]:
                if sa != sb and _overlap(ca, cb):
                    cross[f"{min(sa, sb)}&{max(sa, sb)}"] += 1
    return {"n_images": len(imgs), "all_images_assigned_once": set(imgs) == set(scenes["images"]),
            "groups_in_multiple_splits": groups_in_many, "shared_groups_between_splits": shared,
            "overlapping_tile_pairs_across_splits": dict(cross),
            "dev_test_group_overlap": sorted(scene_sets["dev"] & scene_sets["test"]),
            "det_train_test_group_overlap": sorted(scene_sets["det_train"] & scene_sets["test"]),
            "passed": set(imgs) == set(scenes["images"]) and not groups_in_many and not shared
            and not cross}


def dhash(path: str | Path) -> int:
    with Image.open(path) as im:
        im.draft("L", (160, 160))
        g = np.asarray(im.convert("L").resize((9, 8), Image.BILINEAR), dtype=np.int16)
    bits = (g[:, 1:] > g[:, :-1]).flatten()
    return int("".join("1" if b else "0" for b in bits), 2)


def near_duplicates(hashes: dict[str, int], splits: dict, max_dist: int = DHASH_MAX_DIST) -> list:
    """Auxiliary only: cross-split image pairs (any different splits, different groups) with small
    dHash distance. Not used to define groups."""
    lo, hi = DHASH_INFORMATIVE_BITS
    names = sorted(n for n, h in hashes.items() if lo <= h.bit_count() <= hi)
    arr = np.array([[(hashes[n] >> k) & 1 for k in range(64)] for n in names], dtype=np.uint8)
    imgs = splits["images"]
    split_of = np.array([SPLITS.index(imgs[n]["split"]) for n in names])
    group_of = np.array([imgs[n]["group"] for n in names])
    pairs = []
    for i in range(len(names)):
        d = (arr[i + 1:] != arr[i]).sum(axis=1)
        for j in np.nonzero(d <= max_dist)[0] + i + 1:
            if split_of[i] != split_of[j] and group_of[i] != group_of[j]:
                pairs.append((names[i], names[int(j)], int(d[j - i - 1])))
    return pairs


def write_splits(root: str | Path, scenes_path: str | Path, out: str | Path,
                 report: str | Path, with_dhash: bool = True) -> dict:
    root = Path(root)
    with open(scenes_path, encoding="utf-8") as f:
        scenes = json.load(f)
    splits = build_splits(root, scenes)
    rep = {"summary": summarize(splits), "overlap_check": check_overlap(splits, scenes)}
    if with_dhash:
        hashes = {n: dhash(root / "JPEGImages" / n) for n in splits["images"]}
        pairs = near_duplicates(hashes, splits)
        rep["dhash_aux"] = {"max_hamming": DHASH_MAX_DIST, "informative_bits": DHASH_INFORMATIVE_BITS,
                            "n_informative_images": sum(
                                DHASH_INFORMATIVE_BITS[0] <= h.bit_count() <= DHASH_INFORMATIVE_BITS[1]
                                for h in hashes.values()),
                            "n_cross_split_pairs": len(pairs),
                            "pairs_first_50": pairs[:50]}
    for path, obj in ((out, splits), (report, rep)):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=1, sort_keys=True)
    return rep

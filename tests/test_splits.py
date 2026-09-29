import numpy as np
from PIL import Image

from sarqa.data.splits import (
    SPLITS,
    _deck,
    assign,
    check_overlap,
    dhash,
    imbalance,
    near_duplicates,
    stratum,
    targets,
)


def test_targets_for_136_groups():
    t = targets(136)
    assert t == {"det_train": 88, "det_val": 14, "dev": 10, "test": 24}
    assert sum(t.values()) == 136


def test_deck_has_exact_counts():
    deck = _deck({"a": 5, "b": 2, "c": 3})
    assert sorted(deck) == ["a"] * 5 + ["b"] * 2 + ["c"] * 3


def _groups(n=40):
    return {f"G{i}": {"n_images": 10 + i, "n_inshore": (i % 5) * 2, "origin_unknown": False}
            for i in range(n)}


def test_assign_exact_counts_and_reproducible():
    groups = _groups()
    strata = {g: stratum(v, 30) for g, v in groups.items()}
    tgt = targets(len(groups))
    a, b = assign(strata, tgt, 3), assign(strata, tgt, 3)
    assert a == b
    counts = {s: sum(v == s for v in a.values()) for s in SPLITS}
    assert counts == tgt
    assert imbalance(groups, a) >= 0


def test_stratum_bins():
    assert stratum({"n_images": 10, "n_inshore": 0}, 20) == "ins0_small"
    assert stratum({"n_images": 30, "n_inshore": 30}, 20) == "ins3_big"


def _scenes_splits(second_split):
    scenes = {"images": {
        "a": {"group": "G1", "crop": [0, 800, 0, 800]}, "b": {"group": "G1", "crop": [400, 1200, 0, 800]}}}
    splits = {"images": {"a": {"group": "G1", "split": "test"}, "b": {"group": "G1", "split": second_split}}}
    return scenes, splits


def test_check_overlap_flags_a_group_split_across_splits():
    scenes, splits = _scenes_splits("det_train")
    r = check_overlap(splits, scenes)
    assert not r["passed"] and r["groups_in_multiple_splits"] == ["G1"]
    assert r["overlapping_tile_pairs_across_splits"] == {"det_train&test": 1}


def test_check_overlap_passes_for_whole_group():
    scenes, splits = _scenes_splits("test")
    assert check_overlap(splits, scenes)["passed"]


def test_dhash_and_near_duplicates(tmp_path):
    rng = np.random.default_rng(0)
    base = rng.integers(0, 255, (80, 80), dtype=np.uint8)
    for n, arr in {"a": base, "b": base, "c": base.T.copy()}.items():
        Image.fromarray(arr).save(tmp_path / f"{n}.png")
    h = {n: dhash(tmp_path / f"{n}.png") for n in "abc"}
    splits = {"images": {"a": {"split": "test", "group": "G1"}, "b": {"split": "det_train", "group": "G2"},
                         "c": {"split": "det_train", "group": "G3"}}}
    pairs = near_duplicates(h, splits)
    assert ("a", "b", 0) in pairs and all("c" not in p[:2] for p in pairs)

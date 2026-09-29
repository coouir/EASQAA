"""Question generator and validator on a synthetic pool (no HRSID needed)."""

import copy

import numpy as np
import pytest

from sarqa.boxes import BoxProvider
from sarqa.questions import slots as S
from sarqa.questions.generate import (
    GenerationError,
    _Tally,
    assign_qids,
    generate,
    image_pool,
    summary,
)
from sarqa.questions.validate import validate
from sarqa.tools.base import ToolContext


def make_world(n_images=60, n_groups=6, seed=3):
    rng = np.random.default_rng(seed)
    boxes, scenes, meta = {}, {}, {}
    for i in range(n_images):
        name = f"s{i:03d}.jpg"
        n = int(rng.integers(2, 16))
        rows = []
        for _ in range(n):
            w, h = int(rng.integers(8, 90)), int(rng.integers(8, 90))
            x, y = int(rng.integers(0, 800 - w)), int(rng.integers(0, 800 - h))
            rows.append((x, y, x + w, y + h))
        boxes[name] = rows
        scenes[name] = "inshore" if rng.random() < 0.5 else "offshore"
        meta[name] = {"group": f"G{i % n_groups:04d}", "split": "dev", "question_eligible": True,
                      "n_boxes": n}
    splits = {"images": meta}
    cache = {}

    def load(name):
        if name not in cache:
            r = np.random.default_rng(abs(hash(name)) % 1000)
            img = r.integers(10, 60, (800, 800)).astype(np.uint8)
            q = int(r.integers(0, 4))
            img[(q // 2) * 400:(q // 2) * 400 + 400, (q % 2) * 400:(q % 2) * 400 + 400] += 40
            cache[name] = img
        return cache[name]

    labels = BoxProvider("label", boxes)
    return ToolContext(labels, labels, scenes, load), splits


QUOTAS = {"l1_total_count": 3, "l1_scene": 3, "l1_quadrant_count": 3, "l2_nearest_ratio": 2,
          "l2_count_over_length": 2, "l3_quadrant_most_ships": 3, "l3_empty_quadrants": 2,
          "l4_count_branch": 3, "l4_scene_branch": 2, "l5_scene_quadrant": 1}


@pytest.fixture(scope="module")
def world():
    return make_world()


def test_generation_is_deterministic_and_seed_dependent(world):
    ctx, splits = world
    a = generate("dev", ctx, seed=1, splits=splits, quotas=QUOTAS)
    b = generate("dev", ctx, seed=1, splits=splits, quotas=QUOTAS)
    c = generate("dev", ctx, seed=2, splits=splits, quotas=QUOTAS)
    assert a == b
    assert [(q["image_id"], q["slots"]) for q in a] != [(q["image_id"], q["slots"]) for q in c]


def test_generated_set_validates_and_meets_the_limits(world):
    ctx, splits = world
    qs = generate("dev", ctx, seed=1, splits=splits, quotas=QUOTAS)
    assert validate(qs, "dev", ctx, splits=splits, check_totals=False) == []
    assert len(qs) == sum(QUOTAS.values())
    assert max(summary(qs)["groups"].values()) <= 3 * len(qs) / 6 + 1
    from collections import Counter
    assert max(Counter(q["image_id"] for q in qs).values()) <= 2
    assert [q["qid"] for q in qs if q["level"] == "L1"] == ["D-L1-001", "D-L1-002", "D-L1-003",
                                                              "D-L1-004", "D-L1-005", "D-L1-006",
                                                              "D-L1-007", "D-L1-008", "D-L1-009"]


def test_balance_filters_cap_one_answer_value(world):
    ctx, splits = world
    qs = generate("dev", ctx, seed=1, splits=splits, quotas=QUOTAS)
    scenes = [q["gold_answer"] for q in qs if q["template"] == "l1_scene"]
    assert max(scenes.count(v) for v in set(scenes)) <= 2          # ceil(3 * 0.5)
    branches = [q["branch_spec"]["gold_branch"] for q in qs if q["template"] == "l4_count_branch"]
    assert max(branches.count(v) for v in set(branches)) <= 2


def test_records_carry_the_spec_fields_and_a_reproducible_answer(world):
    ctx, splits = world
    q = generate("dev", ctx, seed=1, splits=splits, quotas={"l4_count_branch": 2})[0]
    assert q["gold_calls"] in (2, 3) and q["budget"] == max(2 * q["gold_calls"], q["gold_calls"] + 3)
    assert q["has_branch"] and q["branch_spec"]["on"] == "ship_count"
    assert q["intermediates"]["label"]["s1"]["count"] == len(ctx.label_boxes.boxes(q["image_id"]))
    assert q["reference_answers"] == {}


def test_validator_catches_a_wrong_answer_a_duplicate_and_a_wrong_split(world):
    ctx, splits = world
    qs = generate("dev", ctx, seed=1, splits=splits, quotas={"l1_total_count": 3, "l2_count_over_length": 2})
    bad = copy.deepcopy(qs)
    bad[0]["gold_answer"] += 1
    assert any("gives" in p for p in validate(bad, "dev", ctx, splits=splits, check_totals=False))
    dup = copy.deepcopy(qs) + [copy.deepcopy(qs[0])]
    assert any("duplicate" in p for p in validate(dup, "dev", ctx, splits=splits, check_totals=False))
    assert any("split" in p for p in validate(qs, "test", ctx, splits=splits, check_totals=False))
    assert any("level counts" in p for p in validate(qs, "dev", ctx, splits=splits))


def test_impossible_quota_raises_instead_of_returning_a_short_set():
    ctx, splits = make_world(n_images=3, n_groups=1)
    with pytest.raises(GenerationError):
        generate("dev", ctx, seed=1, splits=splits, quotas={"l1_total_count": 30})


def test_pool_uses_only_eligible_images_of_the_split():
    _, splits = make_world(n_images=8, n_groups=2)
    splits["images"]["s000.jpg"]["question_eligible"] = False
    splits["images"]["s001.jpg"]["split"] = "test"
    splits["images"]["s002.jpg"]["n_boxes"] = 1
    splits["images"]["s003.jpg"]["n_boxes"] = 16
    names = [n for n, _ in image_pool("dev", splits)]
    assert names == ["s004.jpg", "s005.jpg", "s006.jpg", "s007.jpg"]
    assert [n for n, _ in image_pool("test", splits)] == ["s001.jpg"]


def test_tally_limits_zero_and_repeated_answers():
    t = _Tally(quota=5, balance=__import__("collections").Counter())
    assert t.allows(3, False)
    t.add(0, True)
    assert not t.allows(1, True)                      # ceil(5 * 0.2) = 1 zero allowed
    for _ in range(3):
        t.add(7, False)
    assert not t.allows(7, False)                     # ceil(5 * 0.5) = 3 of one value


def test_margin_helpers():
    assert S.clear_of([10, 20], 15) and not S.clear_of([14], 15) and not S.clear_of([16.4], 15)
    assert S.clear_count(5, 7) and not S.clear_count(6, 7) and not S.clear_count(8, 7)
    assert S.unique_extreme([1, 3, 2], "max") and not S.unique_extreme([3, 3, 1], "max")
    assert S.unique_extreme([2, 1, 5], "min") and not S.unique_extreme([1, 1, 5], "min")
    assert S.stat_argmax_clear({"a": 10.0, "b": 9.0, "c": 1.0}) and not S.stat_argmax_clear(
        {"a": 10.0, "b": 9.9, "c": 1.0}) and not S.stat_argmax_clear({"a": 10.0, "b": None})


def test_qids_are_numbered_per_level():
    qs = [{"level": "L2", "template": "l2_longest_length"}, {"level": "L1", "template": "l1_scene"},
          {"level": "L1", "template": "l1_total_count"}]
    out = assign_qids(qs, "dev")
    assert [q["qid"] for q in out] == ["D-L1-001", "D-L1-002", "D-L2-001"]
    assert [q["template"] for q in out][:2] == ["l1_total_count", "l1_scene"]

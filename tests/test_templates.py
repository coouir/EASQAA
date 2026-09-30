"""Template catalogue: programs run, alternatives agree, vocabulary is closed, quotas add up."""

import numpy as np
import pytest

from sarqa.boxes import BoxProvider
from sarqa.program import run_program, validate_program
from sarqa.questions import vocab
from sarqa.questions.templates import LEVEL_TOTALS, QUOTAS, TEMPLATES
from sarqa.tools.base import ToolContext

BOXES = {"t1.jpg": [(50, 50, 80, 70), (100, 200, 170, 230), (150, 300, 160, 340), (500, 100, 560, 130),
                    (600, 700, 650, 720), (100, 500, 125, 520)]}
SCENES = {"t1.jpg": "inshore", "t2.jpg": "offshore"}
BOXES["t2.jpg"] = BOXES["t1.jpg"]


def _image(name):
    rng = np.random.default_rng(0)
    img = rng.integers(20, 40, (800, 800)).astype(np.uint8)
    img[:400, 400:] = rng.integers(0, 120, (400, 400))     # noisy, brighter top-right quadrant
    for x1, y1, x2, y2 in BOXES[name]:
        img[y1:y2, x1:x2] = 250
    return img


def ctx_for(scene_of=None):
    labels = BoxProvider("label", BOXES)
    return ToolContext(labels, labels, scene_of or SCENES, _image)


SLOTS = {"region": "top_left", "rect": [0, 0, 400, 400], "threshold": 35, "count_threshold": 2}
SLOT_OVERRIDE = {"l4_count_branch": {"threshold": 3}, "l4_quadrant_branch": {"region": "top_left",
                                                                             "threshold": 2},
                 "l4_noise_branch": {"threshold": 10.0}, "l4_maxlen_branch": {"threshold": 55},
                 "l1_brightness": {"region": "top_right"}}


def slots_of(tid):
    return {**SLOTS, **SLOT_OVERRIDE.get(tid, {})}


@pytest.mark.parametrize("tid", sorted(TEMPLATES))
def test_gold_program_is_valid_runs_and_alternatives_agree(tid):
    t = TEMPLATES[tid]
    s = slots_of(tid)
    program = t.program(s)
    assert validate_program(program) == []
    for image in ("t1.jpg", "t2.jpg"):
        res = run_program(program, image, ctx_for().boxes, ctx=ctx_for())
        assert res.ok, (tid, image, res.errors, [c.output for c in res.tool_errors])
        for alt in t.alts(s, program):
            assert validate_program(alt) == [], tid
            r2 = run_program(alt, image, ctx_for().boxes, ctx=ctx_for())
            assert r2.ok and r2.answer == res.answer, (tid, image, r2.answer, res.answer)


@pytest.mark.parametrize("tid", sorted(TEMPLATES))
def test_text_and_interpretation_use_the_closed_vocabulary(tid):
    t = TEMPLATES[tid]
    s = slots_of(tid)
    text = t.text(s)
    assert text and "{" not in text and "None" not in text
    it = t.interpretation(s)
    assert tuple(it) == vocab.INTERPRETATION_KEYS
    assert it["target"] in vocab.TARGETS
    assert it["unit"] in vocab.UNITS and it["answer_type"] in vocab.ANSWER_TYPES
    assert it["unit"] == t.unit and it["answer_type"] == t.answer_type
    assert it["region"] in vocab.REGIONS or (isinstance(it["region"], list) and len(it["region"]) == 4)
    for f in it["filters"]:
        assert f["field"] in vocab.FILTER_FIELDS and f["cmp"] in vocab.COMPARATORS
    if t.has_branch:
        b = it["branch"]
        assert it["target"] == "branch" and tuple(b) == vocab.BRANCH_KEYS
        assert b["on"] in vocab.BRANCH_ON and b["cmp"] in vocab.BRANCH_CMPS
        assert b["then_target"] in vocab.TARGETS[:-1] and b["else_target"] in vocab.TARGETS[:-1]
        assert t.branch_spec is not None and t.branch_spec(s)["on"] == b["on"]
    else:
        assert it["branch"] is None and it["target"] != "branch"


def test_branch_flag_matches_the_program():
    def has_if(steps):
        return any(s["op"] == "if" or has_if(s.get("then", []) + s.get("else", []) + s.get("do", []))
                   for s in steps)

    for tid, t in TEMPLATES.items():
        assert has_if(t.program(slots_of(tid))["steps"]) == t.has_branch, tid
    assert all(t.has_branch for t in TEMPLATES.values() if t.level in ("L4", "L5"))
    assert not any(t.has_branch for t in TEMPLATES.values() if t.level in ("L1", "L2", "L3"))


def test_l2_chains_two_or_three_tools_and_always_calls_calc():
    for tid, t in TEMPLATES.items():
        if t.level != "L2":
            continue
        res = run_program(t.program(slots_of(tid)), "t1.jpg", ctx_for().boxes, ctx=ctx_for())
        tools = {c.tool for c in res.calls}
        assert "calc" in tools and 2 <= len(tools) <= 3, (tid, tools)


def test_l1_has_one_call_and_l3_repeats_one_tool():
    for tid, t in TEMPLATES.items():
        res = run_program(t.program(slots_of(tid)), "t1.jpg", ctx_for().boxes, ctx=ctx_for())
        if t.level == "L1":
            assert res.gold_calls == 1, tid
        if t.level == "L3":
            assert res.gold_calls >= 5, tid


def test_quotas_add_up_and_test_is_mostly_box_dependent():
    for split, totals in LEVEL_TOTALS.items():
        by_level = {}
        for tid, n in QUOTAS[split].items():
            by_level[TEMPLATES[tid].level] = by_level.get(TEMPLATES[tid].level, 0) + n
        assert by_level == totals
        total = sum(totals.values())
        dep = sum(n for tid, n in QUOTAS[split].items() if TEMPLATES[tid].box_dependent)
        assert dep / total >= 0.80, (split, dep, total)
    assert sum(LEVEL_TOTALS["test"].values()) == 360 and sum(LEVEL_TOTALS["dev"].values()) == 90
    assert set(QUOTAS["dev"]) == set(QUOTAS["test"]) == set(TEMPLATES)


def test_at_least_half_of_the_l4_branch_conditions_come_from_boxes():
    box_on = {"ship_count", "max_length"}
    for split in ("dev", "test"):
        l4 = {tid: n for tid, n in QUOTAS[split].items() if TEMPLATES[tid].level == "L4"}
        from_boxes = sum(n for tid, n in l4.items()
                         if TEMPLATES[tid].branch_spec(slots_of(tid))["on"] in box_on)
        assert from_boxes / sum(l4.values()) >= 0.5, split


def test_interpretation_schema_lists_every_target():
    schema = vocab.interpretation_schema()
    assert schema["properties"]["target"]["enum"] == list(vocab.TARGETS)
    assert set(schema["required"]) == set(vocab.INTERPRETATION_KEYS)


def test_longest_length_is_a_float_question_with_five_percent_tolerance():
    from sarqa.grading import grade

    t = TEMPLATES["l2_longest_length"]
    assert t.answer_type == "float" and t.interpretation({})["answer_type"] == "float"
    assert grade(62, "px", 60.0, "px", "float").correct           # 3.3 % off: a small box jitter is fine
    assert not grade(64, "px", 60.0, "px", "float").correct        # 6.7 % off


# ---------------------------------------------------------------- dev review of 2026-09-30

def _text(tid, **over):
    return TEMPLATES[tid].text(slots_of(tid) | over)


def test_review_texts():
    fmt = "(왼쪽 위=top_left, 오른쪽 위=top_right, 왼쪽 아래=bottom_left, 오른쪽 아래=bottom_right 중 하나의 영문 이름으로 답하라)"
    for tid in ("l3_quadrant_most_ships", "l3_quadrant_most_long", "l3_quadrant_brightest", "l3_quadrant_noisiest"):
        assert _text(tid).endswith(fmt), tid
    edge = "상자의 한 변이라도 영상 가장자리에서 20 px 이내에 있는"
    assert edge in _text("l1_edge_count") and edge in _text("l4_noise_branch")
    assert "선박 수를 답하라" in _text("l4_noise_branch")
    # "(선박 중심 기준)" wherever ships are assigned to a quadrant; not for pure image statistics
    for tid in ("l1_quadrant_count", "l3_quadrant_most_ships", "l3_empty_quadrants", "l3_quadrant_most_long",
                "l4_quadrant_branch", "l5_noisy_quadrant", "l5_scene_quadrant"):
        assert "사분면(선박 중심 기준)" in _text(tid), tid
    for tid in ("l3_quadrant_brightest", "l3_quadrant_noisiest", "l1_brightness"):
        assert "선박 중심 기준" not in _text(tid), tid


def test_count_branch_reads_k_plus_one_or_more_and_keeps_every_answer():
    from sarqa.program import run_program

    t = TEMPLATES["l4_count_branch"]
    s = {"threshold": 3}
    assert "4척 이상이면" in t.text(s) and "초과" not in t.text(s)
    it = t.interpretation(s)["branch"]
    assert (it["cmp"], it["threshold"]) == (">=", 4) and t.branch_spec(s)["threshold"] == 4
    prog = t.program(s)
    old = {**prog, "steps": [dict(st) for st in prog["steps"]]}
    old["steps"][1] = {**old["steps"][1], "cond": {"lhs": "$s1.count", "cmp": ">", "rhs": 3}}
    for image in ("t1.jpg", "t2.jpg"):
        a = run_program(prog, image, ctx_for().boxes, ctx=ctx_for()).answer
        b = run_program(old, image, ctx_for().boxes, ctx=ctx_for()).answer
        assert a == b
    for n in range(16):                                    # the two conditions agree for every count
        assert (n >= 3 + 1) == (n > 3)


def test_l4_branches_that_answer_a_length_are_float_questions():
    for tid in ("l4_scene_branch", "l4_count_branch", "l4_quadrant_branch"):
        t = TEMPLATES[tid]
        assert t.answer_type == "float" and t.unit == "px" and t.interpretation(slots_of(tid))["answer_type"] == "float"

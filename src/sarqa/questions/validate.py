"""Validation of a generated question set (SPEC §6.4 step 5).

`validate(questions, split, ctx)` returns a list of problems (empty = passes). Test questions must
not be finalised unless this passes. Checks: schema, gold reproduction by re-running the program
(and every allowed alternative) on label boxes, duplicates, per-level counts against the SPEC,
per-image and per-group limits, ship-count window, budget arithmetic, box-dependent share.
"""

import json
import math
from collections import Counter

from sarqa.program import budget_for, run_program, validate_program
from sarqa.questions.generate import (
    GROUP_CAP_FACTOR,
    MAX_PER_IMAGE,
    image_pool,
    load_splits,
)
from sarqa.questions.slots import MAX_SHIPS, MIN_SHIPS
from sarqa.questions.templates import LEVEL_TOTALS, TEMPLATES
from sarqa.questions.vocab import CATEGORY_ANSWERS, INTERPRETATION_KEYS
from sarqa.tools.base import ToolContext

REQUIRED = ("qid", "split", "level", "template", "image_id", "scene_group", "text_ko", "answer_type",
            "unit", "gold_answer", "tolerance", "program", "alt_programs", "gold_calls", "budget",
            "gold_interpretation", "branch_spec", "box_dependent", "has_branch", "intermediates",
            "reference_answers")


def same_answer(a, b, answer_type: str, rel: float = 0.0) -> bool:
    if answer_type == "float":
        return isinstance(a, (int, float)) and isinstance(b, (int, float)) \
            and math.isclose(a, b, rel_tol=max(rel, 1e-9), abs_tol=1e-9)
    return a == b


def validate(questions: list[dict], split: str, ctx: ToolContext, *, splits: dict | None = None,
             check_totals: bool = True) -> list[str]:
    problems: list[str] = []
    splits = splits or load_splits()
    pool = dict(image_pool(split, splits))
    seen_ids, seen_keys = set(), set()

    for q in questions:
        qid = q.get("qid", "?")
        missing = [k for k in REQUIRED if k not in q]
        if missing:
            problems.append(f"{qid}: missing keys {missing}")
            continue
        if qid in seen_ids:
            problems.append(f"{qid}: duplicate qid")
        seen_ids.add(qid)
        key = (q["template"], q["image_id"], json.dumps(q.get("slots"), sort_keys=True))
        if key in seen_keys:
            problems.append(f"{qid}: duplicate question (same template, image and slots)")
        seen_keys.add(key)
        if q["split"] != split:
            problems.append(f"{qid}: split is {q['split']!r}, expected {split!r}")
        if q["template"] not in TEMPLATES:
            problems.append(f"{qid}: unknown template {q['template']!r}")
            continue
        t = TEMPLATES[q["template"]]
        if q["image_id"] not in pool:
            problems.append(f"{qid}: image {q['image_id']} is not an eligible {split} image")
        elif pool[q["image_id"]] != q["scene_group"]:
            problems.append(f"{qid}: scene group does not match the split file")
        n_ships = len(ctx.label_boxes.boxes(q["image_id"])) if q["image_id"] in ctx.label_boxes else -1
        if not MIN_SHIPS <= n_ships <= MAX_SHIPS:
            problems.append(f"{qid}: {n_ships} label ships, need {MIN_SHIPS}-{MAX_SHIPS}")
        if q["level"] != t.level or q["box_dependent"] != t.box_dependent \
                or q["has_branch"] != t.has_branch:
            problems.append(f"{qid}: level/box_dependent/has_branch differ from the template")
        if tuple(q["gold_interpretation"]) != INTERPRETATION_KEYS:
            problems.append(f"{qid}: gold_interpretation keys are not the closed vocabulary")

        for label, prog in [("program", q["program"])] + [
                (f"alt_programs[{i}]", p) for i, p in enumerate(q["alt_programs"])]:
            bad = validate_program(prog)
            if bad:
                problems.append(f"{qid}: {label} is malformed: {bad[:2]}")
                continue
            res = run_program(prog, q["image_id"], ctx.label_boxes, ctx=ctx)
            if not res.ok:
                problems.append(f"{qid}: {label} does not run cleanly: "
                                f"{res.errors or [c.output for c in res.tool_errors]}")
            elif not same_answer(res.answer, q["gold_answer"], q["answer_type"]):
                problems.append(f"{qid}: {label} gives {res.answer!r}, gold is {q['gold_answer']!r}")
            elif label == "program":
                if res.gold_calls != q["gold_calls"]:
                    problems.append(f"{qid}: gold_calls {q['gold_calls']} != executed {res.gold_calls}")
                if q["budget"] != budget_for(q["gold_calls"]):
                    problems.append(f"{qid}: budget {q['budget']} != budget_for(gold_calls)")
        if t.level == "L5" and not q["has_branch"]:
            problems.append(f"{qid}: L5 question without an `if`")
        if q["answer_type"] == "category" and q["gold_answer"] not in CATEGORY_ANSWERS:
            problems.append(f"{qid}: category answer {q['gold_answer']!r} outside the enum")

    counts = Counter(q["level"] for q in questions)
    if check_totals and split in LEVEL_TOTALS and dict(counts) != LEVEL_TOTALS[split]:
        problems.append(f"level counts {dict(counts)} != {LEVEL_TOTALS[split]}")
    per_image = Counter(q["image_id"] for q in questions)
    for image, n in per_image.items():
        if n > MAX_PER_IMAGE:
            problems.append(f"image {image} has {n} questions (limit {MAX_PER_IMAGE})")
    groups = Counter(q["scene_group"] for q in questions)
    if questions:
        cap = math.ceil(GROUP_CAP_FACTOR * len(questions) / max(1, len(set(pool.values()))))
        for g, n in groups.items():
            if n > cap:
                problems.append(f"scene group {g} has {n} questions (cap {cap})")
    return problems

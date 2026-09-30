"""Input-error sub-categories by replay (SPEC §11.4). No LLM is involved, so it is free and complete.

The boxes the run received are matched to the labels (IoU 0.5); each of the three errors is fixed
**alone** (`inject.correct.correct`) and the gold program is run again on the result:
  - fixing one kind gives `gold_answer`      -> that kind is a sufficient cause (all such are recorded)
  - no single kind suffices, all three do    -> `composite`
  - not even fixing all three gives it       -> `unknown` (the tool outputs differ in structure)
"""

from sarqa.boxes import BoxProvider
from sarqa.detector.match import error_types, match_boxes
from sarqa.grading import value_matches
from sarqa.inject.correct import KINDS, correct
from sarqa.program import run_program


def _tuples(boxes):
    return [(b.x1, b.y1, b.x2, b.y2) for b in boxes]


def error_counts(received: list[tuple], labels: list[tuple]) -> dict[str, int]:
    err = error_types(match_boxes(received, labels))
    return {"miss": len(err.miss), "fp": len(err.fp), "loc": len(err.loc)}


def _answer_on(question: dict, boxes: list[tuple], ctx) -> object:
    provider = BoxProvider("corrected", {question["image_id"]: [list(b) for b in boxes]})
    res = run_program(question["program"], question["image_id"], provider, ctx=ctx)
    return res.answer if res.ok else None


def replay_input(question: dict, provider, ctx) -> dict:
    """`{"errors": {miss, fp, loc}, "sufficient": [kinds], "category": kind | "composite" | "unknown"}`
    where `category` is the single sufficient kind, `multiple` if several suffice."""
    image = question["image_id"]
    received = _tuples(provider.boxes(image))
    labels = _tuples(ctx.label_boxes.boxes(image))
    counts = error_counts(received, labels)
    sufficient = []
    for kind in KINDS:
        if not counts[kind]:
            continue  # nothing of this kind to fix
        fixed = correct(kind, received, labels)
        if value_matches(_answer_on(question, fixed, ctx), question["gold_answer"], question["answer_type"]):
            sufficient.append(kind)
    if len(sufficient) == 1:
        category = sufficient[0]
    elif sufficient:
        category = "multiple"
    else:
        everything = received
        for kind in KINDS:
            everything = correct(kind, everything, labels)
        ok = value_matches(_answer_on(question, everything, ctx), question["gold_answer"],
                           question["answer_type"])
        category = "composite" if ok else "unknown"
    return {"errors": counts, "sufficient": sufficient, "category": category}

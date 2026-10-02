"""Why the input-error replay ends in `unknown` (SPEC §11.4): read-only look at the remaining box differences.

    python -m sarqa.analysis.unknown_causes --classified outputs/analysis/classified.jsonl \
        --questions data/questions/test.json --out outputs/analysis/unknown_input_causes.csv

For every question whose input cause is `unknown`, the received boxes get all three corrections in the
replay order (miss, fp, loc) and are compared with the label boxes: pairs that still differ (IoU >= 0.75
is not counted as a location error, so those boxes stay as the detector drew them) and boxes that still
have no partner. The gold program is then run on the fully corrected boxes and on the label boxes.
Default scope is the detected-input conditions 2 and 5 (same boxes, so one row per question). Nothing here changes a classification; it only reads.
"""

import argparse
import csv
import json
from pathlib import Path

from sarqa.classify.replay import _answer_on, _tuples
from sarqa.detector.match import iou_matrix, match_boxes
from sarqa.grading import value_matches
from sarqa.inject.correct import KINDS, correct


def fully_corrected(received: list[tuple], labels: list[tuple]) -> list[tuple]:
    boxes = received
    for kind in KINDS:
        boxes = correct(kind, boxes, labels)
    return boxes


def residual(received: list[tuple], labels: list[tuple]) -> dict:
    """Differences left between the fully corrected boxes and the labels."""
    fixed = fully_corrected(received, labels)
    m = match_boxes(fixed, labels, 0.5)
    ious = iou_matrix(fixed, labels)
    return {
        "n_labels": len(labels), "n_received": len(received), "n_fixed": len(fixed),
        "pairs_below_1": [(i, j, round(float(ious[i, j]), 3)) for i, j, _ in m.pairs if ious[i, j] < 0.999999],
        "unmatched_fixed": m.unmatched_dets, "unmatched_labels": m.unmatched_labels,
        "fixed": fixed,
    }


def _long(b: tuple) -> float:
    return max(b[2] - b[0], b[3] - b[1])


def rows(classified: list[dict], questions: list[dict], ctx=None, conditions=(2, 5)) -> list[dict]:
    from sarqa.run.conditions import Condition, ProviderPool
    from sarqa.tools import default_context

    ctx = ctx or default_context()
    pool = ProviderPool("test")
    by_q = {q["qid"]: q for q in questions}
    seen, out = {}, []
    for c in classified:
        cause = c.get("input_cause")
        if c["condition"] in conditions and isinstance(cause, dict) and cause.get("category") == "unknown":
            seen.setdefault(c["qid"], []).append(c["condition"])
    for qid, conds in sorted(seen.items()):
        q = by_q[qid]
        cond = min(conds)   # conditions 2 and 5 receive the same detected boxes
        method = "batch" if cond in (4, 5) else "stepwise"
        prov = pool.get(Condition(cond, method, "detected", 0))
        received = _tuples(prov.boxes(q["image_id"]))
        labels = _tuples(ctx.label_boxes.boxes(q["image_id"]))
        r = residual(received, labels)
        fixed_ans = _answer_on(q, r["fixed"], ctx)
        label_ans = _answer_on(q, labels, ctx)
        recv_ans = _answer_on(q, received, ctx)
        diffs = [f"fixed#{i}~label#{j} IoU {v}" for i, j, v in r["pairs_below_1"]]
        diffs += [f"fixed#{i} has no label" for i in r["unmatched_fixed"]]
        diffs += [f"label#{j} has no box" for j in r["unmatched_labels"]]
        out.append({
            "qid": qid, "conditions": "/".join(map(str, sorted(conds))), "template": q["template"], "level": q["level"],
            "labels": r["n_labels"], "received": r["n_received"], "after_3_fixes": r["n_fixed"],
            "remaining_differences": "; ".join(diffs) or "none",
            "gold_answer": q["gold_answer"], "answer_type": q["answer_type"],
            "answer_on_received": recv_ans, "answer_on_all_fixed": fixed_ans,
            "all_fixed_matches_gold": bool(value_matches(fixed_ans, q["gold_answer"], q["answer_type"])),
            "answer_on_label_boxes": label_ans,
            "label_boxes_match_gold": bool(value_matches(label_ans, q["gold_answer"], q["answer_type"])),
        })
    return out


def write_csv(path: Path, data: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, list(data[0]))
        w.writeheader()
        w.writerows(data)


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--classified", default="outputs/analysis/classified.jsonl")
    p.add_argument("--questions", default="data/questions/test.json")
    p.add_argument("--out", default="outputs/analysis/unknown_input_causes.csv")
    a = p.parse_args(argv)
    classified = [json.loads(x) for x in Path(a.classified).read_text(encoding="utf-8").splitlines() if x.strip()]
    questions = json.loads(Path(a.questions).read_text(encoding="utf-8"))["questions"]
    data = rows(classified, questions)
    write_csv(Path(a.out), data)
    print(json.dumps(data, ensure_ascii=False, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

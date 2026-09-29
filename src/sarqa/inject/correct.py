"""Correction (SPEC §8.3): detected boxes with exactly one error kind fixed.

  corrected(miss)  add every unmatched label box to the detections
  corrected(fp)    delete every unmatched detection
  corrected(loc)   replace each matched detection with IoU < 0.75 by its label box
Nothing else is touched. Matching is the frozen greedy IoU 0.5 one-to-one (`detector/match.py`).
"""

from sarqa.detector.match import error_types, match_boxes

KINDS = ("miss", "fp", "loc")


def correct(kind: str, detected: list[tuple], labels: list[tuple]) -> list[tuple]:
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}")
    m = match_boxes(detected, labels)
    err = error_types(m)
    out = list(detected)
    if kind == "miss":
        out += [tuple(labels[j]) for j in err.miss]
    elif kind == "fp":
        drop = set(err.fp)
        out = [b for i, b in enumerate(detected) if i not in drop]
    else:
        swap = {d: j for d, j, _ in err.loc}
        out = [tuple(labels[swap[i]]) if i in swap else b for i, b in enumerate(detected)]
    return out

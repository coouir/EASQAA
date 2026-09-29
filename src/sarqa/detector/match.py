"""IoU matching between detected and label boxes and the three error types (SPEC §8.1).

Boxes are (x1, y1, x2, y2). Errors:
  miss = label box left unmatched, fp = detected box left unmatched,
  loc  = matched pair with IoU < loc_iou. A box pair with IoU < iou never matches, so a badly
  displaced box counts as miss + fp rather than loc.
"""

from dataclasses import dataclass, field

import numpy as np

from sarqa.config import load_config


def iou_matrix(a, b) -> np.ndarray:
    """Pairwise IoU, shape (len(a), len(b)). Degenerate (zero-area) unions give 0."""
    a = np.asarray(a, dtype=np.float64).reshape(-1, 4)
    b = np.asarray(b, dtype=np.float64).reshape(-1, 4)
    if len(a) == 0 or len(b) == 0:
        return np.zeros((len(a), len(b)))
    lt = np.maximum(a[:, None, :2], b[None, :, :2])
    rb = np.minimum(a[:, None, 2:], b[None, :, 2:])
    inter = np.prod(np.clip(rb - lt, 0, None), axis=2)
    area_a = np.prod(a[:, 2:] - a[:, :2], axis=1)
    area_b = np.prod(b[:, 2:] - b[:, :2], axis=1)
    union = area_a[:, None] + area_b[None, :] - inter
    return np.divide(inter, union, out=np.zeros_like(inter), where=union > 0)


@dataclass
class Matching:
    pairs: list[tuple[int, int, float]] = field(default_factory=list)  # (det, label, iou)
    unmatched_dets: list[int] = field(default_factory=list)
    unmatched_labels: list[int] = field(default_factory=list)


def match_boxes(dets, labels, iou_thr: float | None = None) -> Matching:
    """Greedy one-to-one matching, largest IoU first (ties: smaller det index, then label index)."""
    if iou_thr is None:
        iou_thr = load_config("classify")["match"]["iou"]
    m = iou_matrix(dets, labels)
    n_det, n_lab = m.shape
    cand = [(m[i, j], i, j) for i in range(n_det) for j in range(n_lab) if m[i, j] >= iou_thr]
    cand.sort(key=lambda t: (-t[0], t[1], t[2]))
    used_d, used_l, pairs = set(), set(), []
    for v, i, j in cand:
        if i in used_d or j in used_l:
            continue
        used_d.add(i)
        used_l.add(j)
        pairs.append((i, j, float(v)))
    return Matching(
        pairs=sorted(pairs),
        unmatched_dets=[i for i in range(n_det) if i not in used_d],
        unmatched_labels=[j for j in range(n_lab) if j not in used_l],
    )


@dataclass
class ErrorSet:
    miss: list[int]                        # label indices
    fp: list[int]                          # detection indices
    loc: list[tuple[int, int, float]]      # (det, label, iou) with iou < loc_iou


def error_types(matching: Matching, loc_iou: float | None = None) -> ErrorSet:
    if loc_iou is None:
        loc_iou = load_config("classify")["match"]["loc_iou"]
    return ErrorSet(
        miss=list(matching.unmatched_labels),
        fp=list(matching.unmatched_dets),
        loc=[p for p in matching.pairs if p[2] < loc_iou],
    )


def classify_detections(dets, labels) -> ErrorSet:
    """Convenience: match with the frozen thresholds and return the three error sets."""
    return error_types(match_boxes(dets, labels))

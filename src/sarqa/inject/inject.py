"""Error injection (SPEC §8.2): label boxes + exactly one error kind T in {miss, fp, loc}.

Seeded by **(image, kind)** only, so every question on an image and every method get the same boxes.
All measured quantities come from `configs/injection.yaml` (`calibrate.py`). After injecting, the
result is matched back to the labels and must show only errors of kind T (`check_injection`).
"""

import math
from dataclasses import dataclass, field

from sarqa.detector.match import error_types, iou_matrix, match_boxes
from sarqa.inject.calibrate import size_bin, stratum
from sarqa.questions.slots import rng_for

KINDS = ("miss", "fp", "loc")
IMAGE = 800


@dataclass
class Injection:
    boxes: list[tuple[int, int, int, int]]            # the injected list (unordered raw xyxy)
    changed: list[int] = field(default_factory=list)  # label indices missed / perturbed
    added: int = 0                                    # false positives added
    failed: int = 0                                   # draws that found no valid box in 50 tries
    strata: list[str] = field(default_factory=list)   # stratum of every changed label


def _clamp(v: float) -> int:
    return min(max(math.floor(v + 0.5), 0), IMAGE)


def _iou(a, b) -> float:
    return float(iou_matrix([a], [b])[0, 0])


def inject(kind: str, image_id: str, labels: list[tuple[int, int, int, int]], scene: str,
           cfg: dict, seed: int) -> Injection:
    """Boxes of `image_id` with one error kind injected. `labels` are normalised integer xyxy."""
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}")
    rng = rng_for(seed, "inject", image_id, kind)
    cuts = cfg["size_cuts_long_side_px"]
    max_redraws = cfg["rules"]["max_redraws"]
    out = Injection(boxes=list(labels))
    if kind == "miss":
        keep = []
        for i, b in enumerate(labels):
            s = stratum(max(b[2] - b[0], b[3] - b[1]), scene, cuts)
            if rng.random() < cfg["miss_rate"][s]:
                out.changed.append(i)
                out.strata.append(s)
            else:
                keep.append(b)
        out.boxes = keep
    elif kind == "fp":
        n = rng.choice(cfg["fp_counts"][scene]) if cfg["fp_counts"][scene] else 0
        wh, xy = cfg["fp_wh"][scene], cfg["fp_xy"][scene]
        for _ in range(n):
            for _try in range(max_redraws):
                (w, h), (cx, cy) = rng.choice(wh), rng.choice(xy)
                box = (_clamp(cx - w / 2), _clamp(cy - h / 2), _clamp(cx + w / 2), _clamp(cy + h / 2))
                if box[2] - box[0] < 1 or box[3] - box[1] < 1:
                    continue
                if all(_iou(box, lab) <= cfg["rules"]["fp_max_iou_with_label"]
                       for lab in out.boxes):
                    out.boxes.append(box)
                    out.added += 1
                    break
            else:
                out.failed += 1
    else:  # loc
        lo, hi = cfg["rules"]["loc_iou_range"]
        boxes = list(labels)
        for i, b in enumerate(labels):
            w, h = b[2] - b[0], b[3] - b[1]
            s = stratum(max(w, h), scene, cuts)
            if w < 1 or h < 1 or rng.random() >= cfg["loc_rate"][s] or not cfg["loc_samples"]:
                continue
            for _try in range(max_redraws):
                dcx, dcy, dlw, dlh = rng.choice(cfg["loc_samples"])
                cx, cy = (b[0] + b[2]) / 2 + dcx * w, (b[1] + b[3]) / 2 + dcy * h
                nw, nh = w * math.exp(dlw), h * math.exp(dlh)
                cand = (_clamp(cx - nw / 2), _clamp(cy - nh / 2), _clamp(cx + nw / 2), _clamp(cy + nh / 2))
                if cand[2] > cand[0] and cand[3] > cand[1] and lo <= _iou(cand, b) < hi:
                    boxes[i] = cand
                    out.changed.append(i)
                    out.strata.append(s)
                    break
            else:
                out.failed += 1
        out.boxes = boxes
    return out


def check_injection(kind: str, inj: Injection, labels: list) -> list[str]:
    """Problems that show the injection made something other than kind `kind` (empty = fine).

    Matches the injected list back to the labels (IoU 0.5) and counts the three error types."""
    err = error_types(match_boxes(inj.boxes, labels))
    counts = {"miss": len(err.miss), "fp": len(err.fp), "loc": len(err.loc)}
    problems = [f"unexpected {k} errors: {n}" for k, n in counts.items() if k != kind and n]
    expect = {"miss": len(inj.changed), "fp": inj.added, "loc": len(inj.changed)}[kind]
    if counts[kind] != expect:
        problems.append(f"{kind} errors {counts[kind]} != injected {expect}")
    return problems


def size_bin_of(box, cuts) -> str:
    return size_bin(max(box[2] - box[0], box[3] - box[1]), cuts)

"""Detection metrics: AP50 and precision/recall/F1 at a score threshold, threshold search."""

import numpy as np

from sarqa.detector.match import iou_matrix, match_boxes

# preds: image -> (boxes[N,4], scores[N]); gts: image -> boxes[M,4]


def ap50(preds: dict, gts: dict, iou_thr: float = 0.5) -> float:
    """COCO-style AP at one IoU: detections ranked by score over all images, each matched to the
    best still-unmatched label box in its image; all-point interpolated precision."""
    n_gt = sum(len(v) for v in gts.values())
    if n_gt == 0:
        return 0.0
    entries = [(float(s), img, k) for img, (b, sc) in preds.items() for k, s in enumerate(sc)]
    entries.sort(key=lambda t: -t[0])
    ious = {img: iou_matrix(preds[img][0], gts.get(img, [])) for img in preds}
    used = {img: np.zeros(len(gts.get(img, [])), dtype=bool) for img in preds}
    tp = np.zeros(len(entries))
    for r, (_, img, k) in enumerate(entries):
        row = ious[img][k] if ious[img].size else np.zeros(0)
        if row.size:
            cand = np.where(~used[img], row, -1.0)
            j = int(cand.argmax())
            if cand[j] >= iou_thr:
                used[img][j] = True
                tp[r] = 1
    ctp, cfp = np.cumsum(tp), np.cumsum(1 - tp)
    rec = ctp / n_gt
    prec = ctp / np.maximum(ctp + cfp, 1e-12)
    mrec = np.concatenate([[0.0], rec, [1.0]])
    mpre = np.concatenate([[0.0], prec, [0.0]])
    mpre = np.maximum.accumulate(mpre[::-1])[::-1]
    idx = np.where(mrec[1:] != mrec[:-1])[0]
    return float(np.sum((mrec[idx + 1] - mrec[idx]) * mpre[idx + 1]))


def prf(preds: dict, gts: dict, threshold: float, iou_thr: float = 0.5) -> dict:
    """Precision/recall/F1 keeping detections with score >= threshold (§8.1 greedy matching)."""
    tp = fp = fn = 0
    for img, g in gts.items():
        boxes, scores = preds.get(img, (np.zeros((0, 4)), np.zeros(0)))
        keep = np.asarray(scores) >= threshold
        m = match_boxes(np.asarray(boxes).reshape(-1, 4)[keep], g, iou_thr)
        tp += len(m.pairs)
        fp += len(m.unmatched_dets)
        fn += len(m.unmatched_labels)
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * p * r / (p + r) if p + r else 0.0
    return {"threshold": float(threshold), "tp": tp, "fp": fp, "fn": fn,
            "precision": p, "recall": r, "f1": f1}


def best_f1_threshold(preds: dict, gts: dict, grid=None) -> dict:
    """Threshold with the highest F1 (ties: the higher threshold)."""
    if grid is None:
        grid = np.round(np.arange(0.05, 1.0, 0.01), 2)  # 0.05..0.99: scores saturate near 1
    best = None
    for t in grid:
        r = prf(preds, gts, float(t))
        if best is None or r["f1"] >= best["f1"]:
            best = r
    return best

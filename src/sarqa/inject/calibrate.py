"""Calibration of the injection from the detector's errors on the **dev** images (SPEC §8.2).

Everything is measured, not chosen: real detector errors concentrate on small ships and on inshore
scenes, so rates are per stratum = ship size bin x inshore/offshore. Size bins are terciles of the
dev label boxes' longer side. Output: `configs/injection.yaml` (frozen with the code at freeze-v1).

  miss  per-label-box probability = dev miss rate of its stratum
  fp    per image: as many as the miss injection is expected to remove (`fp_count_rule:
        expected_miss`; `fp_counts` keeps the dev detector's own counts for reference); size (w, h)
        and centre (x, y) from the empirical false-positive boxes of the scene
  loc   per matched box: probability = dev share of IoU < 0.75 among matched pairs of its stratum;
        the perturbation is a whole empirical tuple (dcx/w, dcy/h, log w ratio, log h ratio)
"""

import math
from collections import defaultdict

import numpy as np
import yaml

from sarqa.boxes import detected_provider, label_provider
from sarqa.config import load_config, repo_path
from sarqa.detector.match import error_types, match_boxes

SIZE_BINS = ("small", "mid", "large")
SCENES = ("inshore", "offshore")
MIN_STRATUM = 20   # fewer label boxes than this -> the stratum falls back to its size bin, then to all


def size_bin(long_side: float, cuts: list[float]) -> str:
    return SIZE_BINS[0] if long_side <= cuts[0] else SIZE_BINS[1] if long_side <= cuts[1] else SIZE_BINS[2]


def stratum(long_side: float, scene: str, cuts: list[float]) -> str:
    return f"{size_bin(long_side, cuts)}|{scene}"


def _xyxy(boxes):
    return [(b.x1, b.y1, b.x2, b.y2) for b in boxes]


def _rate(hits: int, n: int) -> float:
    return round(hits / n, 6) if n else 0.0


def calibrate(split: str = "dev") -> dict:
    """Measure the detector's errors on `split` (dev only) and return the injection settings."""
    if split != "dev":
        raise ValueError("the injection is calibrated on dev images only (SPEC §8.2)")
    from sarqa.questions.generate import load_splits
    from sarqa.tools import default_context

    labels, det, scenes = label_provider(), detected_provider(split), default_context().scenes
    splits = load_splits()
    images = sorted(n for n, m in splits["images"].items() if m["split"] == split and n in det)

    lengths = sorted(b.long_side for n in images for b in labels.boxes(n))
    cuts = [float(np.percentile(lengths, 100 / 3)), float(np.percentile(lengths, 200 / 3))]

    labels_n, misses = defaultdict(int), defaultdict(int)
    matched_n, locs = defaultdict(int), defaultdict(int)
    fp_counts = {s: [] for s in SCENES}
    fp_wh = {s: [] for s in SCENES}
    fp_xy = {s: [] for s in SCENES}
    loc_samples = []
    n_dets = 0
    for name in images:
        lab, dt = labels.boxes(name), det.boxes(name)
        scene = scenes[name]
        m = match_boxes(_xyxy(dt), _xyxy(lab))
        err = error_types(m)
        n_dets += len(dt)
        for i, b in enumerate(lab):
            labels_n[stratum(b.long_side, scene, cuts)] += 1
        for j in err.miss:
            misses[stratum(lab[j].long_side, scene, cuts)] += 1
        for d, j, iou in m.pairs:
            matched_n[stratum(lab[j].long_side, scene, cuts)] += 1
        for d, j, iou in err.loc:
            L, D = lab[j], dt[d]
            locs[stratum(L.long_side, scene, cuts)] += 1
            w, h = L.x2 - L.x1, L.y2 - L.y1
            dw, dh = D.x2 - D.x1, D.y2 - D.y1
            if min(w, h, dw, dh) > 0:
                loc_samples.append([round((D.cx - L.cx) / w, 4), round((D.cy - L.cy) / h, 4),
                                    round(math.log(dw / w), 4), round(math.log(dh / h), 4)])
        fp_counts[scene].append(len(err.fp))
        for d in err.fp:
            D = dt[d]
            fp_wh[scene].append([D.x2 - D.x1, D.y2 - D.y1])
            fp_xy[scene].append([round(D.cx, 1), round(D.cy, 1)])

    def pooled(counter_hits, counter_n, key):
        n, h = counter_n[key], counter_hits[key]
        if n >= MIN_STRATUM:
            return h, n, "stratum"
        sb = key.split("|")[0]
        n2 = sum(v for k, v in counter_n.items() if k.startswith(sb + "|"))
        h2 = sum(v for k, v in counter_hits.items() if k.startswith(sb + "|"))
        if n2 >= MIN_STRATUM:
            return h2, n2, "size_bin"
        return sum(counter_hits.values()), sum(counter_n.values()), "all"

    strata = [f"{b}|{s}" for b in SIZE_BINS for s in SCENES]
    miss_rate, loc_rate, basis = {}, {}, {}
    for k in strata:
        h, n, how = pooled(misses, labels_n, k)
        miss_rate[k] = _rate(h, n)
        h, n, how2 = pooled(locs, matched_n, k)
        loc_rate[k] = _rate(h, n)
        basis[k] = {"miss": how, "loc": how2, "n_labels": labels_n[k], "n_matched": matched_n[k]}
    for s in SCENES:  # a scene without any false positive borrows the other scene's boxes
        if not fp_wh[s]:
            other = SCENES[1 - SCENES.index(s)]
            fp_wh[s], fp_xy[s] = fp_wh[other], fp_xy[other]
    return {
        "calibrated_on": split, "n_images": len(images), "n_label_boxes": sum(labels_n.values()),
        "n_detections": n_dets, "size_cuts_long_side_px": [round(c, 2) for c in cuts],
        "size_bins": list(SIZE_BINS), "strata_basis": basis,
        "miss_rate": miss_rate, "loc_rate": loc_rate,
        "fp_counts": fp_counts, "fp_wh": fp_wh, "fp_xy": fp_xy, "loc_samples": loc_samples,
        "dev_totals": {"miss": sum(misses.values()), "fp": sum(sum(v) for v in fp_counts.values()),
                       "loc": sum(locs.values()), "matched": sum(matched_n.values())},
        "fp_count_rule": "expected_miss",   # not the detector's own rate: see docs/deviations.md (2026-09-30)
        "rules": {"fp_max_iou_with_label": 0.1, "loc_iou_range": [0.5, 0.75], "max_redraws": 50},
    }


def write_injection_yaml(cfg: dict, path=None) -> None:
    path = path or repo_path("configs/injection.yaml")
    header = ("# Injection settings measured from the detector's errors on dev images (SPEC §8.2).\n"
              "# Written by `sarqa inject calibrate`; frozen at freeze-v1.\n")
    with open(path, "w", encoding="utf-8") as f:
        f.write(header)
        yaml.safe_dump(cfg, f, sort_keys=False, allow_unicode=True, default_flow_style=None, width=100)


def load_injection() -> dict:
    return load_config("injection")

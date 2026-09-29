"""Inference cache, score threshold from det_val F1, and outputs/detector_report.json (SPEC §4.3).

The threshold is chosen on det_val only; dev and test are cached at that threshold and test
numbers are reported but never used to tune anything.
"""

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

import torch
from torch.utils.data import DataLoader

from sarqa.config import CONFIG_DIR, REPO_ROOT, load_config, repo_path
from sarqa.detector.dataset import HRSIDDetection, collate, load_split
from sarqa.detector.match import classify_detections
from sarqa.detector.metrics import ap50, best_f1_threshold, prf
from sarqa.detector.model import build_model, predict

SPLITS = ("det_val", "dev", "test")


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run_split(model, split, device, cfg, limit):
    names, boxes = load_split(split, limit)
    ds = HRSIDDetection(names, boxes, train=False)
    loader = DataLoader(ds, batch_size=8, shuffle=False, num_workers=cfg["num_workers"],
                        collate_fn=collate, pin_memory=True)
    return predict(model, loader, device, cfg["amp"]), boxes


def apply_threshold(preds: dict, threshold: float) -> dict:
    out = {}
    for n, (b, s) in preds.items():
        keep = s >= threshold
        out[n] = (b[keep], s[keep])
    return out


def error_summary(preds: dict, gts: dict, tags: dict) -> dict:
    """Miss/fp/loc counts (SPEC §8.1) overall and by inshore/offshore tag."""
    def blank():
        return {"images": 0, "labels": 0, "detections": 0, "miss": 0, "fp": 0, "loc": 0}

    total, by_tag = blank(), {"inshore": blank(), "offshore": blank()}
    for n, g in gts.items():
        e = classify_detections(preds[n][0], g)
        for acc in (total, by_tag[tags[n]]):
            acc["images"] += 1
            acc["labels"] += len(g)
            acc["detections"] += len(preds[n][0])
            acc["miss"] += len(e.miss)
            acc["fp"] += len(e.fp)
            acc["loc"] += len(e.loc)
    for acc in (total, *by_tag.values()):
        acc["miss_rate"] = acc["miss"] / acc["labels"] if acc["labels"] else 0.0
        acc["fp_per_image"] = acc["fp"] / acc["images"] if acc["images"] else 0.0
        acc["loc_rate"] = acc["loc"] / acc["labels"] if acc["labels"] else 0.0
    return {"overall": total, **by_tag}


def write_cache(preds: dict, path: Path, meta: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    images = {n: [[round(float(v), 2) for v in b] + [round(float(s), 4)]
                  for b, s in zip(bs, ss, strict=True)] for n, (bs, ss) in sorted(preds.items())}
    path.write_text(json.dumps({"meta": meta, "images": images}), encoding="utf-8")


def set_threshold_in_config(value: float, force: bool) -> None:
    path = CONFIG_DIR / "default.yaml"
    text = path.read_text(encoding="utf-8")
    m = re.search(r"^(\s*score_threshold:\s*)(\S+)", text, flags=re.MULTILINE)
    if m is None:
        raise RuntimeError("score_threshold key not found in configs/default.yaml")
    if m.group(2) not in ("null", "~") and float(m.group(2)) != value and not force:
        raise SystemExit(f"score_threshold already fixed at {m.group(2)}; use --force to change")
    path.write_text(text[:m.start(2)] + f"{value:g}" + text[m.end(2):], encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    cfg_all = load_config()
    dcfg, paths = cfg_all["detector"], cfg_all["paths"]
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--weights", default=str(Path(paths["detector_dir"]) / "weights.pt"))
    p.add_argument("--det-dir", default=paths["detections_dir"])
    p.add_argument("--report", default=paths["detector_report"])
    p.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    p.add_argument("--max-images", type=int, default=0, help="per split (smoke tests)")
    p.add_argument("--no-config-write", action="store_true")
    p.add_argument("--force", action="store_true", help="overwrite an already fixed threshold")
    args = p.parse_args(argv)

    device = torch.device(args.device)
    weights = repo_path(args.weights)
    ck = torch.load(weights, map_location=device, weights_only=False)
    model = build_model(dcfg, pretrained=False)
    model.load_state_dict(ck["model"])
    model.to(device)

    raw, gts = {}, {}
    for split in SPLITS:
        raw[split], gts[split] = run_split(model, split, device, dcfg, args.max_images or None)
    best = best_f1_threshold(raw["det_val"], gts["det_val"])
    thr = best["threshold"]

    splits_path = repo_path(paths["splits"])
    with open(splits_path, encoding="utf-8") as f:
        tags = {n: m["tag"] for n, m in json.load(f)["images"].items()}
    meta = {"weights_sha256": sha256(weights), "score_threshold": thr, "nms_iou": dcfg["nms_iou"],
            "splits_sha256": sha256(splits_path)}
    det_dir = repo_path(args.det_dir)
    write_cache(raw["det_val"], det_dir / "det_val_raw.json", {**meta, "note": "score >= raw_score_thresh"})
    report = {"weights": str(args.weights), "weights_sha256": meta["weights_sha256"],
              "best_epoch": ck.get("epoch"), "ap50_det_val_at_best_epoch": ck.get("ap50_det_val"),
              "score_threshold": thr, "threshold_rule": "max F1 on det_val (IoU 0.5), ties -> higher",
              "nms_iou": dcfg["nms_iou"], "raw_score_thresh": dcfg["raw_score_thresh"],
              "splits_sha256": meta["splits_sha256"],
              "git": subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True,
                                    capture_output=True, check=False).stdout.strip(),
              "note": "Splits are scene-grouped, so numbers are not comparable to the HRSID paper. "
                      "Test numbers are reported only; nothing was tuned on test.",
              "splits": {}}
    for split in SPLITS:
        kept = apply_threshold(raw[split], thr)
        if split != "det_val":
            write_cache(kept, det_dir / f"{split}.json", {**meta, "split": split})
        report["splits"][split] = {
            "images": len(gts[split]), "labels": int(sum(len(g) for g in gts[split].values())),
            "ap50": ap50(raw[split], gts[split]), "at_threshold": prf(raw[split], gts[split], thr),
            "errors": error_summary(kept, gts[split], tags)}
    rp = repo_path(args.report)
    rp.parent.mkdir(parents=True, exist_ok=True)
    rp.write_text(json.dumps(report, indent=1), encoding="utf-8")
    if not args.no_config_write:
        set_threshold_in_config(thr, args.force)
    t = report["splits"]["test"]
    print(f"threshold {thr:.2f} | det_val F1 {best['f1']:.3f} | test AP50 {t['ap50']:.3f} "
          f"P {t['at_threshold']['precision']:.3f} R {t['at_threshold']['recall']:.3f} -> {rp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

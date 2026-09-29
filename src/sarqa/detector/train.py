"""Fine-tune Faster R-CNN on det_train with det_val AP50 logging and epoch-level resume.

Run (resumes automatically from <out>/last.pt if present):
    python -m sarqa.detector.train --out outputs/detector
"""

import argparse
import hashlib
import json
import logging
import math
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

import torch
from torch.utils.data import DataLoader

from sarqa.config import REPO_ROOT, load_config, repo_path
from sarqa.detector.dataset import HRSIDDetection, collate, load_split
from sarqa.detector.metrics import ap50, prf
from sarqa.detector.model import build_model, predict

log = logging.getLogger("sarqa.detector.train")


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def atomic_save(obj, path: Path) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    torch.save(obj, tmp)
    os.replace(tmp, path)


def lr_factor(it: int, warmup: int, total: int) -> float:
    if it < warmup:
        return 0.001 + (1 - 0.001) * it / warmup
    return 0.5 * (1 + math.cos(math.pi * (it - warmup) / max(1, total - warmup)))


def setup_logging(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    for h in (logging.FileHandler(out / "train.log"), logging.StreamHandler(sys.stdout)):
        h.setFormatter(fmt)
        logging.getLogger().addHandler(h)
    logging.getLogger().setLevel(logging.INFO)


def train(args) -> int:
    cfg_all = load_config()
    cfg = dict(cfg_all["detector"])
    if args.epochs:
        cfg["epochs"] = args.epochs
    out = Path(args.out)
    setup_logging(out)
    device = torch.device(args.device)
    seed = cfg_all["seed"]
    torch.manual_seed(seed)

    done = out / "done.json"
    if done.exists() and not args.no_resume:
        if json.loads(done.read_text(encoding="utf-8"))["epochs"] == cfg["epochs"]:
            log.info("done.json exists in %s: training already finished", out)
            return 0
        done.unlink()  # the epoch budget changed: continue from last.pt

    tr_names, tr_boxes = load_split("det_train", args.max_train_images)
    va_names, va_boxes = load_split("det_val", args.max_val_images)
    train_ds = HRSIDDetection(tr_names, tr_boxes, train=True)
    val_ds = HRSIDDetection(va_names, va_boxes, train=False)
    val_loader = DataLoader(val_ds, batch_size=8, shuffle=False, num_workers=cfg["num_workers"],
                            collate_fn=collate, pin_memory=True)

    model = build_model(cfg, pretrained=True).to(device)
    params = [p for p in model.parameters() if p.requires_grad]
    opt = torch.optim.SGD(params, lr=cfg["lr"], momentum=cfg["momentum"],
                          weight_decay=cfg["weight_decay"])
    iters_per_epoch = math.ceil(len(train_ds) / cfg["batch_size"])
    total_iters = cfg["epochs"] * iters_per_epoch
    sched = torch.optim.lr_scheduler.LambdaLR(
        opt, lambda it: lr_factor(it, cfg["warmup_iters"], total_iters))
    scaler = torch.amp.GradScaler("cuda", enabled=cfg["amp"] and device.type == "cuda")

    state = {"epoch": 0, "best_ap50": -1.0, "best_epoch": 0, "history": []}
    last = out / "last.pt"
    if last.exists() and not args.no_resume:
        ck = torch.load(last, map_location=device, weights_only=False)
        model.load_state_dict(ck["model"])
        opt.load_state_dict(ck["optimizer"])
        sched.load_state_dict(ck["scheduler"])
        scaler.load_state_dict(ck["scaler"])
        state = {k: ck[k] for k in state}
        log.info("resumed from %s after epoch %d (best AP50 %.4f @ epoch %d)", last,
                 state["epoch"], state["best_ap50"], state["best_epoch"])
    else:
        meta = {"command": sys.argv, "git": git_commit(), "config": cfg, "seed": seed,
                "splits_sha256": sha256(repo_path(cfg_all["paths"]["splits"])),
                "n_train": len(train_ds), "n_val": len(val_ds), "torch": torch.__version__,
                "cuda": torch.version.cuda, "python": platform.python_version(),
                "gpu": torch.cuda.get_device_name(0) if device.type == "cuda" else "cpu"}
        (out / "run_meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
        log.info("start: %d train / %d val images, %d iters per epoch", len(train_ds), len(val_ds),
                 iters_per_epoch)

    gts = va_boxes
    bad_steps = 0
    for epoch in range(state["epoch"], cfg["epochs"]):
        model.train()
        g = torch.Generator()
        g.manual_seed(seed + epoch)
        loader = DataLoader(train_ds, batch_size=cfg["batch_size"], shuffle=True, generator=g,
                            num_workers=cfg["num_workers"], collate_fn=collate, pin_memory=True,
                            drop_last=False)
        t0, sums, n = time.time(), {}, 0
        for i, (imgs, targets, _) in enumerate(loader):
            imgs = [x.to(device, non_blocking=True) for x in imgs]
            targets = [{k: v.to(device) for k, v in t.items()} for t in targets]
            with torch.autocast(device_type=device.type, enabled=cfg["amp"] and device.type == "cuda"):
                losses = model(imgs, targets)
                loss = sum(losses.values())
            if not torch.isfinite(loss):
                bad_steps += 1
                log.warning("non-finite loss at epoch %d iter %d (%d in a row)", epoch + 1, i, bad_steps)
                if bad_steps > 20:
                    raise RuntimeError("loss stayed non-finite for 20 consecutive steps")
                opt.zero_grad(set_to_none=True)
                sched.step()
                continue
            bad_steps = 0
            opt.zero_grad(set_to_none=True)
            scaler.scale(loss).backward()
            scaler.unscale_(opt)
            torch.nn.utils.clip_grad_norm_(params, cfg["grad_clip"])
            scaler.step(opt)
            scaler.update()
            sched.step()
            for k, v in losses.items():
                sums[k] = sums.get(k, 0.0) + v.item()
            n += 1
            if (i + 1) % 50 == 0 or i + 1 == iters_per_epoch:
                el = time.time() - t0
                log.info("epoch %d/%d iter %d/%d loss %.4f lr %.5f %.2f it/s eta_epoch %ds",
                         epoch + 1, cfg["epochs"], i + 1, iters_per_epoch, loss.item(),
                         opt.param_groups[0]["lr"], (i + 1) / el,
                         int(el / (i + 1) * (iters_per_epoch - i - 1)))
        train_s = time.time() - t0
        preds = predict(model, val_loader, device, cfg["amp"])
        ap = ap50(preds, gts)
        at05 = prf(preds, gts, 0.5)
        rec = {"epoch": epoch + 1, "ap50": ap, "precision@0.5": at05["precision"],
               "recall@0.5": at05["recall"], "train_seconds": round(train_s, 1),
               "loss": {k: v / max(n, 1) for k, v in sums.items()}, "lr": opt.param_groups[0]["lr"]}
        state["history"].append(rec)
        if ap > state["best_ap50"]:
            state["best_ap50"], state["best_epoch"] = ap, epoch + 1
            atomic_save({"model": model.state_dict(), "epoch": epoch + 1, "ap50_det_val": ap,
                         "config": cfg}, out / "weights.pt")
            log.info("new best det_val AP50 %.4f at epoch %d -> weights.pt", ap, epoch + 1)
        state["epoch"] = epoch + 1
        atomic_save({"model": model.state_dict(), "optimizer": opt.state_dict(),
                     "scheduler": sched.state_dict(), "scaler": scaler.state_dict(), **state}, last)
        with open(out / "metrics.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
        log.info("epoch %d done: det_val AP50 %.4f (best %.4f @ %d) P@0.5 %.3f R@0.5 %.3f",
                 epoch + 1, ap, state["best_ap50"], state["best_epoch"], at05["precision"],
                 at05["recall"])

    (out / "done.json").write_text(json.dumps(
        {"best_epoch": state["best_epoch"], "best_ap50_det_val": state["best_ap50"],
         "weights_sha256": sha256(out / "weights.pt"), "epochs": cfg["epochs"]}, indent=1),
        encoding="utf-8")
    log.info("finished: best det_val AP50 %.4f at epoch %d", state["best_ap50"], state["best_epoch"])
    return 0


def add_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--out", default=load_config()["paths"]["detector_dir"])
    p.add_argument("--epochs", type=int, default=0, help="override config (smoke tests)")
    p.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    p.add_argument("--max-train-images", type=int, default=0)
    p.add_argument("--max-val-images", type=int, default=0)
    p.add_argument("--no-resume", action="store_true", help="ignore last.pt / done.json")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    add_args(p)
    return train(p.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())

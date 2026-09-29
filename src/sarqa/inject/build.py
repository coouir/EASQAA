"""Build the injected and corrected box files of a split and the per-question reference answers.

For every image that carries a question: `data/injected/<split>_<kind>.json` (label + one error kind,
seeded by (image, kind)) and `data/corrected/<split>_<kind>.json` (detection with one kind fixed).
The question file gets `reference_answers` (gold program run on detected / injected / corrected
boxes) and `answer_changed` (injected answer differs from the gold answer, SPEC §8.2).
"""

import hashlib
import json
from pathlib import Path

from sarqa.boxes import detected_provider, file_provider, label_provider
from sarqa.config import load_config, repo_path
from sarqa.grading import value_matches
from sarqa.inject.calibrate import load_injection
from sarqa.inject.correct import correct
from sarqa.inject.inject import KINDS, check_injection, inject
from sarqa.program import run_program

MAX_ATTEMPTS = 10


def _tuples(boxes):
    return [(b.x1, b.y1, b.x2, b.y2) for b in boxes]


def file_paths(split: str, kind: str) -> dict[str, Path]:
    return {"injected": repo_path(f"data/injected/{split}_{kind}.json"),
            "corrected": repo_path(f"data/corrected/{split}_{kind}.json")}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_boxes(split: str, images: list[str], scenes: dict, seed: int | None = None) -> dict:
    """Write the six box files of `split`; returns a summary (per kind counts) for PROTOCOL.md."""
    cfg = load_injection()
    seed = load_config()["seed"] if seed is None else seed
    labels, det = label_provider(), detected_provider(split)
    summary = {}
    inj_tables = {k: {} for k in KINDS}
    cor_tables = {k: {} for k in KINDS}
    stats = {k: {"images": 0, "changed": 0, "added": 0, "failed": 0, "attempts_gt1": 0,
                 "check_failures": []} for k in KINDS}
    for name in images:
        lab = _tuples(labels.boxes(name))
        dt = _tuples(det.boxes(name))
        for kind in KINDS:
            for attempt in range(MAX_ATTEMPTS):
                inj = inject(kind, name, lab, scenes[name], cfg, seed + attempt)
                problems = check_injection(kind, inj, lab)
                if not problems:
                    break
            s = stats[kind]
            s["images"] += 1
            s["changed"] += len(inj.changed)
            s["added"] += inj.added
            s["failed"] += inj.failed
            s["attempts_gt1"] += attempt > 0
            if problems:
                s["check_failures"].append({"image": name, "problems": problems})
            inj_tables[kind][name] = [list(b) for b in inj.boxes]
            cor_tables[kind][name] = [list(b) for b in correct(kind, dt, lab)]
    for kind in KINDS:
        for source, table in (("injected", inj_tables[kind]), ("corrected", cor_tables[kind])):
            path = file_paths(split, kind)[source]
            path.parent.mkdir(parents=True, exist_ok=True)
            meta = {"split": split, "kind": kind, "source": source, "seed": seed,
                    "n_images": len(table), "injection_yaml_sha256": sha256(repo_path("configs/injection.yaml"))}
            path.write_text(json.dumps({"meta": meta, "images": table}, separators=(",", ":")),
                            encoding="utf-8")
        s = stats[kind]
        s["mean_per_image"] = round((s["changed"] + s["added"]) / max(1, s["images"]), 4)
        summary[kind] = s
    return summary


def providers(split: str) -> dict:
    """detected + injected(kind) + corrected(kind) providers of a split (files must exist)."""
    out = {"detected": detected_provider(split)}
    for kind in KINDS:
        paths = file_paths(split, kind)
        out[f"injected_{kind}"] = file_provider("injected", paths["injected"])
        out[f"corrected_{kind}"] = file_provider("corrected", paths["corrected"])
    return out


def add_reference_answers(questions: list[dict], ctx, split: str) -> None:
    """Fill `reference_answers` and `answer_changed` of every question, in place."""
    provs = providers(split)
    for q in questions:
        refs, changed = {}, {}
        for name, prov in provs.items():
            res = run_program(q["program"], q["image_id"], prov, ctx=ctx)
            refs[name] = res.answer if res.ok else None
            if name.startswith("injected_"):
                changed[name.removeprefix("injected_")] = not (
                    res.ok and value_matches(res.answer, q["gold_answer"], q["answer_type"]))
        q["reference_answers"] = refs
        q["answer_changed"] = changed

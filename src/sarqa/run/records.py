"""Run records (SPEC §10.2): one JSON line per run. The agent fills the interaction part; the runner
adds identity, the box provenance, the reachable answer and the run metadata."""

import hashlib
import json
import subprocess
from pathlib import Path

from sarqa.agents.common import FAIL_KINDS, prompt_hashes
from sarqa.config import REPO_ROOT, load_config
from sarqa.program import run_program

STATUSES = ("ok", "exec_fail")
REQUIRED = ("run_id", "condition", "method", "input", "qid", "level", "repeat", "seed", "status",
            "fail_kind", "error_detail", "answer_raw", "answer", "correct", "answer_format_ok",
            "unit_only_fix", "reachable_answer", "interpretation", "turns", "decisions", "tool_calls",
            "llm_calls", "tokens_in", "tokens_out", "wall_ms", "boxes_hash", "budget", "over_budget",
            "meta")
META_KEYS = ("git", "model_digest", "prompt_hashes", "config_hash", "data_hash", "ollama_version")


def run_id(condition: int, qid: str, repeat: int) -> str:
    return hashlib.sha256(f"{condition}|{qid}|{repeat}".encode()).hexdigest()[:16]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def boxes_hash(provider, image_id: str) -> str:
    rows = [(b.x1, b.y1, b.x2, b.y2) for b in provider.boxes(image_id)]
    return hashlib.sha256(json.dumps(rows).encode()).hexdigest()[:16]


def reachable_answer(question: dict, provider, ctx):
    """Gold program on the boxes the run actually received (`gold_answer` if boxes do not matter)."""
    if not question["box_dependent"]:
        return question["gold_answer"]
    res = run_program(question["program"], question["image_id"], provider, ctx=ctx)
    return res.answer if res.ok else None


def git_commit() -> str:
    out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True, check=False)
    return out.stdout.strip() or "unknown"


def config_hash() -> str:
    blob = "".join((REPO_ROOT / "configs" / f"{n}.yaml").read_text(encoding="utf-8")
                   for n in ("default", "classify", "conditions", "injection")
                   if (REPO_ROOT / "configs" / f"{n}.yaml").exists())
    return hashlib.sha256(blob.encode()).hexdigest()


def data_files(split: str) -> list[Path]:
    cfg = load_config()
    files = [REPO_ROOT / cfg["paths"]["splits"], REPO_ROOT / cfg["paths"]["scenes"],
             REPO_ROOT / "data" / "detections" / f"{split}.json",
             REPO_ROOT / "data" / "questions" / f"{split}.json"]
    for kind in ("miss", "fp", "loc"):
        files += [REPO_ROOT / "data" / "injected" / f"{split}_{kind}.json",
                  REPO_ROOT / "data" / "corrected" / f"{split}_{kind}.json"]
    return [f for f in files if f.exists()]


def data_hash(split: str) -> str:
    h = hashlib.sha256()
    for f in data_files(split):
        h.update(f"{f.relative_to(REPO_ROOT)}={sha256_file(f)}\n".encode())
    return h.hexdigest()


def run_meta(split: str, llm_info: dict) -> dict:
    """Metadata shared by every record of one runner start (computed once)."""
    return {"git": git_commit(), "model_digest": llm_info.get("model_digest"),
            "prompt_hashes": prompt_hashes(), "config_hash": config_hash(),
            "data_hash": data_hash(split), "ollama_version": llm_info.get("ollama_version")}


def validate_record(rec: dict) -> list[str]:
    """Schema problems of a record (empty = passes)."""
    problems = [f"missing {k}" for k in REQUIRED if k not in rec]
    if problems:
        return problems
    if rec["status"] not in STATUSES:
        problems.append(f"status {rec['status']!r}")
    if rec["status"] == "ok":
        if rec["fail_kind"] is not None or rec["answer"] is None:
            problems.append("ok record needs an answer and no fail_kind")
    else:
        if rec["fail_kind"] not in FAIL_KINDS:
            problems.append(f"fail_kind {rec['fail_kind']!r}")
        if rec["correct"]:
            problems.append("a run without an answer cannot be correct")
    if not isinstance(rec["turns"], list) or not isinstance(rec["decisions"], list):
        problems.append("turns and decisions must be lists")
    problems += [f"meta lacks {k}" for k in META_KEYS if k not in rec["meta"]]
    return problems


def failure_record(question: dict, cond, seed: int, detail: str, meta: dict) -> dict:
    """A record for a run whose agent code raised (`runner_exception`, SPEC §10.1)."""
    return {"run_id": run_id(cond.id, question["qid"], cond.repeat), "condition": cond.id,
            "method": cond.method, "input": cond.input, "qid": question["qid"],
            "level": question["level"], "repeat": cond.repeat, "seed": seed, "status": "exec_fail",
            "fail_kind": "runner_exception", "error_detail": detail[:2000], "answer_raw": None,
            "answer": None, "correct": False, "answer_format_ok": False, "unit_only_fix": False,
            "reachable_answer": None, "interpretation": None, "turns": [], "decisions": [],
            "tool_calls": 0, "llm_calls": 0, "tokens_in": 0, "tokens_out": 0, "wall_ms": 0,
            "boxes_hash": None, "budget": question["budget"], "over_budget": False, "meta": meta}

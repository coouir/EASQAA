"""Experiment runner (SPEC §10.1): resume, mixed order, never stops on a failing run.

    sarqa run --conditions all --split test --out outputs/runs/

`run_id = hash(condition, qid, repeat)`; ids already in the output files are skipped, so a killed
run continues where it stopped without duplicates. Order: priority groups of SPEC §9 in order;
inside a group question by question with the conditions of that question together (so drift in model
state or server load does not pile up on one condition). Any exception inside a run becomes a
`runner_exception` record. GPU work is serial. Test-split runs must pass the freeze guard first.
"""

import json
import time
import traceback
from collections import defaultdict
from pathlib import Path

from sarqa.agents import run_agent
from sarqa.agents.llm import LLMError, seed_for
from sarqa.config import REPO_ROOT, load_config
from sarqa.questions.slots import rng_for
from sarqa.run import records as R
from sarqa.run.conditions import (
    Condition,
    ProviderPool,
    load_conditions,
    priority_groups,
)
from sarqa.run.freeze import check_freeze
from sarqa.tools import default_context


class FreezeGuardError(RuntimeError):
    pass


def plan(questions: list[dict], selection: list[int], seed: int) -> list[tuple[dict, Condition]]:
    """Runs in execution order (priority groups first, questions shuffled within a group)."""
    conds = load_conditions()
    out = []
    for gi, group in enumerate(priority_groups()):
        ids = [c for c in group if c in selection]
        if not ids:
            continue
        order = list(questions)
        rng_for(seed, "run-order", gi).shuffle(order)
        out += [(q, conds[c]) for q in order for c in ids]
    return out


def path_of(out_dir: Path, condition: int) -> Path:
    return Path(out_dir) / f"condition_{condition:02d}.jsonl"


def load_records(out_dir: Path) -> list[dict]:
    """Every readable record in `out_dir` (a torn last line is skipped)."""
    recs = []
    for f in sorted(Path(out_dir).glob("condition_*.jsonl")):
        recs += read_file(f)[0]
    return recs


def read_file(path: Path) -> tuple[list[dict], int]:
    """(records, number of unreadable lines) of one JSONL file."""
    recs, torn = [], 0
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            recs.append(json.loads(line))
        except json.JSONDecodeError:
            torn += 1
    return recs, torn


def append_record(path: Path, rec: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    needs_newline = path.exists() and path.stat().st_size > 0 and not path.read_bytes().endswith(b"\n")
    with open(path, "a", encoding="utf-8") as f:
        f.write(("\n" if needs_newline else "") + json.dumps(rec, ensure_ascii=False) + "\n")
        f.flush()


def summarize(recs: list[dict]) -> dict:
    n = len(recs)
    if not n:
        return {"n": 0}
    fails = defaultdict(int)
    for r in recs:
        if r["status"] == "exec_fail":
            fails[r["fail_kind"]] += 1
    return {"n": n, "accuracy": round(sum(r["correct"] for r in recs) / n, 4),
            "fail_rate": round(sum(fails.values()) / n, 4), "fail_kinds": dict(fails),
            "mean_tool_calls": round(sum(r["tool_calls"] for r in recs) / n, 2),
            "mean_llm_calls": round(sum(r["llm_calls"] for r in recs) / n, 2),
            "mean_wall_s": round(sum(r["wall_ms"] for r in recs) / n / 1000, 1),
            "format_error_rate": round(sum(r["fail_kind"] == "format_error" for r in recs) / n, 4)}


def _eta(elapsed: float, done: int, total: int) -> str:
    if not done:
        return "?"
    left = elapsed / done * (total - done)
    return f"{int(left // 3600)}h{int(left % 3600 // 60):02d}m"


def run(selection: list[int], split: str, questions: list[dict], out_dir: str | Path, llm=None, *,
        limit: int | None = None, wall_limit_s: float | None = None, agent=run_agent,
        log=print, ctx=None) -> dict:
    """Run the selected conditions on `questions`; returns `{condition: summary}` of this call."""
    out_dir = Path(out_dir)
    if split == "test":
        problems = check_freeze(REPO_ROOT)
        if problems:
            raise FreezeGuardError("test run refused:\n  " + "\n  ".join(problems))
    if llm is None:
        from sarqa.agents.llm import OllamaClient

        llm = OllamaClient()
    cfg = load_config()
    wall_limit_s = wall_limit_s or cfg["llm"]["wall_limit_s"]
    ctx = ctx or default_context()
    try:
        info = llm.info()
    except LLMError as e:
        info = {"ollama_version": None, "model_digest": None}
        log(f"WARNING: cannot reach the model server ({e}); runs will fail as llm_error")
    meta = R.run_meta(split, info)
    log(f"run start: split={split} conditions={selection} questions={len(questions)} out={out_dir} "
        f"git={meta['git'][:8]} model={info.get('model_digest', '')[:12] if info.get('model_digest') else None}")

    pool = ProviderPool(split)
    done = {r["run_id"] for r in load_records(out_dir)}
    todo = [(q, c) for q, c in plan(questions, selection, cfg["seed"])
            if R.run_id(c.id, q["qid"], c.repeat) not in done]
    if limit is not None:
        todo = todo[:limit]
    per_condition_total = {c: len(questions) for c in selection}
    per_condition_done = defaultdict(int)
    for r in load_records(out_dir):
        per_condition_done[r["condition"]] += 1
    log(f"{len(done)} runs already recorded, {len(todo)} to do")

    t0, fresh = time.monotonic(), defaultdict(list)
    for i, (q, cond) in enumerate(todo, 1):
        seed = seed_for(q["qid"], cond.repeat)
        try:
            provider = pool.get(cond)
            rec = agent(cond.method, q, ctx.with_boxes(provider), llm, repeat=cond.repeat,
                        wall_limit_s=wall_limit_s)
            rec.update({"run_id": R.run_id(cond.id, q["qid"], cond.repeat), "condition": cond.id,
                        "input": cond.input, "boxes_hash": R.boxes_hash(provider, q["image_id"]),
                        "reachable_answer": R.reachable_answer(q, provider, ctx), "meta": meta})
        except Exception:  # noqa: BLE001 - a broken run must not stop the experiment (SPEC §0-6)
            rec = R.failure_record(q, cond, seed, traceback.format_exc(), meta)
        problems = R.validate_record(rec)
        if problems:
            rec["schema_problems"] = problems
        append_record(path_of(out_dir, cond.id), rec)
        fresh[cond.id].append(rec)
        per_condition_done[cond.id] += 1
        log(f"[{i}/{len(todo)}] c{cond.id:02d} {q['qid']} {'OK ' if rec['correct'] else 'BAD'} "
            f"{rec['status']}{'/' + rec['fail_kind'] if rec['fail_kind'] else ''} "
            f"calls={rec['tool_calls']}/{q['gold_calls']} {rec['wall_ms'] / 1000:.1f}s "
            f"ETA {_eta(time.monotonic() - t0, i, len(todo))}")
        if per_condition_done[cond.id] == per_condition_total.get(cond.id):
            log(f"condition {cond.id} finished: {json.dumps(summarize(load_condition(out_dir, cond.id)))}")
    write_manifest(out_dir)
    return {c: summarize(v) for c, v in fresh.items()}


def load_condition(out_dir: Path, condition: int) -> list[dict]:
    return [r for r in load_records(out_dir) if r["condition"] == condition]


def write_manifest(out_dir: str | Path) -> dict:
    """`manifest.json`: file hashes, run counts per condition (SPEC §10.2)."""
    out_dir = Path(out_dir)
    files = {}
    for f in sorted(out_dir.glob("condition_*.jsonl")):
        recs, torn = read_file(f)
        files[f.name] = {"sha256": R.sha256_file(f), "runs": len(recs), "torn_lines": torn,
                         "questions": len({r["qid"] for r in recs}),
                         "duplicates": len(recs) - len({r["run_id"] for r in recs})}
    manifest = {"files": files, "total_runs": sum(v["runs"] for v in files.values())}
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return manifest

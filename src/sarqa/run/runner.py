"""Experiment runner (SPEC §10.1): resume, mixed order, never stops on a failing run.

    sarqa run --conditions all --split test --out outputs/runs/

`run_id = hash(condition, qid, repeat)`; ids already in the output files are skipped, so a killed
run continues where it stopped without duplicates. Order: priority groups of SPEC §9 in order;
inside a group question by question with the conditions of that question together (so drift in model
state or server load does not pile up on one condition). Any exception inside a run becomes a
`runner_exception` record. GPU work is serial. Test-split runs must pass the freeze guard first.
"""

import datetime as dt
import hashlib
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
from sarqa.run.server import ServerWatch
from sarqa.tools import default_context


class FreezeGuardError(RuntimeError):
    pass


def plan(questions: list[dict], selection: list[int], seed: int) -> list[tuple[dict, Condition]]:
    """Runs in execution order: priority groups first; inside a group the questions are shuffled with a fixed
    seed, the conditions of one question stay together and their order is shuffled per question with a fixed
    seed too, so neither a question nor a condition owns a fixed slot in time (SPEC §10.1)."""
    conds = load_conditions()
    out = []
    for gi, group in enumerate(priority_groups()):
        ids = [c for c in group if c in selection]
        if not ids:
            continue
        order = list(questions)
        rng_for(seed, "run-order", gi).shuffle(order)
        for q in order:
            mine = list(ids)
            rng_for(seed, "condition-order", gi, q["qid"]).shuffle(mine)
            out += [(q, conds[c]) for c in mine]
    return out


def order_document(full_plan: list[tuple[dict, Condition]], selection: list[int], seed: int,
                   questions_sha: str) -> dict:
    """The planned order of every run of this invocation (`run_index` = position in this list)."""
    return {"seed": seed, "conditions": selection, "questions_sha256": questions_sha,
            "runs": [{"run_index": i, "qid": q["qid"], "condition": c.id,
                      "run_id": R.run_id(c.id, q["qid"], c.repeat)} for i, (q, c) in enumerate(full_plan)]}


def save_order_file(out_dir: Path, doc: dict) -> Path:
    """`order.json`; a different plan in the same folder (other selection or questions) gets its own file
    `order_<hash>.json`, the earlier one is never overwritten."""
    text = json.dumps(doc, indent=1)
    digest = hashlib.sha256(text.encode()).hexdigest()
    out_dir.mkdir(parents=True, exist_ok=True)
    main = out_dir / "order.json"
    if not main.exists() or main.read_text(encoding="utf-8") == text:
        main.write_text(text, encoding="utf-8")
        return main
    other = out_dir / f"order_{digest[:8]}.json"
    other.write_text(text, encoding="utf-8")
    return other


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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
    full_plan = plan(questions, selection, cfg["seed"])
    questions_sha = hashlib.sha256(json.dumps([q["qid"] for q in questions]).encode()).hexdigest()
    order_path = save_order_file(out_dir, order_document(full_plan, selection, cfg["seed"], questions_sha))
    run_index = {(q["qid"], c.id): i for i, (q, c) in enumerate(full_plan)}
    todo = [(q, c) for q, c in full_plan if R.run_id(c.id, q["qid"], c.repeat) not in done]
    if limit is not None:
        todo = todo[:limit]
    per_condition_total = {c: len(questions) for c in selection}
    per_condition_done = defaultdict(int)
    for r in load_records(out_dir):
        per_condition_done[r["condition"]] += 1
    log(f"{len(done)} runs already recorded, {len(todo)} to do; order file {order_path.name}")
    watch = ServerWatch(getattr(llm, "host", "") or "")
    last_server = watch.identity()
    log(f"Ollama server process: {last_server.as_dict() if last_server else 'unknown (not a local Linux server)'}")

    t0, fresh = time.monotonic(), defaultdict(list)
    for i, (q, cond) in enumerate(todo, 1):
        seed = seed_for(q["qid"], cond.repeat)
        started_at = _now()
        server = watch.identity()
        if server != last_server:
            log(f"WARNING: the Ollama server process changed: {last_server.as_dict() if last_server else None} -> "
                f"{server.as_dict() if server else None}. Same seeds no longer guarantee the same outputs "
                f"(docs/env_notes.md); continuing, no automatic restart.")
            last_server = server
        try:
            provider = pool.get(cond)
            rec = agent(cond.method, q, ctx.with_boxes(provider), llm, repeat=cond.repeat,
                        wall_limit_s=wall_limit_s)
            rec.update({"run_id": R.run_id(cond.id, q["qid"], cond.repeat), "condition": cond.id,
                        "input": cond.input, "boxes_hash": R.boxes_hash(provider, q["image_id"]),
                        "reachable_answer": R.reachable_answer(q, provider, ctx), "meta": meta})
        except Exception:  # noqa: BLE001 - a broken run must not stop the experiment (SPEC §0-6)
            rec = R.failure_record(q, cond, seed, traceback.format_exc(), meta)
        rec.update({"run_index": run_index[(q["qid"], cond.id)], "started_at": started_at,
                    "server": server.as_dict() if server else None})
        problems = R.validate_record(rec)
        if problems:
            rec["schema_problems"] = problems
        append_record(path_of(out_dir, cond.id), rec)
        fresh[cond.id].append(rec)
        per_condition_done[cond.id] += 1
        log(f"[{i}/{len(todo)}] c{cond.id:02d} {q['qid']} {'OK ' if rec['correct'] else 'BAD'} "
            f"{rec['status']}{'/' + rec['fail_kind'] if rec['fail_kind'] else ''} "
            f"calls={rec['tool_calls']}/{q['gold_calls']} {rec['wall_ms'] / 1000:.1f}s "
            f"prompt<={rec.get('prompt_tokens_max', 0)} "
            f"ETA {_eta(time.monotonic() - t0, i, len(todo))}")
        if per_condition_done[cond.id] == per_condition_total.get(cond.id):
            log(f"condition {cond.id} finished: {json.dumps(summarize(load_condition(out_dir, cond.id)))}")
    write_manifest(out_dir)
    return {c: summarize(v) for c, v in fresh.items()}


def load_condition(out_dir: Path, condition: int) -> list[dict]:
    return [r for r in load_records(out_dir) if r["condition"] == condition]


def _servers(out_dir: Path) -> list[dict]:
    """Distinct server processes seen in the records with the run_index range they served."""
    seen: dict[tuple, dict] = {}
    for r in load_records(out_dir):
        srv = r.get("server")
        key = (srv["pid"], srv["started_at"]) if srv else (None, None)
        e = seen.setdefault(key, {"pid": key[0], "started_at": key[1], "runs": 0, "first_run_index": None,
                                  "last_run_index": None})
        e["runs"] += 1
        idx = r.get("run_index")
        if idx is not None:
            e["first_run_index"] = idx if e["first_run_index"] is None else min(e["first_run_index"], idx)
            e["last_run_index"] = idx if e["last_run_index"] is None else max(e["last_run_index"], idx)
    return sorted(seen.values(), key=lambda e: (e["first_run_index"] is None, e["first_run_index"]))


def _max_prompt(out_dir: Path) -> int:
    return max([r.get("prompt_tokens_max", 0) for r in load_records(out_dir)] or [0])


def write_manifest(out_dir: str | Path) -> dict:
    """`manifest.json`: file hashes, run counts per condition (SPEC §10.2)."""
    out_dir = Path(out_dir)
    files = {}
    for f in sorted(out_dir.glob("condition_*.jsonl")):
        recs, torn = read_file(f)
        files[f.name] = {"sha256": R.sha256_file(f), "runs": len(recs), "torn_lines": torn,
                         "questions": len({r["qid"] for r in recs}),
                         "duplicates": len(recs) - len({r["run_id"] for r in recs})}
    manifest = {"files": files, "total_runs": sum(v["runs"] for v in files.values()),
                "order_files": {f.name: R.sha256_file(f) for f in sorted(out_dir.glob("order*.json"))},
                "servers": _servers(out_dir), "prompt_tokens_max": _max_prompt(out_dir)}
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return manifest

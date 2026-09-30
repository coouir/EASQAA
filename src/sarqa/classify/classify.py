"""Error classifier (SPEC §11): input error and agent error as separate attributes, first deviation.

    input_error  box_dependent and the answer reachable from the boxes the run received != gold_answer
    agent_error  no final answer, or the agent's answer != that reachable answer (unit included)

A wrong answer lands in exactly one cell: `input_only`, `agent_only`, `both`. A correct answer with both
errors is `lucky_correct`. The **first deviation** is defined for `agent_error` runs only: the earliest
non-harmless deviation by (turn, table order of the stages). Runs with no answer (stage 0) record the
earliest stage 1-6 deviation found before they stopped, else `exec_fail`. Nothing found -> `unknown`.
"""

import json
from collections import Counter
from pathlib import Path

from sarqa.classify import replay, stages
from sarqa.classify.stages import STAGE_NAMES, Dev
from sarqa.grading import grade, normalize_unit, value_matches
from sarqa.run.conditions import Condition, ProviderPool
from sarqa.run.runner import load_records


def input_error(question: dict, reachable) -> bool:
    if not question["box_dependent"]:
        return False
    return reachable is None or not value_matches(reachable, question["gold_answer"], question["answer_type"])


def agent_error(rec: dict, question: dict, reachable) -> bool:
    if rec["status"] != "ok":
        return True
    if reachable is None:
        return False   # the boxes made the answer impossible; nothing to hold against the agent
    ans = rec["answer"] or {}
    return not grade(ans.get("value"), ans.get("unit"), reachable, question["unit"],
                     question["answer_type"]).correct


def cell_of(correct: bool, in_err: bool, ag_err: bool) -> str:
    if correct:
        return "lucky_correct" if in_err and ag_err else "correct"
    return "both" if in_err and ag_err else "input_only" if in_err else "agent_only"


def find_deviations(rec: dict, question: dict, provider, ctx, reachable, exps=None) -> tuple[list[Dev], dict]:
    """All deviations of stages 1-6 (harmless ones flagged) and some counters."""
    trace = stages.build_trace(rec)
    exps = exps or stages.expected_runs(question, provider, ctx)
    has_answer = rec["status"] == "ok"
    exp, unmatched, missing = stages.best_expected(trace, exps)

    devs: list[Dev] = []
    s1 = stages.stage1(rec, trace, question)
    devs += stages.stage2(trace, exp, unmatched, missing, has_answer)
    devs += stages.stage3(trace, rec, question)
    devs += stages.stage4(trace, question, exps)
    devs += stages.stage5(trace, exp, has_answer, rec)
    if has_answer:
        s6 = stages.stage6(rec, trace, question, reachable)
        if s6:
            devs.append(s6)
    extras = {"expected_program": exp.name}
    if s1 is not None:
        # a record-only mismatch: the calls and branches went the gold way
        followed = not any(d.stage in (2, 4) and not d.harmless for d in devs)
        unit_ok = not has_answer or normalize_unit((rec["answer"] or {}).get("unit")) == question["unit"]
        if followed and unit_ok:
            s1.harmless = True
            extras["interp_record_mismatch"] = True
        devs.append(s1)
    # a wrong recorded branch that the calls did not follow is only a wrong record
    for d in devs:
        if d.stage == 4 and d.kind == "wrong_branch" and not any(
                x.stage == 2 and not x.harmless for x in devs):
            d.harmless = True
    # calls and calcs after a truly wrong branch follow the branch the agent chose: consequences, not new errors
    wrong = [d for d in devs if d.stage == 4 and d.kind == "wrong_branch" and not d.harmless]
    if wrong:
        t0 = min(d.turn for d in wrong)
        for d in devs:
            if d.stage in (2, 5) and d.turn >= t0 and not d.harmless:
                d.harmless, d.detail = True, "consequence of the wrong branch: " + d.detail
    return devs, extras


def first_deviation(devs: list[Dev]) -> Dev | None:
    real = [d for d in devs if not d.harmless]
    return min(real, key=lambda d: (d.turn, d.stage)) if real else None


def classify_run(rec: dict, question: dict, provider, ctx, exps=None) -> dict:
    reachable = rec.get("reachable_answer")
    in_err = input_error(question, reachable)
    ag_err = agent_error(rec, question, reachable)
    out = {"run_id": rec["run_id"], "qid": rec["qid"], "condition": rec["condition"],
           "method": rec["method"], "input": rec["input"], "level": rec["level"],
           "template": question["template"], "correct": rec["correct"], "status": rec["status"],
           "fail_kind": rec["fail_kind"], "over_budget": rec.get("over_budget", False),
           "box_dependent": question["box_dependent"], "input_error": in_err, "agent_error": ag_err,
           "cell": cell_of(rec["correct"], in_err, ag_err), "input_cause": None,
           "first_deviation_stage": None, "first_deviation_stage_name": None,
           "first_deviation_turn": None, "deviations": [], "harmless_deviations": [],
           "interp_record_mismatch": False, "unit_only_fix": rec.get("unit_only_fix", False),
           "interp_statistic_only_diff": stages.statistic_only_diff(rec.get("interpretation"),
                                                                    question["gold_interpretation"])}
    if in_err:
        out["input_cause"] = replay.replay_input(question, provider, ctx)
    if ag_err:
        devs, extras = find_deviations(rec, question, provider, ctx, reachable, exps)
        out["interp_record_mismatch"] = extras.get("interp_record_mismatch", False)
        out["deviations"] = [d.as_dict() for d in devs if not d.harmless]
        out["harmless_deviations"] = [d.as_dict() for d in devs if d.harmless]
        first = first_deviation(devs)
        if first:
            out["first_deviation_stage"], out["first_deviation_turn"] = first.stage, first.turn
            out["first_deviation_stage_name"] = STAGE_NAMES[first.stage]
        elif rec["status"] != "ok":
            out["first_deviation_stage"], out["first_deviation_stage_name"] = 0, STAGE_NAMES[0]
        else:
            out["first_deviation_stage"], out["first_deviation_stage_name"] = None, "unknown"
    return out


def classify_all(runs_dir: str | Path, questions: list[dict], split: str, ctx=None) -> list[dict]:
    """Classify every record under `runs_dir`; results are also written to `classified.jsonl`."""
    from sarqa.tools import default_context

    ctx = ctx or default_context()
    by_qid = {q["qid"]: q for q in questions}
    pool = ProviderPool(split)
    exp_cache: dict = {}
    out = []
    for rec in load_records(Path(runs_dir)):
        q = by_qid.get(rec["qid"])
        if q is None:
            continue
        cond = Condition(rec["condition"], rec["method"], rec["input"], rec["repeat"])
        provider = pool.get(cond)
        key = (rec["qid"], rec["input"])
        if key not in exp_cache:
            exp_cache[key] = stages.expected_runs(q, provider, ctx)
        out.append(classify_run(rec, q, provider, ctx, exp_cache[key]))
    with open(Path(runs_dir) / "classified.jsonl", "w", encoding="utf-8") as f:
        f.writelines(json.dumps(c, ensure_ascii=False) + "\n" for c in out)
    return out


def summarize(classified: list[dict]) -> dict:
    """Cells, first-deviation stages, unknown share, input causes, harmless counts."""
    n = len(classified)
    wrong = [c for c in classified if not c["correct"]]
    agent = [c for c in classified if c["agent_error"]]
    return {
        "runs": n, "correct": n - len(wrong),
        "cells": dict(Counter(c["cell"] for c in classified)),
        "wrong": len(wrong),
        "first_deviation": dict(Counter(c["first_deviation_stage_name"] for c in agent)),
        "unknown_share_of_agent_errors": round(
            sum(c["first_deviation_stage_name"] == "unknown" for c in agent) / len(agent), 4) if agent else 0,
        "unknown_share_of_wrong": round(
            sum(c["first_deviation_stage_name"] == "unknown" for c in wrong if c["agent_error"]) / len(wrong), 4)
        if wrong else 0,
        "input_causes": dict(Counter(c["input_cause"]["category"] for c in classified if c["input_cause"])),
        "interp_record_mismatch": sum(c["interp_record_mismatch"] for c in classified),
        "interp_statistic_only_diff_runs": dict(Counter(
            f for c in classified for f in c.get("interp_statistic_only_diff", []))),
        "harmless_deviation_runs": sum(bool(c["harmless_deviations"]) for c in classified),
        "fail_kinds": dict(Counter(c["fail_kind"] for c in classified if c["fail_kind"])),
    }

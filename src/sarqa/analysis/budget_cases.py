"""Why runs exceed the tool-call budget: every `budget_exceeded` record, classified by cause.

    python -m sarqa.analysis.budget_cases --runs outputs/runs/pilotA --questions <dev.json> --out <md>

Causes (first that applies):
  termination_failure   every call the gold/alternative program needs had been made (and at least as many
                        calc calls), yet the agent kept calling tools instead of answering
  repeated_call         the same tool with the same arguments again (2+ repeats, or >= 30 % of the calls)
  error_loop            3+ calls answered with {"error"} (wrong region name, bad reference, ...)
  exploration           calls the gold program does not need (other tools / queries / regions) while a
                        needed call was still missing
  other                 none of the above
"""

import argparse
import json
from collections import Counter
from pathlib import Path

from sarqa.classify import stages
from sarqa.questions.generate import read_questions
from sarqa.run.conditions import Condition, ProviderPool
from sarqa.run.runner import load_records
from sarqa.tools import default_context

CAUSES = ("termination_failure", "repeated_call", "error_loop", "exploration", "other")


def _label(c) -> str:
    a = c.args if isinstance(c.args, dict) else {}
    bits = [str(a[k]) for k in ("op", "query", "region", "ship_a", "ship_b") if a.get(k) not in (None, "full")]
    return f"{c.tool}({','.join(bits)})" if bits else c.tool


def analyse(rec: dict, question: dict, provider, ctx) -> dict:
    trace = stages.build_trace(rec)
    exps = stages.expected_runs(question, provider, ctx)
    exp, unmatched, missing = stages.best_expected(trace, exps)
    keys = [stages.call_key(c.tool, c.args) if c.tool != "calc" else ("calc", json.dumps(c.args, sort_keys=True, default=str))
            for c in trace.calls]
    repeats = sum(k in keys[:i] for i, k in enumerate(keys))
    errors = sum("error" in c.output for c in trace.calls)
    need_calc = sum(c.tool == "calc" for c in exp.result.calls)
    made_calc = sum(c.tool == "calc" for c in trace.calls)
    done = not missing and made_calc >= need_calc
    n = len(trace.calls)
    if done:
        cause = "termination_failure"
    elif repeats >= 2 or (n and repeats / n >= 0.3):
        cause = "repeated_call"
    elif errors >= 3:
        cause = "error_loop"
    elif [u for u in unmatched if "error" not in u.output]:
        cause = "exploration"
    else:
        cause = "other"
    return {"qid": rec["qid"], "condition": rec["condition"], "template": question["template"],
            "level": question["level"], "gold_calls": question["gold_calls"], "budget": question["budget"],
            "calls": n, "repeats": repeats, "errors": errors, "unmatched": len(unmatched),
            "missing": len(missing), "cause": cause, "sequence": [_label(c) for c in trace.calls],
            "interp_target": (rec.get("interpretation") or {}).get("target")}


def collect(runs_dir: Path, questions: list[dict], split: str = "dev", conditions=(1, 2)) -> list[dict]:
    by_qid = {q["qid"]: q for q in questions}
    ctx, pool, out = default_context(), ProviderPool(split), []
    for rec in load_records(runs_dir):
        if rec["condition"] in conditions and rec["fail_kind"] == "budget_exceeded":
            prov = pool.get(Condition(rec["condition"], rec["method"], rec["input"], rec["repeat"]))
            out.append(analyse(rec, by_qid[rec["qid"]], prov, ctx))
    return sorted(out, key=lambda x: (x["condition"], x["qid"]))


def render(cases: list[dict], title: str) -> str:
    lines = [f"# {title}", "", "자동 생성: `python -m sarqa.analysis.budget_cases`. 원인 정의는 모듈 머리말 참고.", ""]
    lines += ["## 원인 × 조건", "", "| 원인 | 조건 1 | 조건 2 | 합 |", "|---|---|---|---|"]
    for cause in CAUSES:
        c1 = sum(x["cause"] == cause and x["condition"] == 1 for x in cases)
        c2 = sum(x["cause"] == cause and x["condition"] == 2 for x in cases)
        lines.append(f"| {cause} | {c1} | {c2} | {c1 + c2} |")
    lines += ["", "## 템플릿별", "", "| 템플릿 | 건수 | 원인 |", "|---|---|---|"]
    for t in sorted({x["template"] for x in cases}):
        rows = [x for x in cases if x["template"] == t]
        lines.append(f"| `{t}` | {len(rows)} | {dict(Counter(x['cause'] for x in rows))} |")
    n = max(1, len(cases))
    mean = (f"평균 호출 수: {sum(x['calls'] for x in cases) / n:.1f} (평균 상한 {sum(x['budget'] for x in cases) / n:.1f}, "
            f"평균 gold_calls {sum(x['gold_calls'] for x in cases) / n:.1f})")
    lines += ["", mean, "", "## 사례", "",
              "| qid | 조건 | 템플릿 | 호출/상한/gold | 원인 | 반복 | 오류 | 없는 호출 | 호출 순서 |",
              "|---|---|---|---|---|---|---|---|---|"]
    for x in cases:
        lines.append(f"| {x['qid']} | {x['condition']} | `{x['template']}` | {x['calls']}/{x['budget']}/{x['gold_calls']} | "
                     f"{x['cause']} | {x['repeats']} | {x['errors']} | {x['missing']} | {' → '.join(x['sequence'])} |")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--runs", required=True)
    p.add_argument("--questions", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--title", default="예산 초과 사례 분석 (파일럿 A, 조건 1·2)")
    a = p.parse_args(argv)
    cases = collect(Path(a.runs), read_questions(a.questions))
    Path(a.out).write_text(render(cases, a.title), encoding="utf-8")
    print(f"{len(cases)} budget-exceeded runs -> {a.out}", dict(Counter(c['cause'] for c in cases)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

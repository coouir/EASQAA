"""Compare run directories on the same questions (prompt versions, budget variants, re-runs).

    python -m sarqa.analysis.compare_runs A=outputs/runs/pilotA B=outputs/runs/pilotA2 [--qids-from file.json]

Prints, per condition, for each directory: runs, accuracy, failure rate by kind, budget-exceeded, mean
tool calls, mean seconds; and the runs whose correctness flipped between the first two directories.
"""

import argparse
import json
from collections import Counter
from pathlib import Path

from sarqa.run.runner import load_records


def load(path: str, qids: set | None) -> dict[tuple, dict]:
    return {(r["condition"], r["qid"]): r for r in load_records(Path(path)) if qids is None or r["qid"] in qids}


def table(named: dict[str, dict]) -> str:
    conds = sorted({c for recs in named.values() for c, _ in recs})
    lines = ["| 조건 | 실행 | 정확도 | 실패율 | 예산 초과 | format_error | 평균 도구 호출 | 평균 시간(s) |", "|---|---|---|---|---|---|---|---|"]
    for c in conds:
        for name, recs in named.items():
            rs = [r for (cc, _), r in recs.items() if cc == c]
            if not rs:
                continue
            n = len(rs)
            kinds = Counter(r["fail_kind"] for r in rs if r["status"] == "exec_fail")
            lines.append(f"| {c} · {name} | {n} | {sum(r['correct'] for r in rs)}/{n} ({sum(r['correct'] for r in rs) / n:.3f}) | "
                         f"{sum(kinds.values())}/{n} | {kinds.get('budget_exceeded', 0)} | {kinds.get('format_error', 0)} | "
                         f"{sum(r['tool_calls'] for r in rs) / n:.2f} | {sum(r['wall_ms'] for r in rs) / n / 1000:.1f} |")
    return "\n".join(lines)


def flips(a: dict, b: dict) -> list[str]:
    out = []
    for key in sorted(set(a) & set(b)):
        if a[key]["correct"] != b[key]["correct"]:
            out.append(f"c{key[0]} {key[1]}: {'정답→오답' if a[key]['correct'] else '오답→정답'} "
                       f"({a[key]['fail_kind'] or 'ok'} → {b[key]['fail_kind'] or 'ok'})")
    return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("dirs", nargs="+", help="NAME=path")
    p.add_argument("--qids-from", default=None)
    a = p.parse_args(argv)
    qids = None
    if a.qids_from:
        qids = {q["qid"] for q in json.loads(Path(a.qids_from).read_text(encoding="utf-8"))["questions"]}
    named = {d.split("=")[0]: load(d.split("=", 1)[1], qids) for d in a.dirs}
    print(table(named))
    names = list(named)
    if len(names) >= 2:
        f = flips(named[names[0]], named[names[1]])
        print(f"\n{names[0]} → {names[1]}: {len(f)} runs changed correctness")
        print("\n".join(f))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

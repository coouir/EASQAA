"""Korean vs English question wording, condition 1 only (step-by-step, label boxes).

    python -m sarqa.analysis.language_comparison --ko outputs/runs/pilotA3 --en outputs/runs/pilotEN \
        --questions data/questions/dev.json --out docs/language_comparison_dev.md

Both directories must have been classified (`sarqa classify --runs DIR`, `classified.jsonl`). Compared on
the same questions: accuracy, execution-failure rate (by kind), runs whose first deviation is the
interpretation, accuracy per level, tool calls and time, and the runs whose correctness differs.
"""

import argparse
import json
from collections import Counter
from pathlib import Path

from sarqa.run.runner import load_records

LEVELS = ("L1", "L2", "L3", "L4", "L5")


def _load(runs: Path, condition: int) -> tuple[dict, dict]:
    recs = {r["qid"]: r for r in load_records(runs) if r["condition"] == condition}
    cls = {}
    f = runs / "classified.jsonl"
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            c = json.loads(line)
            if c["condition"] == condition:
                cls[c["qid"]] = c
    return recs, cls


def stats(recs: dict, cls: dict) -> dict:
    rs = list(recs.values())
    n = len(rs)
    kinds = Counter(r["fail_kind"] for r in rs if r["status"] == "exec_fail")
    first = Counter(c["first_deviation_stage_name"] for c in cls.values() if c["agent_error"])
    return {
        "n": n, "correct": sum(r["correct"] for r in rs), "fails": sum(kinds.values()), "kinds": dict(kinds),
        "interp_first": first.get("interpretation", 0), "first": dict(first),
        "by_level": {lv: (sum(r["correct"] for r in rs if r["level"] == lv), sum(r["level"] == lv for r in rs))
                     for lv in LEVELS},
        "calls": sum(r["tool_calls"] for r in rs) / max(1, n), "secs": sum(r["wall_ms"] for r in rs) / max(1, n) / 1000,
        "tokens_in": sum(r["tokens_in"] for r in rs) / max(1, n),
    }


def render(ko: dict, en: dict, ko_recs: dict, en_recs: dict, note: str = "") -> str:
    def pct(a, b):
        return f"{a}/{b} ({a / b:.3f})" if b else "-"

    intro = ("자동 생성: `python -m sarqa.analysis.language_comparison`. 같은 문항·영상·정답, 문구만 다름. "
             "프롬프트는 두 언어 모두 영어 시스템 프롬프트(질문 문구만 다름). 어느 언어를 쓸지는 사용자가 정한다(기본값은 한국어). "
             "디버깅용 dev 결과이며 90회 한 번씩이라 차이의 통계적 유의성은 따지지 않는다.")
    lines = ["# 질문 언어 비교: 한국어 vs 영어 (dev 90문항, 조건 1)", "", intro, ""]
    if note:
        lines += [note, ""]
    lines += ["| 지표 | 한국어 | 영어 |", "|---|---|---|",
              f"| 정확도 | {pct(ko['correct'], ko['n'])} | {pct(en['correct'], en['n'])} |",
              f"| 실행 실패율 | {pct(ko['fails'], ko['n'])} | {pct(en['fails'], en['n'])} |",
              f"| 실패 종류 | {ko['kinds']} | {en['kinds']} |",
              f"| 첫 이탈이 해석인 건수 | {ko['interp_first']} | {en['interp_first']} |",
              f"| 첫 이탈 단계 분포 (agent_error) | {ko['first']} | {en['first']} |",
              f"| 평균 도구 호출 | {ko['calls']:.2f} | {en['calls']:.2f} |",
              f"| 평균 시간(s) | {ko['secs']:.1f} | {en['secs']:.1f} |",
              f"| 평균 입력 토큰 | {ko['tokens_in']:.0f} | {en['tokens_in']:.0f} |", "",
              "## 유형별 정답", "", "| 유형 | 한국어 | 영어 |", "|---|---|---|"]
    for lv in LEVELS:
        lines.append(f"| {lv} | {pct(*ko['by_level'][lv])} | {pct(*en['by_level'][lv])} |")
    flips = [(q, ko_recs[q], en_recs[q]) for q in sorted(set(ko_recs) & set(en_recs))
             if ko_recs[q]["correct"] != en_recs[q]["correct"]]
    lines += ["", f"## 정오가 다른 문항 ({len(flips)}건)", "", "| qid | 한국어 | 영어 |", "|---|---|---|"]
    for q, a, b in flips:
        lines.append(f"| {q} | {'정답' if a['correct'] else '오답'} ({a['fail_kind'] or 'ok'}) | "
                     f"{'정답' if b['correct'] else '오답'} ({b['fail_kind'] or 'ok'}) |")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--ko", required=True)
    p.add_argument("--en", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--condition", type=int, default=1)
    p.add_argument("--note", default="")
    a = p.parse_args(argv)
    kr, kc = _load(Path(a.ko), a.condition)
    er, ec = _load(Path(a.en), a.condition)
    qids = set(kr) & set(er)
    kr, er = {q: kr[q] for q in qids}, {q: er[q] for q in qids}
    kc, ec = {q: c for q, c in kc.items() if q in qids}, {q: c for q, c in ec.items() if q in qids}
    Path(a.out).write_text(render(stats(kr, kc), stats(er, ec), kr, er, a.note), encoding="utf-8")
    print(f"{len(qids)} common questions -> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

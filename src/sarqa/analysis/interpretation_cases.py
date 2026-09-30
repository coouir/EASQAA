"""List every run whose first deviation is the interpretation (stage 1), for reading and review.

    python -m sarqa.analysis.interpretation_cases --runs outputs/runs/pilotA \
        --questions outputs/runs/pilotA/questions_at_run.json --out docs/interpretation_cases.md

Per case: the question text, the gold interpretation, the agent's interpretation, which fields differ
(fields the gold program uses and fields it does not use are told apart), and whether the final answer
was right. The vocabulary is not touched here.
"""

import argparse
import json
from pathlib import Path

from sarqa.classify.stages import interpretation_diff
from sarqa.questions.generate import read_questions
from sarqa.run.runner import load_records


def _c(v) -> str:
    return json.dumps(v, ensure_ascii=False, separators=(",", ":"))


def cases(runs_dir: Path, questions: list[dict], conditions=(1, 2)) -> list[dict]:
    by_qid = {q["qid"]: q for q in questions}
    recs = {r["run_id"]: r for r in load_records(runs_dir)}
    out = []
    for line in (runs_dir / "classified.jsonl").read_text(encoding="utf-8").splitlines():
        c = json.loads(line)
        if c["condition"] not in conditions or c["first_deviation_stage_name"] != "interpretation":
            continue
        rec, q = recs[c["run_id"]], by_qid[c["qid"]]
        used, unused = interpretation_diff(rec["interpretation"], q["gold_interpretation"])
        out.append({"cls": c, "rec": rec, "q": q, "used": used, "unused": unused})
    return sorted(out, key=lambda x: (x["cls"]["condition"], x["q"]["qid"]))


def render(items: list[dict], source: str) -> str:
    intro = (f"자동 생성: `python -m sarqa.analysis.interpretation_cases` (입력: `{source}`). 어휘와 문구는 바꾸지 않았다. "
             "\"다른 필드\"는 정답 풀이가 쓰는 필드(판정에 쓰임)와 쓰지 않는 필드(참고)를 나눠 적었다. "
             "해석은 항상 가장 이른 턴이라, 사례에 해석 차이가 있고 그것이 \"무해\"(호출·분기가 정답 방식으로 이뤄짐)로 "
             "판정되지 않으면 첫 이탈이 된다.")
    lines = ["# 첫 이탈이 \"해석\"인 사례 (파일럿 A, 조건 1·2)", "", intro, ""]
    for cond in (1, 2):
        rows = [x for x in items if x["cls"]["condition"] == cond]
        lines += [f"## 조건 {cond} ({'label' if cond == 1 else 'detected'} 입력): {len(rows)}건", ""]
        by_field: dict[str, int] = {}
        for x in rows:
            for f in x["used"]:
                by_field[f] = by_field.get(f, 0) + 1
        n_right = sum(x["cls"]["correct"] for x in rows)
        lines += [f"정답 풀이가 쓰는 필드 중 다른 필드별 건수: {by_field or '-'}; 이 중 최종 답이 맞은 건: {n_right}", ""]
        lines += ["| qid | 템플릿 | 다른 필드(쓰임) | 다른 필드(안 쓰임) | 최종 답 | 정오 |", "|---|---|---|---|---|---|"]
        for x in rows:
            ans = x["rec"]["answer"]
            shown = f"{_c(ans['value'])} {ans['unit']}" if ans else f"(답 없음: {x['rec']['fail_kind']})"
            verdict = "정답" if x["cls"]["correct"] else "오답"
            lines.append(f"| {x['q']['qid']} | `{x['q']['template']}` | {', '.join(x['used']) or '-'} | "
                         f"{', '.join(x['unused']) or '-'} | {shown} | {verdict} (정답값 {_c(x['q']['gold_answer'])}) |")
        lines.append("")
        for x in rows:
            q, rec = x["q"], x["rec"]
            g, a = q["gold_interpretation"], rec["interpretation"] or {}
            lines += [f"### {q['qid']} · 조건 {cond} · `{q['template']}`", "",
                      f"- 질문: {q['text_ko']}",
                      f"- 정답 해석: `{_c(g)}`", f"- 에이전트 해석: `{_c(a)}`"]
            for f in x["used"] + x["unused"]:
                tag = "쓰임" if f in x["used"] else "안 쓰임"
                lines.append(f"- 다른 필드 `{f}` ({tag}): 정답 `{_c(g.get(f))}` / 에이전트 `{_c(a.get(f))}`")
            ans = rec["answer"]
            shown = f"{_c(ans['value'])} {ans['unit']}" if ans else f"없음 ({rec['fail_kind']})"
            verdict = "정답" if x["cls"]["correct"] else "오답"
            tail = (f"- 최종 답: {shown} → {verdict}, 정답값 {_c(q['gold_answer'])}, "
                    f"에이전트가 받은 상자로 도달 가능한 값 {_c(rec['reachable_answer'])}")
            lines += [tail, ""]
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--runs", required=True)
    p.add_argument("--questions", required=True)
    p.add_argument("--out", required=True)
    a = p.parse_args(argv)
    items = cases(Path(a.runs), read_questions(a.questions))
    Path(a.out).write_text(render(items, a.questions), encoding="utf-8")
    print(f"{len(items)} cases -> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

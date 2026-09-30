"""Pilot report (SPEC §14 M4): accuracy per level, failure rates, classifier unknown share, and the
main-run time estimate. Debugging aid on dev; nothing here decides a rule on test."""

import json
from collections import defaultdict
from pathlib import Path

from sarqa.classify import classify as CL
from sarqa.run.runner import load_records, summarize

LEVELS = ("L1", "L2", "L3", "L4", "L5")
TEST_QUESTIONS = 360


def _acc(recs) -> str:
    return f"{sum(r['correct'] for r in recs)}/{len(recs)}" if recs else "-"


def estimate_main_run(per_condition_mean_s: dict[int, float], stepwise_mean_s: float) -> dict:
    """Σ(runs × mean time). Conditions not measured use the stepwise mean of condition 1 (batch runs
    are expected to be faster, so this is an upper bound)."""
    from sarqa.run.conditions import priority_groups

    total, groups = 0.0, []
    for g in priority_groups():
        t = sum(TEST_QUESTIONS * per_condition_mean_s.get(c, stepwise_mean_s) for c in g)
        groups.append(round(t / 3600, 2))
        total += t
    return {"hours_per_group": groups, "hours_total": round(total / 3600, 2),
            "hours_group1": groups[0]}


def report(runs_dir: str | Path, classified: list[dict]) -> str:
    recs = load_records(Path(runs_dir))
    by_c = defaultdict(list)
    for r in recs:
        by_c[r["condition"]].append(r)
    lines = ["# 파일럿 A 결과 (dev 90문항 × 조건 1·2, 디버깅용)", "",
             "자동 생성: `sarqa.run.pilot`. 이 결과로 test 규칙을 정하지 않는다.", ""]
    lines += ["## 조건별 요약", "", "| 조건 | 실행 | 정확도 | 실패율 | format_error | 평균 도구 호출 | 평균 LLM 호출 | 평균 시간(s) |",
              "|---|---|---|---|---|---|---|---|"]
    means = {}
    for c, rs in sorted(by_c.items()):
        s = summarize(rs)
        means[c] = s["mean_wall_s"]
        lines.append(f"| {c} | {s['n']} | {s['accuracy']:.3f} | {s['fail_rate']:.3f} | "
                     f"{s['format_error_rate']:.3f} | {s['mean_tool_calls']} | {s['mean_llm_calls']} | {s['mean_wall_s']} |")
    lines += ["", "## 유형별 정답 수", "", "| 조건 | " + " | ".join(LEVELS) + " |", "|---|" + "---|" * len(LEVELS)]
    for c, rs in sorted(by_c.items()):
        lines.append(f"| {c} | " + " | ".join(_acc([r for r in rs if r["level"] == lv]) for lv in LEVELS) + " |")
    lines += ["", "## 실패 종류", ""]
    for c, rs in sorted(by_c.items()):
        lines.append(f"- 조건 {c}: {summarize(rs).get('fail_kinds')}")
    lines += ["", "## 분류기 (dev 오답)", ""]
    for c in sorted(by_c):
        cs = [x for x in classified if x["condition"] == c]
        s = CL.summarize(cs)
        lines += [f"### 조건 {c}", "", f"- 칸: {s['cells']}", f"- 첫 이탈 단계 (agent_error 기준): {s['first_deviation']}",
                  f"- unknown 비율 (agent_error 중): {s['unknown_share_of_agent_errors']}",
                  f"- 입력 오류 하위 범주: {s['input_causes']}",
                  f"- 해석 기록만 틀림: {s['interp_record_mismatch']}, 무해한 이탈이 있는 실행: {s['harmless_deviation_runs']}", ""]
    if 1 in means:
        est = estimate_main_run(means, means[1])
        lines += ["## 본 실행 시간 추정 (SPEC §14)", "",
                  f"조건별 평균 시간(파일럿) × 360문항. 측정하지 못한 조건은 조건 1의 평균({means[1]}s)으로 가정(일괄 계획은 더 빠를 것이므로 상한).",
                  "", f"- 우선순위 그룹별 시간(h): {est['hours_per_group']}", f"- 전체: {est['hours_total']} h, 1그룹: {est['hours_group1']} h",
                  "- 기준: 10/4 20시 시작, 1그룹은 10/5 24시(28 h 후), 전체는 10/6 12시(40 h 후)까지 끝나야 함", ""]
    (Path(runs_dir) / "classified_summary.json").write_text(
        json.dumps(CL.summarize(classified), ensure_ascii=False, indent=1), encoding="utf-8")
    return "\n".join(lines) + "\n"

"""Analysis of the main run (SPEC §12, PROTOCOL.md §9). Reads the run records, classifies them with the
**frozen** classifier (nothing is changed or tuned here) and writes CSV tables and a summary to a new folder.

    python -m sarqa.analysis.main_run --runs outputs/runs --questions data/questions/test.json \
        --out outputs/analysis

Statistics (SPEC §12.2): every comparison pairs the same questions; confidence intervals are percentile
intervals of a bootstrap over the **scene groups** (the 23 groups are resampled with replacement, B = 10,000,
fixed seed; one index matrix is reused for every statistic). A ratio (accuracy, mean paired difference) is
the pooled sum over the resampled groups divided by their number of questions.
The summary lists numbers only, no interpretation.
"""

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

import numpy as np

from sarqa.run.runner import load_records

B = 10_000
SEED = 20260929
CONDITIONS = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11)
MAIN_PAIRS = ((1, 2), (1, 6), (1, 7), (1, 8), (2, 9), (2, 10), (2, 11), (1, 3), (1, 4), (2, 5))
PLACEBO_PAIRS = ((1, 6), (1, 7), (1, 8), (2, 9), (2, 10), (2, 11))
TABLE1_PAIRS = ((1, 6), (1, 7), (1, 8), (2, 9), (2, 10), (2, 11))   # PROTOCOL §9: box_dependent=true only
DECOMP_CONDITIONS = (1, 2, 4, 5)
STAGES = ("interpretation", "tool_selection", "result_reading", "planning_branch", "calculation",
          "answer_formatting", "exec_fail", "unknown")
CAUSES = ("miss", "fp", "loc", "multiple", "composite", "unknown")
EXPECTED = {   # numbers written in PROTOCOL.md §10 (computed from the question file before any run)
    "answer_changed_miss": 62, "answer_changed_fp": 43, "answer_changed_loc": 6,
    "detected_wrong": 81, "recoverable_miss": 43, "recoverable_fp": 6, "recoverable_loc": 2,
}


# ---------------------------------------------------------------- data

class Data:
    def __init__(self, recs: list[dict], questions: list[dict], classified: list[dict] | None = None):
        self.q = sorted(questions, key=lambda q: q["qid"])
        self.qids = [q["qid"] for q in self.q]
        self.qix = {qid: i for i, qid in enumerate(self.qids)}
        self.rec = {(r["condition"], r["qid"]): r for r in recs}
        self.cls = {(c["condition"], c["qid"]): c for c in (classified or [])}
        self.groups = sorted({q["scene_group"] for q in self.q})
        gix = {g: i for i, g in enumerate(self.groups)}
        self.g = np.array([gix[q["scene_group"]] for q in self.q])
        self.box_dep = np.array([q["box_dependent"] for q in self.q])
        self.level = np.array([q["level"] for q in self.q])
        self.depth = np.array([q["gold_calls"] for q in self.q])
        self.idx = np.random.default_rng(SEED).integers(0, len(self.groups), (B, len(self.groups)))

    def correct(self, cond: int) -> np.ndarray:
        return np.array([self.rec[(cond, qid)]["correct"] for qid in self.qids], dtype=float)

    def answer(self, cond: int) -> list:
        out = []
        for qid in self.qids:
            r = self.rec[(cond, qid)]
            a = r["answer"]
            out.append(None if (r["status"] != "ok" or not a) else (json.dumps(a["value"], sort_keys=True), a["unit"]))
        return out

    def masks(self) -> dict[str, np.ndarray]:
        return {"all": np.ones(len(self.qids), bool), "box_dependent": self.box_dep, "not_box_dependent": ~self.box_dep}

    def group_stats(self, values: list[np.ndarray], mask: np.ndarray) -> np.ndarray:
        """(groups, len(values)+1): per-group sums of each value over the masked questions, then the count."""
        cols = [np.bincount(self.g, weights=v * mask, minlength=len(self.groups)) for v in values]
        cols.append(np.bincount(self.g, weights=mask.astype(float), minlength=len(self.groups)))
        return np.stack(cols, axis=1)

    def boot(self, stats: np.ndarray, f) -> tuple[float | None, float | None, float | None]:
        """Point value of `f(total)` and its 95 % percentile interval over group resamples."""
        total = stats.sum(0, keepdims=True)
        if total[0, -1] == 0:
            return None, None, None
        with np.errstate(divide="ignore", invalid="ignore"):
            point = float(f(total)[0])
            vals = f(stats[self.idx].sum(axis=1))
        vals = vals[np.isfinite(vals)]
        return point, float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def ratio(S):          # accuracy, mean paired difference, share
    return S[:, 0] / S[:, -1]


def fmt(x, d=4):
    return "" if x is None else round(float(x), d)


# ---------------------------------------------------------------- tables

def table_accuracy(d: Data) -> list[dict]:
    rows = []
    for name, m in d.masks().items():
        for c in CONDITIONS:
            x = d.correct(c)
            p, lo, hi = d.boot(d.group_stats([x], m), ratio)
            rows.append({"condition": c, "subset": name, "n": int(m.sum()), "correct": int((x * m).sum()),
                         "accuracy": fmt(p), "ci_low": fmt(lo), "ci_high": fmt(hi)})
    return rows


def paired_row(d: Data, a: int, b: int, name: str, m: np.ndarray, tag: str) -> dict:
    xa, xb = d.correct(a), d.correct(b)
    p, lo, hi = d.boot(d.group_stats([xa - xb], m), ratio)
    pa, _, _ = d.boot(d.group_stats([xa], m), ratio)
    pb, _, _ = d.boot(d.group_stats([xb], m), ratio)
    return {"comparison": f"{a}-{b}", "role": tag, "subset": name, "n": int(m.sum()), "acc_A": fmt(pa), "acc_B": fmt(pb),
            "diff_A_minus_B": fmt(p), "ci_low": fmt(lo), "ci_high": fmt(hi),
            "both_correct": int(((xa == 1) & (xb == 1) & m).sum()), "only_A_correct": int(((xa == 1) & (xb == 0) & m).sum()),
            "only_B_correct": int(((xa == 0) & (xb == 1) & m).sum()), "both_wrong": int(((xa == 0) & (xb == 0) & m).sum())}


def table_paired(d: Data) -> list[dict]:
    ms = d.masks()
    rows = []
    for a, b in MAIN_PAIRS:
        primary = "box_dependent" if (a, b) in TABLE1_PAIRS else "all"
        for name in ("all", "box_dependent"):
            rows.append(paired_row(d, a, b, name, ms[name], "main (primary subset)" if name == primary else "main (other subset)"))
    for a, b in PLACEBO_PAIRS:
        rows.append(paired_row(d, a, b, "not_box_dependent", ms["not_box_dependent"], "placebo"))
    return rows


def table_noise(d: Data) -> list[dict]:
    rows = []
    for name, m in d.masks().items():
        x1, x3 = d.correct(1), d.correct(3)
        a1, a3 = d.answer(1), d.answer(3)
        flip = np.array([u != v for u, v in zip(x1, x3, strict=True)], dtype=float)
        diff_ans = np.array([u != v for u, v in zip(a1, a3, strict=True)], dtype=float)
        acc = d.boot(d.group_stats([x1 - x3], m), ratio)
        fl = d.boot(d.group_stats([flip], m), ratio)
        da = d.boot(d.group_stats([diff_ans], m), ratio)
        rows.append({"subset": name, "n": int(m.sum()), "acc_cond1": fmt(d.boot(d.group_stats([x1], m), ratio)[0]),
                     "acc_cond3": fmt(d.boot(d.group_stats([x3], m), ratio)[0]),
                     "acc_diff_1_minus_3": fmt(acc[0]), "acc_diff_ci_low": fmt(acc[1]), "acc_diff_ci_high": fmt(acc[2]),
                     "share_correctness_differs": fmt(fl[0]), "correctness_differs_ci_low": fmt(fl[1]), "correctness_differs_ci_high": fmt(fl[2]),
                     "share_final_answer_differs": fmt(da[0]), "answer_differs_ci_low": fmt(da[1]), "answer_differs_ci_high": fmt(da[2]),
                     "questions_correctness_differs": int((flip * m).sum()), "questions_answer_differs": int((diff_ans * m).sum())})
    return rows


def _wrong(d: Data, c: int):
    return [d.cls[(c, qid)] for qid in d.qids if not d.rec[(c, qid)]["correct"]]


def table_decomposition(d: Data) -> tuple[list[dict], list[dict], list[dict]]:
    """cells, input causes, first deviation stages for conditions 1, 2, 4, 5."""
    cells, causes, stages = [], [], []
    for c in DECOMP_CONDITIONS:
        allc = [d.cls[(c, qid)] for qid in d.qids]
        n = len(allc)
        k = Counter(x["cell"] for x in allc)
        wrong = n - k["correct"] - k["lucky_correct"]
        for cell in ("correct", "lucky_correct", "input_only", "agent_only", "both"):
            cells.append({"condition": c, "cell": cell, "runs": k[cell], "share_of_all_runs": fmt(k[cell] / n),
                          "share_of_wrong_runs": fmt(k[cell] / wrong) if cell in ("input_only", "agent_only", "both") and wrong else ""})
        inp = [x for x in allc if x["input_error"]]
        cc = Counter((x["input_cause"] or {}).get("category") for x in inp)
        for cause in CAUSES:
            causes.append({"condition": c, "input_cause": cause, "runs": cc[cause],
                           "share_of_input_error_runs": fmt(cc[cause] / len(inp)) if inp else ""})
        causes.append({"condition": c, "input_cause": "(all input-error runs)", "runs": len(inp), "share_of_input_error_runs": 1.0 if inp else ""})
        ag = [x for x in allc if x["agent_error"]]
        sc = Counter(x["first_deviation_stage_name"] for x in ag)
        for st in STAGES:
            stages.append({"condition": c, "first_deviation": st, "runs": sc[st], "share_of_agent_error_runs": fmt(sc[st] / len(ag)) if ag else ""})
        stages.append({"condition": c, "first_deviation": "(all agent-error runs)", "runs": len(ag), "share_of_agent_error_runs": 1.0 if ag else ""})
        fk = Counter(x["fail_kind"] for x in allc if x["status"] == "exec_fail")
        stages.append({"condition": c, "first_deviation": "(execution failures: " + ", ".join(f"{a}={b}" for a, b in sorted(fk.items())) + ")",
                       "runs": sum(fk.values()), "share_of_agent_error_runs": ""})
    return cells, causes, stages


def table_level_depth(d: Data) -> tuple[list[dict], list[dict]]:
    lv_rows, depth_rows = [], []
    buckets = {"1": lambda x: x == 1, "2": lambda x: x == 2, "3": lambda x: x == 3, "4": lambda x: x == 4,
               "5": lambda x: x == 5, "6-9": lambda x: x >= 6}
    for c in DECOMP_CONDITIONS:
        xc = d.correct(c)
        groups = [(lv, d.level == lv) for lv in ("L1", "L2", "L3", "L4", "L5")] + \
                 [(f"gold_calls {k}", f(d.depth)) for k, f in buckets.items()]
        for name, m in groups:
            p, lo, hi = d.boot(d.group_stats([xc], m), ratio)
            ag = [d.cls[(c, qid)] for qid, mm in zip(d.qids, m, strict=True) if mm and d.cls[(c, qid)]["agent_error"]]
            sc = Counter(x["first_deviation_stage_name"] for x in ag)
            row = {"condition": c, "group": name, "n": int(m.sum()), "correct": int((xc * m).sum()), "accuracy": fmt(p),
                   "ci_low": fmt(lo), "ci_high": fmt(hi), "agent_error_runs": len(ag),
                   "budget_exceeded": sum(1 for qid, mm in zip(d.qids, m, strict=True) if mm and d.rec[(c, qid)]["fail_kind"] == "budget_exceeded"),
                   **{f"first_{s}": sc[s] for s in STAGES}}
            (lv_rows if name.startswith("L") else depth_rows).append(row)
    return lv_rows, depth_rows


def table_injection_correction(d: Data) -> tuple[list[dict], list[dict]]:
    """Effects of conditions 6-8 and 9-11, restricted to the questions whose answer the box change really changes."""
    bd = d.box_dep
    from sarqa.grading import value_matches

    def right(q, key):
        return value_matches(q["reference_answers"][key], q["gold_answer"], q["answer_type"])

    det_wrong = np.array([not right(q, "detected") for q in d.q]) & bd
    rows, checks = [], []
    for kind, cond in (("miss", 6), ("fp", 7), ("loc", 8)):
        changed = np.array([bool(q["answer_changed"][kind]) for q in d.q]) & bd
        for name, m in (("box_dependent (all)", bd), ("answer changed by the injection", changed), ("answer not changed", bd & ~changed)):
            r = paired_row(d, 1, cond, "x", m, "")
            rows.append({"effect": f"injection {kind}", "condition_pair": f"1 -> {cond}", "questions": name, "n": r["n"],
                         "acc_before": r["acc_A"], "acc_after": r["acc_B"], "change_after_minus_before": fmt(
                             None if r["diff_A_minus_B"] == "" else -float(r["diff_A_minus_B"])),
                         "ci_low": fmt(None if r["ci_high"] == "" else -float(r["ci_high"])),
                         "ci_high": fmt(None if r["ci_low"] == "" else -float(r["ci_low"]))})
        checks.append({"item": f"questions with answer changed by injection ({kind})", "expected_PROTOCOL": EXPECTED[f"answer_changed_{kind}"],
                       "actual": int(changed.sum())})
    checks.append({"item": "detected answer wrong (box_dependent)", "expected_PROTOCOL": EXPECTED["detected_wrong"], "actual": int(det_wrong.sum())})
    for kind, cond in (("miss", 9), ("fp", 10), ("loc", 11)):
        rec = np.array([right(q, f"corrected_{kind}") for q in d.q]) & det_wrong
        for name, m in (("box_dependent (all)", bd), ("detected wrong and recoverable", rec), ("detected wrong, not recoverable", det_wrong & ~rec)):
            r = paired_row(d, cond, 2, "x", m, "")
            rows.append({"effect": f"correction {kind}", "condition_pair": f"2 -> {cond}", "questions": name, "n": r["n"],
                         "acc_before": r["acc_B"], "acc_after": r["acc_A"], "change_after_minus_before": r["diff_A_minus_B"],
                         "ci_low": r["ci_low"], "ci_high": r["ci_high"]})
        checks.append({"item": f"recoverable by correction ({kind})", "expected_PROTOCOL": EXPECTED[f"recoverable_{kind}"], "actual": int(rec.sum())})
    # consistency between the recorded runs and the question file: input errors of the runs
    for kind, cond in (("miss", 6), ("fp", 7), ("loc", 8)):
        n_in = sum(d.cls[(cond, qid)]["input_error"] for qid in d.qids)
        changed = int(sum(bool(q["answer_changed"][kind]) and q["box_dependent"] for q in d.q))
        checks.append({"item": f"input_error runs of condition {cond} = answer_changed ({kind})", "expected_PROTOCOL": changed, "actual": n_in})
    n_det = sum(d.cls[(2, qid)]["input_error"] for qid in d.qids)
    checks.append({"item": "input_error runs of condition 2 = detected wrong", "expected_PROTOCOL": int(det_wrong.sum()), "actual": n_det})
    for kind, cond in (("miss", 9), ("fp", 10), ("loc", 11)):
        wrong_after = int(sum(not right(q, f"corrected_{kind}") for q in d.q if q["box_dependent"]))
        checks.append({"item": f"input_error runs of condition {cond} = corrected answer wrong", "expected_PROTOCOL": wrong_after,
                       "actual": sum(d.cls[(cond, qid)]["input_error"] for qid in d.qids)})
    return rows, checks


def table_method(d: Data) -> list[dict]:
    rows = []
    ms = d.masks()
    for name in ("all", "box_dependent"):
        m = ms[name]
        xs = {c: d.correct(c) for c in (1, 2, 4, 5)}
        stats = d.group_stats([xs[1], xs[2], xs[4], xs[5]], m)
        for label, f in (("stepwise accuracy drop label->detected (cond 1 - cond 2)", lambda S: (S[:, 0] - S[:, 1]) / S[:, -1]),
                         ("batch accuracy drop label->detected (cond 4 - cond 5)", lambda S: (S[:, 2] - S[:, 3]) / S[:, -1]),
                         ("difference of the drops (1->2) - (4->5)", lambda S: (S[:, 0] - S[:, 1] - S[:, 2] + S[:, 3]) / S[:, -1]),
                         ("batch minus stepwise, label (cond 4 - cond 1)", lambda S: (S[:, 2] - S[:, 0]) / S[:, -1]),
                         ("batch minus stepwise, detected (cond 5 - cond 2)", lambda S: (S[:, 3] - S[:, 1]) / S[:, -1])):
            p, lo, hi = d.boot(stats, f)
            rows.append({"subset": name, "n": int(m.sum()), "quantity": label, "value": fmt(p), "ci_low": fmt(lo), "ci_high": fmt(hi)})
    for a, b in ((1, 4), (2, 5)):
        for name in ("all", "box_dependent"):
            r = paired_row(d, a, b, name, ms[name], "method comparison")
            rows.append({"subset": name, "n": r["n"], "quantity": f"accuracy cond {a} - cond {b} (paired)", "value": r["diff_A_minus_B"],
                         "ci_low": r["ci_low"], "ci_high": r["ci_high"]})
    return rows


def table_failures(d: Data) -> list[dict]:
    rows = []
    for c in CONDITIONS:
        rs = [d.rec[(c, qid)] for qid in d.qids]
        k = Counter(r["fail_kind"] for r in rs if r["status"] == "exec_fail")
        n = len(rs)
        rows.append({"condition": c, "method": rs[0]["method"], "input": rs[0]["input"], "runs": n,
                     "correct": sum(r["correct"] for r in rs), "accuracy": fmt(sum(r["correct"] for r in rs) / n),
                     "exec_fail": sum(k.values()), "exec_fail_rate": fmt(sum(k.values()) / n),
                     "budget_exceeded": k["budget_exceeded"], "budget_exceeded_rate": fmt(k["budget_exceeded"] / n),
                     "format_error": k["format_error"], "plan_format_error": k["plan_format_error"],
                     "other_fail": sum(v for kk, v in k.items() if kk not in ("budget_exceeded", "format_error", "plan_format_error")),
                     "mean_tool_calls": fmt(sum(r["tool_calls"] for r in rs) / n, 2),
                     "mean_llm_calls": fmt(sum(r["llm_calls"] for r in rs) / n, 2),
                     "mean_wall_s": fmt(sum(r["wall_ms"] for r in rs) / n / 1000, 1),
                     "unit_only_fix": sum(bool(r["unit_only_fix"]) for r in rs)})
    return rows


# ---------------------------------------------------------------- classification with the frozen classifier

def classify_all_to(runs_dir: Path, questions: list[dict], split: str, out_file: Path, ctx=None) -> list[dict]:
    """Same procedure as `sarqa classify`, but the result goes to `out_file`, not into the run folder."""
    from sarqa.classify import classify as CL
    from sarqa.classify import stages
    from sarqa.run.conditions import Condition, ProviderPool
    from sarqa.tools import default_context

    ctx = ctx or default_context()
    by_qid = {q["qid"]: q for q in questions}
    pool, cache, out = ProviderPool(split), {}, []
    for rec in load_records(runs_dir):
        q = by_qid[rec["qid"]]
        provider = pool.get(Condition(rec["condition"], rec["method"], rec["input"], rec["repeat"]))
        key = (rec["qid"], rec["input"])
        if key not in cache:
            cache[key] = stages.expected_runs(q, provider, ctx)
        out.append(CL.classify_run(rec, q, provider, ctx, cache[key]))
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        f.writelines(json.dumps(c, ensure_ascii=False) + "\n" for c in out)
    return out


# ---------------------------------------------------------------- output

def write_csv(path: Path, rows: list[dict]) -> None:
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, keys)
        w.writeheader()
        w.writerows(rows)


def md_table(rows: list[dict], cols: list[str] | None = None) -> str:
    cols = cols or list(dict.fromkeys(k for r in rows for k in r))
    return "\n".join(["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)] +
                     ["| " + " | ".join(str(r.get(c, "")) for c in cols) + " |" for r in rows])


def run(runs_dir: Path, questions_path: Path, out: Path, split: str = "test") -> dict:
    recs = load_records(runs_dir)
    questions = json.loads(Path(questions_path).read_text(encoding="utf-8"))["questions"]
    out.mkdir(parents=True, exist_ok=True)
    classified = classify_all_to(runs_dir, questions, split, out / "classified.jsonl")
    d = Data(recs, questions, classified)
    tables = {}
    tables["failures_by_condition"] = table_failures(d)
    tables["accuracy_by_condition"] = table_accuracy(d)
    tables["paired_comparisons"] = table_paired(d)
    tables["noise_cond1_vs_cond3"] = table_noise(d)
    tables["decomposition_cells"], tables["decomposition_input_causes"], tables["decomposition_first_deviation"] = table_decomposition(d)
    tables["by_level"], tables["by_depth"] = table_level_depth(d)
    tables["injection_correction_effects"], tables["consistency_checks"] = table_injection_correction(d)
    tables["method_comparison"] = table_method(d)
    for name, rows in tables.items():
        write_csv(out / f"{name}.csv", rows)
    return tables


def summary_md(tables: dict, runs_dir: Path, out: Path) -> str:
    intro = (f"입력: `{runs_dir}` (3,960건), 분류는 freeze-v1의 분류기를 그대로 사용(`classified.jsonl`). 신뢰구간: 장면 묶음 23개 단위 "
             f"부트스트랩 B={B:,}, 시드 {SEED}, 95% 백분위 구간. 모든 비교는 같은 문항끼리 짝지음.")
    L = ["# 본 실행 분석 요약 (숫자만, 해석 없음)", "", intro, ""]
    sec = [("조건별 실행 요약", "failures_by_condition", None),
           ("1. 조건별 정확도와 95% 구간 (전체 360 / box_dependent 304 / 아닌 것 56)", "accuracy_by_condition", None),
           ("2. 주 비교 10건과 위약 대조 6건 (A − B)", "paired_comparisons", ["comparison", "role", "subset", "n", "acc_A", "acc_B", "diff_A_minus_B", "ci_low", "ci_high", "only_A_correct", "only_B_correct"]),
           ("3. 잡음 수준: 조건 1 대 3", "noise_cond1_vs_cond3", None),
           ("4a. 오답 분해: 칸", "decomposition_cells", None),
           ("4b. 입력 오류 원인", "decomposition_input_causes", None),
           ("4c. 에이전트 오류의 첫 이탈 단계", "decomposition_first_deviation", None),
           ("5a. 질문 유형별", "by_level", ["condition", "group", "n", "correct", "accuracy", "ci_low", "ci_high", "agent_error_runs", "budget_exceeded"] + [f"first_{s}" for s in STAGES]),
           ("5b. 호출 깊이(gold_calls)별", "by_depth", ["condition", "group", "n", "correct", "accuracy", "ci_low", "ci_high", "agent_error_runs", "budget_exceeded"] + [f"first_{s}" for s in STAGES]),
           ("6. 주입·수정 효과", "injection_correction_effects", None),
           ("6b. 기대와의 일치 확인", "consistency_checks", None),
           ("7. 방법 비교", "method_comparison", None)]
    for title, key, cols in sec:
        L += [f"## {title}", "", md_table(tables[key], cols), ""]
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--runs", default="outputs/runs")
    p.add_argument("--questions", default="data/questions/test.json")
    p.add_argument("--out", default="outputs/analysis")
    p.add_argument("--split", default="test")
    a = p.parse_args(argv)
    tables = run(Path(a.runs), Path(a.questions), Path(a.out), a.split)
    (Path(a.out) / "summary.md").write_text(summary_md(tables, Path(a.runs), Path(a.out)), encoding="utf-8")
    print(f"wrote {len(tables)} tables and summary.md to {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

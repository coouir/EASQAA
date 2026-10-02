"""Group bootstrap statistics and the human-sample split of the main-run analysis (synthetic data)."""

import csv
import json

import numpy as np

from sarqa.analysis import main_run as M
from sarqa.analysis import main_run_human as H


def make_data(n_groups=6, per_group=10):
    qs, recs = [], []
    rng = np.random.default_rng(1)
    for g in range(n_groups):
        for i in range(per_group):
            qid = f"T-L1-{g * per_group + i:03d}"
            qs.append({"qid": qid, "scene_group": f"G{g}", "box_dependent": i % 5 != 0, "level": "L1", "gold_calls": 1})
            for c in (1, 2):
                ok = bool(rng.random() < (0.9 if c == 1 else 0.6))
                recs.append({"condition": c, "qid": qid, "correct": ok, "status": "ok",
                             "answer": {"value": 3 if ok else 4, "unit": "ships"}})
    return M.Data(recs, qs)


def test_accuracy_point_is_the_pooled_ratio_and_the_interval_brackets_it():
    d = make_data()
    x = d.correct(1)
    p, lo, hi = d.boot(d.group_stats([x], np.ones(len(x), bool)), M.ratio)
    assert abs(p - x.mean()) < 1e-12 and lo <= p <= hi


def test_paired_difference_uses_the_same_questions_and_is_deterministic():
    d, d2 = make_data(), make_data()
    row = M.paired_row(d, 1, 2, "all", d.masks()["all"], "main")
    assert row["n"] == 60 and row["both_correct"] + row["only_A_correct"] + row["only_B_correct"] + row["both_wrong"] == 60
    assert abs(row["diff_A_minus_B"] - (d.correct(1) - d.correct(2)).mean()) < 1e-4
    assert row == M.paired_row(d2, 1, 2, "all", d2.masks()["all"], "main")          # fixed seed: same interval
    assert row["ci_low"] <= row["diff_A_minus_B"] <= row["ci_high"]


def test_resampling_is_over_scene_groups_not_questions():
    d = make_data(n_groups=6, per_group=10)
    assert d.idx.shape == (M.B, 6) and d.idx.max() == 5 and len(d.groups) == 6
    stats = d.group_stats([d.correct(1)], np.ones(60, bool))
    assert stats.shape == (6, 2) and stats[:, 1].tolist() == [10.0] * 6


def test_a_difference_of_drops_statistic():
    d = make_data()
    stats = d.group_stats([d.correct(1), d.correct(2), d.correct(1), d.correct(2)], np.ones(60, bool))
    p, lo, hi = d.boot(stats, lambda S: (S[:, 0] - S[:, 1] - S[:, 2] + S[:, 3]) / S[:, -1])
    assert p == 0 and lo == 0 and hi == 0                       # identical drops cancel exactly


def test_empty_subset_gives_no_numbers():
    d = make_data()
    assert d.boot(d.group_stats([d.correct(1)], np.zeros(60, bool)), M.ratio) == (None, None, None)


def _classified():
    out, i = [], 0
    for cond, n in ((1, 40), (2, 80), (4, 40), (5, 80)):
        for k in range(n):
            out.append({"run_id": f"r{i:04d}", "qid": f"T-{i:03d}", "condition": cond, "level": "L1", "correct": False,
                        "cell": "agent_only" if k % 2 else "input_only", "first_deviation_stage_name": "tool_selection" if k % 2 else None,
                        "input_cause": None if k % 2 else {"category": "miss"}})
            i += 1
    return out


def test_human_sample_is_150_centred_on_conditions_2_and_5_and_reproducible():
    c = _classified()
    s = H.sample(c)
    assert len(s) == 150 and s == H.sample(c)
    by = {k: sum(x["condition"] == k for x in s) for k in (1, 2, 4, 5)}
    assert by[2] + by[5] == 120 and by[1] + by[4] == 30


def test_form_has_the_gold_solution_and_no_automatic_label_while_the_key_is_apart(tmp_path):
    c = _classified()[:4] + _classified()[60:64]
    runs = tmp_path / "runs"
    runs.mkdir()
    q = {"qid": "x", "text_ko": "몇 척?", "gold_answer": 3, "unit": "ships", "gold_calls": 1,
         "program": {"steps": [{"id": "s1", "op": "detect_ships", "args": {"image_id": "IMG"}}], "answer": "$s1.count"},
         "intermediates": {"label": {"s1": {"count": 3}}}}
    recs, qs = [], []
    for x in c:
        recs.append({"run_id": x["run_id"], "qid": x["qid"], "condition": x["condition"], "method": "stepwise", "input": "detected",
                     "repeat": 0, "level": "L1", "correct": False, "status": "ok", "fail_kind": None, "reachable_answer": 3,
                     "answer": {"value": 4, "unit": "ships"}, "interpretation": {"target": "ship_count"}, "turns": [], "decisions": []})
        qs.append({**q, "qid": x["qid"]})
    (runs / "condition_01.jsonl").write_text("\n".join(json.dumps(r) for r in recs) + "\n")
    res = H.build(runs, qs, c, tmp_path / "out", images=False)
    assert res["sampled"] == 8
    form = (tmp_path / "out/human_sample/human_sample.csv").read_text(encoding="utf-8-sig")
    page = (tmp_path / "out/human_sample/human_sample.html").read_text(encoding="utf-8")
    assert "gold program" in form and "$s1.count" in form and "auto_" not in form and "auto_" not in page
    assert "selected" not in page and "input_only</option>" in page            # only the choice list, nothing pre-selected
    with open(tmp_path / "out/human_sample_KEY/human_sample_key.csv", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 8 and {"auto_cell", "auto_first_deviation", "auto_input_cause"} <= set(rows[0])

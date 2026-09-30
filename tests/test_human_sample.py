import csv
import json
from collections import Counter

import pytest

from sarqa.analysis import cli as acli
from sarqa.analysis.human_sample import (
    HUMAN_COLUMNS,
    agreement,
    build,
    kappa,
    key_row,
    stratify,
    stratum_of,
)


def row(i, cell="agent_only", stage="calculation", cause=None, correct=False):
    return {"run_id": f"r{i:04d}", "qid": f"D-L1-{i:03d}", "condition": 2, "method": "stepwise", "input": "detected",
            "level": "L1", "template": "l1_total_count", "correct": correct, "cell": cell,
            "first_deviation_stage_name": stage, "input_cause": {"category": cause} if cause else None}


def population():
    rows, i = [], 0
    for cell, stage, cause, n in (("agent_only", "calculation", None, 60), ("agent_only", "tool_selection", None, 30),
                                  ("input_only", None, "miss", 40), ("input_only", None, "fp", 8),
                                  ("both", "interpretation", "loc", 3), ("agent_only", "unknown", None, 2)):
        for _ in range(n):
            rows.append(row(i, cell, stage, cause))
            i += 1
    rows += [row(1000 + k, "correct", None, None, correct=True) for k in range(20)]
    return rows


def test_sample_respects_the_cap_the_minimum_per_stratum_and_is_deterministic():
    pop = population()
    s = stratify(pop, cap=60, min_per=5, seed=1)
    assert len(s) == 60 and s == stratify(pop, cap=60, min_per=5, seed=1)
    assert s != stratify(pop, cap=60, min_per=5, seed=2)
    counts = Counter(stratum_of(c) for c in s)
    sizes = Counter(stratum_of(c) for c in pop if not c["correct"])
    assert all(counts[k] >= min(5, sizes[k]) for k in sizes)               # every stratum has its minimum (or all)
    assert counts[("both", "interpretation", "loc")] == 3 and counts[("agent_only", "unknown", None)] == 2
    assert counts[("agent_only", "calculation", None)] > counts[("input_only", None, "fp")]     # proportional rest
    assert all(not c["correct"] for c in s)


def test_a_small_population_is_taken_whole_and_the_cap_is_bounded():
    pop = [row(i) for i in range(10)]
    assert len(stratify(pop, cap=120)) == 10
    with pytest.raises(ValueError):
        stratify(pop, cap=151)
    many = [row(i, stage=f"s{i % 40}") for i in range(400)]                # 40 strata, cap 30 < 40 x min
    got = stratify(many, cap=30, min_per=5)
    assert len(got) == 30 and len({stratum_of(c) for c in got}) == 30


def test_kappa_and_agreement(tmp_path):
    assert kappa(["a", "b", "a", "b"], ["a", "b", "a", "b"]) == 1.0
    assert kappa(["a", "a"], ["a", "a"]) is None
    assert kappa(["a", "b", "a", "b"], ["b", "a", "b", "a"]) == -1.0
    rows = [row(i, cell=c, stage=s) for i, (c, s) in enumerate(
        [("agent_only", "calculation"), ("agent_only", "tool_selection"), ("input_only", None), ("both", "interpretation")])]
    with open(tmp_path / "key.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, list(key_row(rows[0])))
        w.writeheader()
        w.writerows(key_row(r) for r in rows)

    def human(name, labels):
        with open(tmp_path / name, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, ["run_id", *HUMAN_COLUMNS])
            w.writeheader()
            for r, (cell, stage) in zip(rows, labels, strict=True):
                w.writerow({"run_id": r["run_id"], "human_cell": cell, "human_first_deviation": stage,
                            "human_input_cause": "", "human_note": ""})

    human("h1.csv", [("agent_only", "calculation"), ("agent_only", "tool_selection"), ("input_only", "none"), ("both", "calculation")])
    human("h2.csv", [("agent_only", "calculation"), ("agent_only", "calculation"), ("input_only", "none"), ("both", "calculation")])
    res = agreement(tmp_path / "h1.csv", tmp_path / "key.csv", tmp_path / "h2.csv")
    assert res["n"] == 4 and res["fields"]["human_cell"]["agreement"] == 1.0
    assert res["fields"]["human_first_deviation"]["agreement"] == 0.75
    assert res["disagreements"] == [{"run_id": "r0003", "human_first_deviation": ("calculation", "interpretation")}]
    assert res["fields"]["human_first_deviation"]["kappa_between_humans"] is not None


def _recs(tmp_path, pop):
    d = tmp_path / "runs"
    d.mkdir()
    recs = [{"run_id": c["run_id"], "qid": c["qid"], "condition": 2, "method": "stepwise", "input": "detected", "repeat": 0,
             "level": "L1", "correct": False, "status": "ok", "fail_kind": None, "reachable_answer": 3,
             "answer": {"value": 4, "unit": "ships"}, "interpretation": {"target": "ship_count"},
             "turns": [{"turn": 1, "action": {"call_id": "c1", "tool": "detect_ships", "args_raw": {}}, "tool_output": "{}",
                        "reading": []}], "decisions": []} for c in pop]
    (d / "condition_02.jsonl").write_text("\n".join(json.dumps(r) for r in recs) + "\n")
    (d / "classified.jsonl").write_text("\n".join(json.dumps(c) for c in pop) + "\n")
    return d


def test_build_writes_forms_without_any_automatic_label_and_a_separate_key(tmp_path):
    pop = [row(i, "agent_only", "calculation") for i in range(6)] + [row(10 + i, "input_only", None, "miss") for i in range(6)]
    runs = _recs(tmp_path, pop)
    qs = [{"qid": c["qid"], "text_ko": "몇 척인가?", "gold_answer": 3, "unit": "ships"} for c in pop]
    res = build(runs, qs, "dev", tmp_path / "out", cap=8, seed=0, images=False)
    assert res["sampled"] == 8
    sheet = (tmp_path / "out" / "human_sample.csv").read_text(encoding="utf-8-sig")
    html_ = (tmp_path / "out" / "human_sample.html").read_text(encoding="utf-8")
    for secret in ("agent_only", "input_only", "calculation", "auto_"):
        assert secret not in sheet                                               # the CSV has no automatic label
    assert "auto_" not in html_ and "selected" not in html_                     # nothing is pre-selected
    assert html_.count("<option>agent_only</option>") == 8                       # the choice list only, once per card
    assert "</section>" in html_ and html_.count("<section") == 8
    key = (tmp_path / "out" / "human_sample_key.csv").read_text(encoding="utf-8-sig")
    assert "auto_cell" in key and "agent_only" in key
    assert "몇 척인가?" in html_ and "Download CSV" in html_


def test_analyze_entry_lists_subcommands_and_defers_the_planned_ones(capsys):
    assert acli.main([]) == 0 and "human-sample" in capsys.readouterr().out
    assert acli.main(["metrics"]) == 2 and "after the freeze" in capsys.readouterr().out


def test_sarqa_analyze_is_registered_in_the_frozen_cli(capsys):
    from sarqa.cli import main

    assert main(["analyze"]) == 0 and "subcommands" in capsys.readouterr().out
    assert main(["analyze", "figures"]) == 2


def test_runs_option_works_before_and_after_the_subcommand():
    p = acli.build_parser()
    assert p.parse_args(["--runs", "a", "human-sample"]).runs == "a"
    assert p.parse_args(["human-sample", "--runs", "b"]).runs == "b"
    assert p.parse_args(["human-sample"]).runs == "outputs/runs/"

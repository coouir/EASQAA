import csv
import importlib.util
from pathlib import Path

import pytest

from sarqa.analysis import human_check, human_compare, unknown_causes

SRC = Path(__file__).resolve().parents[1] / "src" / "sarqa" / "analysis"


def _load_figure2():
    spec = importlib.util.spec_from_file_location("figure2", SRC / "figure2.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_residual_keeps_boxes_above_loc_iou():
    labels = [(0, 0, 100, 100), (300, 300, 340, 340)]
    received = [(5, 5, 100, 100)]            # IoU 0.9: not a location error, stays as drawn; second label missed
    r = unknown_causes.residual(received, labels)
    assert r["n_fixed"] == 2
    assert [p[2] for p in r["pairs_below_1"]] == [0.902]
    assert r["unmatched_fixed"] == [] and r["unmatched_labels"] == []


def test_balanced_order_prefixes_are_even():
    items = [{"run_id": f"{s}{i}", "s": s} for s, n in (("a", 10), ("b", 6), ("c", 1)) for i in range(n)]
    order = human_check.balanced_order(items, lambda x: x["s"], seed=1)
    assert len(order) == 17 and len({x["run_id"] for x in order}) == 17
    first6 = [x["s"] for x in order[:6]]
    assert sorted(first6) == ["a", "a", "b", "b", "c", "a"] or {first6.count(s) for s in "ab"} == {2, 3}
    assert "c" in [x["s"] for x in order[:3]]
    assert order == human_check.balanced_order(items, lambda x: x["s"], seed=1)


def test_eligible_drops_input_only():
    rows = [{"run_id": "1", "auto_cell": "input_only", "auto_first_deviation": "none"},
            {"run_id": "2", "auto_cell": "both", "auto_first_deviation": "tool_selection"}]
    assert [r["run_id"] for r in human_check.eligible(rows)] == ["2"]


def test_guide_has_rules_and_all_stages():
    g = human_check.guide_html({})
    for word in ("가장 이른 턴", "무해한 이탈", "대상, 영역, 필터, 분기 조건", "구성 예"):
        assert word in g
    assert "<select" not in g


def test_compare_uses_labelled_count_only():
    key = [{"run_id": str(i), "auto_first_deviation": s, "condition": "1", "qid": f"q{i}"}
           for i, s in enumerate(["interpretation", "tool_selection", "tool_selection", "calculation"])]
    human = [{"run_id": "0", "human_first_deviation": "interpretation", "human_note": ""},
             {"run_id": "1", "human_first_deviation": "tool_selection", "human_note": ""},
             {"run_id": "2", "human_first_deviation": "calculation", "human_note": "x"},
             {"run_id": "3", "human_first_deviation": "", "human_note": ""}]
    r = human_compare.compare(human, key)
    assert r["n"] == 3 and r["agree"] == 2
    assert [d["run_id"] for d in r["disagreements"]] == ["2"]
    assert r["confusion"][("calculation", "tool_selection")] == 1
    assert "labelled runs: 3" in human_compare.summary(r)


def test_kappa_perfect_and_chance():
    assert human_compare.kappa(list("aabb"), list("aabb")) == 1.0
    assert human_compare.kappa(list("abab"), list("aabb")) == 0.0


def test_figure2_reads_csv_and_refuses_undrawn_stage(tmp_path):
    f2 = _load_figure2()
    cells = tmp_path / "c.csv"
    cells.write_text("condition,cell,runs,share_of_all_runs,share_of_wrong_runs\n1,agent_only,75,0.2083,1.0\n", encoding="utf-8-sig")
    assert f2.cell_shares(f2.read_csv(cells))[1]["agent_only"] == pytest.approx(20.83)
    dev = tmp_path / "d.csv"
    dev.write_text("condition,first_deviation,runs,share_of_agent_error_runs\n1,planning_branch,3,0.04\n", encoding="utf-8-sig")
    with pytest.raises(SystemExit):
        f2.stage_shares(f2.read_csv(dev))


def test_figure2_draws_when_matplotlib_and_font_exist(tmp_path):
    pytest.importorskip("matplotlib")
    f2 = _load_figure2()
    ana = tmp_path / "a"
    ana.mkdir()
    with open(ana / "decomposition_cells.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["condition", "cell", "runs", "share_of_all_runs", "share_of_wrong_runs"])
        for c in f2.CONDITIONS:
            for cell in ("input_only", "both", "agent_only"):
                w.writerow([c, cell, 1, 0.1, ""])
    with open(ana / "decomposition_first_deviation.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["condition", "first_deviation", "runs", "share_of_agent_error_runs"])
        for c in f2.CONDITIONS:
            w.writerows([[c, "interpretation", 1, 0.5], [c, "tool_selection", 1, 0.5]])
    try:
        paths = f2.make(ana, tmp_path / "out")
    except SystemExit as e:
        pytest.skip(str(e))
    assert all(p.exists() for p in paths)

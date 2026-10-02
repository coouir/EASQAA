import csv
import json
from pathlib import Path

import pytest

from sarqa.analysis import ai_check


def fake_run(i, cond, stage):
    return {"run_id": f"r{i:04d}", "qid": f"T-{i}", "condition": cond, "agent_error": True, "first_deviation_stage_name": stage,
            "cell": "agent_only", "input_cause": None}


def fake_population():
    pop, i = [], 0
    for cond, stage, n in [(1, "interpretation", 40), (1, "tool_selection", 50), (1, "exec_fail", 1), (2, "interpretation", 30),
                           (2, "tool_selection", 25), (4, "calculation", 6), (4, "result_reading", 2), (5, "exec_fail", 12)]:
        for _ in range(n):
            pop.append(fake_run(i, cond, stage))
            i += 1
    return pop


def test_allocate_minimum_total_and_cap():
    sizes = {(1, "a"): 100, (1, "b"): 2, (2, "a"): 1, (2, "b"): 30, (4, "c"): 3}
    take = ai_check.allocate(sizes, total=40)
    assert sum(take.values()) == 40
    assert take[(1, "b")] == 2 and take[(2, "a")] == 1 and take[(4, "c")] == 3      # all of a stratum below 3 (or exactly 3)
    assert all(take[k] <= sizes[k] for k in sizes) and all(take[k] >= min(3, sizes[k]) for k in sizes)
    assert take[(1, "a")] > take[(2, "b")]                                        # proportional to the room


def test_draw_is_deterministic_and_hits_the_target():
    pop = fake_population()
    a, table = ai_check.draw(pop)
    b, _ = ai_check.draw(list(reversed(pop)))
    assert [c["run_id"] for c in a] == [c["run_id"] for c in b]
    assert len(a) == 100 and sum(v[1] for v in table.values()) == 100
    assert min(v[1] for v in table.values()) >= 1 and table[(1, "exec_fail")] == (1, 1)
    assert [c["run_id"] for c in a] != sorted(c["run_id"] for c in a)           # random judging order
    assert len({c["run_id"] for c in a}) == 100


def test_population_excludes_first_sample_and_refuses_missing_stage():
    pop = fake_population()
    got = ai_check.population(pop, {"r0000", "r0001"})
    assert len(got) == len(pop) - 2 and all(c["run_id"] not in {"r0000", "r0001"} for c in got)
    bad = pop + [dict(fake_run(9999, 1, None))]
    with pytest.raises(SystemExit):
        ai_check.population(bad, set())


def test_assessor_material_carries_no_label_or_stratum():
    labelled = [dict(fake_run(i, 1, f"STAGE_SENTINEL_{i % 3}")) for i in range(30)]
    picked, _ = ai_check.draw(labelled, total=10)
    row = {"run_id": picked[0]["run_id"], "qid": "T-1", "condition": 1, "method": "stepwise", "input": "label", "level": "L1",
           "question": "q", "gold_answer": 1, "unit": "ships", "answer_reachable_from_received_boxes": 1, "agent_answer": "1",
           "fail_kind": "", "image": "", "agent_record": "[interpretation] {}"}
    extra = {"interpretation": "{}", "programs": "gold", "received": "on received"}
    text = ai_check.page([ai_check.card(1, 1, row, extra)], 1)
    assert "STAGE_SENTINEL" not in text and "auto_" not in text and "ai_check2_KEY" not in text and "stratum" not in text.lower()
    assert "guide.html" in text and "human_first_deviation" in text and "ai_check2_v1" in text


@pytest.mark.data
def test_build_writes_only_label_free_files(tmp_path):
    root = Path(__file__).resolve().parents[1]
    classified = [json.loads(x) for x in (root / "outputs/analysis/classified.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    questions = json.loads((root / "data/questions/test.json").read_text(encoding="utf-8"))["questions"]
    with open(root / "outputs/analysis/human_sample/human_order.csv", encoding="utf-8-sig") as f:
        first = {r["run_id"] for r in csv.DictReader(f)}
    guide = root / "outputs/analysis/human_sample/guide.html"
    res = ai_check.build(root / "outputs/runs", questions, classified, first, guide, tmp_path, images=False)
    assert res["sample"] == 100
    form = tmp_path / "ai_check2"
    assert sorted(p.name for p in form.iterdir()) == ["check.html", "check_order.csv", "guide.html"]
    assert (form / "guide.html").read_bytes() == guide.read_bytes()
    with open(form / "check_order.csv", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    assert list(rows[0]) == ["rank", "run_id"] and not {r["run_id"] for r in rows} & first
    text = (form / "check.html").read_text(encoding="utf-8")
    assert "auto_" not in text and "stratum" not in text.lower() and "ai_check2_KEY" not in text
    key = tmp_path / "ai_check2_KEY" / "ai_check2_key.csv"
    with open(key, encoding="utf-8-sig") as f:
        assert {r["run_id"] for r in csv.DictReader(f)} == {r["run_id"] for r in rows}

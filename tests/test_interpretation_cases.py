import json

from sarqa.analysis.interpretation_cases import cases, render
from sarqa.questions.vocab import blank_interpretation

GOLD = blank_interpretation(target="max_length", unit="px", answer_type="float")
Q = {"qid": "D-L2-006", "template": "l2_longest_length", "text_ko": "가장 긴 선박은?", "gold_answer": 60.0,
     "gold_interpretation": GOLD}


def _rec(interp, run_id):
    return {"run_id": run_id, "qid": "D-L2-006", "condition": 1, "interpretation": interp,
            "answer": {"value": 60, "unit": "px"}, "fail_kind": None, "reachable_answer": 60.0}


def test_lists_only_interpretation_first_deviations_and_names_the_fields(tmp_path):
    wrong = {**GOLD, "target": "ship_count", "filters": [{"field": "noise", "cmp": ">", "threshold": 1}]}
    recs = [_rec(wrong, "a"), _rec(GOLD, "b")]
    (tmp_path / "condition_01.jsonl").write_text("\n".join(json.dumps(r) for r in recs) + "\n")
    cls = [{"run_id": "a", "qid": "D-L2-006", "condition": 1, "first_deviation_stage_name": "interpretation",
            "correct": True},
           {"run_id": "b", "qid": "D-L2-006", "condition": 1, "first_deviation_stage_name": "calculation",
            "correct": False}]
    (tmp_path / "classified.jsonl").write_text("\n".join(json.dumps(c) for c in cls) + "\n")
    items = cases(tmp_path, [Q])
    assert len(items) == 1 and items[0]["used"] == ["target"] and items[0]["unused"] == ["filters"]
    text = render(items, "x")
    assert "D-L2-006" in text and "가장 긴 선박은?" in text and "다른 필드 `target` (쓰임)" in text
    assert "정답값 60.0" in text

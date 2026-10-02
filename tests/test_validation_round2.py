from sarqa.analysis import human_compare, validation_round2


def test_confidence_reads_only_the_leading_tag():
    assert human_compare.confidence("[high] reason") == "high"
    assert human_compare.confidence("  [Medium] x") == "medium"
    assert human_compare.confidence("[low]") == "low"
    assert human_compare.confidence("reason [high]") == "none" and human_compare.confidence("") == "none"


def _rows():
    key = [{"run_id": str(i), "auto_first_deviation": s, "condition": c, "qid": f"q{i}"}
           for i, (s, c) in enumerate([("interpretation", "1"), ("tool_selection", "1"), ("tool_selection", "2"), ("calculation", "2")])]
    human = [{"run_id": "0", "human_first_deviation": "interpretation", "human_note": "[high] a"},
             {"run_id": "1", "human_first_deviation": "calculation", "human_note": "[low] b"},
             {"run_id": "2", "human_first_deviation": "tool_selection", "human_note": "[high] c"},
             {"run_id": "3", "human_first_deviation": "calculation", "human_note": "d"}]
    return human, key


def test_agreement_by_confidence_and_condition_and_exclusion():
    human, key = _rows()
    r = human_compare.compare(human, key)
    assert r["n"] == 4 and r["agree"] == 3
    conf = human_compare.agreement_by(r["done"], r["keyed"], lambda h, k: human_compare.confidence(h["human_note"]))
    assert conf == {"high": (2, 2), "low": (1, 0), "none": (1, 1)}
    cond = human_compare.agreement_by(r["done"], r["keyed"], lambda h, k: int(k["condition"]))
    assert cond == {1: (2, 1), 2: (2, 2)}
    assert human_compare.compare(human, key, frozenset({"1"}))["n"] == 3
    assert human_compare.compare(human, key)["n"] == 4          # default behaviour unchanged


def test_first_deviation_kind_and_top_cells():
    human, key = _rows()
    classified = {
        "1": {"first_deviation_stage": 2, "first_deviation_turn": 3, "first_deviation_stage_name": "tool_selection",
              "deviations": [{"stage": 2, "turn": 3, "kind": "missing_call", "harmless": False}]},
    }
    assert validation_round2.first_deviation_kind(classified["1"]) == "missing_call"
    assert validation_round2.first_deviation_kind({"first_deviation_stage": 0, "first_deviation_turn": None,
                                                   "first_deviation_stage_name": "exec_fail", "deviations": []}).startswith("(exec_fail")
    r = human_compare.compare(human, key)
    cells = validation_round2.disagreement_cells(r, classified, {"0": 1, "1": 2, "2": 3, "3": 4})
    assert [(c["ai"], c["auto"], c["n"], c["representative_ranks"]) for c in cells] == [("calculation", "tool_selection", 1, "2")]
    assert '"missing_call": 1' in cells[0]["auto_codes"]

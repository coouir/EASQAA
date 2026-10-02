"""Four places where the classifier did not follow SPEC §11 (issue #101). Fixtures are cut down from the runs that exposed them."""

from types import SimpleNamespace as NS

from sarqa.classify import classify, stages
from sarqa.classify.stages import ACall, Expected, Trace


def gold_call(call_id, tool, args, resolved, step_id="s1"):
    return NS(call_id=call_id, tool=tool, args=args, resolved_args=resolved, step_id=step_id, output={})


def expected(calls, decisions=()):
    res = NS(calls=list(calls), decisions=list(decisions))
    return Expected("gold", res, set(), {"steps": []})


# A1 (c9cebc5a3d56ad9d): an earlier calc failed, so the later call's references stayed unresolved ------------------------
def test_a1_unresolved_reference_with_the_gold_structure_is_not_wrong_args():
    gold = gold_call("c4", "spatial_query", {"image_id": "I", "query": "nearest_to", "ship_a": "$s3.result"},
                     {"image_id": "I", "query": "nearest_to", "ship_a": "s2"}, "s4")
    raw = {"image_id": "I", "query": "nearest_to", "ship_a": "$s3.result"}
    agent = ACall("c4", "spatial_query", raw, raw, {"error": "s3 has no field 'result'"}, 1, unresolved=True)
    trace = Trace("batch", calls=[agent])
    un, missing = stages._match(trace, expected([gold]))
    assert un == [] and missing == []
    assert stages.stage2(trace, expected([gold]), un, missing, True) == []


def test_a1_unresolved_reference_with_another_field_is_still_wrong_args():
    gold = gold_call("c4", "spatial_query", {"image_id": "I", "query": "nearest_to", "ship_a": "$s3.result"},
                     {"image_id": "I", "query": "nearest_to", "ship_a": "s2"}, "s4")
    raw = {"image_id": "I", "query": "nearest_to", "ship_a": "$s3.ship_ids"}
    agent = ACall("c4", "spatial_query", raw, raw, {"error": "x"}, 1, unresolved=True)
    trace = Trace("batch", calls=[agent])
    un, missing = stages._match(trace, expected([gold]))
    assert [d.kind for d in stages.stage2(trace, expected([gold]), un, missing, True)] == ["wrong_args"]


def test_a1_resolved_wrong_value_is_still_wrong_args():
    gold = gold_call("c1", "spatial_query", {"query": "nearest_to", "ship_a": "s2"}, {"query": "nearest_to", "ship_a": "s2"})
    agent = ACall("c1", "spatial_query", {"query": "nearest_to", "ship_a": "s1"}, {"query": "nearest_to", "ship_a": "s1"}, {}, 1)
    trace = Trace("stepwise", calls=[agent])
    un, missing = stages._match(trace, expected([gold]))
    assert [d.kind for d in stages.stage2(trace, expected([gold]), un, missing, True)] == ["wrong_args"]


# D1 (a3e99e958dad3a78, 1d220310b3ac1be1): the gold interpretation has a branch, the run never branched ------------------
def _branch_question():
    gi = {"target": "branch", "region": "full", "filters": [], "unit": "ships", "answer_type": "int",
          "branch": {"on": "max_length", "cmp": ">=", "threshold": 65, "then_target": "ship_count", "else_target": "ship_count",
                     "then_region": None, "else_region": None}}
    return {"has_branch": True, "gold_interpretation": gi, "unit": "ships", "answer_type": "int", "branch_spec": {"on": "max_length"},
            "box_dependent": True}


def _branch_record(decisions):
    interp = {"target": "ship_count", "region": "full", "filters": [], "branch": None, "unit": "ships", "answer_type": "int"}
    turns = [{"turn": 1, "kind": "step", "llm_output": {"decision": decisions[0]} if decisions else {}, "reading": [],
              "action": {"call_id": "c1", "tool": "spatial_query", "args_raw": {"query": "count"},
                         "args_resolved": {"query": "count"}}, "tool_output": '{"count": 2}'}]
    return {"method": "stepwise", "status": "ok", "turns": turns, "interpretation": interp, "answer": {"value": 2, "unit": "ships"},
            "decisions": decisions}


def test_d1_branch_question_without_any_decision_is_not_a_harmless_interpretation_mismatch():
    q = _branch_question()
    exps = [expected([gold_call("c1", "spatial_query", {"query": "count"}, {"query": "count"})],
                     [{"top_level": True, "chosen": "else"}])]
    devs, extras = classify.find_deviations(_branch_record([]), q, None, None, 2, exps)
    s1 = next(d for d in devs if d.stage == 1)
    assert not s1.harmless and "interp_record_mismatch" not in extras


def test_d1_with_a_branch_decision_the_record_mismatch_stays_harmless():
    q = _branch_question()
    dec = {"condition_from": "c1.count", "condition_value": 2, "threshold": 65, "cmp": ">=", "chosen": "else"}
    exps = [expected([gold_call("c1", "spatial_query", {"query": "count"}, {"query": "count"})],
                     [{"top_level": True, "chosen": "else"}])]
    devs, extras = classify.find_deviations(_branch_record([dec]), q, None, None, 2, exps)
    assert next(d for d in devs if d.stage == 1).harmless and extras["interp_record_mismatch"]


# D2 (1d1c462bb9c34b1f): an errored extra calc and no answer are not "the same value" --------------------------------------
def _calc(call_id, output, turn=1):
    return ACall(call_id, "calc", {"op": "count"}, {"op": "count"}, output, turn)


def test_d2_errored_extra_calc_without_an_answer_is_harmless():
    trace = Trace("batch", calls=[_calc("c3", {"error": "calc: list item must be a finite number"})], calc_turn=2)
    devs = stages.stage5(trace, expected([]), False, {"answer": None})
    assert [(d.kind, d.harmless) for d in devs] == [("extra_calc", True)]


def test_d2_extra_calc_whose_result_is_the_answer_is_still_used():
    trace = Trace("stepwise", calls=[_calc("c3", {"op": "count", "result": 4})])
    devs = stages.stage5(trace, expected([]), True, {"answer": {"value": 4, "unit": "ships"}})
    assert [(d.kind, d.harmless) for d in devs] == [("extra_calc", False)]


# E10 (53233d1ffcc8117a): a wrong decision value gets the same harmless test as a wrong reading ------------------------------
def _decision(value, chosen):
    return {"condition_from": "c1.scene", "condition_value": value, "threshold": "inshore", "cmp": "==", "chosen": chosen}


def _scene_trace(decisions):
    meta = ACall("c1", "get_metadata", {}, {}, {"scene": "offshore", "width": 800, "height": 800}, 1)
    return Trace("stepwise", calls=[meta], llm_decisions=[(i + 1, d) for i, d in enumerate(decisions)])


def _stage3(decisions):
    q = {"has_branch": True, "branch_spec": {"on": "scene"}}
    exps = [expected([], [{"top_level": True, "chosen": "else"}])]
    return stages.stage3(_scene_trace(decisions), {"answer": None}, q, exps)


def test_e10_superseded_wrong_decision_value_is_harmless():
    devs = _stage3([_decision({"scene": "inshore"}, "then"), _decision("offshore", "else")])
    assert [(d.kind, d.harmless) for d in devs] == [("decision_value_mismatch", True)]


def test_e10_wrong_value_that_still_chose_the_right_branch_is_harmless():
    devs = _stage3([_decision("coastal", "else")])
    assert [(d.kind, d.harmless) for d in devs] == [("decision_value_mismatch", True)]


def test_e10_final_wrong_value_that_chose_the_wrong_branch_is_a_deviation():
    devs = _stage3([_decision("offshore", "else"), _decision("inshore", "then")])
    assert [(d.kind, d.harmless) for d in devs] == [("decision_value_mismatch", False)]

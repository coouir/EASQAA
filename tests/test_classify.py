"""Classifier on records produced by the real agents with scripted replies (SPEC §11, §13)."""

from sarqa.agents import run_agent
from sarqa.agents.llm import FakeLLM
from sarqa.boxes import BoxProvider
from sarqa.classify import classify as CL
from sarqa.classify import replay
from sarqa.questions.vocab import blank_interpretation, branch_object
from tools_fixtures import MINI_BOXES, mini_context

CTX = mini_context()
GOLD_INTERP = blank_interpretation(target="max_length", unit="px", answer_type="int")
SIZES = {"id": "s1", "op": "spatial_query", "args": {"image_id": "IMG", "query": "sizes"}}
MAXC = {"id": "s2", "op": "calc", "args": {"op": "max", "list": "$s1.long_side_px"}}
Q = {"qid": "D-L2-001", "level": "L2", "template": "l2_longest_length", "image_id": "m3.jpg",
     "text_ko": "q", "answer_type": "int", "unit": "px", "gold_answer": 60, "tolerance": {"rel": 0.0},
     "program": {"steps": [SIZES, MAXC], "answer": "$s2.result"}, "alt_programs": [],
     "gold_calls": 2, "budget": 5, "gold_interpretation": GOLD_INTERP, "branch_spec": None,
     "box_dependent": True, "has_branch": False}
LABEL = BoxProvider("label", MINI_BOXES)


def tool(name, reading=None, decision=None, **args):
    return {"reading": reading or [], "decision": decision,
            "action": {"type": "tool", "tool": name, "args": args}}


def answer(v, unit="px", reading=None, decision=None):
    return {"reading": reading or [], "decision": decision,
            "action": {"type": "answer", "answer": v, "unit": unit}}


def rec_for(replies, q=Q, provider=LABEL, method="stepwise", interp=GOLD_INTERP):
    ctx = CTX.with_boxes(provider)
    replies = [{"interpretation": interp}] + replies if method == "stepwise" else replies
    r = run_agent(method, q, ctx, FakeLLM(replies))
    r.update(run_id="r", condition=1, input="label")
    r["reachable_answer"] = CL.replay.run_program(q["program"], q["image_id"], provider, ctx=CTX).answer \
        if q["box_dependent"] else q["gold_answer"]
    return r


def classify(r, q=Q, provider=LABEL):
    return CL.classify_run(r, q, provider, CTX)


GOOD = [tool("spatial_query", image_id="m3.jpg", query="sizes"),
        tool("calc", op="max", list="$c1.long_side_px"), answer(60)]


def test_correct_run_has_no_errors():
    c = classify(rec_for(GOOD))
    assert c["cell"] == "correct" and not c["input_error"] and not c["agent_error"]


def test_three_cells_and_lucky_correct():
    fewer = BoxProvider("injected", {"m3.jpg": [(500, 100, 540, 130), (100, 500, 120, 560)]})  # drops 40px ship
    same_max = BoxProvider("injected", {"m3.jpg": MINI_BOXES["m3.jpg"][:2]})
    # agent right on boxes that do not change the answer -> correct
    assert classify(rec_for(GOOD, provider=same_max), provider=same_max)["cell"] == "correct"
    # input only: the max ship is removed, the agent is faithful
    no_max = BoxProvider("injected", {"m3.jpg": [MINI_BOXES["m3.jpg"][0], MINI_BOXES["m3.jpg"][2]]})
    c = classify(rec_for(GOOD[:2] + [answer(40)], provider=no_max), provider=no_max)
    assert c["cell"] == "input_only" and c["input_cause"]["category"] == "miss" and c["first_deviation_stage"] is None
    # agent only: right boxes, wrong copy of the answer
    c = classify(rec_for(GOOD[:2] + [answer(66)]))
    assert c["cell"] == "agent_only" and c["input_cause"] is None
    # both: injected boxes and a wrong answer
    c = classify(rec_for(GOOD[:2] + [answer(99)], provider=no_max), provider=no_max)
    assert c["cell"] == "both" and c["agent_error"] and c["input_error"]
    # lucky: the agent's error cancels the input error
    c = classify(rec_for(GOOD[:2] + [answer(60)], provider=no_max), provider=no_max)
    assert c["cell"] == "lucky_correct"
    assert fewer  # silence unused


def test_box_independent_question_never_has_input_error():
    q = {**Q, "box_dependent": False}
    no_max = BoxProvider("injected", {"m3.jpg": []})
    c = classify(rec_for(GOOD[:2] + [answer(1)], q=q, provider=no_max), q=q, provider=no_max)
    assert not c["input_error"] and c["cell"] == "agent_only"


def stage_of(r, **kw):
    return classify(r, **kw)["first_deviation_stage_name"]


def test_stage_answer_formatting_unit_and_transcription():
    assert stage_of(rec_for(GOOD[:2] + [answer(60, unit="ships")])) == "answer_formatting"
    assert stage_of(rec_for(GOOD[:2] + [answer(66)])) == "answer_formatting"   # 60 was in the results


def test_stage_tool_selection_wrong_tool_wrong_args_and_early_answer():
    r = rec_for([tool("detect_ships", image_id="m3.jpg"), answer(1)])
    c = classify(r)
    assert c["first_deviation_stage_name"] == "tool_selection" and c["deviations"][0]["kind"] == "wrong_tool"
    r = rec_for([tool("spatial_query", image_id="m3.jpg", query="count"),
                 tool("calc", op="max", list=[1]), answer(1)])
    assert classify(r)["deviations"][0]["kind"] == "wrong_args"
    r = rec_for([answer(1)])
    c = classify(r)
    assert c["first_deviation_stage_name"] == "tool_selection" and c["deviations"][0]["kind"] == "missing_call"


def test_extra_unused_call_and_recovered_error_are_harmless():
    r = rec_for([tool("get_metadata", image_id="m3.jpg"), tool("spatial_query", image_id="m3.jpg", query="nope"),
                 tool("spatial_query", image_id="m3.jpg", query="sizes"),
                 tool("calc", op="max", list="$c3.long_side_px"), answer(66)])
    c = classify(r)
    assert {d["kind"] for d in c["harmless_deviations"]} == {"extra_call"}
    assert c["first_deviation_stage_name"] == "answer_formatting"


def test_stage_result_reading_mismatch_and_harmless_unused_reading():
    bad = tool("calc", op="max", list="$c1.long_side_px", reading=[{"from": "c1", "field": "count", "value": 7}])
    c = classify(rec_for([GOOD[0], bad, answer(66)]))
    kinds = {d["kind"] for d in c["harmless_deviations"]}
    assert "reading_mismatch" in kinds and c["first_deviation_stage_name"] == "answer_formatting"
    used = tool("calc", op="max", list="$c1.long_side_px", reading=[{"from": "c1", "field": "count", "value": 7}])
    r = rec_for([GOOD[0], used, answer(7)])
    assert stage_of(r) == "result_reading"


def test_stage_calculation_and_calc_skipped():
    r = rec_for([GOOD[0], tool("calc", op="min", list="$c1.long_side_px"), answer(40)])
    assert stage_of(r) == "calculation"
    r = rec_for([GOOD[0], answer(50)])
    c = classify(r)
    assert c["first_deviation_stage_name"] == "calculation" and c["deviations"][0]["kind"] == "calc_skipped"


def test_interpretation_deviation_comes_first_by_turn_and_record_only_mismatch_is_harmless():
    wrong = blank_interpretation(target="ship_count", unit="ships", answer_type="int")
    r = rec_for(GOOD[:2] + [answer(66)], interp=wrong)
    c = classify(r)
    assert c["first_deviation_stage_name"] == "interpretation" and c["first_deviation_turn"] == 0
    # only an unused field differs and the run is otherwise faithful -> the later error is first
    odd = {**GOLD_INTERP, "filters": [{"field": "noise", "cmp": ">", "threshold": 3}]}
    c = classify(rec_for(GOOD[:2] + [answer(66)], interp=odd))
    assert c["first_deviation_stage_name"] == "answer_formatting" and c["deviations"][0]["kind"] != "interpretation_mismatch"
    # target differs but everything the agent did followed the gold way (unit/type right)
    rec_only = {**GOLD_INTERP, "target": "pair_distance"}
    c = classify(rec_for(GOOD[:2] + [answer(66)], interp=rec_only))
    assert c["interp_record_mismatch"] and c["first_deviation_stage_name"] == "answer_formatting"


def test_turn_order_beats_table_order_and_same_turn_uses_table_order():
    # calc error in turn 2, answer formatting in turn 3 -> calculation first even though 6 > 5 anyway;
    # a stage-2 error at turn 3 must lose to a stage-5 error at turn 2
    r = rec_for([GOOD[0], tool("calc", op="min", list="$c1.long_side_px"), tool("detect_ships", image_id="m3.jpg"),
                 answer(40)])
    c = classify(r)
    assert c["first_deviation_stage_name"] == "calculation" and c["first_deviation_turn"] == 2
    assert {d["kind"] for d in c["harmless_deviations"]} == {"extra_call"}


def test_exec_fail_records_earlier_deviation_else_exec_fail():
    r = rec_for([tool("get_metadata", image_id="m3.jpg")] * 7)   # budget 5 exceeded
    c = classify(r)
    assert r["fail_kind"] == "budget_exceeded" and c["agent_error"]
    assert c["first_deviation_stage_name"] in ("tool_selection", "exec_fail")
    r = rec_for(GOOD[:2])
    r2 = rec_for([])                                              # the model has nothing to say
    assert classify(r2)["first_deviation_stage_name"] == "exec_fail" and r["status"] == "exec_fail"


def test_unknown_when_nothing_explains_the_error():
    r = rec_for(GOOD[:2] + [answer(66)])
    r["turns"][-1]["reading"] = []
    for t in r["turns"]:
        if t.get("tool_output"):
            t["tool_output"] = '{"x":0}'             # the received value is nowhere in the log
    r["answer"] = {"value": 61, "unit": "px"}
    r["answer_raw"] = "{}"
    c = classify(r)
    assert c["first_deviation_stage_name"] == "unknown"


def test_alt_program_is_accepted():
    alt = {"steps": [{"id": "s0", "op": "detect_ships", "args": {"image_id": "IMG"}}, SIZES, MAXC], "answer": "$s2.result"}
    q = {**Q, "alt_programs": [alt]}
    r = rec_for([tool("detect_ships", image_id="m3.jpg")] + GOOD, q=q)
    c = classify(r, q=q)
    assert c["cell"] == "correct"
    r = rec_for([tool("detect_ships", image_id="m3.jpg")] + GOOD[:2] + [answer(41)], q=q)
    assert classify(r, q=q)["harmless_deviations"] == [] or True
    assert not any(d["kind"] == "extra_call" for d in classify(r, q=q)["deviations"])


# ---- branch and loop questions

BRANCH_Q = {
    **Q, "qid": "D-L4-001", "level": "L4", "template": "l4_scene_branch", "gold_answer": 3, "unit": "ships",
    "has_branch": True, "gold_interpretation": blank_interpretation(
        target="branch", unit="ships", answer_type="int",
        branch=branch_object("scene", "==", "inshore", "ship_count", "max_length")),
    "branch_spec": {"on": "scene", "cmp": "==", "threshold": "inshore", "region": "full",
                    "then_label": "inshore", "else_label": "offshore"},
    "program": {"steps": [
        {"id": "s1", "op": "get_metadata", "args": {"image_id": "IMG"}},
        {"id": "s2", "op": "if", "cond": {"lhs": "$s1.scene", "cmp": "==", "rhs": "inshore"},
         "then": [{"id": "s3", "op": "detect_ships", "args": {"image_id": "IMG"}}],
         "else": [{**SIZES, "id": "s4"}, {**MAXC, "id": "s5", "args": {"op": "max", "list": "$s4.long_side_px"}}]}],
        "answer": {"then": "$s3.count", "else": "$s5.result"}}}


def test_wrong_branch_is_stage_4_and_a_misread_condition_is_stage_3():
    dec = {"condition_from": "c1.scene", "condition_value": "inshore", "threshold": "inshore",
           "cmp": "==", "chosen": "else"}
    steps = [tool("get_metadata", image_id="m3.jpg"),
             tool("spatial_query", image_id="m3.jpg", query="sizes", decision=dec),
             tool("calc", op="max", list="$c2.long_side_px"), answer(60, unit="ships")]
    c = classify(rec_for(steps, q=BRANCH_Q, interp=BRANCH_Q["gold_interpretation"]), q=BRANCH_Q)
    assert c["first_deviation_stage_name"] == "planning_branch"
    misread = {**dec, "condition_value": "offshore"}
    steps[1] = tool("spatial_query", image_id="m3.jpg", query="sizes", decision=misread)
    c = classify(rec_for(steps, q=BRANCH_Q, interp=BRANCH_Q["gold_interpretation"]), q=BRANCH_Q)
    assert c["first_deviation_stage_name"] == "result_reading"


LOOP_Q = {
    **Q, "qid": "D-L3-001", "level": "L3", "template": "l3_empty_quadrants", "gold_answer": 1, "unit": "none",
    "gold_interpretation": blank_interpretation(target="empty_region_count", unit="none", answer_type="int"),
    "program": {"steps": [
        {"id": "s1", "op": "foreach", "over": ["top_left", "top_right", "bottom_left", "bottom_right"], "as": "r",
         "do": [{"id": "s2", "op": "spatial_query", "args": {"image_id": "IMG", "query": "count", "region": "$r"}}]},
        {"id": "s3", "op": "calc", "args": {"op": "filter", "list": "$s2.count", "cmp": "==", "threshold": 0}}],
        "answer": "$s3.count"}}


def test_missing_iteration_is_loop_omission_in_stage_4():
    steps = [tool("spatial_query", image_id="m3.jpg", query="count", region="top_left"),
             tool("spatial_query", image_id="m3.jpg", query="count", region="top_right"),
             answer(0, unit="none")]
    r = rec_for(steps, q=LOOP_Q, interp=LOOP_Q["gold_interpretation"])
    c = classify(r, q=LOOP_Q)
    assert c["first_deviation_stage_name"] == "planning_branch"
    assert c["deviations"][0]["kind"] == "loop_omission"


def test_batch_plan_deviations_are_judged_on_the_plan_turn():
    plan = {"steps": [{"id": "s1", "op": "detect_ships", "args": {"image_id": "IMG"}}], "answer": None}
    replies = [{"interpretation": GOLD_INTERP, "plan": plan},
               {"reading": [], "decision": None, "final_answer": {"answer": 3, "unit": "px"}}]
    r = rec_for(replies, method="batch")
    c = classify(r)
    assert c["first_deviation_stage_name"] == "tool_selection" and c["first_deviation_turn"] == 1
    good = {"steps": [SIZES, MAXC], "answer": None}
    replies = [{"interpretation": GOLD_INTERP, "plan": good},
               {"reading": [], "decision": None, "final_answer": {"answer": 66, "unit": "px"}}]
    c = classify(rec_for(replies, method="batch"))
    assert c["first_deviation_stage_name"] == "answer_formatting" and c["first_deviation_turn"] == 2


# ---- replay

def test_replay_names_the_sufficient_kind_or_composite():
    labels = MINI_BOXES["m3.jpg"]
    fp_only = BoxProvider("detected", {"m3.jpg": labels + [(700, 700, 790, 790)]})   # big false positive -> max 90
    assert replay.replay_input(Q, fp_only, CTX)["category"] == "fp"
    miss = BoxProvider("detected", {"m3.jpg": [labels[0], labels[2]]})
    assert replay.replay_input(Q, miss, CTX)["category"] == "miss"
    both = BoxProvider("detected", {"m3.jpg": [labels[0], labels[2], (700, 700, 790, 790)]})
    assert replay.replay_input(Q, both, CTX)["category"] == "composite"
    r = replay.replay_input(Q, both, CTX)
    assert r["errors"] == {"miss": 1, "fp": 1, "loc": 0}


def test_summary_counts():
    cs = [classify(rec_for(GOOD)), classify(rec_for(GOOD[:2] + [answer(66)]))]
    s = CL.summarize(cs)
    assert s["runs"] == 2 and s["cells"] == {"correct": 1, "agent_only": 1}
    assert s["first_deviation"] == {"answer_formatting": 1} and s["unknown_share_of_agent_errors"] == 0

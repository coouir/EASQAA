"""Agents with scripted replies: happy paths, retries, budget, timeouts, format errors, shared rules."""

import json

import pytest

from sarqa.agents import common as C
from sarqa.agents import run_agent
from sarqa.agents.llm import FakeLLM, LLMError, seed_for
from sarqa.grading import grade
from sarqa.questions.vocab import blank_interpretation
from tools_fixtures import mini_context

QUESTION = {
    "qid": "D-L2-001", "level": "L2", "image_id": "m3.jpg", "text_ko": "가장 긴 선박의 긴 변은 몇 px인가?",
    "answer_type": "int", "unit": "px", "gold_answer": 60, "tolerance": {"rel": 0.0},
    "budget": 5, "gold_calls": 2,
}
INTERP = {"interpretation": blank_interpretation(target="max_length", unit="px", answer_type="int")}


def tool(name, **args):
    return {"reading": [], "decision": None, "action": {"type": "tool", "tool": name, "args": args}}


def answer(value, unit="px", reading=None):
    return {"reading": reading or [], "decision": None,
            "action": {"type": "answer", "answer": value, "unit": unit}}


HAPPY = [INTERP,
         tool("spatial_query", image_id="m3.jpg", query="sizes"),
         tool("calc", op="max", list="$c1.long_side_px"),
         answer(60, reading=[{"from": "c2", "field": "result", "value": 60}])]


def test_stepwise_happy_path_logs_everything():
    llm = FakeLLM(HAPPY)
    rec = run_agent("stepwise", QUESTION, mini_context(), llm)
    assert rec["status"] == "ok" and rec["correct"] and rec["answer"] == {"value": 60, "unit": "px"}
    assert rec["tool_calls"] == 2 and rec["llm_calls"] == 4          # tool calls + 2
    assert rec["interpretation"]["target"] == "max_length"
    t = rec["turns"]
    assert [x["kind"] for x in t] == ["interpretation", "step", "step", "step"]
    assert t[2]["action"] == {"call_id": "c2", "tool": "calc",
                              "args_raw": {"op": "max", "list": "$c1.long_side_px"},
                              "args_resolved": {"op": "max", "list": [40, 60, 40]}}
    assert json.loads(t[2]["tool_output"]) == {"op": "max", "result": 60}
    assert t[3]["reading"][0]["from"] == "c2" and rec["seed"] == seed_for("D-L2-001", 0)
    assert all(c["seed"] == rec["seed"] for c in llm.calls)


def test_the_seed_ignores_the_condition_and_depends_on_qid_and_repeat():
    assert seed_for("D-L1-001", 0) == seed_for("D-L1-001", 0)
    assert seed_for("D-L1-001", 0) != seed_for("D-L1-001", 1) != seed_for("D-L1-002", 1)
    assert 0 <= seed_for("D-L1-001", 0) < 2**31


def test_stepwise_reference_errors_come_back_as_tool_text_and_the_run_continues():
    llm = FakeLLM([INTERP, tool("calc", op="max", list="$c9.long_side_px"),
                   tool("spatial_query", image_id="m3.jpg", query="sizes"),
                   tool("calc", op="max", list="$c2.long_side_px"), answer(60)])
    rec = run_agent("stepwise", QUESTION, mini_context(), llm)
    assert rec["status"] == "ok" and rec["correct"] and rec["tool_calls"] == 3
    assert "error" in json.loads(rec["turns"][1]["tool_output"])
    assert "error" in llm.calls[2]["messages"][-1]["content"]   # the model saw the error text
    assert "did not run" in llm.calls[2]["messages"][-1]["content"]   # and is told not to resend it
    assert "did not run" not in llm.calls[3]["messages"][-1]["content"]  # a good result has no such note


def test_stepwise_budget_exceeded_stops_the_run():
    q = {**QUESTION, "budget": 2}
    llm = FakeLLM([INTERP] + [tool("get_metadata", image_id="m3.jpg")] * 4)
    rec = run_agent("stepwise", q, mini_context(), llm)
    assert rec["status"] == "exec_fail" and rec["fail_kind"] == "budget_exceeded" and rec["over_budget"]
    assert rec["tool_calls"] == 2 and not rec["correct"]


def test_one_format_retry_then_success_and_then_failure():
    llm = FakeLLM(["not json", INTERP] + HAPPY[1:])
    rec = run_agent("stepwise", QUESTION, mini_context(), llm)
    assert rec["status"] == "ok" and rec["format_retries"] == 1 and rec["llm_calls"] == 5
    assert "not accepted" in llm.calls[1]["messages"][-1]["content"]
    bad = run_agent("stepwise", QUESTION, mini_context(), FakeLLM(["x", "y"]))
    assert bad["status"] == "exec_fail" and bad["fail_kind"] == "format_error"


def test_llm_error_and_wall_limit_are_recorded_not_raised():
    rec = run_agent("stepwise", QUESTION, mini_context(), FakeLLM([LLMError("connection refused")]))
    assert rec["fail_kind"] == "llm_error" and "connection refused" in rec["error_detail"]
    rec = run_agent("stepwise", QUESTION, mini_context(), FakeLLM(HAPPY), wall_limit_s=-1)
    assert rec["fail_kind"] == "timeout" and rec["status"] == "exec_fail"


def test_wrong_unit_is_wrong_but_flagged_as_unit_only_fix():
    llm = FakeLLM([INTERP, answer(60, unit="none")])
    rec = run_agent("stepwise", QUESTION, mini_context(), llm)
    assert rec["status"] == "ok" and not rec["correct"] and rec["unit_only_fix"]


def test_decision_records_are_kept_with_their_turn():
    step = tool("get_metadata", image_id="m3.jpg")
    step["decision"] = {"condition_from": "c1.scene", "condition_value": "inshore",
                        "threshold": "inshore", "cmp": "==", "chosen": "then"}
    rec = run_agent("stepwise", QUESTION, mini_context(), FakeLLM([INTERP, step, answer(60)]))
    assert rec["decisions"][0]["chosen"] == "then" and rec["decisions"][0]["turn"] == 1


# ---------------------------------------------------------------- batch

PLAN = {"steps": [{"id": "s1", "op": "spatial_query", "args": {"image_id": "IMG", "query": "sizes"}},
                  {"id": "s2", "op": "calc", "args": {"op": "max", "list": "$s1.long_side_px"}}],
        "answer": None}
BATCH_ANSWER = {"reading": [{"from": "c2", "field": "result", "value": 60}], "decision": None,
                "final_answer": {"answer": 60, "unit": "px"}}


def test_batch_happy_path_uses_two_llm_calls_and_the_same_tools():
    llm = FakeLLM([{**INTERP, "plan": PLAN}, BATCH_ANSWER])
    rec = run_agent("batch", QUESTION, mini_context(), llm)
    assert rec["status"] == "ok" and rec["correct"]
    assert rec["llm_calls"] == 2 and rec["tool_calls"] == 2
    assert [t["kind"] for t in rec["turns"]] == ["plan", "answer"]
    ex = rec["turns"][0]["execution"]
    assert ex[1]["args_resolved"] == {"op": "max", "list": [40, 60, 40]} and ex[1]["step"] == "s2"
    assert rec["turns"][0]["step_calls"] == {"s1": ["c1"], "s2": ["c2"]}
    assert "c2 (plan step s2) calc" in llm.calls[1]["messages"][-1]["content"]
    assert llm.calls[0]["seed"] == llm.calls[1]["seed"] == seed_for("D-L2-001", 0)


def test_batch_plan_with_a_bad_reference_gets_one_retry_then_fails():
    bad = {"steps": [{"id": "s1", "op": "calc", "args": {"op": "max", "list": "$s7.x"}}], "answer": None}
    rec = run_agent("batch", QUESTION, mini_context(), FakeLLM([{**INTERP, "plan": bad}, {**INTERP, "plan": bad}]))
    assert rec["fail_kind"] == "plan_format_error" and rec["llm_calls"] == 2 and rec["tool_calls"] == 0
    llm = FakeLLM([{**INTERP, "plan": bad}, {**INTERP, "plan": PLAN}, BATCH_ANSWER])
    ok = run_agent("batch", QUESTION, mini_context(), llm)
    assert ok["status"] == "ok" and ok["format_retries"] == 1


def test_batch_tool_error_does_not_stop_the_executor():
    plan = {"steps": [{"id": "s1", "op": "spatial_query", "args": {"image_id": "IMG", "query": "nope"}},
                      {"id": "s2", "op": "get_metadata", "args": {"image_id": "IMG"}}], "answer": None}
    llm = FakeLLM([{**INTERP, "plan": plan}, {**BATCH_ANSWER, "final_answer": {"answer": 1, "unit": "px"}}])
    rec = run_agent("batch", QUESTION, mini_context(), llm)
    assert rec["status"] == "ok" and rec["tool_calls"] == 2 and not rec["correct"]
    assert "error" in rec["turns"][0]["execution"][0]["tool_output"]
    assert "error" in llm.calls[1]["messages"][-1]["content"]


def test_batch_budget_counts_executed_calls_including_foreach():
    plan = {"steps": [{"id": "s1", "op": "foreach", "over": ["top_left"] * 6, "as": "r",
                       "do": [{"id": "s2", "op": "spatial_query",
                               "args": {"image_id": "IMG", "query": "count", "region": "top_left"}}]}],
            "answer": None}
    rec = run_agent("batch", {**QUESTION, "budget": 4}, mini_context(), FakeLLM([{**INTERP, "plan": plan}]))
    assert rec["fail_kind"] == "budget_exceeded" and rec["tool_calls"] == 4 and rec["llm_calls"] == 1


def test_batch_decisions_are_taken_from_the_executor():
    plan = {"steps": [{"id": "s1", "op": "get_metadata", "args": {"image_id": "IMG"}},
                      {"id": "s2", "op": "if", "cond": {"lhs": "$s1.scene", "cmp": "==", "rhs": "inshore"},
                       "then": [{"id": "s3", "op": "detect_ships", "args": {"image_id": "IMG"}}], "else": []}],
            "answer": None}
    answer_ = {**BATCH_ANSWER, "final_answer": {"answer": 3, "unit": "ships"}}
    rec = run_agent("batch", QUESTION, mini_context(), FakeLLM([{**INTERP, "plan": plan}, answer_]))
    assert rec["decisions"] == [{"condition_from": "c1.scene", "condition_value": "inshore",
                                 "threshold": "inshore", "cmp": "==", "chosen": "then", "step": "s2"}]


# ---------------------------------------------------------------- shared

def test_both_methods_share_tool_text_and_rules():
    for method in ("stepwise", "batch"):
        text = C.system_prompt(method)
        assert "$c<k>.<field>" in text and "never as a reference" in text
        assert "detect_ships" in text and "get_metadata" in text
    assert len(C.prompt_hashes()) == 4


def test_no_gold_or_image_content_in_the_prompts():
    text = C.system_prompt("stepwise") + C.system_prompt("batch")
    for word in ("gold", "label box", "ground truth"):
        assert word not in text.lower()


def test_grading_rules():
    g = lambda a, u="px", gold=60, t="int": grade(a, u, gold, "px", t)
    assert g(60).correct and g(60.0).correct and not g(59).correct and not g(None).correct
    assert g(60, "pixels").correct and not g(60, "ships").correct and g(60, "ships").unit_only_fix
    assert g(63, gold=60.0, t="float").correct and not g(63.1, gold=60.0, t="float").correct
    assert grade("Top_Left", "none", "top_left", "none", "category").correct
    assert not grade("top_left", "none", "top_right", "none", "category").correct
    assert not g("abc").answer_format_ok and g("60").answer_format_ok


def test_schemas_are_json_serialisable_and_list_all_tools():
    schema = C.stepwise_schema()
    json.dumps(schema)
    tools = schema["properties"]["action"]["anyOf"][0]["properties"]["tool"]["enum"]
    assert tools == ["calc", "detect_ships", "get_metadata", "image_stats", "spatial_query"]
    assert pytest.approx(0) == 0


def test_question_language_defaults_to_korean_and_english_only_on_request():
    en = {**QUESTION, "lang": "en", "text_en": "What is the longest ship in px?"}
    llm_ko, llm_en = FakeLLM(HAPPY), FakeLLM([INTERP])
    rec_ko = run_agent("stepwise", QUESTION, mini_context(), llm_ko)
    run_agent("stepwise", en, mini_context(), llm_en)
    assert "가장 긴 선박" in llm_ko.calls[0]["messages"][1]["content"] and rec_ko["lang"] == "ko"
    assert "What is the longest ship in px?" in llm_en.calls[0]["messages"][1]["content"]
    assert "가장" not in llm_en.calls[0]["messages"][1]["content"] + llm_en.calls[0]["messages"][0]["content"]

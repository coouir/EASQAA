import pytest

from sarqa.program import run_program
from sarqa.tools.refs import RefError, iter_refs, parse_ref, resolve_refs
from sarqa.tools.session import BudgetExceeded, ToolSession
from tools_fixtures import mini_context

SCOPE = {"c1": {"count": 3, "ships": [{"id": "s1", "x1": 5}], "long_side_px": [40, 60]},
         "c2": {"error": "spatial_query: boom"}, "item": {"x1": 9}, "region": "top_left"}


def test_resolve_values_lists_and_nested_objects():
    assert resolve_refs("$c1.count", SCOPE) == 3
    assert resolve_refs("$c1.long_side_px", SCOPE) == [40, 60]
    assert resolve_refs({"list": "$c1.long_side_px", "op": "max"}, SCOPE) == \
        {"list": [40, 60], "op": "max"}
    assert resolve_refs(["a", "$c1.count", 7], SCOPE) == ["a", 3, 7]
    assert resolve_refs("$c1.ships.0.id", SCOPE) == "s1"
    assert resolve_refs("$item.x1", SCOPE) == 9
    assert resolve_refs("$region", SCOPE) == "top_left"  # bare loop variable
    assert resolve_refs("full", SCOPE) == "full" and resolve_refs(5, SCOPE) == 5


@pytest.mark.parametrize("ref,fragment", [
    ("$c9.count", "no such call"),
    ("$c1.nope", "no field 'nope'"),
    ("$c1.ships.3", "no field '3'"),
    ("$c1.count.x", "no field 'x'"),
    ("$c2.count", "returned an error: spatial_query: boom"),
    ("$", "malformed"),
    ("$c1.", "malformed"),
    ("$c1..count", "malformed"),
    ("$5 dollars", "malformed"),
])
def test_bad_references_raise_with_a_helpful_message(ref, fragment):
    with pytest.raises(RefError, match=fragment):
        resolve_refs(ref, SCOPE)


def test_parse_and_iter_refs():
    assert parse_ref("$c3.count") == ("c3", ["count"])
    assert parse_ref("$item") == ("item", [])
    assert sorted(iter_refs({"a": "$c1.x", "b": ["$c2.y", "z"], "c": 3})) == ["$c1.x", "$c2.y"]


CTX = mini_context()


def test_session_numbers_calls_and_resolves_c_references():
    s = ToolSession(CTX)
    a = s.call("spatial_query", {"image_id": "m3.jpg", "query": "sizes"})
    b = s.call("calc", {"op": "max", "list": "$c1.long_side_px"})
    assert (a.call_id, b.call_id) == ("c1", "c2")
    assert b.output == {"op": "max", "result": 60}
    assert b.resolved_args == {"op": "max", "list": [40, 60, 40]}
    assert b.args == {"op": "max", "list": "$c1.long_side_px"}
    assert [c.call_id for c in s.calls] == ["c1", "c2"] and s.outputs["c2"]["result"] == 60


def test_missing_call_or_field_gives_an_error_output_and_still_counts():
    s = ToolSession(CTX)
    r = s.call("calc", {"op": "max", "list": "$c7.count"})
    assert "error" in r.output and "no such call" in r.output["error"] and r.is_error
    s.call("detect_ships", {"image_id": "m3.jpg"})
    r = s.call("calc", {"op": "max", "list": "$c2.nope"})
    assert "no field 'nope'" in r.output["error"]
    assert len(s.calls) == 3


def test_budget_raises_before_the_extra_call():
    s = ToolSession(CTX, budget=2)
    s.call("get_metadata", {"image_id": "m1.jpg"})
    s.call("get_metadata", {"image_id": "m1.jpg"})
    with pytest.raises(BudgetExceeded):
        s.call("get_metadata", {"image_id": "m1.jpg"})
    assert len(s.calls) == 2


def test_stepwise_style_and_batch_plan_resolve_the_same_way():
    """Same references, same tools -> same outputs from a ToolSession and from the DSL."""
    s = ToolSession(CTX)
    s.call("spatial_query", {"image_id": "m3.jpg", "query": "sizes"})
    stepwise = s.call("calc", {"op": "max", "list": "$c1.long_side_px"}).output
    plan = {"steps": [
        {"id": "s1", "op": "spatial_query", "args": {"image_id": "IMG", "query": "sizes"}},
        {"id": "s2", "op": "calc", "args": {"op": "max", "list": "$s1.long_side_px"}}],
        "answer": "$s2.result"}
    res = run_program(plan, "m3.jpg", CTX.boxes, ctx=CTX)
    assert res.calls[1].output == stepwise
    assert [c.output for c in res.calls] == [c.output for c in s.calls]
    assert res.step_calls == {"s1": ["c1"], "s2": ["c2"]}

import pytest

from sarqa.boxes import BoxProvider
from sarqa.program import ProgramError, budget_for, run_program, validate_program
from tools_fixtures import MINI_BOXES, mini_context

CTX = mini_context()
LABEL = CTX.boxes
QUADS = ["top_left", "top_right", "bottom_left", "bottom_right"]


def call(tool, sid, /, **args):
    """A tool-call step; every tool but calc takes the image id."""
    return {"id": sid, "op": tool, "args": args if tool == "calc" else {"image_id": "IMG", **args}}


COUNT = {"steps": [call("detect_ships", "s1")], "answer": "$s1.count"}
NEAREST = {"steps": [call("spatial_query", "s1", query="nearest_pair")], "answer": "$s1.distance_px"}
# the example program of SPEC §6.3
BRANCH = {"steps": [
    call("get_metadata", "s1"),
    {"id": "s2", "op": "if", "cond": {"lhs": "$s1.scene", "cmp": "==", "rhs": "inshore"},
     "then": [call("detect_ships", "s3")],
     "else": [call("spatial_query", "s4", query="sizes"),
              call("calc", "s5", op="max", list="$s4.long_side_px")]}],
    "answer": {"then": "$s3.count", "else": "$s5.result"}}
ARGMAX = {"steps": [
    {"id": "s1", "op": "foreach", "over": QUADS, "as": "r",
     "do": [call("spatial_query", "s2", query="count", region="$r")]},
    call("calc", "s3", op="argmax", list="$s2.count", labels=QUADS)],
    "answer": "$s3.result"}
OVER_THRESHOLD = {"steps": [
    call("spatial_query", "s1", query="sizes"),
    call("calc", "s2", op="filter", list="$s1.long_side_px", cmp=">", threshold=40),
    call("calc", "s3", op="count", list="$s2.result")], "answer": "$s3.result"}
BRIGHTNESS = {"steps": [call("image_stats", "s1", region="top_left")],
              "answer": "$s1.mean_brightness"}
FAR_SHIP = {"steps": [   # foreach over detected ships: distance from s1 to each ship, then max
    call("detect_ships", "s1"),
    {"id": "s2", "op": "foreach", "over": "$s1.ships", "as": "ship",
     "do": [call("spatial_query", "s3", query="distance", ship_a="s1", ship_b="$ship.id")]},
    call("calc", "s4", op="max", list="$s3.distance_px")], "answer": "$s4.result"}


def run(program, image, provider=LABEL):
    return run_program(program, image, provider, ctx=CTX)


# five mini images, answers computed by hand (see tests/tools_fixtures.py for the boxes)
HAND_CASES = [
    (COUNT, "m5.jpg", 15, 1),            # 15 ships in a row
    (COUNT, "m1.jpg", 0, 1),             # empty sea
    (NEAREST, "m3.jpg", 505.0, 1),       # s1 (520,115) to s3 (620,610): hypot(100, 495)
    (BRANCH, "m3.jpg", 3, 2),            # inshore -> then: get_metadata + detect_ships
    (BRANCH, "m2.jpg", 30, 3),           # offshore -> else: get_metadata + sizes + calc; 30x20 -> 30
    (ARGMAX, "m4.jpg", "bottom_right", 5),   # counts 1, 0, 1, 2 -> 4 spatial_query + 1 calc
    (OVER_THRESHOLD, "m3.jpg", 1, 3),    # long sides 40, 60, 40 -> only 60 is > 40
    (BRIGHTNESS, "m2.jpg", 50.56, 1),    # 50 + 150 * 600 / 160000 = 50.5625
    (FAR_SHIP, "m3.jpg", 583.4, 5),      # distances from s1: 0.0, 583.4 (s2), 505.0 (s3)
]


@pytest.mark.parametrize("program,image,answer,calls", HAND_CASES)
def test_answers_and_gold_calls_match_hand_calculation(program, image, answer, calls):
    res = run(program, image)
    assert res.ok, (res.errors, [c.output for c in res.tool_errors])
    assert res.answer == answer
    assert res.gold_calls == calls == len(res.calls)


def test_ties_in_argmax_go_to_the_first_region():
    assert run(ARGMAX, "m3.jpg").answer == "top_right"  # counts 0, 1, 1, 1


def test_gold_calls_counts_only_the_branch_that_ran():
    inshore, offshore = run(BRANCH, "m3.jpg"), run(BRANCH, "m2.jpg")
    assert [c.tool for c in inshore.calls] == ["get_metadata", "detect_ships"]
    assert [c.tool for c in offshore.calls] == ["get_metadata", "spatial_query", "calc"]
    assert inshore.step_calls == {"s1": ["c1"], "s3": ["c2"]}
    assert offshore.step_calls == {"s1": ["c1"], "s4": ["c2"], "s5": ["c3"]}
    assert inshore.decisions[0]["chosen"] == "then" and offshore.decisions[0]["chosen"] == "else"


def test_foreach_unrolls_calls_and_gathers_fields_after_the_loop():
    res = run(ARGMAX, "m4.jpg")
    assert res.step_calls["s2"] == ["c1", "c2", "c3", "c4"] and res.step_calls["s3"] == ["c5"]
    assert res.intermediates["s2"]["count"] == [1, 0, 1, 2]
    assert res.intermediates["s2"]["region"] == QUADS
    assert "r" not in res.intermediates  # loop variable does not leak
    assert run(FAR_SHIP, "m3.jpg").intermediates["s3"]["distance_px"] == [0.0, 583.4, 505.0]


def test_budget_formula():
    assert [budget_for(g) for g in (1, 2, 3, 4, 5, 8)] == [4, 5, 6, 8, 10, 16]
    assert run(BRANCH, "m3.jpg").budget == 5 and run(BRANCH, "m2.jpg").budget == 6
    assert run(ARGMAX, "m4.jpg").budget == 10 and run(COUNT, "m1.jpg").budget == 4


def test_call_budget_stops_the_run():
    res = run_program(ARGMAX, "m4.jpg", LABEL, ctx=CTX, budget=3)
    assert res.budget_exceeded and res.answer is None and len(res.calls) == 3 and not res.ok
    assert run_program(ARGMAX, "m4.jpg", LABEL, ctx=CTX, budget=5).ok


@pytest.mark.parametrize("source", ["detected", "injected", "corrected"])
def test_same_program_runs_on_every_source_with_the_same_output_format(source):
    other = BoxProvider(source, {"m3.jpg": [(500, 100, 540, 130), (100, 500, 120, 560)]})
    for prog in (COUNT, BRANCH, NEAREST):
        a, b = run(prog, "m3.jpg"), run(prog, "m3.jpg", other)
        assert b.ok
        assert [list(c.output) for c in a.calls][:1] == [list(c.output) for c in b.calls][:1]
    assert run(COUNT, "m3.jpg", other).answer == 2 and run(COUNT, "m3.jpg").answer == 3
    assert run(NEAREST, "m3.jpg", other).answer == 583.4


def test_gold_run_does_not_touch_the_box_source_of_image_stats():
    other = BoxProvider("injected", {"m2.jpg": []})
    assert run(BRIGHTNESS, "m2.jpg", other).answer == run(BRIGHTNESS, "m2.jpg").answer


def test_answer_forms():
    lit = {"steps": [call("get_metadata", "s1"),
                     {"id": "s2", "op": "if", "cond": {"lhs": "$s1.scene", "cmp": "==", "rhs": "inshore"},
                      "then": [], "else": []}],
           "answer": {"if": "s2", "then": "yes", "else": "no"}}
    assert run(lit, "m3.jpg").answer == "yes" and run(lit, "m1.jpg").answer == "no"
    assert run({"steps": [call("get_metadata", "s1")], "answer": 7}, "m1.jpg").answer == 7


def test_broken_run_is_recorded_not_raised():
    bad_ref = {"steps": [call("detect_ships", "s1"), call("calc", "s2", op="max", list="$s1.nope")],
               "answer": "$s2.result"}
    res = run(bad_ref, "m3.jpg")
    assert not res.ok and res.answer is None and len(res.calls) == 2
    assert "no field 'nope'" in res.calls[1].output["error"]
    unknown_image = run(COUNT, "zz.jpg")
    assert unknown_image.tool_errors and unknown_image.answer is None
    empty_loop = run(FAR_SHIP, "m1.jpg")  # no ships: nothing to gather, later reference fails
    assert not empty_loop.ok and empty_loop.gold_calls == 2


def test_if_that_cannot_be_evaluated_takes_no_branch():
    prog = {"steps": [call("get_metadata", "s1"),
                      {"id": "s2", "op": "if", "cond": {"lhs": "$s1.nope", "cmp": "==", "rhs": 1},
                       "then": [call("detect_ships", "s3")]}], "answer": "$s3.count"}
    res = run(prog, "m3.jpg")
    assert res.gold_calls == 1 and res.decisions[0]["chosen"] is None and not res.ok
    ordering = {"steps": [call("get_metadata", "s1"),
                          {"id": "s2", "op": "if", "cond": {"lhs": "$s1.scene", "cmp": ">", "rhs": 3},
                           "then": []}], "answer": 1}
    assert "cannot order" in run(ordering, "m3.jpg").errors[0]


def test_numeric_if_conditions():
    prog = {"steps": [call("detect_ships", "s1"),
                      {"id": "s2", "op": "if", "cond": {"lhs": "$s1.count", "cmp": ">=", "rhs": 3},
                       "then": [call("get_metadata", "s3")], "else": []}], "answer": "$s3.scene"}
    assert run(prog, "m3.jpg").answer == "inshore"
    assert run(prog, "m2.jpg").answer is None  # 1 ship: else branch, answer needs s3


@pytest.mark.parametrize("program,fragment", [
    ("nope", "JSON object"),
    ({"answer": 1}, "'steps'"),
    ({"steps": [], "answer": 1}, "'steps'"),
    ({"steps": [call("detect_ships", "s1")]}, "'answer' is missing"),
    ({"steps": [call("detect_ships", "s1"), call("detect_ships", "s1")], "answer": 1}, "duplicate"),
    ({"steps": [{"id": "s1", "op": "zoom"}], "answer": 1}, "unknown op"),
    ({"steps": [{"op": "detect_ships"}], "answer": 1}, "string 'id'"),
    ({"steps": [call("calc", "s1", op="max", list="$s2.x"), call("detect_ships", "s2")],
      "answer": 1}, "earlier step"),
    ({"steps": [call("detect_ships", "s1")], "answer": "$s9.count"}, "earlier step"),
    ({"steps": [call("detect_ships", "s1")], "answer": "$s1..count"}, "malformed"),
    ({"steps": [{"id": "s1", "op": "detect_ships", "args": [1]}], "answer": 1}, "'args' must be"),
    ({"steps": [{"id": "s1", "op": "detect_ships", "args": {}, "x": 1}], "answer": 1}, "unexpected key"),
    ({"steps": [{"id": "s1", "op": "if", "cond": {"lhs": 1, "cmp": "=>", "rhs": 2}, "then": []}],
      "answer": 1}, "cmp must be"),
    ({"steps": [{"id": "s1", "op": "if", "cond": {"lhs": 1}, "then": []}], "answer": 1}, "exactly"),
    ({"steps": [{"id": "s1", "op": "if", "cond": {"lhs": 1, "cmp": "==", "rhs": 1}}],
      "answer": 1}, "'then' is missing"),
    ({"steps": [{"id": "s1", "op": "foreach", "over": 5, "do": []}], "answer": 1}, "'over'"),
    ({"steps": [{"id": "s1", "op": "foreach", "over": [1], "as": "s1", "do": []}],
      "answer": 1}, "also a step id"),
    ({"steps": [{"id": "s1", "op": "foreach", "over": [1]}], "answer": 1}, "'do' is missing"),
])
def test_validation_problems(program, fragment):
    problems = validate_program(program)
    assert any(fragment in p for p in problems), problems
    with pytest.raises(ProgramError):
        run_program(program, "m1.jpg", LABEL, ctx=CTX)


def test_nesting_depth_is_limited():
    inner = [call("detect_ships", "d")]
    for i in range(5):
        inner = [{"id": f"f{i}", "op": "foreach", "over": [1], "do": inner}]
    assert any("nested deeper" in p for p in validate_program({"steps": inner, "answer": 1}))


def test_valid_programs_have_no_problems():
    for prog in (COUNT, NEAREST, BRANCH, ARGMAX, OVER_THRESHOLD, BRIGHTNESS, FAR_SHIP):
        assert validate_program(prog) == []


def test_mini_images_cover_the_five_hand_cases():
    assert {img for _, img, _, _ in HAND_CASES} == set(MINI_BOXES)


@pytest.mark.data
def test_real_data_program_runs_on_all_four_source_kinds(tmp_path):
    import json

    from sarqa.boxes import detected_provider, file_provider, label_provider
    from sarqa.tools import default_context

    labels = label_provider()
    name = next(n for n in labels.image_ids() if 2 <= len(labels.boxes(n)) <= 15)
    raw = {name: [[b.x1, b.y1, b.x2, b.y2] for b in labels.boxes(name)]}
    path = tmp_path / "x.json"
    path.write_text(json.dumps(raw))
    det = detected_provider("dev")
    dev_name = det.image_ids()[0]
    gold = run_program(BRANCH, name, labels, ctx=default_context())
    assert gold.ok
    for prov in (file_provider("injected", path), file_provider("corrected", path)):
        assert run_program(BRANCH, name, prov, ctx=default_context()).answer == gold.answer
    assert run_program(COUNT, dev_name, det, ctx=default_context()).ok

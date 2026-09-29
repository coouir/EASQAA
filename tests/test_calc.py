import pytest

from sarqa.tools import call_tool
from tools_fixtures import mini_context

CTX = mini_context()


def calc(**kw):
    return call_tool(CTX, "calc", kw)


def test_aggregates():
    xs = [40, 60, 40, 15]
    assert calc(op="count", list=xs) == {"op": "count", "result": 4}
    assert calc(op="sum", list=xs)["result"] == 155
    assert calc(op="mean", list=xs)["result"] == 38.75
    assert calc(op="max", list=xs)["result"] == 60
    assert calc(op="min", list=xs)["result"] == 15
    assert calc(op="sort", list=xs)["result"] == [15, 40, 40, 60]
    assert calc(op="sort", list=xs, order="desc")["result"] == [60, 40, 40, 15]
    assert calc(op="count", list=[]) == {"op": "count", "result": 0}
    assert calc(op="sum", list=[])["result"] == 0


def test_filter_uses_each_comparison():
    xs = [10, 20, 20, 30]
    assert calc(op="filter", list=xs, cmp=">", threshold=20) == {"op": "filter", "result": [30], "count": 1}
    assert calc(op="filter", list=xs, cmp=">=", threshold=20)["count"] == 3
    assert calc(op="filter", list=xs, cmp="<", threshold=20)["result"] == [10]
    assert calc(op="filter", list=xs, cmp="<=", threshold=20)["count"] == 3
    assert calc(op="filter", list=xs, cmp="==", threshold=20)["count"] == 2
    assert calc(op="filter", list=xs, cmp="!=", threshold=20)["count"] == 2
    assert calc(op="filter", list=[], cmp=">", threshold=1)["result"] == []


def test_argmax_argmin_with_labels_and_ties():
    counts, regions = [2, 5, 5, 0], ["top_left", "top_right", "bottom_left", "bottom_right"]
    assert calc(op="argmax", list=counts, labels=regions) == {
        "op": "argmax", "result": "top_right", "index": 1, "value": 5}  # first of the tie
    assert calc(op="argmin", list=counts, labels=regions)["result"] == "bottom_right"
    assert calc(op="argmax", list=counts)["result"] == 1
    assert calc(op="argmin", list=[3, 1, 1])["index"] == 1


def test_arithmetic():
    assert calc(op="add", a=2, b=3)["result"] == 5
    assert calc(op="sub", a=2, b=3)["result"] == -1
    assert calc(op="mul", a=1.5, b=4)["result"] == 6.0
    assert calc(op="div", a=1, b=3)["result"] == 0.3333
    assert calc(op="div", a=10, b=4)["result"] == 2.5


def test_expr_whitelist_accepts_arithmetic():
    assert calc(op="expr", expr="(a - b) * 2 / 4", vars={"a": 10, "b": 4})["result"] == 3.0
    assert calc(op="expr", expr="-x + 7 // 2 + 7 % 4", vars={"x": 1})["result"] == 5
    assert calc(op="expr", expr="3 * 4")["result"] == 12


@pytest.mark.parametrize("expr", [
    "__import__('os').system('true')", "().__class__", "(1).real", "a.b", "a[0]", "f(1)",
    "abs(-1)", "exec('1')", "open('x')", "lambda: 1", "[i for i in a]", "1 if a else 2",
    "'text'", "a; b", "(x := 3)", "1 < 2", "not a", "a and b", "2 ** 10", "[1, 2]", "True",
    "1j", "a if", "", "   ", "x" * 300, "1e10", "__builtins__", "print",
])
def test_expr_rejects_everything_else(expr):
    out = calc(op="expr", expr=expr, vars={"a": 1, "b": 2})
    assert "error" in out, expr


def test_expr_cannot_reach_names_outside_vars_and_keeps_no_state():
    assert "unknown name" in calc(op="expr", expr="ctx")["error"]
    assert "unknown name" in calc(op="expr", expr="calc")["error"]
    assert "simple names" in calc(op="expr", expr="a", vars={"__x__": 1})["error"]
    assert "finite number" in calc(op="expr", expr="a", vars={"a": "1"})["error"]
    assert "finite number" in calc(op="expr", expr="a", vars={"a": True})["error"]


def test_expr_is_bounded():
    assert "too long" in calc(op="expr", expr="+".join(["1"] * 40))["error"]
    assert "too large" in calc(op="expr", expr="9999999999")["error"]
    assert "division by zero" in calc(op="expr", expr="1 / a", vars={"a": 0})["error"]
    assert "not a valid" in calc(op="expr", expr="((((" * 5)["error"]


def test_errors():
    assert "unknown op" in calc(op="eval", expr="1")["error"]
    assert "needs" in calc(op="max")["error"]
    assert "needs" in calc(op="add", a=1)["error"]
    assert "does not take" in calc(op="max", list=[1], a=2)["error"]
    assert "empty list" in calc(op="max", list=[])["error"]
    assert "empty list" in calc(op="mean", list=[])["error"]
    assert "empty list" in calc(op="argmax", list=[])["error"]
    assert "list of numbers" in calc(op="max", list="abc")["error"]
    assert "finite number" in calc(op="max", list=[1, "2"])["error"]
    assert "finite number" in calc(op="sum", list=[1, None])["error"]
    assert "finite number" in calc(op="sum", list=[True])["error"]
    assert "division by zero" in calc(op="div", a=1, b=0)["error"]
    assert "cmp must be" in calc(op="filter", list=[1], cmp="=>", threshold=1)["error"]
    assert "order must be" in calc(op="sort", list=[1], order="up")["error"]
    assert "labels must be" in calc(op="argmax", list=[1, 2], labels=["a"])["error"]
    assert "more than" in calc(op="sum", list=[1] * 1001)["error"]
    assert "unexpected argument" in call_tool(CTX, "calc", {"op": "sum", "list": [1], "code": "x"})["error"]

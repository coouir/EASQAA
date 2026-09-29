"""`calc`: exact arithmetic on values the agent already has (SPEC §5.2).

Operands are named, flat arguments (the DSL of SPEC §6.3 writes `{"op": "calc", "args": {"op":
"max", "list": "$s4.long_side_px"}}`). Results are `{"op", "result", ...}`; floats are rounded to
`DECIMALS`. `expr` evaluates a formula through a whitelisted AST (numbers, `+ - * / // %`, unary
`+ -`, variable names taken from `vars`); it never calls `eval`, and calls, attributes,
subscripts, comprehensions and strings are all rejected.

There is no unit conversion: HRSID has no resolution, all distances and lengths are px (§5.3).
"""

import ast
import math
import operator
import re

from sarqa.tools.base import ToolContext, ToolError, tool

DECIMALS = 4
MAX_EXPR_LEN = 200
MAX_EXPR_NODES = 60
MAX_CONST = 1e9
MAX_LIST = 1000

CMPS = {">": operator.gt, ">=": operator.ge, "<": operator.lt, "<=": operator.le,
        "==": operator.eq, "!=": operator.ne}
BINOPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
          ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod}
UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_LIST = list  # the `list` argument of `calc` shadows the builtin inside the tool
NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,15}$")

# op -> (required arguments, optional arguments)
OPS = {
    "count": ({"list"}, set()), "sum": ({"list"}, set()), "mean": ({"list"}, set()),
    "max": ({"list"}, set()), "min": ({"list"}, set()),
    "sort": ({"list"}, {"order"}), "filter": ({"list", "cmp", "threshold"}, set()),
    "argmax": ({"list"}, {"labels"}), "argmin": ({"list"}, {"labels"}),
    "add": ({"a", "b"}, set()), "sub": ({"a", "b"}, set()),
    "mul": ({"a", "b"}, set()), "div": ({"a", "b"}, set()),
    "expr": ({"expr"}, {"vars"}),
}


def _num(v, what: str):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise ToolError(f"{what} must be a finite number, got {v!r}")
    return v


def _numbers(v, what: str = "list") -> list:
    if not isinstance(v, _LIST):
        raise ToolError(f"{what} must be a list of numbers, got {type(v).__name__}")
    if len(v) > MAX_LIST:
        raise ToolError(f"{what} has more than {MAX_LIST} items")
    return [_num(x, f"{what} item") for x in v]


def _out(v):
    if isinstance(v, float):
        if not math.isfinite(v):
            raise ToolError("result is not finite")
        return round(v, DECIMALS)
    return v


def _eval_node(node, names: dict, budget: list):
    budget[0] -= 1
    if budget[0] < 0:
        raise ToolError("expression is too long")
    if isinstance(node, ast.Expression):
        return _eval_node(node.body, names, budget)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise ToolError("only numbers are allowed in expr")
        if abs(node.value) > MAX_CONST:
            raise ToolError("number too large")
        return node.value
    if isinstance(node, ast.Name):
        if node.id not in names:
            raise ToolError(f"unknown name {node.id!r} in expr; pass it in vars")
        return names[node.id]
    if isinstance(node, ast.UnaryOp) and type(node.op) in UNARY:
        return UNARY[type(node.op)](_eval_node(node.operand, names, budget))
    if isinstance(node, ast.BinOp) and type(node.op) in BINOPS:
        left, right = _eval_node(node.left, names, budget), _eval_node(node.right, names, budget)
        try:
            return BINOPS[type(node.op)](left, right)
        except ZeroDivisionError:
            raise ToolError("division by zero") from None
    raise ToolError(f"{type(node).__name__} is not allowed in expr")


def _expr(expr, variables) -> float | int:
    if not isinstance(expr, str) or not expr.strip():
        raise ToolError("expr must be a non-empty string")
    if len(expr) > MAX_EXPR_LEN:
        raise ToolError(f"expr is longer than {MAX_EXPR_LEN} characters")
    variables = {} if variables is None else variables
    if not isinstance(variables, dict) or not all(
            isinstance(k, str) and NAME.match(k) for k in variables):
        raise ToolError("vars must be an object mapping simple names to numbers")
    names = {k: _num(v, f"vars.{k}") for k, v in variables.items()}
    try:
        tree = ast.parse(expr.strip(), mode="eval")
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        raise ToolError("expr is not a valid arithmetic expression") from None
    return _eval_node(tree, names, [MAX_EXPR_NODES])


@tool
def calc(ctx: ToolContext, op: str, list=None, a=None, b=None, cmp=None, threshold=None,
         order=None, labels=None, expr=None, vars=None) -> dict:
    if op not in OPS:
        raise ToolError(f"unknown op {op!r}; use one of {sorted(OPS)}")
    given = {"list": list, "a": a, "b": b, "cmp": cmp, "threshold": threshold, "order": order,
             "labels": labels, "expr": expr, "vars": vars}
    required, optional = OPS[op]
    missing = sorted(k for k in required if given[k] is None)
    if missing:
        raise ToolError(f"op {op!r} needs {missing}")
    extra = sorted(k for k, v in given.items() if v is not None and k not in required | optional)
    if extra:
        raise ToolError(f"op {op!r} does not take {extra}")

    if op == "expr":
        return {"op": op, "result": _out(_expr(expr, vars))}
    if op in ("add", "sub", "mul", "div"):
        x, y = _num(a, "a"), _num(b, "b")
        if op == "div":
            if y == 0:
                raise ToolError("division by zero")
            return {"op": op, "result": _out(x / y)}
        return {"op": op, "result": _out({"add": x + y, "sub": x - y, "mul": x * y}[op])}
    values = _numbers(list)
    if op == "count":
        return {"op": op, "result": len(values)}
    if op == "sum":
        return {"op": op, "result": _out(sum(values))}
    if op in ("mean", "max", "min", "argmax", "argmin") and not values:
        raise ToolError(f"{op} of an empty list")
    if op == "mean":
        return {"op": op, "result": _out(sum(values) / len(values))}
    if op in ("max", "min"):
        return {"op": op, "result": (max if op == "max" else min)(values)}
    if op == "sort":
        if order not in (None, "asc", "desc"):
            raise ToolError("order must be 'asc' or 'desc'")
        return {"op": op, "result": sorted(values, reverse=order == "desc")}
    if op == "filter":
        if cmp not in CMPS:
            raise ToolError(f"cmp must be one of {sorted(CMPS)}")
        keep = [v for v in values if CMPS[cmp](v, _num(threshold, "threshold"))]
        return {"op": op, "result": keep, "count": len(keep)}
    # argmax / argmin: the first extreme wins ties
    if op == "argmax":
        idx = max(range(len(values)), key=lambda i: (values[i], -i))
    else:
        idx = min(range(len(values)), key=lambda i: (values[i], i))
    if labels is not None:
        if not isinstance(labels, _LIST) or len(labels) != len(values):
            raise ToolError("labels must be a list as long as list")
        return {"op": op, "result": labels[idx], "index": idx, "value": values[idx]}
    return {"op": op, "result": idx, "index": idx, "value": values[idx]}

"""Stage detectors of the error classifier (SPEC §11.3). Every stage is judged **against what the agent
itself received**: the gold program is re-run on the run's own boxes (`expected_runs`), so a wrong
input box never counts as the agent's deviation.

`Dev` = one deviation: stage 1..6, the turn it happened in, a short kind and a detail. A deviation that
does not matter for the answer is `harmless` (SPEC §11.1 table): it is recorded but never becomes the
first deviation. Turns: stepwise interpretation = 0, action turns 1..n; plan-first plan = 1, answer = 2.
Within a turn the stage order of the table decides. Known simplification: for a wrong reading or calc
argument that *is* used later, the SPEC's "replace by the right value and re-run" test is not done;
a used wrong value counts as a deviation.
"""

import json
import re
from dataclasses import dataclass, field

from sarqa.grading import normalize_unit, value_matches
from sarqa.program import run_program
from sarqa.tools.refs import RefError, resolve_ref

STAGE_NAMES = {0: "exec_fail", 1: "interpretation", 2: "tool_selection", 3: "result_reading",
               4: "planning_branch", 5: "calculation", 6: "answer_formatting"}
# Stage 1 judges target, region, filters and the branch condition. `unit` and `answer_type` are left out
# (SPEC §11.3 lists them; docs/deviations.md 2026-10-01): the final answer's unit is judged at stage 6, and an
# int/float slip in the record does not change what the agent does. They are counted, never judged.
USED_FIELDS_ALWAYS = ("target",)
STATISTIC_ONLY_FIELDS = ("unit", "answer_type")
# what a branch condition reads: on -> (tools that may supply it, output field)
BRANCH_SOURCE = {"scene": (("get_metadata",), "scene"),
                 "ship_count": (("spatial_query", "detect_ships"), "count"),
                 "max_length": (("calc",), "result"),
                 "noise": (("image_stats",), "background_noise")}
REGION_QUERIES = ("count", "sizes", "nearest_pair", "edge")


@dataclass
class Dev:
    stage: int
    turn: int
    kind: str
    detail: str = ""
    harmless: bool = False

    def as_dict(self) -> dict:
        return {"stage": self.stage, "stage_name": STAGE_NAMES[self.stage], "turn": self.turn,
                "kind": self.kind, "detail": self.detail[:300], "harmless": self.harmless}


# ---------------------------------------------------------------- values

def same_value(a, b, tol: float = 1e-6) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= tol * max(1.0, abs(a), abs(b))
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(same_value(x, y, tol) for x, y in zip(a, b, strict=True))
    if isinstance(a, dict) and isinstance(b, dict):
        return set(a) == set(b) and all(same_value(a[k], b[k], tol) for k in a)
    return a == b


def _freeze(v):
    if isinstance(v, list):
        return tuple(_freeze(x) for x in v)
    if isinstance(v, float) and v == int(v):
        return int(v)
    return v


def flatten(v):
    """Every leaf value of a JSON-like structure."""
    if isinstance(v, dict):
        for x in v.values():
            yield from flatten(x)
    elif isinstance(v, (list, tuple)):
        yield v
        for x in v:
            yield from flatten(x)
    else:
        yield v


# ---------------------------------------------------------------- the agent's trace

@dataclass
class ACall:
    call_id: str
    tool: str
    args: dict
    raw_args: object
    output: dict
    turn: int
    step: str | None = None


@dataclass
class Trace:
    method: str
    calls: list[ACall] = field(default_factory=list)
    readings: list[tuple[int, dict]] = field(default_factory=list)          # (turn, reading item)
    llm_decisions: list[tuple[int, dict]] = field(default_factory=list)     # written by the model
    branch_decisions: list[tuple[int, dict]] = field(default_factory=list)  # what decided the branch
    interp_turn: int = 0
    final_turn: int = 0
    calc_turn: int | None = None     # plan-first: calc steps are judged after the run (turn 2)

    def call(self, call_id: str) -> ACall | None:
        return next((c for c in self.calls if c.call_id == call_id), None)


def _parse(text) -> dict:
    try:
        out = json.loads(text)
        return out if isinstance(out, dict) else {"_value": out}
    except (TypeError, json.JSONDecodeError):
        return {"_unparsed": str(text)}


def build_trace(rec: dict) -> Trace:
    t = Trace(rec["method"])
    turns = rec["turns"]
    if rec["method"] == "stepwise":
        t.interp_turn = 0
        for turn in turns:
            n = turn["turn"]
            t.final_turn = max(t.final_turn, n)
            for r in turn.get("reading") or []:
                t.readings.append((n, r))
            d = (turn.get("llm_output") or {}).get("decision") if turn["kind"] == "step" else None
            if d:
                t.llm_decisions.append((n, d))
                t.branch_decisions.append((n, d))
            act = turn.get("action")
            if act:
                t.calls.append(ACall(act["call_id"], act["tool"],
                                     act["args_resolved"] if isinstance(act.get("args_resolved"), dict)
                                     else (act["args_raw"] if isinstance(act.get("args_raw"), dict) else {}),
                                     act["args_raw"], _parse(turn.get("tool_output")), n))
    else:
        t.interp_turn, t.final_turn, t.calc_turn = 1, 1, 2
        for turn in turns:
            if turn["kind"] == "plan":
                for e in turn.get("execution") or []:
                    t.calls.append(ACall(e["call_id"], e["tool"],
                                         e["args_resolved"] if isinstance(e.get("args_resolved"), dict)
                                         else (e["args_raw"] if isinstance(e["args_raw"], dict) else {}),
                                         e["args_raw"], _parse(e.get("tool_output")), 1, e.get("step")))
                for d in rec.get("decisions") or []:
                    t.branch_decisions.append((1, d))
            else:
                t.final_turn = 2
                for r in turn.get("reading") or []:
                    t.readings.append((2, r))
                if turn.get("decision"):
                    t.llm_decisions.append((2, turn["decision"]))
    return t


# ---------------------------------------------------------------- expected runs

def loop_steps(program: dict) -> set[str]:
    """Ids of every step inside a `foreach` body (calls that the loop repeats)."""
    found: set[str] = set()

    def walk(steps, inside):
        for s in steps:
            if inside:
                found.add(s["id"])
            if s["op"] == "foreach":
                walk(s.get("do", []), True)
            elif s["op"] == "if":
                walk(s.get("then", []), inside)
                walk(s.get("else", []), inside)

    walk(program["steps"], False)
    return found


@dataclass
class Expected:
    name: str
    result: object          # ProgramResult
    loops: set[str]
    program: dict


def expected_runs(question: dict, provider, ctx) -> list[Expected]:
    """Gold program first, then the allowed alternatives, all run on the run's own boxes."""
    out = []
    progs = [("gold", question["program"])] + [(f"alt{i}", p) for i, p in enumerate(question["alt_programs"])]
    for name, prog in progs:
        res = run_program(prog, question["image_id"], provider, ctx=ctx)
        out.append(Expected(name, res, loop_steps(prog), prog))
    return out


def call_key(tool: str, args: dict) -> tuple:
    a = args if isinstance(args, dict) else {}
    region = _freeze(a.get("region", "full"))
    if tool == "detect_ships":
        return (tool, region)
    if tool == "spatial_query":
        q = a.get("query")
        return (tool, q, region if q in REGION_QUERIES else None, a.get("ship_a"), a.get("ship_b"))
    if tool == "image_stats":
        return (tool, region)
    return (tool,)


# ---------------------------------------------------------------- usage tracking (harmless test)

def call_used_later(trace: Trace, call: ACall, final_value=None) -> bool:
    """Was the output of `call` used afterwards? Followed through references (`$c<k>`), readings and
    decisions that name it."""
    ref = re.compile(rf"\${re.escape(call.call_id)}(?![0-9A-Za-z_])")
    for later in trace.calls:
        if later.call_id != call.call_id and int(later.call_id[1:]) > int(call.call_id[1:]) \
                and ref.search(json.dumps(later.raw_args, ensure_ascii=False, default=str)):
            return True
    for _, r in trace.readings:
        if str(r.get("from", "")).lstrip("$") == call.call_id:
            return True
    return any(str(d.get("condition_from", "")).lstrip("$").split(".")[0] == call.call_id
               for _, d in trace.llm_decisions)


# ---------------------------------------------------------------- stage 1: interpretation

def _norm_region(r):
    return tuple(int(x) for x in r) if isinstance(r, (list, tuple)) else r


def _norm_filters(fs):
    return sorted((f.get("field"), f.get("cmp"), float(f.get("threshold"))) for f in (fs or [])
                  if isinstance(f, dict) and isinstance(f.get("threshold"), (int, float)))


def _norm_branch(b, top_region):
    if not isinstance(b, dict):
        return None
    out = {k: b.get(k) for k in ("on", "cmp", "threshold", "then_target", "else_target")}
    out["then_region"] = _norm_region(b.get("then_region") or top_region)
    out["else_region"] = _norm_region(b.get("else_region") or top_region)
    return out


def interpretation_diff(agent: dict | None, gold: dict) -> tuple[list[str], list[str]]:
    """(differing fields that are judged, differing fields that are not: unused by the gold program or
    statistic-only `unit` / `answer_type`)."""
    if not isinstance(agent, dict):
        return [f for f in gold if f not in STATISTIC_ONLY_FIELDS], []
    used, unused = [], []
    for f in ("target", "region", "filters", "branch", "unit", "answer_type"):
        a, g = agent.get(f), gold.get(f)
        if f == "region":
            same = _norm_region(a) == _norm_region(g)
        elif f == "filters":
            same = _norm_filters(a) == _norm_filters(g)
        elif f == "branch":
            same = _norm_branch(a, agent.get("region")) is None and g is None or (
                g is not None and _norm_branch(a, agent.get("region")) is not None
                and same_value(_norm_branch(a, agent.get("region")), _norm_branch(g, gold.get("region"))))
        else:
            same = a == g
        if same:
            continue
        is_used = f in USED_FIELDS_ALWAYS or (f == "region" and _norm_region(g) != "full") \
            or (f == "filters" and bool(g)) or (f == "branch" and g is not None)
        (used if is_used else unused).append(f)
    return used, unused


def statistic_only_diff(agent: dict | None, gold: dict) -> list[str]:
    """`unit` / `answer_type` fields of the interpretation that differ from the gold one (counted, not judged)."""
    if not isinstance(agent, dict):
        return []
    return [f for f in STATISTIC_ONLY_FIELDS if agent.get(f) != gold.get(f)]


def stage1(rec: dict, trace: Trace, question: dict) -> Dev | None:
    used, _ = interpretation_diff(rec.get("interpretation"), question["gold_interpretation"])
    return Dev(1, trace.interp_turn, "interpretation_mismatch", f"differs in {used}") if used else None


# ---------------------------------------------------------------- stage 2 (+ loop omission of stage 4)

def best_expected(trace: Trace, exps: list[Expected]):
    """The expected run (gold or an allowed alternative) closest to what the agent did."""
    best = None
    for e in exps:
        un, miss = _match(trace, e)
        score = len(un) + len(miss)
        if best is None or score < best[0]:
            best = (score, e, un, miss)
    return best[1], best[2], best[3]


def _match(trace: Trace, exp: Expected):
    calls = exp.result.calls
    remaining = [c for c in calls if c.tool != "calc"]
    unmatched = []
    for a in trace.calls:
        if a.tool == "calc":
            continue
        k = call_key(a.tool, a.args)
        hit = next((c for c in remaining if call_key(c.tool, c.resolved_args or {}) == k), None)
        if hit is None:
            unmatched.append(a)
        else:
            remaining.remove(hit)
    return unmatched, remaining


def stage2(trace: Trace, exp: Expected, unmatched, missing, has_answer: bool) -> list[Dev]:
    devs: list[Dev] = []
    um, ms = list(unmatched), list(missing)
    for u in list(um):
        j = next((i for i, e in enumerate(ms) if e.tool == u.tool), None)
        if j is not None:
            e = ms.pop(j)
            um.remove(u)
            devs.append(Dev(2, u.turn, "wrong_args",
                            f"{u.call_id} {u.tool} {json.dumps(u.args, default=str)[:120]} "
                            f"instead of {json.dumps(e.resolved_args, default=str)[:120]}"))
    for u in list(um):
        if ms:
            e = ms.pop(0)
            um.remove(u)
            devs.append(Dev(2, u.turn, "wrong_tool", f"{u.call_id} {u.tool} instead of {e.tool}"))
    for u in um:
        errored = "error" in u.output
        used = call_used_later(trace, u)
        devs.append(Dev(2, u.turn, "extra_call", f"{u.call_id} {u.tool}", harmless=not used or errored))
    if has_answer:
        turn = trace.final_turn
        for e in ms:
            in_loop = e.step_id in exp.loops
            devs.append(Dev(4 if in_loop else 2, turn, "loop_omission" if in_loop else "missing_call",
                            f"expected {e.tool} {json.dumps(e.resolved_args, default=str)[:120]}"))
    return devs


# ---------------------------------------------------------------- stage 3: reading the results

def _lookup(trace: Trace, call_id: str, fieldname: str):
    call = trace.call(call_id)
    if call is None:
        return False, None
    try:
        return True, resolve_ref(f"${call_id}.{fieldname}", {call_id: call.output})
    except RefError:
        return False, None


def unwrap_value(value, fieldname: str):
    """Models often write a reading as `{"count": 3}` instead of `3`. Unwrap only a one-key object whose key is
    the field's own name (last part of a dotted path); any other object stays as written (a real mismatch)."""
    if isinstance(value, dict) and len(value) == 1:
        (key, inner), = value.items()
        if key == str(fieldname).split(".")[-1]:
            return inner
    return value


def _split_from(item: dict) -> tuple[str, str]:
    src = str(item.get("from", "")).strip().lstrip("$")
    fld = str(item.get("field", "")).strip()
    if "." in src and not fld:
        src, fld = src.split(".", 1)
    return src, fld


def _value_used(trace: Trace, src: str, fld: str, value, rec: dict) -> bool:
    later_ref = f"{src}.{fld}"
    if any(str(d.get("condition_from", "")).lstrip("$") == later_ref for _, d in trace.llm_decisions):
        return True
    blob = json.dumps([c.raw_args for c in trace.calls], ensure_ascii=False, default=str)
    if isinstance(value, (int, float, str)) and json.dumps(value) in blob:
        return True
    ans = (rec.get("answer") or {}).get("value")
    return ans is not None and same_value(ans, value)


def stage3(trace: Trace, rec: dict, question: dict) -> list[Dev]:
    devs = []
    for turn, item in trace.readings:
        src, fld = _split_from(item)
        found, actual = _lookup(trace, src, fld)
        if not found:
            devs.append(Dev(3, turn, "reading_source_missing", f"{src}.{fld} not in any tool result",
                            harmless=not _value_used(trace, src, fld, item.get("value"), rec)))
        elif not same_value(unwrap_value(item.get("value"), fld), actual):
            devs.append(Dev(3, turn, "reading_mismatch",
                            f"{src}.{fld}: wrote {item.get('value')!r}, result has {actual!r}",
                            harmless=not _value_used(trace, src, fld, item.get("value"), rec)))
    spec = question.get("branch_spec") or {}
    for turn, d in trace.llm_decisions:
        if not question["has_branch"]:
            continue
        src, fld = _split_from({"from": str(d.get("condition_from", "")).split(".")[0],
                                "field": ".".join(str(d.get("condition_from", "")).split(".")[1:])})
        found, actual = _lookup(trace, src, fld)
        call = trace.call(src)
        if not found:
            devs.append(Dev(3, turn, "decision_source_missing", f"condition_from {d.get('condition_from')}"))
            continue
        if not same_value(unwrap_value(d.get("condition_value"), fld), actual):
            devs.append(Dev(3, turn, "decision_value_mismatch",
                            f"wrote {d.get('condition_value')!r}, result has {actual!r}"))
            continue
        tools, want = BRANCH_SOURCE.get(spec.get("on"), ((), None))
        if call is not None and want and (call.tool not in tools or fld.split(".")[-1] != want):
            devs.append(Dev(3, turn, "decision_wrong_source",
                            f"condition read from {call.tool}.{fld}, expected {tools}.{want}"))
    return devs


# ---------------------------------------------------------------- stage 4: branch and order

def stage4(trace: Trace, question: dict, exps: list[Expected]) -> list[Dev]:
    devs = []
    if question["has_branch"] and trace.branch_decisions:
        gold = next((e for e in exps if e.name == "gold"), exps[0])
        top = [d for d in gold.result.decisions if d.get("top_level") and d.get("chosen")]
        if top:
            correct = top[-1]["chosen"]
            turn, chosen = trace.branch_decisions[-1][0], trace.branch_decisions[-1][1].get("chosen")
            if chosen != correct:
                devs.append(Dev(4, turn, "wrong_branch", f"chose {chosen}, the received values give {correct}"))
    for i, c in enumerate(trace.calls):
        err = c.output.get("error", "") if isinstance(c.output, dict) else ""
        m = re.search(r"no such call or variable '(c\d+)'", str(err))
        if m and int(m.group(1)[1:]) > i:     # refers to a call that has not been made yet
            devs.append(Dev(4, c.turn, "order_error", f"{c.call_id} used {m.group(1)} before it existed"))
    return devs


# ---------------------------------------------------------------- stage 5: calculation

def _calc_args(args: dict) -> dict:
    return {k: v for k, v in (args or {}).items() if v is not None}


def stage5(trace: Trace, exp: Expected, has_answer: bool, rec: dict) -> list[Dev]:
    devs = []
    turn_of = (lambda c: trace.calc_turn or c.turn)
    agent = [c for c in trace.calls if c.tool == "calc"]
    gold = [c for c in exp.result.calls if c.tool == "calc"]
    for i, c in enumerate(agent):
        if i >= len(gold):
            used = call_used_later(trace, c) or same_value((rec.get("answer") or {}).get("value"),
                                                           c.output.get("result"))
            devs.append(Dev(5, turn_of(c), "extra_calc", f"{c.call_id}", harmless=not used))
            continue
        g = gold[i]
        ga, aa = _calc_args(g.resolved_args), _calc_args(c.args)
        if "error" in c.output or ga.get("op") != aa.get("op") or not same_value(ga, aa):
            used = call_used_later(trace, c) or same_value((rec.get("answer") or {}).get("value"),
                                                           c.output.get("result"))
            devs.append(Dev(5, turn_of(c), "calc_mismatch",
                            f"{c.call_id} {json.dumps(aa, default=str)[:140]} instead of "
                            f"{json.dumps(ga, default=str)[:140]}", harmless=not used and "error" not in c.output))
    if has_answer and len(agent) < len(gold):
        devs.append(Dev(5, trace.final_turn if trace.method == "stepwise" else 2, "calc_skipped",
                        f"{len(gold) - len(agent)} calc step(s) not made; the value was computed by the model"))
    return devs


# ---------------------------------------------------------------- stage 6: answer formatting

def stage6(rec: dict, trace: Trace, question: dict, reachable) -> Dev | None:
    ans = rec.get("answer")
    if not ans:
        return None
    turn = trace.final_turn if trace.method == "stepwise" else 2
    value, unit = ans.get("value"), ans.get("unit")
    unit_ok = normalize_unit(unit) == question["unit"]
    v_ok = value_matches(value, reachable, question["answer_type"])
    if not rec.get("answer_format_ok", True):
        return Dev(6, turn, "format", f"answer {value!r} unit {unit!r} is not well formed")
    if v_ok and not unit_ok:
        return Dev(6, turn, "unit", f"unit {unit!r}, expected {question['unit']!r}")
    if not v_ok and reachable is not None:
        seen = list(flatten([c.output for c in trace.calls])) + [r.get("value") for _, r in trace.readings]
        if any(_present(reachable, x, question["answer_type"]) for x in seen):
            return Dev(6, turn, "transcription", f"answered {value!r}; the received value {reachable!r} was in the results")
    return None


def _present(reachable, candidate, answer_type: str) -> bool:
    if isinstance(candidate, (list, tuple, dict)):
        return False
    if answer_type == "category":
        return isinstance(candidate, str) and candidate == reachable
    return isinstance(candidate, (int, float)) and not isinstance(candidate, bool) \
        and same_value(candidate, reachable, 1e-6)

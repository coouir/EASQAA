"""Gold-program DSL and executor (SPEC §6.3), also the plan language of the batch agent (§7.3).

A program is JSON: `{"steps": [...], "answer": ...}`. Step kinds:
  tool call   {"id", "op": <tool name>, "args": {...}}
  if          {"id", "op": "if", "cond": {"lhs", "cmp", "rhs"}, "then": [...], "else": [...]}
  foreach     {"id", "op": "foreach", "over": <list or ref>, "as": "item", "do": [...]}
Arguments may hold `$<step id>.<field>` references (and `$<loop var>[.<field>]`). The literal image
id `"IMG"` in an `image_id` argument means the image the program runs on.

Inside a `foreach` body a step id refers to the current iteration; after the loop it refers to the
values gathered over all iterations: `$s5.count` is then the list of each iteration's `count`.
`answer` is a literal, a reference, or `{"then": ..., "else": ...}` (optionally `"if": "<id>"`),
which picks the side of the named `if` step, or of the last top-level `if` that ran.

`run_program` runs every tool call through the same `ToolSession` and tool functions the agents
use. Each executed call gets an id `c<k>`; `step_calls` maps plan step ids to those ids.
"""

from dataclasses import dataclass, field
from typing import Any

from sarqa.boxes import BoxProvider
from sarqa.tools import TOOLS, ToolContext, default_context
from sarqa.tools.calc import CMPS
from sarqa.tools.refs import RefError, is_ref, iter_refs, parse_ref, resolve_refs
from sarqa.tools.session import BudgetExceeded, CallRecord, ToolSession

STRUCTURAL = ("if", "foreach")
IMAGE_PLACEHOLDER = "IMG"
HARD_CALL_CAP = 500  # runaway guard when no budget is given (gold programs make <= ~20 calls)
MAX_DEPTH = 4


class ProgramError(ValueError):
    """The program is malformed. `problems` lists every issue found."""

    def __init__(self, problems: list[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


def budget_for(gold_calls: int) -> int:
    """Call limit of a question: max(2 * gold_calls, gold_calls + 3) (SPEC §6.3)."""
    return max(2 * gold_calls, gold_calls + 3)


# ---------------------------------------------------------------- validation

def validate_program(program: Any) -> list[str]:
    """Structural problems of a program, empty if it is well formed."""
    problems: list[str] = []
    if not isinstance(program, dict):
        return ["program must be a JSON object"]
    if not isinstance(program.get("steps"), list) or not program["steps"]:
        problems.append("'steps' must be a non-empty list")
    if "answer" not in program:
        problems.append("'answer' is missing")
    ids: dict[str, int] = {}
    loop_vars: list[str] = []

    def check_refs(value, visible: set[str], where: str):
        for r in iter_refs(value):
            try:
                ident, _ = parse_ref(r)
            except RefError as e:
                problems.append(f"{where}: {e}")
                continue
            if ident not in visible:
                problems.append(f"{where}: reference {r!r} names no earlier step or loop variable")

    def walk(steps, visible: set[str], depth: int):
        if depth > MAX_DEPTH:
            problems.append(f"steps are nested deeper than {MAX_DEPTH}")
            return
        if not isinstance(steps, list):
            problems.append("a step list must be a list")
            return
        for step in steps:
            if not isinstance(step, dict) or not isinstance(step.get("id"), str) or not step["id"]:
                problems.append("every step must be an object with a string 'id'")
                continue
            sid, op = step["id"], step.get("op")
            where = f"step {sid}"
            if sid in ids:
                problems.append(f"{where}: duplicate step id")
            ids[sid] = 1
            if op in TOOLS:
                extra = sorted(set(step) - {"id", "op", "args"})
                if extra:
                    problems.append(f"{where}: unexpected key(s) {extra}")
                if not isinstance(step.get("args", {}), dict):
                    problems.append(f"{where}: 'args' must be an object")
                else:
                    check_refs(step.get("args", {}), visible, where)
            elif op == "if":
                cond = step.get("cond")
                if not isinstance(cond, dict) or set(cond) != {"lhs", "cmp", "rhs"}:
                    problems.append(f"{where}: 'cond' needs exactly lhs, cmp, rhs")
                else:
                    if cond["cmp"] not in CMPS:
                        problems.append(f"{where}: cmp must be one of {sorted(CMPS)}")
                    check_refs(cond, visible, where)
                if "then" not in step:
                    problems.append(f"{where}: 'then' is missing")
                walk(step.get("then", []), visible, depth + 1)
                walk(step.get("else", []), visible, depth + 1)
            elif op == "foreach":
                var = step.get("as", "item")
                if not isinstance(var, str) or not var.isidentifier():
                    problems.append(f"{where}: 'as' must be a simple name")
                    var = "item"
                over = step.get("over")
                if not (isinstance(over, list) or is_ref(over)):
                    problems.append(f"{where}: 'over' must be a list or a reference")
                else:
                    check_refs(over, visible, where)
                if "do" not in step:
                    problems.append(f"{where}: 'do' is missing")
                loop_vars.append(var)
                body_visible = visible | {var}
                walk(step.get("do", []), body_visible, depth + 1)
                visible |= body_visible - {var}  # after the loop, body ids hold gathered lists
            else:
                problems.append(f"{where}: unknown op {op!r}; tools are {sorted(TOOLS)} "
                                f"plus {list(STRUCTURAL)}")
            visible.add(sid)  # ids stay visible to later steps, including after a loop

    visible: set[str] = set()
    walk(program.get("steps", []), visible, 1)
    for v in loop_vars:
        if v in ids:
            problems.append(f"loop variable {v!r} is also a step id")
    if "answer" in program:
        check_refs(program["answer"], visible, "answer")
    return problems


# ---------------------------------------------------------------- execution

@dataclass
class ProgramResult:
    answer: Any
    intermediates: dict[str, Any]              # step id -> output (gathered lists after a loop)
    calls: list[CallRecord]
    step_calls: dict[str, list[str]]           # step id -> call ids it produced
    decisions: list[dict] = field(default_factory=list)   # one entry per `if` evaluated
    errors: list[str] = field(default_factory=list)       # executor-level problems
    budget_exceeded: bool = False

    @property
    def gold_calls(self) -> int:
        """Tool calls actually executed: `if` not counted, untaken branches not counted,
        `foreach` counted per unrolled call (SPEC §6.3)."""
        return len(self.calls)

    @property
    def budget(self) -> int:
        return budget_for(self.gold_calls)

    @property
    def tool_errors(self) -> list[CallRecord]:
        return [c for c in self.calls if c.is_error]

    @property
    def ok(self) -> bool:
        """Ran to the end, no tool error, and an answer was produced."""
        return not (self.errors or self.tool_errors or self.budget_exceeded) \
            and self.answer is not None


class _Executor:
    def __init__(self, session: ToolSession, image_id: str):
        self.session = session
        self.image_id = image_id
        self.env: dict[str, Any] = {}
        self.step_calls: dict[str, list[str]] = {}
        self.decisions: list[dict] = []
        self.errors: list[str] = []

    def run(self, steps: list, trace: list[str], top: bool = False) -> None:
        for step in steps:
            op = step["op"]
            if op == "if":
                self._if(step, trace, top)
            elif op == "foreach":
                self._foreach(step, trace)
            else:
                self._call(step, trace)

    def _call(self, step: dict, trace: list[str]) -> None:
        sid = step["id"]
        args = dict(step.get("args", {}))
        if args.get("image_id") == IMAGE_PLACEHOLDER:
            args["image_id"] = self.image_id
        rec = self.session.call(step["op"], args, scope=self.env, step_id=sid)
        self.env[sid] = rec.output
        self.step_calls.setdefault(sid, []).append(rec.call_id)
        trace.append(sid)

    def _if(self, step: dict, trace: list[str], top: bool) -> None:
        cond = step["cond"]
        entry = {"step": step["id"], "cmp": cond["cmp"], "chosen": None}
        try:
            lhs, rhs = resolve_refs(cond["lhs"], self.env), resolve_refs(cond["rhs"], self.env)
            entry.update(lhs=lhs, rhs=rhs)
            numeric = all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in (lhs, rhs))
            if not numeric and cond["cmp"] not in ("==", "!="):
                raise RefError(f"cannot order {lhs!r} and {rhs!r} with {cond['cmp']}")
            entry["chosen"] = "then" if CMPS[cond["cmp"]](lhs, rhs) else "else"
        except RefError as e:
            self.errors.append(f"step {step['id']}: {e}")
        entry["top_level"] = top
        self.decisions.append(entry)
        if entry["chosen"]:
            self.run(step.get(entry["chosen"], []), trace)

    def _foreach(self, step: dict, trace: list[str]) -> None:
        sid, var = step["id"], step.get("as", "item")
        try:
            items = resolve_refs(step["over"], self.env)
            if not isinstance(items, list):
                raise RefError(f"'over' resolved to {type(items).__name__}, not a list")
        except RefError as e:
            self.errors.append(f"step {sid}: {e}")
            return
        gathered: dict[str, dict[str, list]] = {}
        for item in items:
            self.env[var] = item
            ran: list[str] = []
            self.run(step["do"], ran)
            for body_id in dict.fromkeys(ran):
                for key, val in self.env[body_id].items():
                    gathered.setdefault(body_id, {}).setdefault(key, []).append(val)
        self.env.pop(var, None)
        self.env.update(gathered)
        self.env[sid] = {"iterations": len(items)}
        trace.append(sid)

    def answer(self, spec: Any) -> Any:
        if isinstance(spec, dict) and set(spec) <= {"if", "then", "else"} and \
                ("then" in spec or "else" in spec):
            chosen = None
            for d in self.decisions:
                if d["chosen"] and (d["step"] == spec.get("if") if "if" in spec else d["top_level"]):
                    chosen = d["chosen"]
            if chosen is None:
                raise RefError("answer depends on an 'if' step that did not run")
            spec = spec.get(chosen)
        return resolve_refs(spec, self.env)


def run_program(program: dict, image_id: str, box_provider: BoxProvider, *,
                ctx: ToolContext | None = None, budget: int | None = None) -> ProgramResult:
    """Execute `program` on one image with boxes from `box_provider`.

    `ctx` supplies everything except the boxes (scene tags, pixels, label boxes); it defaults to
    the real HRSID data. `budget` stops the run with `budget_exceeded` when the next call would
    pass it (agent plans, SPEC §7.3); gold programs run without one.
    """
    problems = validate_program(program)
    if problems:
        raise ProgramError(problems)
    ctx = (ctx or default_context()).with_boxes(box_provider)
    session = ToolSession(ctx, budget if budget is not None else HARD_CALL_CAP)
    ex = _Executor(session, image_id)
    exceeded, answer = False, None
    try:
        ex.run(program["steps"], [], top=True)
    except BudgetExceeded as e:
        exceeded = True
        ex.errors.append(str(e))
    if not exceeded:
        try:
            answer = ex.answer(program["answer"])
        except RefError as e:
            ex.errors.append(f"answer: {e}")
    return ProgramResult(answer, dict(ex.env), session.calls, ex.step_calls, ex.decisions,
                         ex.errors, exceeded)

"""Plan-first agent (SPEC §7.3): one planning call, the executor runs the plan, one answering call.

    question -> [LLM: interpretation + whole plan (DSL of program.py)] -> executor runs the tools
             -> [LLM: reading + decision + final answer]

The planner never sees a tool result; earlier results are used only through `$id.field` references.
`if` and `foreach` are allowed in the plan. Tool errors do not stop the executor; their text goes to
the answering call as it is. The call budget counts executed tool calls, `foreach` expansions included.
A plan that does not parse or validate gets one retry, then the run fails as `plan_format_error`.
"""

import json
import time

from sarqa.agents import common as C
from sarqa.agents.llm import seed_for
from sarqa.program import ProgramError, run_program
from sarqa.tools import render
from sarqa.tools.base import ToolContext
from sarqa.tools.session import ToolSession


def _trace(result, plan: dict) -> str:
    """Text of every executed call for the answering call: id, step, tool, arguments, output."""
    step_of = {c.call_id: c.step_id for c in result.calls}
    lines = []
    for c in result.calls:
        args = c.resolved_args if c.resolved_args is not None else c.args
        lines.append(f"{c.call_id} (plan step {step_of[c.call_id]}) {c.tool} "
                     f"{json.dumps(args, ensure_ascii=False)} -> {render(c.output)}")
    return "\n".join(lines) if lines else "(no tool call ran)"


def _plan_conditions(steps: list, out: dict | None = None) -> dict:
    out = {} if out is None else out
    for s in steps:
        if s.get("op") == "if":
            out[s["id"]] = s["cond"]
        for key in ("then", "else", "do"):
            if isinstance(s.get(key), list):
                _plan_conditions(s[key], out)
    return out


def run_batch(question: dict, tool_ctx: ToolContext, llm, *, repeat: int = 0,
              wall_limit_s: float = 300) -> dict:
    seed = seed_for(question["qid"], repeat)
    rec = C.base_record(question, "batch", repeat, seed)
    meter = C.Meter(deadline=time.monotonic() + wall_limit_s)
    session = ToolSession(tool_ctx, budget=question["budget"])  # only for the shared call counters
    messages = [{"role": "system", "content": C.system_prompt("batch")},
                {"role": "user", "content": C.question_message(
                    question, "Reply with your interpretation and the whole plan.")}]
    final, abort = None, None
    try:
        a = C.ask(llm, meter, seed, messages, C.plan_turn_schema(), C.validate_plan_turn,
                  format_kind="plan_format_error")
        plan = a.obj["plan"]
        rec["interpretation"] = a.obj["interpretation"]
        plan_turn = {"turn": 1, "kind": "plan", "llm_prompt_hash": a.prompt_hash, "llm_output": a.obj,
                     "plan": plan, "reading": [], "action": None, "tool_output": None,
                     "tokens_in": a.tokens_in, "tokens_out": a.tokens_out, "ms": a.ms}
        rec["turns"].append(plan_turn)

        try:
            result = run_program(plan, question["image_id"], tool_ctx.boxes, ctx=tool_ctx,
                                 budget=question["budget"])
        except ProgramError as e:  # validated already; kept so a runner bug is not a crash
            raise C.AgentAbort("plan_format_error", str(e)) from e
        session.calls = result.calls   # counters (`tool_calls`) come from the executor's run
        plan_turn["execution"] = [{"call_id": c.call_id, "step": c.step_id, "tool": c.tool,
                                   "args_raw": c.args, "args_resolved": c.resolved_args,
                                   "tool_output": render(c.output)} for c in result.calls]
        plan_turn["step_calls"] = result.step_calls
        conds = _plan_conditions(plan["steps"])
        rec["decisions"] = [C.decision_from_executor(d, conds[d["step"]], result.step_calls)
                            for d in result.decisions if d["step"] in conds]
        if result.budget_exceeded:
            raise C.AgentAbort("budget_exceeded", "; ".join(result.errors))

        messages += [{"role": "assistant", "content": a.reply.content},
                     {"role": "user", "content": "The plan was run. Results:\n" + _trace(result, plan)
                      + ("\n\nExecutor notes: " + "; ".join(e for e in result.errors)
                         if result.errors else "")}]
        b = C.ask(llm, meter, seed, messages, C.batch_answer_schema(), C.validate_batch_answer)
        rec["turns"].append({"turn": 2, "kind": "answer", "llm_prompt_hash": b.prompt_hash,
                             "llm_output": b.obj, "reading": b.obj["reading"], "decision": b.obj["decision"],
                             "action": None, "tool_output": None, "tokens_in": b.tokens_in,
                             "tokens_out": b.tokens_out, "ms": b.ms})
        final = b.obj["final_answer"]
    except C.AgentAbort as e:
        abort = e
    return C.finish(rec, question, meter, session, final, abort)

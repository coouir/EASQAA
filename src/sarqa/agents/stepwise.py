"""Step-by-step agent (SPEC §7.2): interpretation, then one action per turn.

    question -> [LLM: interpretation] -> repeat { [LLM: reading + decision + one tool call | answer]
                                                   -> run the tool -> add the result to the chat }

LLM calls = tool calls + 2. Loops and conditions are done by the model, one call at a time. The tool
call budget is enforced here (`ToolSession` raises before the call that would exceed it); the model
is not told the budget.
"""

import time

from sarqa.agents import common as C
from sarqa.agents.llm import seed_for
from sarqa.tools import render
from sarqa.tools.base import ToolContext
from sarqa.tools.session import BudgetExceeded, ToolSession

FIRST_ACTION = "Interpretation recorded. Now choose your first action."
ERROR_NOTE = ("\n(This call returned an error and did not run. Read the message and change the call "
              "before you try again; sending it unchanged gives the same error.)")


def run_stepwise(question: dict, tool_ctx: ToolContext, llm, *, repeat: int = 0,
                 wall_limit_s: float = 300) -> dict:
    seed = seed_for(question["qid"], repeat)
    rec = C.base_record(question, "stepwise", repeat, seed)
    meter = C.Meter(deadline=time.monotonic() + wall_limit_s)
    session = ToolSession(tool_ctx, budget=question["budget"])
    system = C.system_prompt("stepwise")
    messages = [{"role": "system", "content": system},
                {"role": "user", "content": C.question_message(
                    question, "First reply with your interpretation of the question.")}]
    final, abort = None, None
    try:
        a = C.ask(llm, meter, seed, messages, C.interpretation_turn_schema(),
                  C.validate_interpretation_turn)
        rec["interpretation"] = a.obj["interpretation"]
        rec["turns"].append({"turn": 0, "kind": "interpretation", "llm_prompt_hash": a.prompt_hash,
                             "llm_output": a.obj, "reading": [], "action": None, "tool_output": None,
                             "tokens_in": a.tokens_in, "tokens_out": a.tokens_out, "ms": a.ms})
        messages += [{"role": "assistant", "content": a.reply.content},
                     {"role": "user", "content": FIRST_ACTION}]
        turn = 0
        while final is None:
            turn += 1
            a = C.ask(llm, meter, seed, messages, C.stepwise_schema(), C.validate_step)
            step, action = a.obj, a.obj["action"]
            entry = {"turn": turn, "kind": "step", "llm_prompt_hash": a.prompt_hash, "llm_output": step,
                     "reading": step["reading"], "action": None, "tool_output": None,
                     "tokens_in": a.tokens_in, "tokens_out": a.tokens_out, "ms": a.ms}
            rec["turns"].append(entry)
            if step["decision"] is not None:
                rec["decisions"].append({**step["decision"], "turn": turn})
            if action["type"] == "answer":
                final = {"answer": action["answer"], "unit": action["unit"]}
                break
            try:
                call = session.call(action["tool"], action["args"])
            except BudgetExceeded as e:
                raise C.AgentAbort("budget_exceeded", str(e)) from e
            entry["action"] = {"call_id": call.call_id, "tool": call.tool, "args_raw": call.args,
                               "args_resolved": call.resolved_args}
            entry["tool_output"] = render(call.output)
            messages += [{"role": "assistant", "content": a.reply.content},
                         {"role": "user", "content": f"Result of {call.call_id} ({call.tool}):\n"
                                                     f"{entry['tool_output']}"
                                                     f"{ERROR_NOTE if 'error' in call.output else ''}"}]
    except C.AgentAbort as e:
        abort = e
    return C.finish(rec, question, meter, session, final, abort)

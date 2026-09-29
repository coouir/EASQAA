"""What both agents share (SPEC §7.1): prompts, output schemas, the one-retry LLM call, budget and
time limits, grading and the run-record skeleton.

Both methods use the same tools and tool text, answer format, call budget, seed rule, reference
rule (`$c<k>.<field>`, handled by `ToolSession`) and log format. Prompt text lives in
`agents/prompts/*.md`; its SHA-256 goes into every run record.
"""

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sarqa.agents.llm import LLMError, LLMReply
from sarqa.grading import grade
from sarqa.questions.vocab import (
    CATEGORY_ANSWERS,
    INTERPRETATION_KEYS,
    UNITS,
    interpretation_schema,
)
from sarqa.tools import TOOLS

PROMPT_DIR = Path(__file__).parent / "prompts"
DECISION_CMPS = ("==", "!=", ">", ">=", "<", "<=")
FAIL_KINDS = ("budget_exceeded", "format_error", "plan_format_error", "tool_error", "timeout",
              "llm_error", "runner_exception", "unknown")


class AgentAbort(Exception):
    """The run cannot continue; `kind` is the `fail_kind` of the record."""

    def __init__(self, kind: str, detail: str = ""):
        super().__init__(f"{kind}: {detail}")
        self.kind, self.detail = kind, detail


# ---------------------------------------------------------------- prompts

def load_prompt(name: str) -> str:
    return (PROMPT_DIR / f"{name}.md").read_text(encoding="utf-8")


def prompt_hashes() -> dict[str, str]:
    return {p.stem: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(PROMPT_DIR.glob("*.md"))}


def system_prompt(method: str) -> str:
    parts = {"stepwise": ["common", "stepwise"], "batch": ["common", "batch_plan", "batch_answer"]}
    return "\n\n".join(load_prompt(n) for n in parts[method])


def question_message(question: dict, tail: str) -> str:
    return f"image_id: {question['image_id']}\n\nQuestion: {question['text_ko']}\n\n{tail}"


# ---------------------------------------------------------------- schemas

_ANY = {}
_ANSWER_VALUE = {"anyOf": [{"type": "number"}, {"type": "string", "enum": list(CATEGORY_ANSWERS)}]}


def reading_schema() -> dict:
    item = {"type": "object",
            "properties": {"from": {"type": "string"}, "field": {"type": "string"}, "value": _ANY},
            "required": ["from", "field", "value"]}
    return {"type": "array", "items": item}


def decision_schema() -> dict:
    obj = {"type": "object",
           "properties": {"condition_from": {"type": "string"}, "condition_value": _ANY,
                          "threshold": _ANY, "cmp": {"type": "string", "enum": list(DECISION_CMPS)},
                          "chosen": {"type": "string", "enum": ["then", "else"]}},
           "required": ["condition_from", "condition_value", "threshold", "cmp", "chosen"]}
    return {"anyOf": [{"type": "null"}, obj]}


def interpretation_turn_schema() -> dict:
    return {"type": "object", "properties": {"interpretation": interpretation_schema()},
            "required": ["interpretation"]}


def final_answer_schema() -> dict:
    return {"type": "object",
            "properties": {"answer": _ANSWER_VALUE, "unit": {"type": "string", "enum": list(UNITS)}},
            "required": ["answer", "unit"]}


def stepwise_schema() -> dict:
    tool = {"type": "object",
            "properties": {"type": {"type": "string", "enum": ["tool"]},
                           "tool": {"type": "string", "enum": sorted(TOOLS)},
                           "args": {"type": "object"}},
            "required": ["type", "tool", "args"]}
    answer = {"type": "object",
              "properties": {"type": {"type": "string", "enum": ["answer"]},
                             **final_answer_schema()["properties"]},
              "required": ["type", "answer", "unit"]}
    return {"type": "object",
            "properties": {"reading": reading_schema(), "decision": decision_schema(),
                           "action": {"anyOf": [tool, answer]}},
            "required": ["reading", "decision", "action"]}


def plan_turn_schema() -> dict:
    plan = {"type": "object",
            "properties": {"steps": {"type": "array", "items": {"type": "object"}}, "answer": _ANY},
            "required": ["steps", "answer"]}
    return {"type": "object",
            "properties": {"interpretation": interpretation_schema(), "plan": plan},
            "required": ["interpretation", "plan"]}


def batch_answer_schema() -> dict:
    return {"type": "object",
            "properties": {"reading": reading_schema(), "decision": decision_schema(),
                           "final_answer": final_answer_schema()},
            "required": ["reading", "decision", "final_answer"]}


# ---------------------------------------------------------------- light validation of replies

def _validate_reading(x) -> list[str]:
    if not isinstance(x, list):
        return ["reading must be a list"]
    return [f"reading[{i}] needs from, field, value" for i, r in enumerate(x)
            if not (isinstance(r, dict) and {"from", "field", "value"} <= set(r))]


def _validate_decision(x) -> list[str]:
    if x is None:
        return []
    need = {"condition_from", "condition_value", "threshold", "cmp", "chosen"}
    if not (isinstance(x, dict) and need <= set(x)) or x.get("chosen") not in ("then", "else"):
        return ["decision must be null or {condition_from, condition_value, threshold, cmp, chosen}"]
    return []


def _validate_final(x) -> list[str]:
    if not isinstance(x, dict) or "answer" not in x or "unit" not in x:
        return ["the answer needs `answer` and `unit`"]
    return []


def validate_interpretation_turn(x) -> list[str]:
    it = x.get("interpretation") if isinstance(x, dict) else None
    if not isinstance(it, dict) or not set(INTERPRETATION_KEYS) <= set(it):
        return [f"`interpretation` must be an object with {list(INTERPRETATION_KEYS)}"]
    return []


def validate_step(x) -> list[str]:
    if not isinstance(x, dict) or not {"reading", "decision", "action"} <= set(x):
        return ["reply must be an object with reading, decision, action"]
    problems = _validate_reading(x["reading"]) + _validate_decision(x["decision"])
    a = x["action"]
    if not isinstance(a, dict) or a.get("type") not in ("tool", "answer"):
        return problems + ["action.type must be 'tool' or 'answer'"]
    if a["type"] == "tool" and not (isinstance(a.get("tool"), str) and isinstance(a.get("args"), dict)):
        problems.append("a tool action needs `tool` (string) and `args` (object)")
    if a["type"] == "answer":
        problems += _validate_final(a)
    return problems


def validate_plan_turn(x) -> list[str]:
    problems = validate_interpretation_turn(x)
    plan = x.get("plan") if isinstance(x, dict) else None
    if not isinstance(plan, dict):
        return problems + ["`plan` must be an object {steps, answer}"]
    from sarqa.program import validate_program

    return problems + validate_program(plan)


def validate_batch_answer(x) -> list[str]:
    if not isinstance(x, dict) or not {"reading", "decision", "final_answer"} <= set(x):
        return ["reply must be an object with reading, decision, final_answer"]
    return _validate_reading(x["reading"]) + _validate_decision(x["decision"]) \
        + _validate_final(x["final_answer"])


# ---------------------------------------------------------------- the LLM call with one retry

@dataclass
class Meter:
    """Counts of one run: LLM calls (retries included), tokens, the wall-clock deadline."""

    deadline: float
    llm_calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    format_retries: int = 0
    t0: float = field(default_factory=time.monotonic)

    @property
    def wall_ms(self) -> int:
        return int((time.monotonic() - self.t0) * 1000)

    def remaining(self) -> float:
        return self.deadline - time.monotonic()


@dataclass
class Ask:
    obj: Any
    reply: LLMReply
    prompt_hash: str
    tokens_in: int
    tokens_out: int
    ms: int


def ask(llm, meter: Meter, seed: int, messages: list[dict], schema: dict, validator,
        format_kind: str = "format_error") -> Ask:
    """One structured LLM call. A reply that does not parse or validate gets **one** retry with the
    problem stated; a second failure aborts the run as `format_kind` (SPEC §7.1)."""
    prompt_hash = hashlib.sha256(json.dumps(messages, ensure_ascii=False).encode()).hexdigest()
    tin = tout = ms = 0
    convo, problems = messages, []
    for attempt in range(2):
        if meter.remaining() <= 0:
            raise AgentAbort("timeout", "wall-clock limit reached before the LLM call")
        try:
            reply = llm.chat(convo, schema, seed, timeout=max(1.0, meter.remaining()))
        except LLMError as e:
            raise AgentAbort("timeout" if meter.remaining() <= 0 else "llm_error", str(e)) from e
        meter.llm_calls += 1
        meter.tokens_in += reply.tokens_in
        meter.tokens_out += reply.tokens_out
        tin, tout, ms = tin + reply.tokens_in, tout + reply.tokens_out, ms + reply.ms
        try:
            obj = json.loads(reply.content)
            problems = validator(obj)
        except json.JSONDecodeError as e:
            obj, problems = None, [f"not valid JSON ({e.msg})"]
        if not problems:
            return Ask(obj, reply, prompt_hash, tin, tout, ms)
        if attempt == 0:
            meter.format_retries += 1
            convo = messages + [
                {"role": "assistant", "content": reply.content},
                {"role": "user", "content": "Your last reply was not accepted: " + "; ".join(problems[:4])
                 + ". Reply again with only the JSON object in the required format."}]
    raise AgentAbort(format_kind, "; ".join(problems[:4]))


# ---------------------------------------------------------------- decisions and records

def decision_from_executor(entry: dict, cond: dict, step_calls: dict[str, list[str]]) -> dict:
    """Executor `if` record -> the run-record `decisions` format (`condition_from` = `c<k>.<field>`)."""
    lhs = cond["lhs"]
    ref = lhs
    if isinstance(lhs, str) and lhs.startswith("$"):
        ident, _, rest = lhs[1:].partition(".")
        calls = step_calls.get(ident)
        ref = f"{calls[-1]}.{rest}" if calls else lhs[1:]
    return {"condition_from": ref, "condition_value": entry.get("lhs"), "threshold": entry.get("rhs"),
            "cmp": entry["cmp"], "chosen": entry["chosen"], "step": entry["step"]}


def base_record(question: dict, method: str, repeat: int, seed: int) -> dict:
    return {"method": method, "qid": question["qid"], "level": question["level"], "repeat": repeat,
            "seed": seed, "status": None, "fail_kind": None, "error_detail": None,
            "answer_raw": None, "answer": None, "correct": False, "answer_format_ok": False,
            "unit_only_fix": False, "interpretation": None, "turns": [], "decisions": [],
            "tool_calls": 0, "llm_calls": 0, "tokens_in": 0, "tokens_out": 0, "format_retries": 0,
            "wall_ms": 0, "budget": question["budget"], "over_budget": False}


def finish(rec: dict, question: dict, meter: Meter, session, final: dict | None,
           abort: AgentAbort | None) -> dict:
    """Fill the counters and grade the final answer (or record the failure)."""
    rec["tool_calls"] = len(session.calls)
    rec["llm_calls"], rec["tokens_in"], rec["tokens_out"] = meter.llm_calls, meter.tokens_in, meter.tokens_out
    rec["format_retries"], rec["wall_ms"] = meter.format_retries, meter.wall_ms
    if abort is not None or final is None:
        rec["status"] = "exec_fail"
        rec["fail_kind"] = abort.kind if abort else "unknown"
        rec["error_detail"] = abort.detail if abort else "no final answer"
        rec["over_budget"] = rec["fail_kind"] == "budget_exceeded"
        return rec
    rec["status"] = "ok"
    rec["answer_raw"] = json.dumps(final, ensure_ascii=False)
    rec["answer"] = {"value": final.get("answer"), "unit": final.get("unit")}
    g = grade(final.get("answer"), final.get("unit"), question["gold_answer"], question["unit"],
              question["answer_type"], question["tolerance"]["rel"] or 0.05)
    rec["correct"], rec["unit_only_fix"], rec["answer_format_ok"] = g.correct, g.unit_only_fix, g.answer_format_ok
    return rec

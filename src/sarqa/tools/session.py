"""One run's tool calls: call ids, reference resolution, budget, and the call log.

Both agents and the gold-program executor call tools only through `ToolSession.call`, so ids
(`c1, c2, ...`), reference handling and error texts are identical everywhere (SPEC §7.1).
"""

from dataclasses import dataclass
from typing import Any

from sarqa.tools.base import ToolContext, call_tool
from sarqa.tools.refs import RefError, resolve_refs


class BudgetExceeded(Exception):
    """The next call would exceed the call budget (SPEC §6.3); the run stops as 'budget exceeded'."""


@dataclass
class CallRecord:
    call_id: str
    tool: Any
    args: Any            # as written by the caller (references unresolved)
    resolved_args: Any   # after reference resolution; None if resolution failed
    output: dict
    step_id: str | None = None

    @property
    def is_error(self) -> bool:
        return "error" in self.output


class ToolSession:
    def __init__(self, ctx: ToolContext, budget: int | None = None):
        self.ctx = ctx
        self.budget = budget
        self.calls: list[CallRecord] = []
        self.outputs: dict[str, dict] = {}  # call id -> output, the scope of `$c<k>` references

    def call(self, tool: Any, args: Any, *, scope: dict | None = None,
             step_id: str | None = None) -> CallRecord:
        """Run one call. `scope` adds names (plan step ids, loop variables) to the `$c<k>` outputs.

        Raises `BudgetExceeded` *before* running if the budget is used up. Unresolvable references
        do not raise: the call still counts and its output is `{"error": ...}` (SPEC §7.1).
        """
        if self.budget is not None and len(self.calls) >= self.budget:
            raise BudgetExceeded(f"tool call budget of {self.budget} used up")
        call_id = f"c{len(self.calls) + 1}"
        try:
            resolved = resolve_refs(args, {**self.outputs, **(scope or {})})
            output = call_tool(self.ctx, tool, resolved)
        except RefError as e:
            resolved, output = None, {"error": f"{tool}: {e}"}
        rec = CallRecord(call_id, tool, args, resolved, output, step_id)
        self.calls.append(rec)
        self.outputs[call_id] = output
        return rec

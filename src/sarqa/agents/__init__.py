"""The two agents (SPEC §7): step-by-step (ReAct-like) and plan-first (ReWOO-like)."""

METHODS = ("stepwise", "batch")


def run_agent(method: str, question: dict, tool_ctx, llm, *, repeat: int = 0, wall_limit_s: float = 300):
    """Run one question with one method; returns the agent part of the run record."""
    if method == "stepwise":
        from sarqa.agents.stepwise import run_stepwise

        return run_stepwise(question, tool_ctx, llm, repeat=repeat, wall_limit_s=wall_limit_s)
    if method == "batch":
        from sarqa.agents.batch import run_batch

        return run_batch(question, tool_ctx, llm, repeat=repeat, wall_limit_s=wall_limit_s)
    raise ValueError(f"unknown method {method!r}; expected one of {METHODS}")

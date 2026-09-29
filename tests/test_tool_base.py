import pytest

from sarqa.tools.base import TOOLS, ToolError, call_tool, render, tool
from tools_fixtures import mini_context


@pytest.fixture
def scratch_tools():
    before = dict(TOOLS)

    @tool
    def _echo(ctx, image_id, n=1):
        ctx.ship_boxes(image_id)
        return {"image_id": image_id, "n": n}

    @tool
    def _fails(ctx):
        raise ToolError("no way")

    @tool
    def _buggy(ctx):
        return 1 // 0

    yield
    TOOLS.clear()
    TOOLS.update(before)


def test_call_tool_ok_and_defaults(scratch_tools):
    ctx = mini_context()
    assert call_tool(ctx, "_echo", {"image_id": "m1.jpg"}) == {"image_id": "m1.jpg", "n": 1}


def test_call_tool_error_cases_return_error_dicts(scratch_tools):
    ctx = mini_context()
    assert "unknown tool" in call_tool(ctx, "nope", {})["error"]
    assert "unknown tool" in call_tool(ctx, ["x"], {})["error"]
    assert "JSON object" in call_tool(ctx, "_echo", [1])["error"]
    assert "missing required" in call_tool(ctx, "_echo", {})["error"]
    assert "unexpected argument" in call_tool(ctx, "_echo", {"image_id": "m1.jpg", "k": 2})["error"]
    assert "unknown image_id" in call_tool(ctx, "_echo", {"image_id": "zz.jpg"})["error"]
    assert "image_id must be a string" in call_tool(ctx, "_echo", {"image_id": 3})["error"]
    assert call_tool(ctx, "_fails", {}) == {"error": "_fails: no way"}
    assert "internal error (ZeroDivisionError" in call_tool(ctx, "_buggy", {})["error"]


def test_render_is_compact_json():
    assert render({"a": [1, 2], "b": "x"}) == '{"a":[1,2],"b":"x"}'

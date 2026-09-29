"""docs/tools.md is pinned to the code: parameter lists and example outputs must match."""

import inspect
import json
import re
from pathlib import Path

import pytest

from sarqa.tools import TOOLS, call_tool, render
from tools_fixtures import mini_context

DOC = (Path(__file__).resolve().parents[1] / "docs" / "tools.md").read_text(encoding="utf-8")
EXAMPLE = re.compile(r"<!--example (\{.*?\}) -->\n```json\n(.*?)\n```", re.DOTALL)
PARAMS = re.compile(r"<!--params (\w+): (.*?) -->")


def test_the_five_tools_are_exactly_those_of_the_spec():
    assert sorted(TOOLS) == ["calc", "detect_ships", "get_metadata", "image_stats", "spatial_query"]


def test_documented_parameters_match_the_signatures():
    documented = {name: [p.strip() for p in params.split(",")] for name, params in PARAMS.findall(DOC)}
    assert set(documented) == set(TOOLS)
    for name, fn in TOOLS.items():
        assert documented[name] == list(inspect.signature(fn).parameters)[1:], name


EXAMPLES = [(json.loads(spec), out) for spec, out in EXAMPLE.findall(DOC)]


def test_examples_exist_for_every_tool():
    assert {spec["tool"] for spec, _ in EXAMPLES} == set(TOOLS)


@pytest.mark.parametrize("spec,expected", EXAMPLES,
                         ids=[f"{s['tool']}-{i}" for i, (s, _) in enumerate(EXAMPLES)])
def test_documented_example_is_the_real_output(spec, expected):
    actual = render(call_tool(mini_context(), spec["tool"], spec["args"]))
    assert actual == expected

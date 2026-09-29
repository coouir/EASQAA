"""Shared tool machinery (SPEC §5.1): context, error convention, registry, text rendering.

A tool is a function `fn(ctx, **args) -> dict`. It never raises to the caller: `call_tool` turns
every failure into `{"error": "..."}` so the agent can read it on the next turn. The same functions
run the gold programs (SPEC §6.3), always through `call_tool`.
"""

import functools
import inspect
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from typing import Any

import numpy as np

from sarqa.boxes import Box, BoxProvider
from sarqa.config import load_config, repo_path


class ToolError(Exception):
    """A domain error raised inside a tool; its message becomes the `error` text."""


@dataclass(frozen=True)
class ToolContext:
    """What tools may look at.

    boxes       the box source under test (label | detected | injected | corrected)
    label_boxes always the human labels; only `image_stats` uses them (noise mask, SPEC §5.3)
    scenes      image id -> "inshore" | "offshore"
    load_image  image id -> 2-D uint8 grayscale array
    """

    boxes: BoxProvider
    label_boxes: BoxProvider
    scenes: Mapping[str, str]
    load_image: Callable[[str], np.ndarray]

    def with_boxes(self, boxes: BoxProvider) -> "ToolContext":
        return replace(self, boxes=boxes)

    def ship_boxes(self, image_id: str) -> list[Box]:
        if not isinstance(image_id, str):
            raise ToolError("image_id must be a string")
        try:
            return self.boxes.boxes(image_id)
        except KeyError:
            raise ToolError(f"unknown image_id: {image_id}") from None


@functools.lru_cache(maxsize=1)
def default_context() -> ToolContext:
    """Real-data context: label boxes as the box source, scene tags, HRSID JPEG loader."""
    from PIL import Image

    from sarqa.boxes import label_provider

    cfg = load_config()
    with open(repo_path(cfg["paths"]["scenes"]), encoding="utf-8") as f:
        scenes = {n: m["tag"] for n, m in json.load(f)["images"].items()}
    img_dir = repo_path(cfg["paths"]["hrsid_root"]) / "JPEGImages"

    @functools.lru_cache(maxsize=cfg["tools"]["image_cache"])
    def load(image_id: str) -> np.ndarray:
        try:
            with Image.open(img_dir / image_id) as im:
                return np.asarray(im.convert("L"), dtype=np.uint8)
        except (FileNotFoundError, OSError) as e:
            raise ToolError(f"cannot read image {image_id}") from e

    labels = label_provider()
    return ToolContext(boxes=labels, label_boxes=labels, scenes=scenes, load_image=load)


TOOLS: dict[str, Callable[..., dict]] = {}


def tool(fn: Callable[..., dict]) -> Callable[..., dict]:
    """Register a tool under its function name."""
    TOOLS[fn.__name__] = fn
    return fn


def call_tool(ctx: ToolContext, name: Any, args: Any) -> dict:
    """Run one tool call. Always returns a dict; failures are `{"error": "..."}`."""
    if not isinstance(name, str) or name not in TOOLS:
        return {"error": f"unknown tool: {name!r}; available: {sorted(TOOLS)}"}
    if not isinstance(args, dict):
        return {"error": "arguments must be a JSON object"}
    params = list(inspect.signature(TOOLS[name]).parameters.values())[1:]  # skip ctx
    unknown = sorted(set(args) - {p.name for p in params})
    if unknown:
        return {"error": f"{name}: unexpected argument(s) {unknown}; "
                         f"allowed: {[p.name for p in params]}"}
    missing = [p.name for p in params if p.default is inspect.Parameter.empty and p.name not in args]
    if missing:
        return {"error": f"{name}: missing required argument(s) {missing}"}
    try:
        return TOOLS[name](ctx, **args)
    except ToolError as e:
        return {"error": f"{name}: {e}"}
    except Exception as e:  # noqa: BLE001 - a tool bug must not stop a run (SPEC §0-6)
        return {"error": f"{name}: internal error ({type(e).__name__}: {e})"}


def render(output: dict) -> str:
    """The text the agent reads: compact JSON, key order as produced by the tool."""
    return json.dumps(output, ensure_ascii=False, separators=(",", ":"))

"""The five tools (SPEC §5.2). Importing this package registers them in `TOOLS`."""

from sarqa.tools import (  # noqa: F401  (register the tools)
    detect_ships,
    get_metadata,
    spatial_query,
)
from sarqa.tools.base import TOOLS, ToolContext, ToolError, call_tool, default_context, render

__all__ = ["TOOLS", "ToolContext", "ToolError", "call_tool", "default_context", "render"]

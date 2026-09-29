"""Reference resolution shared by both agents and the gold-program executor (SPEC §7.1).

An argument value may be a literal or a reference `$<id>.<field>[.<field>...]` to an earlier
output, e.g. `$c3.count`, `$c2.long_side_px`, `$s1.scene`, or `$item.x1` for a loop variable.
A string that is exactly a reference is replaced by the referenced value (a number, a list, ...);
lists and objects are searched recursively. A string starting with `$` that is not a well-formed
reference is an error. Path parts may be field names or list indices (`$c1.ships.0.id`).
"""

import re
from collections.abc import Iterator, Mapping
from typing import Any

REF = re.compile(r"^\$([A-Za-z_][A-Za-z0-9_]*)((?:\.[A-Za-z0-9_]+)*)$")


class RefError(Exception):
    """A reference that cannot be resolved; the caller turns it into a tool `{"error"}`."""


def is_ref(value: Any) -> bool:
    return isinstance(value, str) and value.startswith("$")


def parse_ref(value: str) -> tuple[str, list[str]]:
    m = REF.match(value)
    if m is None:
        raise RefError(f"malformed reference {value!r}; write $<id>.<field>, e.g. $c1.count")
    return m.group(1), [p for p in m.group(2).split(".") if p]


def resolve_ref(value: str, scope: Mapping[str, Any]) -> Any:
    ident, path = parse_ref(value)
    if ident not in scope:
        raise RefError(f"no such call or variable {ident!r} (reference {value!r})")
    cur = scope[ident]
    for part in path:
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        elif isinstance(cur, list) and part.isdigit() and int(part) < len(cur):
            cur = cur[int(part)]
        else:
            hint = f" ({ident} returned an error: {cur['error']})" \
                if isinstance(cur, dict) and "error" in cur else ""
            raise RefError(f"{ident} has no field {part!r} (reference {value!r}){hint}")
    return cur


def resolve_refs(value: Any, scope: Mapping[str, Any]) -> Any:
    """Copy of `value` with every reference replaced. Raises `RefError`."""
    if isinstance(value, str):
        return resolve_ref(value, scope) if value.startswith("$") else value
    if isinstance(value, list):
        return [resolve_refs(v, scope) for v in value]
    if isinstance(value, dict):
        return {k: resolve_refs(v, scope) for k, v in value.items()}
    return value


def iter_refs(value: Any) -> Iterator[str]:
    """Every string in `value` that starts with `$` (for static checks)."""
    if isinstance(value, str):
        if value.startswith("$"):
            yield value
    elif isinstance(value, list):
        for v in value:
            yield from iter_refs(v)
    elif isinstance(value, dict):
        for v in value.values():
            yield from iter_refs(v)

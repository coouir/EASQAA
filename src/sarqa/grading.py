"""Scoring (SPEC §6.5). Always against the question's `gold_answer` (label answer).

- `int` and `category`: exact match after normalising case, whitespace and unit spelling
- `float`: |answer - gold| <= 0.05 * |gold|
- the unit must match the question's unit; a wrong unit is `correct=False`, and `unit_only_fix`
  records that the value alone would have been right
"""

import math
from dataclasses import dataclass

REL_TOL = 0.05

UNIT_ALIASES = {
    "px": "px", "pixel": "px", "pixels": "px", "픽셀": "px",
    "ships": "ships", "ship": "ships", "척": "ships", "vessels": "ships",
    "percent": "percent", "%": "percent", "pct": "percent", "퍼센트": "percent",
    "none": "none", "": "none", "null": "none", "unitless": "none", "count": "none",
}


def normalize_unit(unit) -> str | None:
    """Canonical unit, or `None` if the spelling is not recognised."""
    if unit is None:
        return "none"
    return UNIT_ALIASES.get(str(unit).strip().lower())


def _as_number(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)) and math.isfinite(v):
        return float(v)
    if isinstance(v, str):
        try:
            x = float(v.strip().replace(",", ""))
            return x if math.isfinite(x) else None
        except ValueError:
            return None
    return None


def _norm_category(v) -> str | None:
    return v.strip().lower().replace(" ", "_").replace("-", "_") if isinstance(v, str) else None


def value_matches(answer, gold, answer_type: str, rel: float = REL_TOL) -> bool:
    if answer_type == "category":
        return _norm_category(answer) == _norm_category(gold)
    a, g = _as_number(answer), _as_number(gold)
    if a is None or g is None:
        return False
    if answer_type == "int":
        return a == g and a == int(a)
    return abs(a - g) <= rel * abs(g) + 1e-12


@dataclass(frozen=True)
class Grade:
    correct: bool
    unit_only_fix: bool
    answer_format_ok: bool


def grade(answer, unit, gold, gold_unit: str, answer_type: str, rel: float = REL_TOL) -> Grade:
    """`answer`/`unit` as the agent wrote them (either may be missing -> not correct)."""
    if answer is None:
        return Grade(False, False, False)
    value_ok = value_matches(answer, gold, answer_type, rel)
    u = normalize_unit(unit)
    unit_ok = u == gold_unit
    format_ok = (u is not None) and (_as_number(answer) is not None if answer_type != "category"
                                     else _norm_category(answer) is not None)
    return Grade(value_ok and unit_ok, value_ok and not unit_ok, format_ok)

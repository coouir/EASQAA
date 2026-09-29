"""Closed vocabulary of the question interpretation (SPEC §7.1) and the shared answer enums.

The `target` enum is built once from the whole template catalogue; questions never narrow it
(that would hint at the answer). The same vocabulary describes a question's `gold_interpretation`
and the agent's first output, so the classifier compares them field by field (SPEC §11.3, stage 1).
`docs/deviations.md` lists where it goes beyond the SPEC's example (extra targets, `percent`,
the `noisiest_region` / `densest_region` regions, `then_region` / `else_region`).
"""

QUADRANTS = ("top_left", "top_right", "bottom_left", "bottom_right")

TARGETS = (
    "ship_count",                 # ships in `region` (full, a quadrant, edge, or a rectangle)
    "scene_tag",                  # inshore / offshore
    "mean_brightness",            # mean grey level of `region`
    "nearest_distance",           # centre distance of the closest pair of ships (px)
    "nearest_distance_ratio",     # the same, as a percentage of the image width
    "max_length",                 # longest side (px) of the longest ship
    "longest_neighbor_distance",  # from the longest ship to its nearest other ship (px)
    "pair_distance",              # between the longest and the shortest ship (px)
    "count_over_threshold",       # ships whose `filters` hold
    "region_argmax",              # quadrant with the most ships
    "region_argmax_long",         # quadrant with the most ships that satisfy `filters`
    "brightest_region",           # quadrant with the highest mean brightness
    "noisiest_region",            # quadrant with the highest background noise
    "empty_region_count",         # quadrants without a ship
    "branch",                     # a condition picks one of two targets (`branch` object)
)
REGIONS = ("full", *QUADRANTS, "edge", "noisiest_region", "densest_region")  # or [x1, y1, x2, y2]
FILTER_FIELDS = ("length_px", "noise")
COMPARATORS = (">", ">=", "<", "<=")
BRANCH_ON = ("scene", "ship_count", "max_length", "noise")
BRANCH_CMPS = ("==", ">", ">=", "<", "<=")
UNITS = ("px", "ships", "none", "percent")
ANSWER_TYPES = ("int", "float", "category")
CATEGORY_ANSWERS = (*QUADRANTS, "inshore", "offshore", "yes", "no")

INTERPRETATION_KEYS = ("target", "region", "filters", "branch", "unit", "answer_type")
BRANCH_KEYS = ("on", "cmp", "threshold", "then_target", "else_target", "then_region", "else_region")

_NUM = {"type": "number"}
_REGION_RECT = {"type": "array", "items": _NUM, "minItems": 4, "maxItems": 4}


def region_schema() -> dict:
    return {"anyOf": [{"type": "string", "enum": list(REGIONS)}, _REGION_RECT]}


def interpretation_schema() -> dict:
    """JSON schema of the agent's first output (`format` of the Ollama call)."""
    branch = {
        "type": "object",
        "properties": {
            "on": {"type": "string", "enum": list(BRANCH_ON)},
            "cmp": {"type": "string", "enum": list(BRANCH_CMPS)},
            "threshold": {"anyOf": [_NUM, {"type": "string", "enum": ["inshore", "offshore"]}]},
            "then_target": {"type": "string", "enum": list(TARGETS[:-1])},
            "else_target": {"type": "string", "enum": list(TARGETS[:-1])},
            "then_region": {"anyOf": [{"type": "null"}, region_schema()]},
            "else_region": {"anyOf": [{"type": "null"}, region_schema()]},
        },
        "required": list(BRANCH_KEYS),
    }
    flt = {
        "type": "object",
        "properties": {"field": {"type": "string", "enum": list(FILTER_FIELDS)},
                       "cmp": {"type": "string", "enum": list(COMPARATORS)},
                       "threshold": _NUM},
        "required": ["field", "cmp", "threshold"],
    }
    return {
        "type": "object",
        "properties": {
            "target": {"type": "string", "enum": list(TARGETS)},
            "region": region_schema(),
            "filters": {"type": "array", "items": flt},
            "branch": {"anyOf": [{"type": "null"}, branch]},
            "unit": {"type": "string", "enum": list(UNITS)},
            "answer_type": {"type": "string", "enum": list(ANSWER_TYPES)},
        },
        "required": list(INTERPRETATION_KEYS),
    }


def blank_interpretation(**fields) -> dict:
    """A full interpretation with the default (empty) value for every field not given."""
    out = {"target": None, "region": "full", "filters": [], "branch": None,
           "unit": "none", "answer_type": "int"}
    unknown = set(fields) - set(out)
    if unknown:
        raise ValueError(f"unknown interpretation field(s) {sorted(unknown)}")
    out.update(fields)
    return out


def branch_object(on, cmp, threshold, then_target, else_target,
                  then_region=None, else_region=None) -> dict:
    return {"on": on, "cmp": cmp, "threshold": threshold, "then_target": then_target,
            "else_target": else_target, "then_region": then_region, "else_region": else_region}

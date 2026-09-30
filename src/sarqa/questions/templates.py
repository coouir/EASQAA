"""Template catalogue L1-L5 (SPEC §6.2). All distances and lengths are px (no resolution in HRSID).

Every template is a `Template`: Korean text, gold program (the shortest tool-only solution, which
fixes `gold_calls` and the budget), allowed alternative programs, the gold interpretation in the
closed vocabulary of `vocab.py`, and the slot sampler / acceptance check of `slots.py`.

`text_ko` states every threshold and comparison; answer forms are spelled out when a category or
a rounding is required. The wording is a draft for the user's review (docs/dev_questions.md).
"""

import copy
from collections.abc import Callable
from dataclasses import dataclass

from sarqa.questions import slots as S
from sarqa.questions.texts_en import TEXT_EN
from sarqa.questions.vocab import QUADRANTS, blank_interpretation, branch_object

QUAD_KO = {"top_left": "왼쪽 위", "top_right": "오른쪽 위",
           "bottom_left": "왼쪽 아래", "bottom_right": "오른쪽 아래"}
ANSWER_FORMAT = ("(왼쪽 위=top_left, 오른쪽 위=top_right, 왼쪽 아래=bottom_left, 오른쪽 아래=bottom_right "
                 "중 하나의 영문 이름으로 답하라)")
EDGE_KO = "상자의 한 변이라도 영상 가장자리에서 20 px 이내에 있는"


# ---------------------------------------------------------------- program building blocks

def step(sid: str, tool: str, /, **args) -> dict:
    if tool != "calc":
        args = {"image_id": "IMG", **args}
    return {"id": sid, "op": tool, "args": args}


def prog(steps: list, answer) -> dict:
    return {"steps": steps, "answer": answer}


def foreach_quadrants(sid: str, body: list) -> dict:
    return {"id": sid, "op": "foreach", "over": list(QUADRANTS), "as": "r", "do": body}


def with_detect_first(program: dict) -> dict:
    """Allowed alternative: `detect_ships` is called first and its output is not used (SPEC §6.2)."""
    alt = copy.deepcopy(program)
    alt["steps"].insert(0, step("d0", "detect_ships"))
    return alt


def swap_count_for_detect(program: dict) -> dict | None:
    """Allowed alternative: `spatial_query count` -> `detect_ships` (same `count` field)."""
    alt = copy.deepcopy(program)
    changed = False

    def walk(steps):
        nonlocal changed
        for s in steps:
            if s["op"] == "spatial_query" and s["args"].get("query") == "count":
                args = {k: v for k, v in s["args"].items() if k != "query"}
                s["op"], s["args"] = "detect_ships", args
                changed = True
            for key in ("then", "else", "do"):
                if key in s:
                    walk(s[key])

    walk(alt["steps"])
    return alt if changed else None



# ---------------------------------------------------------------- the dataclass

@dataclass(frozen=True)
class Template:
    id: str
    level: str
    answer_type: str            # int | float | category
    unit: str                   # px | ships | none | percent
    box_dependent: bool
    has_branch: bool
    text: Callable[[dict], str]
    program: Callable[[dict], dict]
    interpretation: Callable[[dict], dict]
    sample: Callable
    check: Callable
    alts: Callable[[dict, dict], list] = lambda slots, program: []
    branch_spec: Callable[[dict], dict] | None = None
    category_choices: tuple | None = None
    note: str = ""

    def text_english(self, slots: dict) -> str:
        """The English wording (same meaning as `text`); the Korean text stays the default."""
        return TEXT_EN[self.id](slots)


def _alts_detect_first(slots, program):
    return [with_detect_first(program)]


def _alts_count(slots, program):
    swapped = swap_count_for_detect(program)
    return ([swapped] if swapped else []) + [with_detect_first(program)]


# ---------------------------------------------------------------- L1

def _l1(tid, text, program, interp, sample, box_dep, unit, atype, check=S.c_ok, alts=_alts_detect_first,
        choices=None):
    return Template(tid, "L1", atype, unit, box_dep, False, text, program, interp, sample, check,
                    alts, None, choices)


L1_TEMPLATES = [
    _l1("l1_total_count",
        lambda s: "이 영상에 있는 선박은 모두 몇 척인가?",
        lambda s: prog([step("s1", "detect_ships")], "$s1.count"),
        lambda s: blank_interpretation(target="ship_count", unit="ships", answer_type="int"),
        S.s_l1_total, True, "ships", "int",
        alts=lambda s, p: [prog([step("s1", "spatial_query", query="count")], "$s1.count")]),
    _l1("l1_quadrant_count",
        lambda s: f"이 영상의 {QUAD_KO[s['region']]} 사분면(선박 중심 기준)에 있는 선박은 몇 척인가?",
        lambda s: prog([step("s1", "spatial_query", query="count", region=s["region"])], "$s1.count"),
        lambda s: blank_interpretation(target="ship_count", region=s["region"], unit="ships",
                                       answer_type="int"),
        S.s_l1_quadrant, True, "ships", "int",
        alts=lambda s, p: [prog([step("s1", "detect_ships", region=s["region"])], "$s1.count")]),
    _l1("l1_edge_count",
        lambda s: f"이 영상에서 {EDGE_KO} 선박은 몇 척인가?",
        lambda s: prog([step("s1", "spatial_query", query="edge")], "$s1.count"),
        lambda s: blank_interpretation(target="ship_count", region="edge", unit="ships",
                                       answer_type="int"),
        S.s_l1_edge, True, "ships", "int"),
    _l1("l1_rect_count",
        lambda s: "이 영상에서 중심이 x 좌표 {0}~{2} px, y 좌표 {1}~{3} px 사각형 안에 있는 선박은 "
                  "몇 척인가?".format(*s["rect"]),
        lambda s: prog([step("s1", "spatial_query", query="count", region=s["rect"])], "$s1.count"),
        lambda s: blank_interpretation(target="ship_count", region=list(s["rect"]), unit="ships",
                                       answer_type="int"),
        S.s_l1_rect, True, "ships", "int",
        alts=lambda s, p: [prog([step("s1", "detect_ships", region=s["rect"])], "$s1.count")]),
    _l1("l1_scene",
        lambda s: "이 영상은 연안(inshore) 장면인가, 외해(offshore) 장면인가?",
        lambda s: prog([step("s1", "get_metadata")], "$s1.scene"),
        lambda s: blank_interpretation(target="scene_tag", unit="none", answer_type="category"),
        S.s_l1_scene, False, "none", "category", alts=lambda s, p: [],
        choices=("inshore", "offshore")),
    _l1("l1_brightness",
        lambda s: ("이 영상 전체의 평균 밝기(0~255)는 얼마인가?" if s["region"] == "full" else
                   f"이 영상의 {QUAD_KO[s['region']]} 사분면의 평균 밝기(0~255)는 얼마인가?"),
        lambda s: prog([step("s1", "image_stats", region=s["region"])], "$s1.mean_brightness"),
        lambda s: blank_interpretation(target="mean_brightness", region=s["region"], unit="none",
                                       answer_type="float"),
        S.s_l1_brightness, False, "none", "float", alts=lambda s, p: []),
]


# ---------------------------------------------------------------- L2 (calc + 2-3 distinct tools)

def _l2(tid, text, program, interp, unit, atype, sample=S.s_none, check=S.c_ok, alts=_alts_detect_first):
    return Template(tid, "L2", atype, unit, True, False, text, program, interp, sample, check, alts)


def _ids_and_sizes():
    return [step("s1", "spatial_query", query="count"), step("s2", "spatial_query", query="sizes")]


L2_TEMPLATES = [
    _l2("l2_nearest_ratio",
        lambda s: "가장 가까운 두 선박의 중심 사이 거리는 영상 너비의 몇 %인가? (소수 둘째 자리까지)",
        lambda s: prog([step("s1", "get_metadata"), step("s2", "spatial_query", query="nearest_pair"),
                        step("s3", "calc", op="expr", expr="d / w * 100",
                             vars={"d": "$s2.distance_px", "w": "$s1.width"})], "$s3.result"),
        lambda s: blank_interpretation(target="nearest_distance_ratio", unit="percent",
                                       answer_type="float"),
        "percent", "float", check=S.c_min_ships_pair,
        alts=lambda s, p: [prog([step("s1", "spatial_query", query="nearest_pair"),
                                 step("s2", "get_metadata"),
                                 step("s3", "calc", op="expr", expr="d / w * 100",
                                      vars={"d": "$s1.distance_px", "w": "$s2.width"})],
                                "$s3.result"), with_detect_first(p)]),
    _l2("l2_longest_length",
        lambda s: "이 영상에서 가장 긴 선박의 긴 변은 몇 px인가?",
        lambda s: prog([step("s1", "spatial_query", query="sizes"),
                        step("s2", "calc", op="max", list="$s1.long_side_px")], "$s2.result"),
        lambda s: blank_interpretation(target="max_length", unit="px", answer_type="float"),
        "px", "float"),
    _l2("l2_count_over_length",
        lambda s: f"이 영상에서 긴 변이 {s['threshold']} px 이상인 선박은 몇 척인가?",
        lambda s: prog([step("s1", "spatial_query", query="sizes"),
                        step("s2", "calc", op="filter", list="$s1.long_side_px", cmp=">=",
                             threshold=s["threshold"])], "$s2.count"),
        lambda s: blank_interpretation(
            target="count_over_threshold", unit="ships", answer_type="int",
            filters=[{"field": "length_px", "cmp": ">=", "threshold": s["threshold"]}]),
        "ships", "int", sample=S.s_l2_count_over),
    _l2("l2_longest_neighbor",
        lambda s: "가장 긴 선박에서 가장 가까운 다른 선박까지의 중심 사이 거리는 몇 px인가?",
        lambda s: prog(_ids_and_sizes() + [
            step("s3", "calc", op="argmax", list="$s2.long_side_px", labels="$s1.ship_ids"),
            step("s4", "spatial_query", query="nearest_to", ship_a="$s3.result")], "$s4.distance_px"),
        lambda s: blank_interpretation(target="longest_neighbor_distance", unit="px",
                                       answer_type="float"),
        "px", "float", check=S.c_unique_longest),
    _l2("l2_longest_shortest_distance",
        lambda s: "가장 긴 선박과 가장 짧은 선박 사이의 중심 거리는 몇 px인가?",
        lambda s: prog(_ids_and_sizes() + [
            step("s3", "calc", op="argmax", list="$s2.long_side_px", labels="$s1.ship_ids"),
            step("s4", "calc", op="argmin", list="$s2.long_side_px", labels="$s1.ship_ids"),
            step("s5", "spatial_query", query="distance", ship_a="$s3.result", ship_b="$s4.result")],
            "$s5.distance_px"),
        lambda s: blank_interpretation(target="pair_distance", unit="px", answer_type="float"),
        "px", "float", check=S.c_unique_longest_shortest),
]


# ---------------------------------------------------------------- L3 (one tool, four regions)

def _l3(tid, text, program, interp, unit, atype, box_dep, check=S.c_ok, sample=S.s_none, choices=None,
        alts=_alts_detect_first):
    return Template(tid, "L3", atype, unit, box_dep, False, text, program, interp, sample, check,
                    alts, None, choices)


def _quadrant_loop(query_step: dict, extra: list | None = None) -> list:
    return [foreach_quadrants("s1", [query_step] + (extra or []))]


L3_TEMPLATES = [
    _l3("l3_quadrant_most_ships",
        lambda s: f"네 사분면 중 선박이 가장 많은 사분면(선박 중심 기준)은 어디인가? {ANSWER_FORMAT}",
        lambda s: prog(_quadrant_loop(step("s2", "spatial_query", query="count", region="$r")) + [
            step("s3", "calc", op="argmax", list="$s2.count", labels=list(QUADRANTS))], "$s3.result"),
        lambda s: blank_interpretation(target="region_argmax", unit="none", answer_type="category"),
        "none", "category", True, check=S.c_quad_count_argmax, choices=QUADRANTS,
        alts=lambda s, p: [swap_count_for_detect(p), with_detect_first(p)]),
    _l3("l3_empty_quadrants",
        lambda s: "선박이 한 척도 없는 사분면(선박 중심 기준)은 몇 개인가?",
        lambda s: prog(_quadrant_loop(step("s2", "spatial_query", query="count", region="$r")) + [
            step("s3", "calc", op="filter", list="$s2.count", cmp="==", threshold=0)], "$s3.count"),
        lambda s: blank_interpretation(target="empty_region_count", unit="none", answer_type="int"),
        "none", "int", True,
        alts=lambda s, p: [swap_count_for_detect(p), with_detect_first(p)]),
    _l3("l3_quadrant_most_long",
        lambda s: (f"긴 변이 {s['threshold']} px 이상인 선박이 가장 많은 사분면(선박 중심 기준)은 어디인가? "
                   f"{ANSWER_FORMAT}"),
        lambda s: prog(_quadrant_loop(
            step("s2", "spatial_query", query="sizes", region="$r"),
            [step("s3", "calc", op="filter", list="$s2.long_side_px", cmp=">=",
                  threshold=s["threshold"])]) + [
            step("s4", "calc", op="argmax", list="$s3.count", labels=list(QUADRANTS))], "$s4.result"),
        lambda s: blank_interpretation(
            target="region_argmax_long", unit="none", answer_type="category",
            filters=[{"field": "length_px", "cmp": ">=", "threshold": s["threshold"]}]),
        "none", "category", True, check=S.c_l3_long_count, sample=S.s_l3_long_count,
        choices=QUADRANTS),
    _l3("l3_quadrant_brightest",
        lambda s: f"네 사분면 중 평균 밝기가 가장 높은 사분면은 어디인가? {ANSWER_FORMAT}",
        lambda s: prog(_quadrant_loop(step("s2", "image_stats", region="$r")) + [
            step("s3", "calc", op="argmax", list="$s2.mean_brightness", labels=list(QUADRANTS))],
            "$s3.result"),
        lambda s: blank_interpretation(target="brightest_region", unit="none", answer_type="category"),
        "none", "category", False, check=S.c_stat_argmax("brightness"), choices=QUADRANTS,
        alts=lambda s, p: []),
    _l3("l3_quadrant_noisiest",
        lambda s: f"네 사분면 중 배경 잡음 수치가 가장 큰 사분면은 어디인가? {ANSWER_FORMAT}",
        lambda s: prog(_quadrant_loop(step("s2", "image_stats", region="$r")) + [
            step("s3", "calc", op="argmax", list="$s2.background_noise", labels=list(QUADRANTS))],
            "$s3.result"),
        lambda s: blank_interpretation(target="noisiest_region", unit="none", answer_type="category"),
        "none", "category", False, check=S.c_stat_argmax("noise"), choices=QUADRANTS,
        alts=lambda s, p: []),
]


# ---------------------------------------------------------------- L4 (one condition, two targets)

def _l4(tid, text, program, interp, unit, atype, sample, branch_spec, check=S.c_ok):
    return Template(tid, "L4", atype, unit, True, True, text, program, interp, sample, check,
                    lambda s, p: [with_detect_first(p)], branch_spec)


def _nearest_or_max_branch(cond_ref: str) -> tuple[list, dict]:
    """then: nearest pair distance; else: longest ship. Steps s3 | s4, s5; answer picks by `if`."""
    return ([step("s3", "spatial_query", query="nearest_pair")],
            [step("s4", "spatial_query", query="sizes"),
             step("s5", "calc", op="max", list="$s4.long_side_px")])


def _l4_scene_program(s):
    then, other = _nearest_or_max_branch("")
    return prog([step("s1", "get_metadata"),
                 {"id": "s2", "op": "if", "cond": {"lhs": "$s1.scene", "cmp": "==", "rhs": "inshore"},
                  "then": then, "else": other}],
                {"then": "$s3.distance_px", "else": "$s5.result"})


def _l4_count_program(s):
    then, other = _nearest_or_max_branch("")
    return prog([step("s1", "spatial_query", query="count"),
                 {"id": "s2", "op": "if", "cond": {"lhs": "$s1.count", "cmp": ">=", "rhs": s["threshold"] + 1},
                  "then": then, "else": other}],
                {"then": "$s3.distance_px", "else": "$s5.result"})


def _l4_quadrant_program(s):
    return prog([step("s1", "spatial_query", query="count", region=s["region"]),
                 {"id": "s2", "op": "if",
                  "cond": {"lhs": "$s1.count", "cmp": ">=", "rhs": s["threshold"]},
                  "then": [step("s3", "spatial_query", query="sizes", region=s["region"]),
                           step("s4", "calc", op="max", list="$s3.long_side_px")],
                  "else": [step("s5", "spatial_query", query="nearest_pair")]}],
                {"then": "$s4.result", "else": "$s5.distance_px"})


def _l4_maxlen_program(s):
    return prog([step("s1", "spatial_query", query="sizes"),
                 step("s2", "calc", op="max", list="$s1.long_side_px"),
                 {"id": "s3", "op": "if", "cond": {"lhs": "$s2.result", "cmp": ">=", "rhs": s["threshold"]},
                  "then": [step("s4", "calc", op="filter", list="$s1.long_side_px", cmp=">=",
                                threshold=s["threshold"])],
                  "else": []}],
                {"then": "$s4.count", "else": "$s1.count"})


def _l4_noise_program(s):
    return prog([step("s1", "image_stats"),
                 {"id": "s2", "op": "if",
                  "cond": {"lhs": "$s1.background_noise", "cmp": ">", "rhs": s["threshold"]},
                  "then": [step("s3", "detect_ships")],
                  "else": [step("s4", "spatial_query", query="edge")]}],
                {"then": "$s3.count", "else": "$s4.count"})


L4_TEMPLATES = [
    _l4("l4_scene_branch",
        lambda s: ("이 영상이 연안(inshore) 장면이면 가장 가까운 두 선박의 중심 사이 거리(px)를, "
                   "외해(offshore) 장면이면 가장 긴 선박의 긴 변(px)을 답하라."),
        _l4_scene_program,
        lambda s: blank_interpretation(
            target="branch", unit="px", answer_type="float",
            branch=branch_object("scene", "==", "inshore", "nearest_distance", "max_length")),
        "px", "float", S.s_l4_scene,
        lambda s: {"on": "scene", "cmp": "==", "threshold": "inshore", "region": "full",
                   "then_label": "inshore", "else_label": "offshore"}),
    _l4("l4_count_branch",
        lambda s: (f"이 영상의 선박이 {s['threshold'] + 1}척 이상이면 가장 가까운 두 선박의 중심 사이 거리(px)를, "
                   f"그렇지 않으면 가장 긴 선박의 긴 변(px)을 답하라."),
        _l4_count_program,
        lambda s: blank_interpretation(
            target="branch", unit="px", answer_type="float",
            branch=branch_object("ship_count", ">=", s["threshold"] + 1, "nearest_distance", "max_length")),
        "px", "float", S.s_l4_count,
        lambda s: {"on": "ship_count", "cmp": ">=", "threshold": s["threshold"] + 1, "region": "full",
                   "then_label": "then", "else_label": "else"}),
    _l4("l4_quadrant_branch",
        lambda s: (f"{QUAD_KO[s['region']]} 사분면(선박 중심 기준)의 선박이 {s['threshold']}척 이상이면 그 사분면에서 "
                   f"가장 긴 선박의 긴 변(px)을, 아니면 영상 전체에서 가장 가까운 두 선박의 중심 사이 거리(px)를 "
                   f"답하라."),
        _l4_quadrant_program,
        lambda s: blank_interpretation(
            target="branch", unit="px", region=s["region"], answer_type="float",
            branch=branch_object("ship_count", ">=", s["threshold"], "max_length", "nearest_distance",
                                 s["region"], "full")),
        "px", "float", S.s_l4_quadrant,
        lambda s: {"on": "ship_count", "cmp": ">=", "threshold": s["threshold"], "region": s["region"],
                   "then_label": "then", "else_label": "else"}),
    _l4("l4_maxlen_branch",
        lambda s: (f"이 영상에서 가장 긴 선박의 긴 변이 {s['threshold']} px 이상이면 긴 변이 "
                   f"{s['threshold']} px 이상인 선박의 수를, 아니면 전체 선박 수를 답하라."),
        _l4_maxlen_program,
        lambda s: blank_interpretation(
            target="branch", unit="ships", answer_type="int",
            filters=[{"field": "length_px", "cmp": ">=", "threshold": s["threshold"]}],
            branch=branch_object("max_length", ">=", s["threshold"], "count_over_threshold",
                                 "ship_count")),
        "ships", "int", S.s_l4_maxlen,
        lambda s: {"on": "max_length", "cmp": ">=", "threshold": s["threshold"], "region": "full",
                   "then_label": "then", "else_label": "else"}),
    _l4("l4_noise_branch",
        lambda s: (f"이 영상 전체의 배경 잡음 수치가 {s['threshold']}보다 크면 전체 선박 수를, "
                   f"그렇지 않으면 {EDGE_KO} 선박 수를 답하라."),
        _l4_noise_program,
        lambda s: blank_interpretation(
            target="branch", unit="ships", answer_type="int",
            branch=branch_object("noise", ">", s["threshold"], "ship_count", "ship_count", "full", "edge")),
        "ships", "int", S.s_l4_noise,
        lambda s: {"on": "noise", "cmp": ">", "threshold": s["threshold"], "region": "full",
                   "then_label": "then", "else_label": "else"}),
]


# ---------------------------------------------------------------- L5 (loop + condition + calc)

def _noisy_quadrant_steps(first: int) -> list:
    n = first
    return [foreach_quadrants(f"s{n}", [step(f"s{n + 1}", "image_stats", region="$r")]),
            step(f"s{n + 2}", "calc", op="argmax", list=f"$s{n + 1}.background_noise",
                 labels=list(QUADRANTS))]


def _l5_noisy_program(s):
    return prog(_noisy_quadrant_steps(1) + [
        step("s4", "spatial_query", query="sizes", region="$s3.result"),
        {"id": "s5", "op": "if", "cond": {"lhs": "$s4.count", "cmp": ">=", "rhs": s["count_threshold"]},
         "then": [step("s6", "calc", op="filter", list="$s4.long_side_px", cmp=">=",
                       threshold=s["threshold"])],
         "else": []}],
        {"then": "$s6.count", "else": "$s4.count"})


def _l5_scene_program(s):
    t = s["threshold"]
    return prog([
        step("s1", "get_metadata"),
        {"id": "s2", "op": "if", "cond": {"lhs": "$s1.scene", "cmp": "==", "rhs": "inshore"},
         "then": _noisy_quadrant_steps(3) + [
             step("s6", "spatial_query", query="sizes", region="$s5.result"),
             step("s7", "calc", op="filter", list="$s6.long_side_px", cmp=">=", threshold=t)],
         "else": [foreach_quadrants("s8", [step("s9", "spatial_query", query="count", region="$r")]),
                  step("s10", "calc", op="argmax", list="$s9.count", labels=list(QUADRANTS)),
                  step("s11", "spatial_query", query="sizes", region="$s10.result"),
                  step("s12", "calc", op="filter", list="$s11.long_side_px", cmp=">=", threshold=t)]}],
        {"then": "$s7.count", "else": "$s12.count"})


L5_TEMPLATES = [
    Template(
        "l5_noisy_quadrant", "L5", "int", "ships", True, True,
        lambda s: (f"배경 잡음 수치가 가장 큰 사분면을 찾아라. 그 사분면(선박 중심 기준)의 선박이 "
                   f"{s['count_threshold']}척 이상이면 그 사분면에서 긴 변이 {s['threshold']} px 이상인 선박의 수를, "
                   f"아니면 그 사분면의 선박 수를 답하라."),
        _l5_noisy_program,
        lambda s: blank_interpretation(
            target="branch", unit="ships", region="noisiest_region", answer_type="int",
            filters=[{"field": "length_px", "cmp": ">=", "threshold": s["threshold"]}],
            branch=branch_object("ship_count", ">=", s["count_threshold"], "count_over_threshold",
                                 "ship_count")),
        S.s_l5_noisy, S.c_l5_noisy, lambda s, p: [with_detect_first(p)],
        lambda s: {"on": "ship_count", "cmp": ">=", "threshold": s["count_threshold"],
                   "region": "noisiest_region", "then_label": "then", "else_label": "else"}),
    Template(
        "l5_scene_quadrant", "L5", "int", "ships", True, True,
        lambda s: (f"이 영상이 연안(inshore) 장면이면 배경 잡음 수치가 가장 큰 사분면에서, 외해(offshore) "
                   f"장면이면 선박이 가장 많은 사분면(선박 중심 기준)에서 긴 변이 {s['threshold']} px 이상인 선박은 "
                   f"몇 척인가?"),
        _l5_scene_program,
        lambda s: blank_interpretation(
            target="branch", unit="ships", answer_type="int",
            filters=[{"field": "length_px", "cmp": ">=", "threshold": s["threshold"]}],
            branch=branch_object("scene", "==", "inshore", "count_over_threshold",
                                 "count_over_threshold", "noisiest_region", "densest_region")),
        S.s_l5_scene, S.c_l5_scene, lambda s, p: [with_detect_first(p)],
        lambda s: {"on": "scene", "cmp": "==", "threshold": "inshore", "region": "full",
                   "then_label": "inshore", "else_label": "offshore"}),
]

# ---------------------------------------------------------------- catalogue and quotas

TEMPLATES: dict[str, Template] = {
    t.id: t for t in (*L1_TEMPLATES, *L2_TEMPLATES, *L3_TEMPLATES, *L4_TEMPLATES, *L5_TEMPLATES)}

# Questions per template. dev: 18/22/23/22/5 (SPEC §6.1). test: 72/90/90/90/18, defined here so the
# ratio is reviewed now; the test set is generated once at freeze time (SPEC §14 M5), never earlier.
QUOTAS = {
    "dev": {
        "l1_total_count": 3, "l1_quadrant_count": 3, "l1_edge_count": 3, "l1_rect_count": 3,
        "l1_scene": 3, "l1_brightness": 3,
        "l2_nearest_ratio": 5, "l2_longest_length": 4, "l2_count_over_length": 4,
        "l2_longest_neighbor": 5, "l2_longest_shortest_distance": 4,
        "l3_quadrant_most_ships": 6, "l3_empty_quadrants": 5, "l3_quadrant_most_long": 3,
        "l3_quadrant_brightest": 5, "l3_quadrant_noisiest": 4,
        "l4_scene_branch": 4, "l4_count_branch": 5, "l4_quadrant_branch": 4, "l4_maxlen_branch": 5,
        "l4_noise_branch": 4,
        "l5_noisy_quadrant": 3, "l5_scene_quadrant": 2,
    },
    "test": {
        "l1_total_count": 14, "l1_quadrant_count": 14, "l1_edge_count": 12, "l1_rect_count": 12,
        "l1_scene": 10, "l1_brightness": 10,
        "l2_nearest_ratio": 18, "l2_longest_length": 18, "l2_count_over_length": 18,
        "l2_longest_neighbor": 18, "l2_longest_shortest_distance": 18,
        "l3_quadrant_most_ships": 22, "l3_empty_quadrants": 20, "l3_quadrant_most_long": 12,
        "l3_quadrant_brightest": 18, "l3_quadrant_noisiest": 18,
        "l4_scene_branch": 16, "l4_count_branch": 18, "l4_quadrant_branch": 18,
        "l4_maxlen_branch": 20, "l4_noise_branch": 18,
        # 6 / 12, not 9 / 9: under the balance rule (one branch <= 50 %, zero answers <= 20 %) 9 needs
        # 4+ `then` questions and the test images hold too few (docs/deviations.md 2026-10-01). L5 total stays 18.
        "l5_noisy_quadrant": 6, "l5_scene_quadrant": 12,
    },
}
LEVEL_TOTALS = {"dev": {"L1": 18, "L2": 22, "L3": 23, "L4": 22, "L5": 5},
                "test": {"L1": 72, "L2": 90, "L3": 90, "L4": 90, "L5": 18}}

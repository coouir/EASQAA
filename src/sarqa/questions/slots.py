"""Slot sampling and the per-template acceptance checks (SPEC §6.4 step 1 and 3).

`ImageFacts` describes one image from its **label** boxes through the real tools, so what the
samplers see is what the gold program will see. A sampler returns a slot dict or `None` (retry);
a checker returns `None` when the (slots, image) pair is acceptable or a short reason to reject.

Rules applied here (SPEC §6.4 step 3):
- margin: a value that decides the answer is not within 10 % of the threshold (counts: not within
  +-1, i.e. one added or missing box cannot flip a branch)
- no ties in argmax / argmin (image-statistic argmax needs a 2 % gap: the tools round to 2 decimals)
- degenerate answers are limited by the generator (balance), not here
"""

import random
from dataclasses import dataclass, field
from functools import cached_property

from sarqa.boxes import Box
from sarqa.questions.vocab import QUADRANTS
from sarqa.tools import call_tool
from sarqa.tools.base import ToolContext
from sarqa.tools.geometry import in_region, near_edge, parse_region

REL_MARGIN = 0.10          # threshold margin for measured values
COUNT_MARGIN = 2           # |count - K| >= 2, i.e. not within +-1 of the boundary
ARGMAX_GAP = 0.02          # relative gap between the best and the second value of a statistic
LENGTH_CANDIDATES = tuple(range(15, 151, 5))
MIN_SHIPS, MAX_SHIPS = 2, 15


@dataclass
class ImageFacts:
    image_id: str
    ctx: ToolContext
    boxes: list[Box] = field(init=False)

    def __post_init__(self):
        self.boxes = self.ctx.label_boxes.boxes(self.image_id)

    @cached_property
    def scene(self) -> str:
        return call_tool(self.ctx, "get_metadata", {"image_id": self.image_id})["scene"]

    @property
    def n(self) -> int:
        return len(self.boxes)

    @property
    def lengths(self) -> list[int]:
        return [b.long_side for b in self.boxes]

    @cached_property
    def quad_counts(self) -> dict[str, int]:
        return {q: sum(in_region(b, parse_region(q)) for b in self.boxes) for q in QUADRANTS}

    @cached_property
    def edge_count(self) -> int:
        return sum(near_edge(b) for b in self.boxes)

    def _stat(self, region: str, key: str):
        out = call_tool(self.ctx, "image_stats", {"image_id": self.image_id, "region": region})
        return out.get(key)

    @cached_property
    def noise_full(self):
        return self._stat("full", "background_noise")

    @cached_property
    def quad_noise(self) -> dict:
        return {q: self._stat(q, "background_noise") for q in QUADRANTS}

    @cached_property
    def quad_brightness(self) -> dict:
        return {q: self._stat(q, "mean_brightness") for q in QUADRANTS}

    def lengths_in(self, quadrant: str) -> list[int]:
        reg = parse_region(quadrant)
        return [b.long_side for b in self.boxes if in_region(b, reg)]


# ---------------------------------------------------------------- helpers

def clear_of(values, threshold: float) -> bool:
    """True when no value lies within REL_MARGIN of `threshold` (either side)."""
    return all(abs(v - threshold) > REL_MARGIN * abs(threshold) for v in values)


def clear_count(count: int, k: int) -> bool:
    return abs(count - k) >= COUNT_MARGIN


def unique_extreme(values, kind: str) -> bool:
    if not values:
        return False
    best = max(values) if kind == "max" else min(values)
    return sum(v == best for v in values) == 1


def stat_argmax_clear(values: dict) -> bool:
    """The best statistic beats the runner-up by ARGMAX_GAP (relative) and none is missing."""
    if any(v is None for v in values.values()) or len(values) < 2:
        return False
    vals = sorted(values.values(), reverse=True)
    return vals[0] - vals[1] > ARGMAX_GAP * abs(vals[0])


def threshold_choices(lengths, extra_ok=lambda t: True) -> list[int]:
    return [t for t in LENGTH_CANDIDATES if clear_of(lengths, t) and extra_ok(t)]


def eligible(f: ImageFacts) -> bool:
    return MIN_SHIPS <= f.n <= MAX_SHIPS


# ---------------------------------------------------------------- L1

def s_l1_total(rng, f):
    return {}


def s_l1_quadrant(rng, f):
    return {"region": rng.choice(QUADRANTS)}


def s_l1_edge(rng, f):
    return {}


def s_l1_rect(rng, f):
    w, h = rng.choice((250, 300, 350, 400, 450)), rng.choice((250, 300, 350, 400, 450))
    x1, y1 = rng.randrange(0, 800 - w + 1, 50), rng.randrange(0, 800 - h + 1, 50)
    return {"rect": [x1, y1, x1 + w, y1 + h]}


def s_l1_scene(rng, f):
    return {}


def s_l1_brightness(rng, f):
    return {"region": rng.choice(("full", *QUADRANTS))}


# ---------------------------------------------------------------- L2

def s_none(rng, f):
    return {}


def c_ok(slots, f):
    return None


def c_unique_longest(slots, f):
    return None if unique_extreme(f.lengths, "max") else "longest ship is tied"


def c_unique_longest_shortest(slots, f):
    if not unique_extreme(f.lengths, "max"):
        return "longest ship is tied"
    return None if unique_extreme(f.lengths, "min") else "shortest ship is tied"


def s_l2_count_over(rng, f):
    n = f.n
    ok = threshold_choices(f.lengths, lambda t: 1 <= sum(v >= t for v in f.lengths) <= n - 1)
    return {"threshold": rng.choice(ok)} if ok else None


# ---------------------------------------------------------------- L3

def c_quad_count_argmax(slots, f):
    return None if unique_extreme(list(f.quad_counts.values()), "max") else "count argmax tied"


def c_stat_argmax(key):
    def check(slots, f):
        values = f.quad_noise if key == "noise" else f.quad_brightness
        return None if stat_argmax_clear(values) else f"{key} argmax not clear"
    return check


def s_l3_long_count(rng, f):
    ok = threshold_choices(f.lengths)
    return {"threshold": rng.choice(ok)} if ok else None


def c_l3_long_count(slots, f):
    t = slots["threshold"]
    counts = [sum(v >= t for v in f.lengths_in(q)) for q in QUADRANTS]
    return None if unique_extreme(counts, "max") and max(counts) >= 1 else "long-count argmax tied"


# ---------------------------------------------------------------- L4 / L5

def s_l4_scene(rng, f):
    return {}


def s_l4_count(rng, f):
    ok = [k for k in range(3, 13) if clear_count(f.n, k)]
    return {"threshold": rng.choice(ok)} if ok else None


def s_l4_quadrant(rng, f):
    q = rng.choice(QUADRANTS)
    ok = [k for k in range(2, 7) if clear_count(f.quad_counts[q], k)]
    return {"region": q, "threshold": rng.choice(ok)} if ok else None


def s_l4_maxlen(rng, f):
    ok = threshold_choices(f.lengths)
    return {"threshold": rng.choice(ok)} if ok else None


def s_l4_noise(rng, f):
    noise = f.noise_full
    if noise is None or noise <= 0:
        return None
    u = rng.choice((0.6, 0.7, 0.8, 1.2, 1.35, 1.5))
    t = round(noise * u * 2) / 2
    return {"threshold": t} if t > 0 and clear_of([noise], t) else None


def s_l5_noisy(rng, f):
    ok_k = [k for k in range(2, 7)]
    ok_t = threshold_choices(f.lengths)
    if not ok_t:
        return None
    return {"count_threshold": rng.choice(ok_k), "threshold": rng.choice(ok_t)}


def c_l5_noisy(slots, f):
    if not stat_argmax_clear(f.quad_noise):
        return "noise argmax not clear"
    q = max(f.quad_noise, key=lambda k: f.quad_noise[k])
    c = f.quad_counts[q]
    if not clear_count(c, slots["count_threshold"]):
        return "count within margin of the branch threshold"
    return None


def s_l5_scene(rng, f):
    ok_t = threshold_choices(f.lengths)
    return {"threshold": rng.choice(ok_t)} if ok_t else None


def c_l5_scene(slots, f):
    if f.scene == "inshore":
        return None if stat_argmax_clear(f.quad_noise) else "noise argmax not clear"
    return None if unique_extreme(list(f.quad_counts.values()), "max") else "count argmax tied"


def rng_for(*parts) -> random.Random:
    """Deterministic RNG from any parts (no reliance on Python's randomised `hash`)."""
    import hashlib

    digest = hashlib.sha256("|".join(map(str, parts)).encode()).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))

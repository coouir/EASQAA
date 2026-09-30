"""Question generation (SPEC §6.4): sample slots, run the gold program on label boxes, filter.

Deterministic: every random choice comes from `rng_for(seed, split, template, index, attempt)`.
Questions of a split only use images of that split's scene groups that are `question_eligible`
(splits/splits.json). Test questions are generated **once**, at freeze time (SPEC §0-4, §14 M5);
the CLI refuses `--split test` without an explicit override.
"""

import json
import math
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from sarqa.config import load_config, repo_path
from sarqa.program import run_program
from sarqa.questions.slots import MAX_SHIPS, MIN_SHIPS, ImageFacts, rng_for
from sarqa.questions.templates import LEVEL_TOTALS, QUOTAS, TEMPLATES, Template
from sarqa.tools.base import ToolContext

MAX_PER_IMAGE = 2            # questions per image
GROUP_CAP_FACTOR = 3         # per scene group: at most 3 x the mean number of questions
MAX_ATTEMPTS = 600           # per question
ZERO_SHARE = 0.20            # at most this share of a template's numeric answers may be 0
SAME_ANSWER_SHARE = 0.50     # ... and this share may be one and the same value / category
LEVEL_ORDER = ("L1", "L2", "L3", "L4", "L5")
QID_PREFIX = {"dev": "D", "test": "T"}


class GenerationError(RuntimeError):
    pass


def load_splits() -> dict:
    with open(repo_path(load_config()["paths"]["splits"]), encoding="utf-8") as f:
        return json.load(f)


def image_pool(split: str, splits: dict | None = None) -> list[tuple[str, str]]:
    """(image id, scene group) of the split's question-eligible images with 2-15 label ships."""
    splits = splits or load_splits()
    return sorted((name, m["group"]) for name, m in splits["images"].items()
                  if m["split"] == split and m["question_eligible"]
                  and MIN_SHIPS <= m["n_boxes"] <= MAX_SHIPS)


def _cap(quota: int, share: float) -> int:
    return max(1, math.ceil(quota * share))


@dataclass
class _Tally:
    """What a template has accepted so far, for the balance filters."""
    quota: int
    balance: Counter
    zeros: int = 0

    def allows(self, key, is_zero: bool) -> bool:
        if key is not None and self.quota >= 3 \
                and self.balance[key] + 1 > _cap(self.quota, SAME_ANSWER_SHARE):
            return False
        return not (is_zero and self.zeros + 1 > _cap(self.quota, ZERO_SHARE))

    def add(self, key, is_zero: bool):
        if key is not None:
            self.balance[key] += 1
        self.zeros += is_zero


def _balance_key(t: Template, answer, decisions):
    if t.has_branch:
        top = [d for d in decisions if d["top_level"]]
        return ("branch", top[-1]["chosen"] if top else None, answer if t.answer_type == "category" else None)
    return answer if t.answer_type in ("category", "int", "float") else None


def _json_safe(v):
    return json.loads(json.dumps(v))


def build_record(t: Template, slots: dict, image_id: str, group: str, split: str, ctx: ToolContext,
                 detected_provider=None) -> dict | None:
    """Question record for one accepted (template, slots, image); `None` if the gold run fails."""
    program = t.program(slots)
    res = run_program(program, image_id, ctx.label_boxes, ctx=ctx)
    if not res.ok:
        return None
    answer = res.answer
    if t.answer_type == "int":
        if isinstance(answer, float) and answer == int(answer):
            answer = int(answer)
        if not isinstance(answer, int):
            return None
    if t.answer_type == "float" and isinstance(answer, (int, float)) and not isinstance(answer, bool):
        answer = float(answer)
    branch_spec = t.branch_spec(slots) if t.branch_spec else None
    top = [d for d in res.decisions if d["top_level"]]
    if branch_spec and top:
        branch_spec = {**branch_spec, "gold_branch": top[-1]["chosen"]}
    reference = {}
    if detected_provider is not None:
        r = run_program(program, image_id, detected_provider, ctx=ctx)
        reference["detected"] = r.answer if r.ok else None
    return {
        "qid": None, "split": split, "level": t.level, "template": t.id,
        "image_id": image_id, "scene_group": group,
        "text_ko": t.text(slots), "slots": slots,
        "answer_type": t.answer_type, "unit": t.unit,
        "gold_answer": answer, "tolerance": {"rel": 0.05 if t.answer_type == "float" else 0.0},
        "program": program, "alt_programs": t.alts(slots, program),
        "gold_calls": res.gold_calls, "budget": res.budget,
        "gold_interpretation": t.interpretation(slots),
        "branch_spec": branch_spec,
        "box_dependent": t.box_dependent, "has_branch": t.has_branch,
        "intermediates": {"label": _json_safe(
            {k: v for k, v in res.intermediates.items()})},
        "reference_answers": reference,
    }


def generate(split: str, ctx: ToolContext, *, seed: int | None = None,
             detected_provider=None, splits: dict | None = None,
             quotas: dict | None = None) -> list[dict]:
    """All questions of `split`, ordered by level, template and draw. Raises `GenerationError`
    when a template cannot fill its quota (never returns a short set)."""
    seed = load_config()["seed"] if seed is None else seed
    quotas = quotas or QUOTAS[split]
    pool = image_pool(split, splits)
    if not pool:
        raise GenerationError(f"no eligible images in split {split!r}")
    groups = sorted({g for _, g in pool})
    total = sum(quotas.values())
    group_cap = max(1, math.ceil(GROUP_CAP_FACTOR * total / len(groups)))
    image_uses, group_uses = Counter(), Counter()
    facts_cache: dict[str, ImageFacts] = {}
    out: list[dict] = []

    for tid, quota in quotas.items():
        t = TEMPLATES[tid]
        tally = _Tally(quota, Counter())
        for idx in range(quota):
            for attempt in range(MAX_ATTEMPTS):
                rng = rng_for(seed, split, tid, idx, attempt)
                image_id, group = pool[rng.randrange(len(pool))]
                if image_uses[image_id] >= MAX_PER_IMAGE or group_uses[group] >= group_cap:
                    continue
                if image_id not in facts_cache:
                    facts_cache[image_id] = ImageFacts(image_id, ctx)
                facts = facts_cache[image_id]
                slots = t.sample(rng, facts)
                if slots is None or t.check(slots, facts) is not None:
                    continue
                rec = build_record(t, slots, image_id, group, split, ctx, detected_provider)
                if rec is None:
                    continue
                key = _balance_key(t, rec["gold_answer"], _decisions(rec))
                is_zero = t.answer_type != "category" and rec["gold_answer"] == 0
                if not tally.allows(key, is_zero):
                    continue
                if any(o["template"] == tid and o["image_id"] == image_id and o["slots"] == slots
                       for o in out):
                    continue
                tally.add(key, is_zero)
                image_uses[image_id] += 1
                group_uses[group] += 1
                rec["attempts"] = attempt + 1
                out.append(rec)
                break
            else:
                raise GenerationError(
                    f"template {tid}: could not draw question {idx + 1}/{quota} in {MAX_ATTEMPTS} tries")
    return assign_qids(out, split)


def _decisions(rec: dict) -> list[dict]:
    """Top-level `if` decisions of the gold run (kept by `build_record` in `branch_spec`)."""
    spec = rec.get("branch_spec")
    return [{"top_level": True, "chosen": spec["gold_branch"]}] if spec and "gold_branch" in spec else []


def assign_qids(questions: list[dict], split: str) -> list[dict]:
    """Stable ids `<D|T>-<level>-<nnn>`, numbered per level in the order of the list."""
    questions = sorted(questions, key=lambda q: (LEVEL_ORDER.index(q["level"]),
                                                 list(TEMPLATES).index(q["template"])))
    n = Counter()
    for q in questions:
        n[q["level"]] += 1
        q["qid"] = f"{QID_PREFIX[split]}-{q['level']}-{n[q['level']]:03d}"
    return questions


def write_questions(questions: list[dict], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"split": questions[0]["split"] if questions else None, "questions": questions},
                  f, ensure_ascii=False, indent=1)


def read_questions(path: str | Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)["questions"]


def summary(questions: list[dict]) -> dict:
    return {
        "n": len(questions),
        "by_level": dict(Counter(q["level"] for q in questions)),
        "by_template": dict(Counter(q["template"] for q in questions)),
        "box_dependent": sum(q["box_dependent"] for q in questions),
        "has_branch": sum(q["has_branch"] for q in questions),
        "mean_gold_calls": round(sum(q["gold_calls"] for q in questions) / max(1, len(questions)), 2),
        "gold_calls": dict(sorted(Counter(q["gold_calls"] for q in questions).items())),
        "images": len({q["image_id"] for q in questions}),
        "groups": dict(sorted(Counter(q["scene_group"] for q in questions).items())),
    }


def level_totals(split: str) -> dict:
    return LEVEL_TOTALS[split]


def english_version(questions: list[dict]) -> list[dict]:
    """The same questions with the English wording: `text_en` is added and `lang` is set to `en`, so the
    agents show the English text. Images, slots, programs and gold answers are copied unchanged."""
    out = []
    for q in questions:
        e = json.loads(json.dumps(q))
        e["text_en"] = TEMPLATES[q["template"]].text_english(q["slots"])
        e["lang"] = "en"
        out.append(e)
    return out

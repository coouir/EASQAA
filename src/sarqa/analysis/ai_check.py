"""Second validation of the automatic first-deviation stage (docs/validation_round2.md, fixed before sampling).

    python -m sarqa.analysis.ai_check --runs outputs/runs --questions data/questions/test.json \
        --classified outputs/analysis/classified.jsonl --first-sample outputs/analysis/human_sample/human_order.csv \
        --guide outputs/analysis/human_sample/guide.html --out outputs/analysis

Population: agent-error runs of conditions 1, 2, 4, 5 minus the 110 runs of the first sample. Strata = condition x
automatic first-deviation stage; 100 runs, at least 3 per stratum (all of a smaller stratum), the rest proportional
(largest remainder). Everything the assessor may see goes to `<out>/ai_check2/`, the automatic labels to
`<out>/ai_check2_KEY/`; nothing in `ai_check2/` (file names, columns, HTML) carries a label or the stratum.

    ai_check2/check.html        one card per run (random order): question, gold interpretation, gold and alternative
                                programs with their steps on the label boxes, the programs re-run on the boxes the agent
                                received (path, branch, reachable answer), the agent's record, stage select + note
    ai_check2/check_order.csv   rank, run_id
    ai_check2/guide.html        byte-identical copy of the first round's guide, linked from check.html
    ai_check2/images/           boxes drawn on the image
    ai_check2_KEY/ai_check2_key.csv, strata.csv
"""

import argparse
import csv
import html
import json
import random
import shutil
from pathlib import Path

from sarqa.analysis.human_check import CSS, SCRIPT, STAGE_CHOICES
from sarqa.analysis.human_sample import key_row
from sarqa.analysis.main_run_human import _image, form_row

SEED = 20261002
TOTAL = 100
MIN_PER = 3
CONDITIONS = (1, 2, 4, 5)
JUDGED_FIELDS = ("target", "region", "filters", "branch")


def population(classified: list[dict], first_ids: set[str]) -> list[dict]:
    pop = [c for c in classified if c["condition"] in CONDITIONS and c["agent_error"] and c["run_id"] not in first_ids]
    if any(not c.get("first_deviation_stage_name") for c in pop):
        raise SystemExit("a run of the population has no first deviation stage; stopping (plan: report it)")
    return pop


def stratum(c: dict) -> tuple:
    return (c["condition"], c["first_deviation_stage_name"])


def allocate(sizes: dict, total: int = TOTAL, min_per: int = MIN_PER) -> dict:
    """min(min_per, size) per stratum first, the rest in proportion to the room left (largest remainder, ties by key)."""
    take = {k: min(min_per, n) for k, n in sizes.items()}
    spare = total - sum(take.values())
    room = {k: sizes[k] - take[k] for k in sizes}
    total_room = sum(room.values())
    if spare < 0:
        raise SystemExit("minimum allocation exceeds the target")
    if spare > total_room:
        return {k: sizes[k] for k in sizes}
    raw = {k: spare * room[k] / total_room for k in sizes} if total_room else dict.fromkeys(sizes, 0)
    add = {k: int(raw[k]) for k in sizes}
    left = spare - sum(add.values())
    for k in sorted(sizes, key=lambda k: (-(raw[k] - int(raw[k])), k)):
        if left > 0 and add[k] < room[k]:
            add[k] += 1
            left -= 1
    return {k: take[k] + add[k] for k in sizes}


def draw(pop: list[dict], seed: int = SEED, total: int = TOTAL) -> tuple[list[dict], dict]:
    """(sampled rows in random judging order, {stratum: (population, sample)})."""
    strata: dict = {}
    for c in pop:
        strata.setdefault(stratum(c), []).append(c)
    take = allocate({k: len(v) for k, v in strata.items()}, total)
    picked = []
    for k, rows in strata.items():
        rows = sorted(rows, key=lambda c: c["run_id"])
        random.Random(f"{seed}:ai_check2:{k[0]}:{k[1]}").shuffle(rows)
        picked += rows[:take[k]]
    picked.sort(key=lambda c: c["run_id"])
    random.Random(f"{seed}:ai_check2:order").shuffle(picked)
    return picked, {k: (len(strata[k]), take[k]) for k in sorted(strata)}


# ---------------------------------------------------------------- the extra material of the cards

def _short(v, n=260) -> str:
    t = json.dumps(v, ensure_ascii=False, default=str)
    return t if len(t) <= n else t[:n] + " …"


def _run_lines(res) -> list[str]:
    lines = []
    for c in res.calls:
        lines.append(f"  {c.call_id} {c.tool} {_short(c.resolved_args if c.resolved_args is not None else c.args, 200)} -> {_short(c.output)}")
    for d in res.decisions:
        lines.append(f"  if {d['step']}: {_short(d.get('lhs'), 60)} {d['cmp']} {_short(d.get('rhs'), 60)} -> {d.get('chosen')}"
                     + (" (top level)" if d.get("top_level") else ""))
    lines.append(f"  answer: {_short(res.answer)}")
    return lines


def solution_text(q: dict, label_provider, received_provider, reachable, ctx) -> dict:
    """Gold interpretation, gold and alternative programs on the label boxes, and the same programs re-run on the
    boxes the agent received. Plain facts; no judgement."""
    from sarqa.program import run_program

    gi = {k: q["gold_interpretation"].get(k) for k in JUDGED_FIELDS}
    progs = [("gold program", q["program"])] + [(f"allowed alternative {i + 1}", p) for i, p in enumerate(q["alt_programs"])]
    on_label, on_received = [], []
    for name, prog in progs:
        on_label += [f"{name}: {json.dumps(prog, ensure_ascii=False)}", "  on the label boxes:"]
        on_label += _run_lines(run_program(prog, q["image_id"], label_provider, ctx=ctx))
        on_received += [f"{name} on the boxes the agent received:"] + _run_lines(run_program(prog, q["image_id"], received_provider, ctx=ctx))
    on_received.append(f"answer reachable from the received boxes (gold program): {_short(reachable)}")
    return {"interpretation": json.dumps(gi, ensure_ascii=False), "programs": "\n".join(on_label), "received": "\n".join(on_received)}


def card(rank: int, total: int, r: dict, extra: dict) -> str:
    e = html.escape
    opts = "<option value=''></option>" + "".join(f"<option value='{k}'>{e(v)}</option>" for k, v in STAGE_CHOICES)
    img = f"<img src='{e(r['image'])}' width='400'>" if r["image"] else ""
    return (f"<section data-run='{r['run_id']}' data-rank='{rank}'><h3>#{rank}/{total} · {r['qid']} · 조건 {r['condition']} ({r['method']}, {e(r['input'])}) · {r['level']}</h3>"
            f"<p><b>{e(r['question'])}</b></p><p>gold <b>{e(str(r['gold_answer']))}</b> {r['unit']} · 받은 상자로 도달 가능한 답 "
            f"<b>{e(str(r['answer_reachable_from_received_boxes']))}</b> · 에이전트 답 {e(r['agent_answer'])} {e(r['fail_kind'])}</p>"
            f"<div class='g'><div>{img}<p class='c'>빨강 = 라벨 상자, 파랑 = 이 실행이 받은 상자, 초록 = 사분면 선</p></div>"
            f"<div><h4>정답 해석 (target, region, filters, branch)</h4><pre>{e(extra['interpretation'])}</pre>"
            f"<h4>정답 풀이와 허용 대안 풀이 (라벨 상자 기준 호출과 중간값)</h4><pre>{e(extra['programs'])}</pre></div></div>"
            f"<h4>받은 상자로 정답 풀이를 다시 실행한 경로와 도달 가능한 답</h4><pre>{e(extra['received'])}</pre>"
            f"<h4>에이전트 기록</h4><pre>{e(r['agent_record'])}</pre>"
            f"<p>첫 이탈 단계 <select data-f='human_first_deviation'>{opts}</select> "
            f"메모 (맨 앞에 확신도 [high] / [medium] / [low]) <input data-f='human_note' size='60'></p></section>")


def page(cards: list[str], n: int) -> str:
    return (f"<!doctype html><meta charset='utf-8'><title>check</title><style>{CSS}</style>"
            f"<div id='bar'>분류한 건수 <b id='n'>0</b> / {n} · <a href='guide.html' target='_blank'>분류 기준표 (guide.html)</a> · "
            f"<button onclick='dl()'>CSV 내려받기</button></div><h2>{n}건</h2>"
            "<p>기준표, 질문, 정답 해석·풀이, 에이전트 기록만 보고 실행마다 첫 이탈 단계를 하나 고른다. "
            "메모는 <code>[high]</code>, <code>[medium]</code>, <code>[low]</code> 중 하나(확신도)로 시작한다.</p>"
            + "".join(cards) + f"<script>{SCRIPT.replace('human_check_v1', 'ai_check2_v1')}</script>")


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def build(runs_dir: Path, questions: list[dict], classified: list[dict], first_ids: set[str], guide: Path, out: Path,
          images: bool = True, ctx=None, pool=None) -> dict:
    from sarqa.run.conditions import Condition, ProviderPool
    from sarqa.run.runner import load_records

    picked, table = draw(population(classified, first_ids))
    recs = {r["run_id"]: r for r in load_records(runs_dir)}
    by_q = {q["qid"]: q for q in questions}
    if ctx is None:
        from sarqa.tools import default_context

        ctx = default_context()
    pool = pool or ProviderPool("test")
    label = pool.get(Condition(1, "stepwise", "label", 0))
    form_dir, key_dir = out / "ai_check2", out / "ai_check2_KEY"
    cards = []
    for i, c in enumerate(picked):
        rec, q = recs[c["run_id"]], by_q[c["qid"]]
        received = pool.get(Condition(rec["condition"], rec["method"], rec["input"], rec["repeat"]))
        image = _image(ctx, pool, rec, q, form_dir) if images else ""
        row = form_row(c, rec, q, image)
        cards.append(card(i + 1, len(picked), row, solution_text(q, label, received, rec.get("reachable_answer"), ctx)))
    form_dir.mkdir(parents=True, exist_ok=True)
    (form_dir / "check.html").write_text(page(cards, len(picked)), encoding="utf-8")
    shutil.copyfile(guide, form_dir / "guide.html")
    write_csv(form_dir / "check_order.csv", [{"rank": i + 1, "run_id": c["run_id"]} for i, c in enumerate(picked)])
    write_csv(key_dir / "ai_check2_key.csv", [{**key_row(c), "condition": c["condition"], "qid": c["qid"]} for c in picked])
    write_csv(key_dir / "strata.csv", [{"condition": k[0], "first_deviation": k[1], "population": v[0], "sample": v[1]} for k, v in table.items()])
    return {"population": sum(v[0] for v in table.values()), "sample": len(picked), "strata": table}


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--runs", default="outputs/runs")
    p.add_argument("--questions", default="data/questions/test.json")
    p.add_argument("--classified", default="outputs/analysis/classified.jsonl")
    p.add_argument("--first-sample", default="outputs/analysis/human_sample/human_order.csv")
    p.add_argument("--guide", default="outputs/analysis/human_sample/guide.html")
    p.add_argument("--out", default="outputs/analysis")
    p.add_argument("--no-images", action="store_true")
    a = p.parse_args(argv)
    questions = json.loads(Path(a.questions).read_text(encoding="utf-8"))["questions"]
    classified = [json.loads(x) for x in Path(a.classified).read_text(encoding="utf-8").splitlines() if x.strip()]
    with open(a.first_sample, encoding="utf-8-sig", newline="") as f:
        first_ids = {r["run_id"] for r in csv.DictReader(f)}
    res = build(Path(a.runs), questions, classified, first_ids, Path(a.guide), Path(a.out), not a.no_images)
    print(json.dumps({k: (v if k != "strata" else {f"{c}/{s}": n for (c, s), n in v.items()}) for k, v in res.items()}, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Sample of runs for the human check of the automatic classification (SPEC §11.5).

    sarqa analyze human-sample --runs outputs/runs/ --split test --cap 120

Wrong runs are stratified by (cell, first-deviation stage, input-error sub-category). Every stratum gets at
least `min_per` runs (all of them if it is smaller), the rest of the cap is shared in proportion to the
stratum size; the total never exceeds `cap` (at most 150). Fixed seed, so the same records give the same
sample. Written to `<out>/`:

  human_sample.csv       one row per run, the human columns empty; NO automatic label in it
  human_sample.html      the same runs as cards (question, tool calls, answer, images) with a form and a
                         "download CSV" button; also without any automatic label
  human_sample_key.csv   the automatic labels of the same rows, kept apart for the comparison
  images/<run_id>.png    the boxes the agent received (blue) over the label boxes (red)

`agreement()` then compares one or two filled-in CSVs with the key: agreement rate, confusion matrix,
disagreements, and Cohen's kappa between two people. The result does not change any rule (SPEC §11.5).
"""

import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from sarqa.questions.slots import rng_for

MAX_CAP = 150
STAGES = ("interpretation", "tool_selection", "result_reading", "planning_branch", "calculation",
          "answer_formatting", "exec_fail", "none")
CELLS = ("input_only", "agent_only", "both")
CAUSES = ("miss", "fp", "loc", "multiple", "composite", "unknown", "none")
HUMAN_COLUMNS = ("human_cell", "human_first_deviation", "human_input_cause", "human_note")


def stratum_of(c: dict) -> tuple:
    cause = (c.get("input_cause") or {}).get("category")
    return (c["cell"], c.get("first_deviation_stage_name"), cause)


def stratify(classified: list[dict], cap: int = 120, min_per: int = 5, seed: int = 0) -> list[dict]:
    """The sampled classification rows (wrong runs only), sorted by run id."""
    if not 1 <= cap <= MAX_CAP:
        raise ValueError(f"cap must be between 1 and {MAX_CAP}")
    wrong = [c for c in classified if not c["correct"]]
    strata: dict[tuple, list[dict]] = defaultdict(list)
    for c in wrong:
        strata[stratum_of(c)].append(c)
    if len(wrong) <= cap:
        return sorted(wrong, key=lambda c: c["run_id"])
    keys = sorted(strata, key=lambda k: (-len(strata[k]), str(k)))
    m = min_per
    while m > 0 and sum(min(m, len(strata[k])) for k in keys) > cap:
        m -= 1
    take = {k: min(m, len(strata[k])) for k in keys}
    if sum(take.values()) > cap:                          # still too many strata: the largest ones first
        take = dict.fromkeys(keys, 0)
        for k in keys:
            if sum(take.values()) < cap:
                take[k] = 1
    spare = cap - sum(take.values())
    room = {k: len(strata[k]) - take[k] for k in keys}
    total_room = sum(room.values())
    if spare > 0 and total_room > 0:
        raw = {k: spare * room[k] / total_room for k in keys}
        add = {k: min(room[k], int(raw[k])) for k in keys}
        left = spare - sum(add.values())
        for k in sorted(keys, key=lambda k: -(raw[k] - int(raw[k]))):
            if left > 0 and add[k] < room[k]:
                add[k] += 1
                left -= 1
        for k in keys:
            take[k] += add[k]
    out = []
    for k in keys:
        rows = sorted(strata[k], key=lambda c: c["run_id"])
        rng_for(seed, "human-sample", *map(str, k)).shuffle(rows)
        out += rows[:take[k]]
    return sorted(out, key=lambda c: c["run_id"])


def _trace_lines(rec: dict) -> list[str]:
    lines = []
    interp = rec.get("interpretation")
    if interp is not None:
        lines.append(f"[interpretation] {json.dumps(interp, ensure_ascii=False)}")
    for t in rec["turns"]:
        if t.get("plan") is not None:
            lines.append(f"[turn {t['turn']} plan] {json.dumps(t['plan'], ensure_ascii=False)}")
        for e in t.get("execution") or []:
            lines.append(f"  {e['call_id']} {e['tool']} {json.dumps(e['args_resolved'], ensure_ascii=False)} "
                         f"-> {e['tool_output']}")
        if t.get("reading"):
            lines.append(f"[turn {t['turn']} reading] {json.dumps(t['reading'], ensure_ascii=False)}")
        if t.get("action"):
            a = t["action"]
            lines.append(f"[turn {t['turn']}] {a['call_id']} {a['tool']} {json.dumps(a['args_raw'], ensure_ascii=False)}"
                         f" -> {t['tool_output']}")
    for d in rec.get("decisions") or []:
        lines.append(f"[decision] {json.dumps(d, ensure_ascii=False)}")
    ans = rec.get("answer")
    lines.append(f"[final answer] {json.dumps(ans, ensure_ascii=False) if ans else 'none: ' + str(rec.get('fail_kind'))}")
    return lines


def _row(c: dict, rec: dict, q: dict, image: str) -> dict:
    return {"run_id": c["run_id"], "qid": c["qid"], "condition": c["condition"], "level": c["level"],
            "question": q["text_ko"], "gold_answer": q["gold_answer"], "unit": q["unit"],
            "answer_reachable_from_received_boxes": rec.get("reachable_answer"),
            "agent_answer": json.dumps(rec.get("answer"), ensure_ascii=False), "fail_kind": rec.get("fail_kind") or "",
            "image": image, "trace": "\n".join(_trace_lines(rec)), **dict.fromkeys(HUMAN_COLUMNS, "")}


def key_row(c: dict) -> dict:
    return {"run_id": c["run_id"], "auto_cell": c["cell"], "auto_first_deviation": c.get("first_deviation_stage_name") or "none",
            "auto_input_cause": (c.get("input_cause") or {}).get("category") or "none"}


def write_html(rows: list[dict], path: Path) -> None:
    def sel(name, options):
        opts = "".join(f"<option>{o}</option>" for o in ("",) + tuple(options))
        return f"<select data-f='{name}'>{opts}</select>"

    cards = []
    for r in rows:
        img = f"<img src='{html.escape(r['image'])}' width='400'>" if r["image"] else ""
        cards.append(
            f"<section data-run='{r['run_id']}'><h3>{r['qid']} · condition {r['condition']} · {r['level']}</h3>"
            f"<p><b>{html.escape(r['question'])}</b></p>"
            f"<p>gold {html.escape(str(r['gold_answer']))} {r['unit']} · reachable from received boxes "
            f"{html.escape(str(r['answer_reachable_from_received_boxes']))} · agent {html.escape(r['agent_answer'])}"
            f" {html.escape(r['fail_kind'])}</p>{img}<pre>{html.escape(r['trace'])}</pre>"
            f"<p>cell {sel('human_cell', CELLS)} first deviation {sel('human_first_deviation', STAGES)} "
            f"input cause {sel('human_input_cause', CAUSES)} note <input data-f='human_note' size='40'></p></section>")
    page = ("<!doctype html><meta charset='utf-8'><title>human check</title>"
            "<style>body{font-family:sans-serif;max-width:900px;margin:auto}section{border-top:2px solid #888;margin:1em 0}"
            "pre{white-space:pre-wrap;background:#f4f4f4;padding:.5em;font-size:12px}</style>"
            f"<h1>Human check of {len(rows)} runs</h1><p>Classify from the record only. Nothing on this page is an automatic label.</p>"
            + "".join(cards) + "<button onclick='dl()'>Download CSV</button><script>"
            "function dl(){const cols=['run_id','human_cell','human_first_deviation','human_input_cause','human_note'];"
            "let out=[cols.join(',')];document.querySelectorAll('section').forEach(s=>{const v={run_id:s.dataset.run};"
            "s.querySelectorAll('[data-f]').forEach(e=>v[e.dataset.f]=e.value);"
            "out.push(cols.map(c=>'\"'+String(v[c]||'').replace(/\"/g,'\"\"')+'\"').join(','))});"
            "const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([out.join('\\n')],{type:'text/csv'}));"
            "a.download='human_labels.csv';a.click()}</script>")
    path.write_text(page, encoding="utf-8")


def build(runs_dir: Path, questions: list[dict], split: str, out_dir: Path, cap: int = 120, seed: int = 0,
          images: bool = True, ctx=None) -> dict:
    from sarqa.run.runner import load_records

    classified = [json.loads(x) for x in (runs_dir / "classified.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    picked = stratify(classified, cap, seed=seed)
    recs = {r["run_id"]: r for r in load_records(runs_dir)}
    by_q = {q["qid"]: q for q in questions}
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    if images:
        from sarqa.run.conditions import Condition, ProviderPool
        from sarqa.tools import default_context

        ctx = ctx or default_context()
        pool = ProviderPool(split)
    for c in picked:
        rec, q = recs[c["run_id"]], by_q[c["qid"]]
        image = ""
        if images:
            from PIL import Image, ImageDraw

            img = Image.fromarray(ctx.load_image(q["image_id"])).convert("RGB")
            d = ImageDraw.Draw(img)
            for b in ctx.label_boxes.boxes(q["image_id"]):
                d.rectangle([b.x1, b.y1, b.x2, b.y2], outline=(255, 60, 60), width=2)
            prov = pool.get(Condition(rec["condition"], rec["method"], rec["input"], rec["repeat"]))
            for b in prov.boxes(q["image_id"]):
                d.rectangle([b.x1 - 2, b.y1 - 2, b.x2 + 2, b.y2 + 2], outline=(80, 160, 255), width=2)
                d.text((b.x1, max(0, b.y1 - 12)), b.id, fill=(255, 255, 0))
            (out_dir / "images").mkdir(exist_ok=True)
            image = f"images/{c['run_id']}.png"
            img.save(out_dir / image)
        rows.append(_row(c, rec, q, image))
    for name, data in (("human_sample.csv", rows), ("human_sample_key.csv", [key_row(c) for c in picked])):
        with open(out_dir / name, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, list(data[0]) if data else ["run_id"])
            w.writeheader()
            w.writerows(data)
    write_html(rows, out_dir / "human_sample.html")
    strata = Counter(stratum_of(c) for c in picked)
    return {"wrong_runs": sum(not c["correct"] for c in classified), "sampled": len(picked), "cap": cap,
            "strata": len(strata), "out": str(out_dir)}


def _read_csv(path: Path) -> dict[str, dict]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        return {r["run_id"]: r for r in csv.DictReader(f)}


def kappa(a: list, b: list) -> float | None:
    """Cohen's kappa of two label lists of equal length (None if undefined)."""
    n = len(a)
    if n == 0 or n != len(b):
        return None
    po = sum(x == y for x, y in zip(a, b, strict=True)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return None if pe == 1 else round((po - pe) / (1 - pe), 4)


FIELDS = (("human_cell", "auto_cell"), ("human_first_deviation", "auto_first_deviation"),
          ("human_input_cause", "auto_input_cause"))


def agreement(human_csv: Path, key_csv: Path, second_human_csv: Path | None = None) -> dict:
    """Agreement of the human labels with the automatic ones (and between two people if a second file is given)."""
    human, key = _read_csv(human_csv), _read_csv(key_csv)
    second = _read_csv(second_human_csv) if second_human_csv else None
    ids = [i for i in key if i in human and all(human[i].get(h) for h, _ in FIELDS[:1])]
    out = {"n": len(ids), "fields": {}, "disagreements": []}
    for h, a in FIELDS:
        pairs = [(human[i].get(h) or "none", key[i][a]) for i in ids]
        conf = Counter(pairs)
        out["fields"][h] = {"agreement": round(sum(x == y for x, y in pairs) / len(pairs), 4) if pairs else None,
                            "kappa_vs_auto": kappa([x for x, _ in pairs], [y for _, y in pairs]),
                            "confusion": {f"{x} | auto {y}": n for (x, y), n in sorted(conf.items())}}
        if second is not None:
            both = [i for i in ids if i in second]
            out["fields"][h]["kappa_between_humans"] = kappa([human[i].get(h) or "none" for i in both],
                                                             [second[i].get(h) or "none" for i in both])
    for i in ids:
        diff = {h: (human[i].get(h) or "none", key[i][a]) for h, a in FIELDS if (human[i].get(h) or "none") != key[i][a]}
        if diff:
            out["disagreements"].append({"run_id": i, **diff})
    return out

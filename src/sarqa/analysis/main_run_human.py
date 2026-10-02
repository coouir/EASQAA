"""Human-check sample of the main run (SPEC §11.5): at most 150 wrong runs, stratified by error type, centred on
the detected-input conditions 2 and 5.

    python -m sarqa.analysis.main_run_human --runs outputs/runs --questions data/questions/test.json \
        --classified outputs/analysis/classified.jsonl --out outputs/analysis

Sample: 120 wrong runs of conditions 2 and 5 plus 30 of conditions 1 and 4 (same stratification, fixed seed).
Strata = (cell, first-deviation stage, input-error cause); every stratum gets at least `min_per` runs (all
of them if smaller) and the rest is shared in proportion to the stratum size (`human_sample.stratify`).

Two places, so the key stays closed until the labelling is done:
  <out>/human_sample/         the form: CSV + HTML + images. Question, gold answer, **gold solution** (program
                              and the intermediate values on the label boxes), the answer reachable from the
                              boxes the run received, and the agent's record. **No automatic label.**
  <out>/human_sample_KEY/     the automatic labels of the same runs (open only after labelling).
"""

import argparse
import csv
import html
import json
from pathlib import Path

from sarqa.analysis.human_sample import (
    CAUSES,
    CELLS,
    HUMAN_COLUMNS,
    STAGES,
    _trace_lines,
    key_row,
    stratify,
)
from sarqa.run.runner import load_records

SEED = 20260929
PART = (((2, 5), 120), ((1, 4), 30))


def _gold_lines(q: dict) -> list[str]:
    lines = [f"gold program: {json.dumps(q['program'], ensure_ascii=False)}"]
    lines += [f"  {sid}: {json.dumps(out, ensure_ascii=False)}" for sid, out in q["intermediates"]["label"].items()]
    return lines


def sample(classified: list[dict], seed: int = SEED) -> list[dict]:
    picked = []
    for conds, cap in PART:
        pop = [c for c in classified if c["condition"] in conds]
        picked += stratify(pop, cap=cap, min_per=5, seed=seed)
    return sorted(picked, key=lambda c: (c["condition"], c["qid"]))


def _image(ctx, pool, rec, q, out_dir: Path) -> str:
    from PIL import Image, ImageDraw

    from sarqa.run.conditions import Condition

    img = Image.fromarray(ctx.load_image(q["image_id"])).convert("RGB")
    d = ImageDraw.Draw(img)
    for b in ctx.label_boxes.boxes(q["image_id"]):
        d.rectangle([b.x1, b.y1, b.x2, b.y2], outline=(255, 60, 60), width=2)
    prov = pool.get(Condition(rec["condition"], rec["method"], rec["input"], rec["repeat"]))
    for b in prov.boxes(q["image_id"]):
        d.rectangle([b.x1 - 2, b.y1 - 2, b.x2 + 2, b.y2 + 2], outline=(80, 160, 255), width=2)
        d.text((b.x1, max(0, b.y1 - 12)), b.id, fill=(255, 255, 0))
    d.line([400, 0, 400, 800], fill=(80, 255, 160), width=1)
    d.line([0, 400, 800, 400], fill=(80, 255, 160), width=1)
    (out_dir / "images").mkdir(parents=True, exist_ok=True)
    path = f"images/{rec['run_id']}.png"
    img.save(out_dir / path)
    return path


def form_row(c: dict, rec: dict, q: dict, image: str) -> dict:
    return {"run_id": c["run_id"], "qid": c["qid"], "condition": c["condition"], "method": rec["method"], "input": rec["input"],
            "level": c["level"], "question": q["text_ko"], "gold_answer": q["gold_answer"], "unit": q["unit"],
            "gold_calls": q["gold_calls"], "gold_solution": "\n".join(_gold_lines(q)),
            "answer_reachable_from_received_boxes": rec.get("reachable_answer"),
            "agent_answer": json.dumps(rec.get("answer"), ensure_ascii=False), "fail_kind": rec.get("fail_kind") or "",
            "image": image, "agent_record": "\n".join(_trace_lines(rec)), **dict.fromkeys(HUMAN_COLUMNS, "")}


def write_html(rows: list[dict], path: Path) -> None:
    def sel(name, options):
        return f"<select data-f='{name}'>" + "".join(f"<option>{o}</option>" for o in ("",) + tuple(options)) + "</select>"

    cards = []
    for r in rows:
        img = f"<img src='{html.escape(r['image'])}' width='400'>" if r["image"] else ""
        cards.append(
            f"<section data-run='{r['run_id']}'><h3>{r['qid']} · condition {r['condition']} ({r['method']}, {html.escape(r['input'])}) · {r['level']}</h3>"
            f"<p><b>{html.escape(r['question'])}</b></p>"
            f"<p>gold <b>{html.escape(str(r['gold_answer']))}</b> {r['unit']} · answer reachable from the boxes this run received "
            f"<b>{html.escape(str(r['answer_reachable_from_received_boxes']))}</b> · agent answered {html.escape(r['agent_answer'])} {html.escape(r['fail_kind'])}</p>"
            f"<div class='g'><div>{img}<p class='c'>red = label boxes, blue = boxes the run received, green = quadrant lines</p></div><div>"
            f"<h4>gold solution</h4><pre>{html.escape(r['gold_solution'])}</pre></div></div>"
            f"<h4>agent record</h4><pre>{html.escape(r['agent_record'])}</pre>"
            f"<p>cell {sel('human_cell', CELLS)} first deviation {sel('human_first_deviation', STAGES)} "
            f"input cause {sel('human_input_cause', CAUSES)} note <input data-f='human_note' size='40'></p></section>")
    page = ("<!doctype html><meta charset='utf-8'><title>human check</title><style>body{font-family:sans-serif;max-width:1100px;margin:auto}"
            "section{border-top:3px solid #666;margin:1.5em 0}pre{white-space:pre-wrap;word-break:break-all;background:#f4f4f4;padding:.5em;font-size:12px;max-height:300px;overflow:auto}"
            ".g{display:grid;grid-template-columns:420px 1fr;gap:1em}.c{font-size:12px;color:#555}</style>"
            f"<h1>Human check of {len(rows)} runs</h1><p>Classify from the question, the gold solution and the agent record only. "
            "Nothing on this page is an automatic label. Fill the choices, then download the CSV.</p>"
            + "".join(cards) + "<button onclick='dl()'>Download CSV</button><script>"
            "function dl(){const cols=['run_id','human_cell','human_first_deviation','human_input_cause','human_note'];"
            "let out=[cols.join(',')];document.querySelectorAll('section').forEach(s=>{const v={run_id:s.dataset.run};"
            "s.querySelectorAll('[data-f]').forEach(e=>v[e.dataset.f]=e.value);"
            "out.push(cols.map(c=>'\"'+String(v[c]||'').replace(/\"/g,'\"\"')+'\"').join(','))});"
            "const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([out.join('\\n')],{type:'text/csv'}));"
            "a.download='human_labels.csv';a.click()}</script>")
    path.write_text(page, encoding="utf-8")


def write_csv(path: Path, rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def build(runs_dir: Path, questions: list[dict], classified: list[dict], out: Path, images: bool = True, ctx=None) -> dict:
    picked = sample(classified)
    recs = {r["run_id"]: r for r in load_records(runs_dir)}
    by_q = {q["qid"]: q for q in questions}
    form_dir, key_dir = out / "human_sample", out / "human_sample_KEY"
    form_dir.mkdir(parents=True, exist_ok=True)
    key_dir.mkdir(parents=True, exist_ok=True)
    if images:
        from sarqa.run.conditions import ProviderPool
        from sarqa.tools import default_context

        ctx = ctx or default_context()
        pool = ProviderPool("test")
    rows = []
    for c in picked:
        rec, q = recs[c["run_id"]], by_q[c["qid"]]
        rows.append(form_row(c, rec, q, _image(ctx, pool, rec, q, form_dir) if images else ""))
    write_csv(form_dir / "human_sample.csv", rows)
    write_html(rows, form_dir / "human_sample.html")
    write_csv(key_dir / "human_sample_key.csv", [key_row(c) | {"condition": c["condition"], "qid": c["qid"]} for c in picked])
    by_cond = {}
    for c in picked:
        by_cond[c["condition"]] = by_cond.get(c["condition"], 0) + 1
    return {"sampled": len(picked), "by_condition": dict(sorted(by_cond.items())), "form": str(form_dir), "key": str(key_dir)}


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--runs", default="outputs/runs")
    p.add_argument("--questions", default="data/questions/test.json")
    p.add_argument("--classified", default="outputs/analysis/classified.jsonl")
    p.add_argument("--out", default="outputs/analysis")
    p.add_argument("--no-images", action="store_true")
    a = p.parse_args(argv)
    questions = json.loads(Path(a.questions).read_text(encoding="utf-8"))["questions"]
    classified = [json.loads(x) for x in Path(a.classified).read_text(encoding="utf-8").splitlines() if x.strip()]
    print(json.dumps(build(Path(a.runs), questions, classified, Path(a.out), not a.no_images), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

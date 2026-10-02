"""Results of the second validation (docs/validation_round2.md): the AI assessor's first-deviation labels against the
automatic ones. Plan: no exclusions in the main result; the auxiliary result leaves out the three runs that the guide uses
as examples.

    python -m sarqa.analysis.validation_round2 --labels outputs/analysis/ai_check2_out/ai_labels2.csv \
        --key outputs/analysis/ai_check2_KEY/ai_check2_key.csv --classified outputs/analysis/classified.jsonl \
        --order outputs/analysis/ai_check2/check_order.csv --out outputs/analysis/ai_check2_out

Writes (never into ai_check2/ or ai_check2_KEY/): results_main.csv, results_aux97.csv, confusion.csv, by_stage.csv,
by_confidence.csv, by_condition.csv, disagreement_cells.csv, disagreements.csv, summary.md.
"""

import argparse
import json
from collections import Counter
from pathlib import Path

from sarqa.analysis.human_compare import (
    agreement_by,
    compare,
    confidence,
    read_rows,
    write_csv,
)

GUIDE_EXAMPLES = frozenset({"f3a256b2f40e2d15", "2ed629eaa0dc18e9", "4380d06cf046efe7"})   # #16, #19, #38 of the round-2 order
CONFIDENCE = ("high", "medium", "low", "none")


def first_deviation_kind(c: dict) -> str:
    """Code of the deviation that made the automatic first stage (stage 1-6: earliest by turn, then stage), else the stage name."""
    stage, turn = c.get("first_deviation_stage"), c.get("first_deviation_turn")
    for d in c.get("deviations", []):
        if not d.get("harmless") and d["stage"] == stage and d["turn"] == turn:
            return d["kind"]
    return f"({c.get('first_deviation_stage_name')}: no deviation record)"


def summarize(r: dict) -> dict:
    n = r["n"]
    return {"n": n, "agree": r["agree"], "agreement": r["agree"] / n if n else None, "kappa": r["kappa"],
            "kappa_lo": r["kappa_lo"], "kappa_hi": r["kappa_hi"], "kappa_skipped": r["kappa_skipped"]}


def disagreement_cells(r: dict, classified: dict, order: dict, top: int = 4) -> list[dict]:
    """The `top` off-diagonal confusion cells (rows = AI, columns = automatic) with the automatic deviation codes."""
    cells: dict = {}
    for x in r["done"]:
        ai, auto = x["human_first_deviation"].strip(), r["keyed"][x["run_id"]]["auto_first_deviation"]
        if ai != auto:
            cells.setdefault((ai, auto), []).append(x)
    out = []
    for (ai, auto), rows in sorted(cells.items(), key=lambda kv: (-len(kv[1]), kv[0]))[:top]:
        rows = sorted(rows, key=lambda x: order[x["run_id"]])
        kinds = Counter(first_deviation_kind(classified[x["run_id"]]) for x in rows)
        out.append({"ai": ai, "auto": auto, "n": len(rows), "auto_codes": json.dumps(dict(kinds.most_common()), ensure_ascii=False),
                    "ranks": " ".join(str(order[x["run_id"]]) for x in rows),
                    "representative_ranks": " ".join(str(order[x["run_id"]]) for x in rows[:2])})
    return out


def run(labels: Path, key: Path, classified_path: Path, order_path: Path, out: Path) -> dict:
    human, keyrows = read_rows(labels), read_rows(key)
    with open(classified_path, encoding="utf-8") as f:
        classified = {c["run_id"]: c for c in map(json.loads, (x for x in f if x.strip()))}
    order = {r["run_id"]: int(r["rank"]) for r in read_rows(order_path)}
    main_r, aux_r = compare(human, keyrows), compare(human, keyrows, GUIDE_EXAMPLES)
    labs = main_r["labels"]
    out.mkdir(parents=True, exist_ok=True)
    cols = ["n", "agree", "agreement", "kappa", "kappa_lo", "kappa_hi", "kappa_skipped"]
    write_csv(out / "results_main.csv", [summarize(main_r)], cols)
    write_csv(out / "results_aux97.csv", [{**summarize(aux_r), "excluded": " ".join(sorted(GUIDE_EXAMPLES))}], [*cols, "excluded"])
    write_csv(out / "confusion.csv", [{"ai": h, **{a: main_r["confusion"].get((h, a), 0) for a in labs}} for h in labs], ["ai", *labs])
    write_csv(out / "by_stage.csv", main_r["per_stage"], ["auto_stage", "n_auto", "human_agrees", "n_human"])
    by_conf = agreement_by(main_r["done"], main_r["keyed"], lambda h, k: confidence(h.get("human_note", "")))
    write_csv(out / "by_confidence.csv", [{"confidence": c, "n": by_conf.get(c, (0, 0))[0], "agree": by_conf.get(c, (0, 0))[1],
                                           "agreement": (by_conf[c][1] / by_conf[c][0]) if c in by_conf else ""} for c in CONFIDENCE],
              ["confidence", "n", "agree", "agreement"])
    by_cond = agreement_by(main_r["done"], main_r["keyed"], lambda h, k: int(k["condition"]))
    write_csv(out / "by_condition.csv", [{"condition": c, "n": n, "agree": a, "agreement": a / n} for c, (n, a) in sorted(by_cond.items())],
              ["condition", "n", "agree", "agreement"])
    cells = disagreement_cells(main_r, classified, order)
    write_csv(out / "disagreement_cells.csv", cells, ["ai", "auto", "n", "auto_codes", "ranks", "representative_ranks"])
    dis = [{"rank": order[d["run_id"]], **d, "auto_code": first_deviation_kind(classified[d["run_id"]])} for d in main_r["disagreements"]]
    dis.sort(key=lambda d: d["rank"])
    write_csv(out / "disagreements.csv", dis, ["rank", "run_id", "condition", "qid", "human", "auto", "auto_code", "human_note"])
    return {"main": main_r, "aux": aux_r, "cells": cells, "by_conf": by_conf, "by_cond": by_cond, "labels": labs}


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--labels", required=True)
    p.add_argument("--key", default="outputs/analysis/ai_check2_KEY/ai_check2_key.csv")
    p.add_argument("--classified", default="outputs/analysis/classified.jsonl")
    p.add_argument("--order", default="outputs/analysis/ai_check2/check_order.csv")
    p.add_argument("--out", default="outputs/analysis/ai_check2_out")
    a = p.parse_args(argv)
    res = run(Path(a.labels), Path(a.key), Path(a.classified), Path(a.order), Path(a.out))
    for name in ("main", "aux"):
        r = res[name]
        print(name, summarize(r))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

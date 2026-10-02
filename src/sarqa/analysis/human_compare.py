"""Compare the human first-deviation labels with the automatic ones (SPEC §11.5). Run only after labelling.

    python -m sarqa.analysis.human_compare --human human_labels.csv \
        --key outputs/analysis/human_sample_KEY/human_sample_key.csv --out outputs/analysis/human_compare

`--human` is the CSV exported from `human_check.html` (columns run_id, human_first_deviation, human_note). Rows with an
empty stage are ignored, so any number of labelled runs (below the target 100, above the minimum 60) works; every
figure uses exactly the labelled runs. Writes agreement.csv, confusion.csv, disagreements.csv, summary.md and prints the summary.
Kappa: Cohen's, 95% interval = percentile bootstrap over the labelled runs (B=10,000, fixed seed; resamples where
kappa is undefined are skipped and counted).
"""

import argparse
import csv
import random
import re
from collections import Counter
from pathlib import Path

B = 10_000
SEED = 20261002


def read_rows(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def kappa(a: list, b: list) -> float | None:
    n = len(a)
    if n == 0:
        return None
    po = sum(x == y for x, y in zip(a, b, strict=True)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return None if pe >= 1 else (po - pe) / (1 - pe)


def kappa_ci(a: list, b: list, boot: int = B, seed: int = SEED) -> tuple[float | None, float | None, int]:
    rng = random.Random(seed)
    n, vals, skipped = len(a), [], 0
    for _ in range(boot):
        idx = [rng.randrange(n) for _ in range(n)]
        k = kappa([a[i] for i in idx], [b[i] for i in idx])
        if k is None:
            skipped += 1
        else:
            vals.append(k)
    if not vals:
        return None, None, skipped
    vals.sort()
    return vals[int(0.025 * len(vals))], vals[min(len(vals) - 1, int(0.975 * len(vals)))], skipped


def confidence(note: str) -> str:
    """The confidence written at the very start of a note: `[high]`, `[medium]`, `[low]`; `none` if there is none."""
    m = re.match(r"\s*\[(high|medium|low)\]", note or "", flags=re.IGNORECASE)
    return m.group(1).lower() if m else "none"


def agreement_by(done: list[dict], keyed: dict, group) -> dict:
    """{group value: (n, agreements)} over the labelled runs; `group(human_row, key_row)` gives the group."""
    out: dict = {}
    for h in done:
        k = keyed[h["run_id"]]
        n, a = out.get(group(h, k), (0, 0))
        out[group(h, k)] = (n + 1, a + (h["human_first_deviation"].strip() == k["auto_first_deviation"]))
    return out


def compare(human: list[dict], key: list[dict], exclude: frozenset = frozenset()) -> dict:
    keyed = {k["run_id"]: k for k in key}
    done = [h for h in human if (h.get("human_first_deviation") or "").strip() and h["run_id"] in keyed and h["run_id"] not in exclude]
    unknown_ids = [h["run_id"] for h in human if h["run_id"] not in keyed]
    hum = [h["human_first_deviation"].strip() for h in done]
    aut = [keyed[h["run_id"]]["auto_first_deviation"] for h in done]
    n = len(done)
    lo, hi, skipped = kappa_ci(hum, aut) if n else (None, None, 0)
    labels = sorted(set(hum) | set(aut))
    conf = Counter(zip(hum, aut, strict=True))
    per_stage = []
    for s in labels:
        auto_n = sum(1 for y in aut if y == s)
        per_stage.append({"auto_stage": s, "n_auto": auto_n, "human_agrees": sum(1 for x, y in zip(hum, aut, strict=True) if x == y == s),
                          "n_human": sum(1 for x in hum if x == s)})
    dis = [{"run_id": h["run_id"], "condition": keyed[h["run_id"]].get("condition", ""), "qid": keyed[h["run_id"]].get("qid", ""),
            "human": x, "auto": y, "human_note": h.get("human_note", "")}
           for h, x, y in zip(done, hum, aut, strict=True) if x != y]
    return {"n": n, "agree": sum(x == y for x, y in zip(hum, aut, strict=True)), "kappa": kappa(hum, aut), "kappa_lo": lo, "kappa_hi": hi,
            "kappa_skipped": skipped, "labels": labels, "confusion": conf, "per_stage": per_stage, "disagreements": dis,
            "ids_not_in_key": unknown_ids, "done": done, "keyed": keyed}


def write_csv(path: Path, rows: list[dict], cols: list[str]) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, cols)
        w.writeheader()
        w.writerows(rows)


def summary(r: dict) -> str:
    def f(x):
        return "n/a" if x is None else f"{x:.3f}"

    if not r["n"]:
        return "No labelled runs found.\n"
    kappa_line = (f"Cohen's kappa: {f(r['kappa'])} (95% bootstrap interval {f(r['kappa_lo'])} to {f(r['kappa_hi'])}; "
                  f"{r['kappa_skipped']} of {B} resamples skipped)")
    lines = [f"labelled runs: {r['n']}", f"agreement: {r['agree']}/{r['n']} = {r['agree'] / r['n']:.3f}", kappa_line, "",
             "confusion (rows = human, columns = automatic):"]
    labs = r["labels"]
    lines.append("| human \\ auto | " + " | ".join(labs) + " |")
    lines.append("|---|" + "---|" * len(labs))
    for h in labs:
        lines.append(f"| {h} | " + " | ".join(str(r["confusion"].get((h, a), 0)) for a in labs) + " |")
    lines += ["", f"disagreements: {len(r['disagreements'])}"]
    lines += [f"- {d['run_id']} cond {d['condition']} {d['qid']}: human {d['human']} / auto {d['auto']} {d['human_note']}" for d in r["disagreements"]]
    if r["ids_not_in_key"]:
        lines += ["", f"run_ids not in the key (ignored): {r['ids_not_in_key']}"]
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--human", required=True)
    p.add_argument("--key", default="outputs/analysis/human_sample_KEY/human_sample_key.csv")
    p.add_argument("--out", default="outputs/analysis/human_compare")
    a = p.parse_args(argv)
    r = compare(read_rows(Path(a.human)), read_rows(Path(a.key)))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    labs = r["labels"]
    write_csv(out / "confusion.csv", [{"human": h, **{x: r["confusion"].get((h, x), 0) for x in labs}} for h in labs], ["human", *labs])
    write_csv(out / "agreement.csv", [{"n": r["n"], "agree": r["agree"], "kappa": r["kappa"], "kappa_lo": r["kappa_lo"], "kappa_hi": r["kappa_hi"]}],
              ["n", "agree", "kappa", "kappa_lo", "kappa_hi"])
    write_csv(out / "by_stage.csv", r["per_stage"], ["auto_stage", "n_auto", "human_agrees", "n_human"])
    write_csv(out / "disagreements.csv", r["disagreements"], ["run_id", "condition", "qid", "human", "auto", "human_note"])
    text = summary(r)
    (out / "summary.md").write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

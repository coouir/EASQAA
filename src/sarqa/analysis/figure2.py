"""Figure 2 of the paper: where the wrong answers of conditions 1, 2, 4, 5 come from.

    python src/sarqa/analysis/figure2.py --analysis outputs/analysis --out outputs/analysis/figures

(a) share of all 360 questions answered wrongly, stacked: input only / both / agent only
(b) first-deviation stage of the agent-error runs, stacked, in %

Every number is read from `decomposition_cells.csv` and `decomposition_first_deviation.csv`. The script needs
only matplotlib (no sarqa import, so it runs in any environment that has it). Font: HCR Batang (함초롬바탕),
looked up by file path when matplotlib's cache does not know it; there is no fallback, a missing font stops the run.
One-column size 8 cm x 6 cm, 8 pt text; gray levels and hatches together so it reads in black and white.
"""

import argparse
import csv
import subprocess
from pathlib import Path

CONDITIONS = (1, 2, 4, 5)
COND_LABEL = {1: "라벨", 2: "탐지", 4: "라벨", 5: "탐지"}
METHOD = (("단계별", (1, 2)), ("일괄", (4, 5)))
CELLS = (("input_only", "입력만"), ("both", "둘 다"), ("agent_only", "에이전트만"))
STAGES = (("interpretation", "해석"), ("tool_selection", "도구 선택·호출"), ("result_reading", "결과 해석"),
          ("calculation", "계산"), ("exec_fail", "실행 실패"))
OTHER_STAGES = ("planning_branch", "answer_formatting", "unknown")   # 0 everywhere in the main run; checked below
GRAYS = ("#f2f2f2", "#bdbdbd", "#7a7a7a", "#3d3d3d", "#000000")
HATCHES = ("", "///", "xxx", "...", "\\\\\\")
FONT_NAME = "HCR Batang"
CM = 1 / 2.54


def read_csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def cell_shares(rows: list[dict]) -> dict[int, dict[str, float]]:
    """% of all runs per cell (input_only, both, agent_only) and condition."""
    out: dict[int, dict[str, float]] = {c: {} for c in CONDITIONS}
    for r in rows:
        c = int(r["condition"])
        if c in out and r["cell"] in dict(CELLS):
            out[c][r["cell"]] = 100 * float(r["share_of_all_runs"])
    return out


def stage_shares(rows: list[dict]) -> dict[int, dict[str, float]]:
    """% of the agent-error runs per first-deviation stage and condition. Stages not drawn must be 0."""
    out: dict[int, dict[str, float]] = {c: {} for c in CONDITIONS}
    for r in rows:
        c = int(r["condition"])
        if c in out and r["share_of_agent_error_runs"] != "" and r["first_deviation"] in {k for k, _ in STAGES} | set(OTHER_STAGES):
            out[c][r["first_deviation"]] = 100 * float(r["share_of_agent_error_runs"])
    for c in CONDITIONS:
        missed = [s for s in OTHER_STAGES if out[c].get(s, 0) != 0]
        if missed:
            raise SystemExit(f"condition {c} has first deviations that the figure does not draw: {missed}")
    return out


def use_font(font_manager, plt) -> str:
    """Find HCR Batang; fall back to the font file path (never to another font)."""
    names = {f.name for f in font_manager.fontManager.ttflist}
    if FONT_NAME not in names:
        listed = subprocess.run(["fc-list", ":family=HCR Batang", "file"], capture_output=True, text=True, check=False).stdout
        files = [x.split(":")[0] for x in listed.splitlines() if x.strip() and "Bold" not in x]
        if not files:
            raise SystemExit(f"font {FONT_NAME!r} is not installed; stopping (no other font is used)")
        for f in files:
            font_manager.fontManager.addfont(f)
        if FONT_NAME not in {f.name for f in font_manager.fontManager.ttflist}:
            raise SystemExit(f"matplotlib cannot use {files}")
    plt.rcParams["font.family"] = FONT_NAME
    plt.rcParams["axes.unicode_minus"] = True
    return FONT_NAME


def minus_ok(font_manager) -> bool:
    """True if the font file has U+2212 (the minus sign matplotlib writes for negative tick labels)."""
    path = font_manager.findfont(font_manager.FontProperties(family=FONT_NAME), fallback_to_default=False)
    from matplotlib.ft2font import FT2Font
    return FT2Font(path).get_char_index(0x2212) != 0


def stacked(ax, data: dict[int, dict[str, float]], parts, ylabel: str, ymax: float):
    bottoms = [0.0] * len(CONDITIONS)
    handles = []
    for i, (key, label) in enumerate(parts):
        vals = [data[c].get(key, 0.0) for c in CONDITIONS]
        bar = ax.bar(range(len(CONDITIONS)), vals, 0.68, bottom=bottoms, color=GRAYS[i], hatch=HATCHES[i],
                     edgecolor="black", linewidth=0.5, label=label)
        handles.append(bar)
        bottoms = [b + v for b, v in zip(bottoms, vals)]
    ax.set_ylim(0, ymax)
    ax.set_ylabel(ylabel)
    ax.set_xticks(range(len(CONDITIONS)))
    ax.set_xticklabels([f"{c}\n{COND_LABEL[c]}" for c in CONDITIONS])
    for name, conds in METHOD:    # method names under the condition labels
        x = sum(CONDITIONS.index(c) for c in conds) / len(conds)
        ax.annotate(name, xy=(x, 0), xycoords=("data", "axes fraction"), xytext=(0, -24), textcoords="offset points",
                    ha="center", va="top")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.tick_params(length=2, width=0.5)
    for s in ax.spines.values():
        s.set_linewidth(0.5)
    return bottoms


def make(analysis: Path, out: Path) -> list[Path]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager

    use_font(font_manager, plt)
    plt.rcParams.update({"font.size": 8, "axes.labelsize": 8, "xtick.labelsize": 8, "ytick.labelsize": 8,
                         "legend.fontsize": 8, "hatch.linewidth": 0.4, "pdf.fonttype": 42, "ps.fonttype": 42})
    cells = cell_shares(read_csv(analysis / "decomposition_cells.csv"))
    stages = stage_shares(read_csv(analysis / "decomposition_first_deviation.csv"))
    fig, (a, b) = plt.subplots(1, 2, figsize=(8 * CM, 6 * CM))
    tops = stacked(a, cells, CELLS, "오답 비율 (%)", 50)
    stacked(b, stages, STAGES, "에이전트 오류 중 (%)", 100)
    a.set_title("(a)", loc="left", fontsize=8, pad=2)
    b.set_title("(b)", loc="left", fontsize=8, pad=2)
    for ax, ncol_rows in ((a, len(CELLS)), (b, len(STAGES))):
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.56), frameon=False, ncol=1, handlelength=1.4,
                  handletextpad=0.4, labelspacing=0.2, borderaxespad=0)
    fig.subplots_adjust(left=0.13, right=0.99, top=0.94, bottom=0.53, wspace=0.6)
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    for ext, kw in (("png", {"dpi": 600}), ("pdf", {})):
        p = out / f"figure2.{ext}"
        fig.savefig(p, **kw)
        paths.append(p)
    print("font:", FONT_NAME, "| U+2212 in font:", minus_ok(font_manager), "| tops (a):", [round(t, 1) for t in tops])
    return paths


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--analysis", default="outputs/analysis")
    p.add_argument("--out", default="outputs/analysis/figures")
    a = p.parse_args(argv)
    for path in make(Path(a.analysis), Path(a.out)):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

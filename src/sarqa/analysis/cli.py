"""Entry of `sarqa analyze ...` (extra arguments are forwarded here by `sarqa/cli.py`, which is frozen).

Analysis code lives in `sarqa/analysis/`, which is not frozen (SPEC §0-3), so new subcommands are added
here after the freeze without touching `cli.py`.

    sarqa analyze human-sample --runs outputs/runs/ --split test [--cap 120]
    sarqa analyze agreement --human filled.csv --key human_sample_key.csv [--human2 other.csv]
    sarqa analyze                       # lists the subcommands
    sarqa analyze metrics|tables|figures  # written after the freeze (issues #31, #32)
"""

import argparse
import json
from pathlib import Path

PLANNED = {"metrics": "#31 (accuracy, failures, paired comparison, scene-group bootstrap)",
           "tables": "#32 (tables 1-4)", "figures": "#32 (figure 1)"}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="sarqa analyze", description="analysis of run records")
    p.add_argument("--runs", default="outputs/runs/")
    common = argparse.ArgumentParser(add_help=False)          # `--runs` may come before or after the subcommand
    common.add_argument("--runs", default=argparse.SUPPRESS)
    sub = p.add_subparsers(dest="what")
    hs = sub.add_parser("human-sample", parents=[common],
                        help="stratified sample of wrong runs for the human check (SPEC §11.5)")
    hs.add_argument("--split", default="test")
    hs.add_argument("--questions", default=None)
    hs.add_argument("--cap", type=int, default=120)
    hs.add_argument("--seed", type=int, default=0)
    hs.add_argument("--out", default=None)
    hs.add_argument("--no-images", action="store_true")
    ag = sub.add_parser("agreement", parents=[common], help="compare filled-in human labels with the automatic ones")
    ag.add_argument("--human", required=True)
    ag.add_argument("--key", required=True)
    ag.add_argument("--human2", default=None)
    for name, what in PLANNED.items():
        sub.add_parser(name, parents=[common], help=f"not written yet: {what}")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.what is None:
        print("subcommands: human-sample, agreement (ready); " + "; ".join(f"{k}: {v}" for k, v in PLANNED.items()))
        return 0
    if args.what in PLANNED:
        print(f"'{args.what}' is written after the freeze: {PLANNED[args.what]}")
        return 2
    if args.what == "agreement":
        from sarqa.analysis.human_sample import agreement

        print(json.dumps(agreement(Path(args.human), Path(args.key), Path(args.human2) if args.human2 else None),
                         ensure_ascii=False, indent=1))
        return 0
    from sarqa.analysis.human_sample import build
    from sarqa.config import repo_path
    from sarqa.questions.generate import read_questions

    runs = repo_path(args.runs)
    qs = read_questions(repo_path(args.questions or f"data/questions/{args.split}.json"))
    out = Path(repo_path(args.out)) if args.out else runs / "human_sample"
    print(json.dumps(build(runs, qs, args.split, out, args.cap, args.seed, not args.no_images), indent=1))
    return 0

"""`sarqa` command line entry point. Subcommands are added milestone by milestone."""

import argparse

from sarqa import __version__

HRSID_ROOT = "data/hrsid/HRSID_JPG"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sarqa", description="SAR QA agent error analysis")
    parser.add_argument("--version", action="version", version=f"sarqa {__version__}")
    sub = parser.add_subparsers(dest="command")
    data = sub.add_parser("data", help="HRSID data preparation").add_subparsers(dest="data_command")
    scenes = data.add_parser("scenes", help="build splits/scenes.json")
    scenes.add_argument("--root", default=HRSID_ROOT)
    scenes.add_argument("--out", default="splits/scenes.json")
    splits = data.add_parser("splits", help="build splits/splits.json and the overlap report")
    splits.add_argument("--root", default=HRSID_ROOT)
    splits.add_argument("--scenes", default="splits/scenes.json")
    splits.add_argument("--out", default="splits/splits.json")
    splits.add_argument("--report", default="splits/splits_report.json")
    splits.add_argument("--no-dhash", action="store_true", help="skip the auxiliary dHash check")
    qs = sub.add_parser("questions", help="question generation and review").add_subparsers(
        dest="questions_command")
    gen = qs.add_parser("generate", help="generate a question set (dev only; test needs --allow-test)")
    gen.add_argument("--split", default="dev")
    gen.add_argument("--out", default=None)
    gen.add_argument("--allow-test", action="store_true",
                     help="freeze time only (SPEC §14 M5): test questions are generated once")
    rev = qs.add_parser("review", help="write docs/dev_questions.md and outputs/gold_check.csv")
    rev.add_argument("--split", default="dev")
    rev.add_argument("--questions", default=None)
    val = qs.add_parser("validate", help="validate a question file")
    val.add_argument("--split", default="dev")
    val.add_argument("--questions", default=None)
    det = sub.add_parser("detector", help="detector training and inference").add_subparsers(
        dest="detector_command")
    for name in ("train", "infer"):
        det.add_parser(name, help=f"{name} (extra args are forwarded)").add_argument(
            "rest", nargs=argparse.REMAINDER)
    return parser


def _questions_main(args) -> int:
    import json

    from sarqa.boxes import detected_provider
    from sarqa.config import repo_path
    from sarqa.questions import generate as G
    from sarqa.questions import review as R
    from sarqa.questions.validate import validate
    from sarqa.tools import default_context

    path = repo_path(getattr(args, "out", None) or getattr(args, "questions", None)
                     or f"data/questions/{args.split}.json")
    ctx = default_context()
    if args.questions_command == "generate":
        if args.split == "test" and not args.allow_test:
            print("refusing to generate test questions: they are generated once, at freeze time "
                  "(SPEC §0-4, §14 M5). Pass --allow-test only then.")
            return 2
        qs = G.generate(args.split, ctx, detected_provider=detected_provider(args.split))
        problems = validate(qs, args.split, ctx)
        if problems:
            print("validation failed:\n" + "\n".join(problems[:30]))
            return 1
        G.write_questions(qs, path)
        print(json.dumps({k: v for k, v in G.summary(qs).items() if k != "groups"}, indent=1))
        print(f"wrote {path}")
        return 0
    qs = G.read_questions(path)
    if args.questions_command == "validate":
        problems = validate(qs, args.split, ctx)
        print("\n".join(problems) if problems else f"{len(qs)} questions OK")
        return 1 if problems else 0
    R.write_review_md(qs, repo_path("docs/dev_questions.md"), "dev 문항 검토용 표")
    R.write_gold_check(qs, ctx, repo_path("outputs/gold_check.csv"))
    print("wrote docs/dev_questions.md and outputs/gold_check.csv")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "data" and args.data_command == "scenes":
        from sarqa.data.scenes import write_scenes

        scenes = write_scenes(args.root, args.out)
        print(f"{scenes['n_images']} images -> {scenes['n_groups']} groups ({args.out})")
    if args.command == "data" and args.data_command == "splits":
        import json

        from sarqa.data.splits import write_splits

        rep = write_splits(args.root, args.scenes, args.out, args.report, not args.no_dhash)
        print(json.dumps({k: v for k, v in rep.items() if k != "dhash_aux"}, indent=1))
        if "dhash_aux" in rep:
            print("dhash cross-split pairs:", rep["dhash_aux"]["n_cross_split_pairs"])
    if args.command == "questions" and args.questions_command:
        return _questions_main(args)
    if args.command == "detector" and args.detector_command:
        import importlib

        return importlib.import_module(f"sarqa.detector.{args.detector_command}").main(args.rest)
    return 0

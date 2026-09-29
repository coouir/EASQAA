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
    return parser


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
    return 0

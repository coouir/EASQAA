"""`sarqa` command line entry point. Subcommands are added milestone by milestone."""

import argparse

from sarqa import __version__

HRSID_ROOT = "data/hrsid/HRSID_JPG"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sarqa", description="SAR QA agent error analysis")
    parser.add_argument("--version", action="version", version=f"sarqa {__version__}")
    sub = parser.add_subparsers(dest="command")
    data = sub.add_parser("data", help="HRSID data preparation").add_subparsers(dest="data_command")
    scenes = data.add_parser("scenes", help="build data/scenes.json")
    scenes.add_argument("--root", default=HRSID_ROOT)
    scenes.add_argument("--out", default="data/scenes.json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "data" and args.data_command == "scenes":
        from sarqa.data.scenes import write_scenes

        scenes = write_scenes(args.root, args.out)
        print(f"{scenes['n_images']} images -> {scenes['n_groups']} groups ({args.out})")
    return 0

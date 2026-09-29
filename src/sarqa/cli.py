"""`sarqa` command line entry point. Subcommands are added milestone by milestone."""

import argparse

from sarqa import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sarqa", description="SAR QA agent error analysis")
    parser.add_argument("--version", action="version", version=f"sarqa {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    build_parser().parse_args(argv)
    return 0

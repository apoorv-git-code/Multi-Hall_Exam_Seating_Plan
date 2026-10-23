"""Multi-Hall Exam Seating Allocation: command line entry point.

    python main.py                       interactive menu
    python main.py --students S --halls H [--algorithm A] [--out DIR]
                                         one non-interactive run

Exit codes: 0 success, 1 unreadable or invalid input, 2 command-line usage
error, 3 students could not all be seated.

This file only parses arguments. All behaviour lives in ``src/cli/menu.py``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.analysis.benchmark import ALGORITHMS  # noqa: E402
from src.cli.menu import (  # noqa: E402
    DEFAULT_ALGORITHM,
    DEFAULT_OUT_DIR,
    EXIT_DATA_ERROR,
    Session,
    load_default_config,
    run_menu,
    run_non_interactive,
)
from src.dataio.validator import DataFormatError  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    """Return the argument parser."""
    parser = argparse.ArgumentParser(
        description="Multi-hall exam seating allocation using graph coloring.",
        epilog="Exit codes: 0 success, 1 invalid input data, 2 usage error, "
               "3 students could not all be seated.",
    )
    parser.add_argument("--students", help="students CSV file (use together with --halls)")
    parser.add_argument("--halls", help="halls CSV file (use together with --students)")
    parser.add_argument("--algorithm", choices=ALGORITHMS, default=None,
                        help=f"coloring algorithm (default: {DEFAULT_ALGORITHM})")
    parser.add_argument("--out", default=None,
                        help=f"output folder (default: {DEFAULT_OUT_DIR}/)")
    parser.add_argument("--config", default=None,
                        help="JSON configuration file (default: config/default_config.json)")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Parse ``argv`` and run the menu or a single batch run. Returns the exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if (args.students is None) != (args.halls is None):
        parser.error("--students and --halls must be given together")
    try:
        config = load_default_config(args.config)
    except DataFormatError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_DATA_ERROR

    algorithm = args.algorithm if args.algorithm is not None else DEFAULT_ALGORITHM
    out_dir = args.out if args.out is not None else DEFAULT_OUT_DIR
    if args.students is not None:
        return run_non_interactive(args.students, args.halls, algorithm, out_dir, config)
    return run_menu(config, session=Session(config=config, algorithm=algorithm, out_dir=out_dir))


if __name__ == "__main__":
    sys.exit(main())

"""Run the benchmark harness and write the CSV and SVG plots.

    python scripts/run_benchmarks.py --sizes 50 200 500 1000 --repeats 5

Writes data/results/benchmark_results.csv and SVG plots into output/plots/.
Backtracking is stopped by the node and time limits of the configuration, so
large sizes with many repeats take a while (up to the time limit per run).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.analysis.benchmark import ALGORITHMS, RESULT_COLUMNS, run_benchmarks  # noqa: E402
from src.cli.menu import load_default_config  # noqa: E402
from src.dataio.validator import DataFormatError  # noqa: E402
from src.reporting.csv_export import write_benchmark_csv  # noqa: E402
from src.reporting.svg_plots import save_benchmark_plots  # noqa: E402
from src.reporting.text_chart import render_table  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Benchmark the coloring algorithms.")
    parser.add_argument("--sizes", type=int, nargs="+", default=[50, 200, 500, 1000],
                        help="student counts (default: 50 200 500 1000)")
    parser.add_argument("--repeats", type=int, default=5, help="timed runs per algorithm and size (default 5)")
    parser.add_argument("--seed", type=int, default=None, help="random seed (default: random_seed from the config)")
    parser.add_argument("--courses", type=int, default=12, help="number of courses (default 12)")
    parser.add_argument("--algorithms", nargs="+", choices=ALGORITHMS, default=list(ALGORITHMS),
                        help="algorithms to run (default: all three)")
    parser.add_argument("--config", default=None, help="JSON configuration file")
    parser.add_argument("--csv", default="data/results/benchmark_results.csv", help="result CSV path")
    parser.add_argument("--plots", default="output/plots", help="folder for SVG plots")
    args = parser.parse_args(argv)
    try:
        config = load_default_config(args.config)
    except DataFormatError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    seed = args.seed if args.seed is not None else config["random_seed"]
    try:
        rows = run_benchmarks(args.sizes, args.repeats, seed, config,
                              algorithms=tuple(args.algorithms), n_courses=args.courses)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(render_table(rows, list(RESULT_COLUMNS), float_digits=3))
    write_benchmark_csv(rows, args.csv)
    print(f"\nWrote {args.csv}")
    for path in save_benchmark_plots(rows, args.plots):
        print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

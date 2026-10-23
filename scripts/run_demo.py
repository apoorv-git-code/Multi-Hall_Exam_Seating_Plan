"""Run all three algorithms on the small sample dataset and compare them.

    python scripts/run_demo.py

Uses data/sample/students.csv and data/sample/halls.csv.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.analysis.benchmark import ALGORITHMS, RESULT_COLUMNS, benchmark_dataset  # noqa: E402
from src.cli.menu import load_default_config  # noqa: E402
from src.dataio.parser import load_halls, load_students  # noqa: E402
from src.dataio.validator import DataFormatError  # noqa: E402
from src.graph.conflict_graph import build_conflict_graph  # noqa: E402
from src.graph.graph_metrics import course_clique_lower_bound, graph_summary  # noqa: E402
from src.reporting.text_chart import render_bar_chart, render_table  # noqa: E402


def main() -> int:
    students_path = ROOT / "data" / "sample" / "students.csv"
    halls_path = ROOT / "data" / "sample" / "halls.csv"
    try:
        config = load_default_config()
        students = load_students(str(students_path))
        halls = load_halls(str(halls_path))
    except DataFormatError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    graph = build_conflict_graph(students)
    info = graph_summary(graph)
    print(f"Sample dataset: {len(students)} students, {len(halls)} halls, "
          f"{sum(h.capacity() for h in halls)} usable seats")
    print(f"Conflict graph: {info['n_edges']} edges, density {info['density']:.3f}, "
          f"max degree {info['max_degree']}, lower bound on colors "
          f"{course_clique_lower_bound(students)}, greedy upper bound {info['greedy_upper_bound']}")
    print()

    rows = benchmark_dataset(students, halls, config, ALGORITHMS, repeats=3, graph=graph)
    print(render_table(rows, list(RESULT_COLUMNS), float_digits=3))
    print()
    print(render_bar_chart([(row["algorithm"], row["colors_used"]) for row in rows],
                           width=40, title="Colors used (fewer is better)"))
    print()
    print("Every allocation was checked against the hard constraints (column 'valid').")
    print("Runtime is the mean coloring time over 3 runs; 'completed' tells whether backtracking")
    print("finished its search (so its color count is proven optimal).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Summary report builder.

``build_summary_report`` returns a Markdown document that describes one
allocation run: the dataset, the conflict graph, the coloring run, the
allocation quality, a per-hall table and (optionally) benchmark results.

The report is deterministic: the same inputs give the same text. A timestamp is
included only if the caller passes ``generated_at``.

``reporting`` does not import ``graph`` or ``algorithms``; the caller passes the
graph metrics (``graph.graph_metrics.graph_summary``) and the coloring run
details as plain dicts.
"""

from __future__ import annotations

from pathlib import Path

from src.analysis.benchmark import RESULT_COLUMNS
from src.analysis.metrics import evaluate_allocation
from src.models.allocation import Allocation
from src.models.hall import Hall
from src.models.student import Student
from src.reporting.text_chart import render_table

#: Maximum number of hard-constraint violation messages listed in the report.
MAX_LISTED_VIOLATIONS = 10


def _bullet(label: str, value: object) -> str:
    if isinstance(value, float):
        value = f"{value:.4g}"
    return f"- {label}: {value}"


def build_summary_report(
    students: list[Student],
    halls: list[Hall],
    allocation: Allocation,
    config: dict,
    run_info: dict | None = None,
    graph_info: dict | None = None,
    benchmark_rows: list[dict] | None = None,
    title: str = "Exam Seating Allocation Report",
    generated_at: str | None = None,
) -> str:
    """Return the report as Markdown text.

    Args:
        students: All students.
        halls: All halls.
        allocation: The seating plan to report on.
        config: Configuration (``weights`` and optional ``neighbourhood``).
        run_info: Optional coloring run details. Recognised keys: ``algorithm``,
            ``colors_used``, ``runtime_ms``, ``nodes_explored``, ``completed``.
        graph_info: Optional dict from ``graph_summary`` (keys such as
            ``n_edges``, ``density``, ``max_degree``, ``greedy_upper_bound``).
        benchmark_rows: Optional benchmark rows to include as a table.
        title: Report title.
        generated_at: Optional timestamp text; omitted from the report if None.

    Returns:
        The Markdown text.

    Complexity:
        Time: O(S * c) for the evaluation plus O(rows) for the tables.
        Space: O(V + S).
    """
    quality = evaluate_allocation(allocation, students, halls, config)
    neighbourhood = config.get("neighbourhood", "4")

    lines: list[str] = [f"# {title}", ""]
    if generated_at is not None:
        lines += [f"Generated: {generated_at}", ""]

    # Dataset
    branches: set[str] = set()
    courses: set[str] = set()
    for student in students:
        branches.add(student.branch)
        for course in student.courses:
            courses.add(course)
    total_capacity = 0
    for hall in halls:
        total_capacity += hall.capacity()
    lines += ["## Dataset", ""]
    lines += [
        _bullet("Students", len(students)),
        _bullet("Branches", len(branches)),
        _bullet("Distinct courses", len(courses)),
        _bullet("Halls", len(halls)),
        _bullet("Total usable seats", total_capacity),
        _bullet("Neighbourhood", f"{neighbourhood}-direction"),
        "",
    ]

    # Conflict graph
    if graph_info is not None:
        lines += ["## Conflict graph", ""]
        labels = (
            ("n_edges", "Conflict edges"),
            ("density", "Density"),
            ("max_degree", "Maximum degree"),
            ("min_degree", "Minimum degree"),
            ("average_degree", "Average degree"),
            ("isolated", "Students with no conflicts"),
            ("components", "Connected components"),
            ("greedy_upper_bound", "Greedy upper bound on colors (max degree + 1)"),
            ("clique_lower_bound", "Lower bound on colors (largest course)"),
        )
        for key, label in labels:
            if key in graph_info:
                lines.append(_bullet(label, graph_info[key]))
        lines.append("")

    # Coloring run
    if run_info is not None:
        lines += ["## Coloring run (Phase 1)", ""]
        labels = (
            ("algorithm", "Algorithm"),
            ("colors_used", "Colors used"),
            ("runtime_ms", "Runtime (ms)"),
            ("nodes_explored", "Search nodes explored"),
            ("completed", "Search completed within limits"),
        )
        for key, label in labels:
            if key in run_info:
                value = run_info[key]
                if isinstance(value, bool):
                    value = "yes" if value else "no"
                lines.append(_bullet(label, value))
        lines.append("")

    # Allocation quality
    lines += ["## Allocation (Phase 2)", ""]
    lines.append(_bullet("Hard constraints", "satisfied" if quality["valid"] else "VIOLATED"))
    lines.append(_bullet("Students seated", f"{quality['seated']} of {len(students)}"))
    lines.append(_bullet("Hall utilisation (seated / total capacity)", quality["hall_utilisation"]))
    lines.append(_bullet("Halls in use", quality["used_halls"]))
    lines.append(_bullet("Buffer seats (empty, next to a student)", quality["buffer_seats"]))
    lines.append(_bullet("Wasted seats (empty, no student next to them)", quality["wasted_seats"]))
    lines.append(_bullet("Soft score (lower is better)", quality["soft_score"]))
    lines.append("")
    lines += ["Soft score components:", ""]
    lines += [
        _bullet("Neighbour pairs from the same branch", quality["same_branch_pairs"]),
        _bullet("Neighbour pairs with consecutive roll numbers", quality["consecutive_roll_pairs"]),
        _bullet("Course-sharing pairs two seats apart", quality["distance_two_pairs"]),
        "",
    ]
    if not quality["valid"]:
        lines += ["Violations:", ""]
        for message in quality["violations"][:MAX_LISTED_VIOLATIONS]:
            lines.append(f"- {message}")
        hidden = len(quality["violations"]) - MAX_LISTED_VIOLATIONS
        if hidden > 0:
            lines.append(f"- ... and {hidden} more")
        lines.append("")

    # Per-hall table
    seated_per_hall: dict[str, int] = {}
    for hall_id, _row, _col in allocation.seats.values():
        seated_per_hall[hall_id] = seated_per_hall.get(hall_id, 0) + 1
    hall_rows: list[dict] = []
    for hall in halls:
        seated = seated_per_hall.get(hall.hall_id, 0)
        capacity = hall.capacity()
        hall_rows.append({
            "hall": hall.hall_id,
            "size": f"{hall.rows}x{hall.cols}",
            "blocked": len(hall.blocked),
            "capacity": capacity,
            "seated": seated,
            "utilisation": (seated / capacity) if capacity > 0 else 0.0,
        })
    lines += ["## Halls", "", "```"]
    lines.append(render_table(
        hall_rows, ["hall", "size", "blocked", "capacity", "seated", "utilisation"], float_digits=3))
    lines += ["```", ""]

    # Benchmarks
    if benchmark_rows:
        lines += ["## Benchmark results", "", "```"]
        columns: list[str] = list(RESULT_COLUMNS)
        lines.append(render_table(benchmark_rows, columns, float_digits=3))
        lines += ["```", ""]

    # Configuration
    weights = config.get("weights", {})
    lines += ["## Soft-constraint weights", ""]
    for key in weights:
        lines.append(_bullet(key, weights[key]))
    lines.append("")
    return "\n".join(lines)


def write_report(path: str, text: str) -> None:
    """Write report text to ``path`` (UTF-8); parent folders are created.

    Time: O(len(text)). Space: O(1) extra.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")

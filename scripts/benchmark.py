"""Benchmark harness: run algorithms on datasets and produce result rows.

Each row follows ``benchmark_results.csv`` (README section 4):
``algorithm, n_students, n_edges, colors_used, runtime_ms, nodes_explored,
completed, hall_utilisation, soft_score, valid``.

What is measured:
    * ``runtime_ms`` is the **coloring** runtime, averaged over ``repeats`` runs
      on the same graph. Graph building and seat mapping are not included.
    * ``colors_used``, ``nodes_explored`` and the allocation come from the
      **first** repeat. For Greedy and Welsh-Powell, and for backtracking stopped
      by the node limit, every repeat gives the same result. A backtracking run
      stopped by the time limit can differ between repeats.
    * ``completed`` is True only if **every** repeat completed.
    * If Phase 2 cannot place all students (``InfeasibleAllocationError``) the
      row has ``valid = False``, ``hall_utilisation = 0.0`` and
      ``soft_score = None`` (written as an empty CSV cell).

This module does no file output or printing; ``reporting`` writes the rows.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.algorithms.backtracking import color_backtracking
from src.algorithms.coloring_result import ColoringResult
from src.algorithms.greedy_first_fit import color_greedy_first_fit
from src.algorithms.welsh_powell import color_welsh_powell
from src.analysis.metrics import evaluate_allocation, mean
from src.dataio.generator import generate_halls, generate_students
from src.graph.conflict_graph import ConflictGraph, build_conflict_graph
from src.graph.graph_metrics import graph_summary
from src.grid.seat_mapper import InfeasibleAllocationError, map_colors_to_seats
from src.models.allocation import Allocation
from src.models.hall import Hall
from src.models.student import Student

#: Valid algorithm names, in the order they appear in result tables.
ALGORITHMS: tuple[str, ...] = ("greedy", "welsh_powell", "backtracking")


@dataclass
class PipelineRun:
    """Outcome of one end-to-end allocation run."""

    algorithm: str
    coloring: ColoringResult
    allocation: Allocation | None
    quality: dict | None
    graph_info: dict
    error: str | None = None

    def run_info(self) -> dict:
        return {
            "algorithm": self.algorithm,
            "colors_used": self.coloring.num_colors,
            "runtime_ms": self.coloring.runtime_ms,
            "nodes_explored": self.coloring.nodes_explored,
            "completed": self.coloring.completed,
        }


def run_pipeline(
    students: list[Student],
    halls: list[Hall],
    algorithm: str,
    config: dict,
    graph: ConflictGraph | None = None,
) -> PipelineRun:
    """Run the two-phase pipeline: conflict graph -> coloring -> seat mapping."""
    if graph is None:
        graph = build_conflict_graph(students)
    info = graph_summary(graph)
    coloring = run_coloring(algorithm, graph, config)
    allocation: Allocation | None = None
    quality: dict | None = None
    error: str | None = None
    try:
        allocation = map_colors_to_seats(students, graph, coloring, halls, config)
        quality = evaluate_allocation(allocation, students, halls, config)
    except InfeasibleAllocationError as exc:
        error = str(exc)
    return PipelineRun(
        algorithm=algorithm,
        coloring=coloring,
        allocation=allocation,
        quality=quality,
        graph_info=info,
        error=error,
    )


#: Column order of ``benchmark_results.csv``.
RESULT_COLUMNS: tuple[str, ...] = (
    "algorithm",
    "n_students",
    "n_edges",
    "colors_used",
    "runtime_ms",
    "nodes_explored",
    "completed",
    "hall_utilisation",
    "soft_score",
    "valid",
)


def run_coloring(algorithm: str, graph: ConflictGraph, config: dict) -> ColoringResult:
    """Run one coloring algorithm by name.

    Args:
        algorithm: One of ``ALGORITHMS``.
        graph: The conflict graph.
        config: Configuration; ``backtracking.node_limit`` and
            ``backtracking.time_limit_seconds`` are used for backtracking.

    Raises:
        ValueError: If ``algorithm`` is not a valid name.

    Time: that of the chosen algorithm. Space: that of the chosen algorithm.
    """
    if algorithm == "greedy":
        return color_greedy_first_fit(graph)
    if algorithm == "welsh_powell":
        return color_welsh_powell(graph)
    if algorithm == "backtracking":
        limits = config["backtracking"]
        return color_backtracking(graph, limits["node_limit"], limits["time_limit_seconds"])
    raise ValueError(f"unknown algorithm {algorithm!r}, expected one of {list(ALGORITHMS)}")


def benchmark_dataset(
    students: list[Student],
    halls: list[Hall],
    config: dict,
    algorithms: tuple[str, ...] = ALGORITHMS,
    repeats: int = 1,
    with_breakdown: bool = False,
    extra: dict | None = None,
    graph: ConflictGraph | None = None,
) -> list[dict]:
    """Benchmark the given algorithms on one dataset.

    Args:
        students: The students.
        halls: The halls.
        config: Full configuration (weights, neighbourhood, backtracking limits).
        algorithms: Algorithm names to run, in order.
        repeats: Number of timed coloring runs per algorithm (at least 1).
        with_breakdown: If True, each row also has ``buffer_seats``,
            ``wasted_seats`` and ``used_halls`` (for experiment E5).
        extra: Extra key/value pairs appended to every row (for example the
            experiment variable). Keys must not clash with ``RESULT_COLUMNS``.
        graph: A prebuilt conflict graph of ``students``; built if omitted.

    Returns:
        One row (dict) per algorithm, keys in ``RESULT_COLUMNS`` order.

    Raises:
        ValueError: If ``repeats < 1``, an algorithm name is invalid, or
            ``extra`` clashes with a result column.

    Complexity:
        Time: graph build (once) + ``repeats`` x coloring + one seat mapping
        and evaluation per algorithm.
        Space: O(V + E) for the graph plus one allocation.
    """
    if repeats < 1:
        raise ValueError("repeats must be >= 1")
    for name in algorithms:
        if name not in ALGORITHMS:
            raise ValueError(f"unknown algorithm {name!r}, expected one of {list(ALGORITHMS)}")
    if extra is not None:
        for key in extra:
            if key in RESULT_COLUMNS:
                raise ValueError(f"extra key {key!r} clashes with a result column")

    if graph is None:
        graph = build_conflict_graph(students)
    n_edges = graph.num_edges()

    rows: list[dict] = []
    for name in algorithms:
        runtimes: list[float] = []
        first: ColoringResult | None = None
        all_completed = True
        for _ in range(repeats):
            result = run_coloring(name, graph, config)
            runtimes.append(result.runtime_ms)
            if first is None:
                first = result
            if not result.completed:
                all_completed = False
        assert first is not None

        row: dict = {
            "algorithm": name,
            "n_students": len(students),
            "n_edges": n_edges,
            "colors_used": first.num_colors,
            "runtime_ms": mean(runtimes),
            "nodes_explored": first.nodes_explored,
            "completed": all_completed,
        }

        try:
            allocation = map_colors_to_seats(students, graph, first, halls, config)
        except InfeasibleAllocationError:
            row["hall_utilisation"] = 0.0
            row["soft_score"] = None
            row["valid"] = False
            if with_breakdown:
                row["buffer_seats"] = 0
                row["wasted_seats"] = 0
                row["used_halls"] = 0
        else:
            quality = evaluate_allocation(allocation, students, halls, config)
            row["hall_utilisation"] = quality["hall_utilisation"]
            row["soft_score"] = quality["soft_score"]
            row["valid"] = quality["valid"]
            if with_breakdown:
                row["buffer_seats"] = quality["buffer_seats"]
                row["wasted_seats"] = quality["wasted_seats"]
                row["used_halls"] = quality["used_halls"]

        if extra is not None:
            row.update(extra)
        rows.append(row)
    return rows


def run_benchmarks(
    sizes: list[int],
    repeats: int,
    seed: int,
    config: dict,
    algorithms: tuple[str, ...] = ALGORITHMS,
    n_courses: int = 12,
    min_courses: int = 3,
    max_courses: int = 5,
    students_per_hall: int = 100,
) -> list[dict]:
    """Generate one seeded dataset per size and benchmark every algorithm on it.

    For size ``V`` the dataset has ``V`` students and
    ``ceil(V / students_per_hall)`` halls (at least 1). The same ``seed`` is used
    for every size, so results are reproducible.

    Args:
        sizes: Student counts, for example ``[50, 200, 500, 1000]``.
        repeats: Timed coloring runs per algorithm and size.
        seed: Random seed for the generator.
        config: Full configuration.
        algorithms: Algorithm names to run.
        n_courses: Number of distinct courses.
        min_courses: Fewest courses per student.
        max_courses: Most courses per student.
        students_per_hall: Used to choose the number of halls.

    Returns:
        The concatenated rows, ordered by size then algorithm.

    Raises:
        ValueError: If ``sizes`` is empty, a size is below 1, or
            ``students_per_hall < 1`` (other checks come from the callees).

    Time: sum over sizes of generation + ``benchmark_dataset``. Space: O(V + E).
    """
    if len(sizes) == 0:
        raise ValueError("sizes must not be empty")
    if students_per_hall < 1:
        raise ValueError("students_per_hall must be >= 1")
    rows: list[dict] = []
    for size in sizes:
        if size < 1:
            raise ValueError("every size must be >= 1")
        students = generate_students(size, n_courses, seed, min_courses, max_courses)
        n_halls = max(1, -(-size // students_per_hall))
        halls = generate_halls(n_halls, size, seed)
        rows.extend(
            benchmark_dataset(students, halls, config, algorithms, repeats)
        )
    return rows

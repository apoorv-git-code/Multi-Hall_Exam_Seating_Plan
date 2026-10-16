"""Welsh-Powell graph coloring.

Sort the vertices by degree in descending order, then apply Greedy First-Fit in
that order. High-degree vertices are colored first, while many colors are still
free, which usually uses fewer colors than plain first-fit.

Guarantee: at most ``Delta + 1`` colors. A tighter bound is
``max over i of min(d_i + 1, i)`` where ``d_1 >= d_2 >= ...`` are the sorted
degrees. Not optimal in general.

Ties in degree keep ascending vertex order (the custom merge sort is stable),
so the result is deterministic.
"""

from __future__ import annotations

import time

from src.algorithms.coloring_result import ColoringResult
from src.algorithms.greedy_first_fit import count_colors, greedy_color_in_order
from src.graph.conflict_graph import ConflictGraph
from src.structures.sorting import merge_sort


def color_welsh_powell(graph: ConflictGraph) -> ColoringResult:
    """Color ``graph`` with the Welsh-Powell heuristic.

    Returns:
        A ``ColoringResult`` with ``nodes_explored = 0`` and ``completed = True``.
        ``runtime_ms`` includes the degree sort.

    Complexity:
        Time: O(V log V + E): the custom merge sort costs O(V log V), the
        first-fit pass costs O(V + E).
        Space: O(V) extra (graph storage is O(V + E)).
    """
    start = time.perf_counter()
    adj = graph.adj
    order = merge_sort(
        list(range(graph.n)),
        key=lambda v: len(adj[v]),
        reverse=True,
    )
    colors = greedy_color_in_order(graph, order)
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    return ColoringResult(
        colors=colors,
        num_colors=count_colors(colors),
        runtime_ms=elapsed_ms,
        nodes_explored=0,
        completed=True,
    )

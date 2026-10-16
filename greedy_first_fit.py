"""Greedy First-Fit graph coloring.

Process the vertices in a given order. Give each vertex the smallest color that
none of its already-colored neighbours uses.

Guarantee: never more than ``Delta + 1`` colors, because a vertex has at most
``Delta`` neighbours and so at most ``Delta`` forbidden colors. The result
depends on the vertex order and is not optimal in general.
"""

from __future__ import annotations

import time
from typing import Optional

from src.algorithms.coloring_result import ColoringResult
from src.graph.conflict_graph import ConflictGraph


def greedy_color_in_order(graph: ConflictGraph, order: list[int]) -> list[int]:
    """Core first-fit loop. Assumes ``order`` is a valid vertex permutation.

    Shared by ``color_greedy_first_fit`` and ``color_welsh_powell``. It does no
    validation and no timing.

    Complexity:
        Time: O(V + E). For each vertex it scans its neighbours once to mark
        forbidden colors, then scans colors upward from 0 for at most
        deg(v) + 1 steps.
        Space: O(V) for the colors list and the marker array.
    """
    n = graph.n
    colors = [-1] * n
    # marker[c] == v means color c is forbidden for vertex v. Reusing the
    # vertex id as a stamp avoids clearing the array between vertices.
    marker = [-1] * (n + 1)
    for v in order:
        for u in graph.adj[v]:
            cu = colors[u]
            if cu >= 0:
                marker[cu] = v
        color = 0
        while marker[color] == v:
            color += 1
        colors[v] = color
    return colors


def count_colors(colors: list[int]) -> int:
    """Return ``max(colors) + 1`` (0 for an empty list).

    Time: O(V). Space: O(1).
    """
    best = -1
    for c in colors:
        if c > best:
            best = c
    return best + 1


def color_greedy_first_fit(
    graph: ConflictGraph, order: Optional[list[int]] = None
) -> ColoringResult:
    """Color ``graph`` with Greedy First-Fit.

    Args:
        graph: The conflict graph.
        order: Vertex processing order. ``None`` means ``0, 1, ..., n - 1``.
            If given, it must contain every vertex exactly once.

    Returns:
        A ``ColoringResult`` with ``nodes_explored = 0`` and ``completed = True``.

    Raises:
        ValueError: If ``order`` is not a permutation of the vertices.

    Complexity:
        Time: O(V + E) (the order check adds O(V)).
        Space: O(V) extra (graph storage is O(V + E)).
    """
    start = time.perf_counter()
    n = graph.n
    if order is None:
        order = list(range(n))
    else:
        if len(order) != n:
            raise ValueError("order must list every vertex exactly once")
        seen = [False] * n
        for v in order:
            if v < 0 or v >= n or seen[v]:
                raise ValueError("order must list every vertex exactly once")
            seen[v] = True

    colors = greedy_color_in_order(graph, order)
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    return ColoringResult(
        colors=colors,
        num_colors=count_colors(colors),
        runtime_ms=elapsed_ms,
        nodes_explored=0,
        completed=True,
    )

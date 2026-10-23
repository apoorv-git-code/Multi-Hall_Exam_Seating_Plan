"""Shared result type and helpers for all coloring algorithms.

Every coloring algorithm returns a ``ColoringResult`` so that the benchmark
harness, the seat mapper and the reports can treat the algorithms uniformly.
Colors are integers ``0, 1, 2, ...`` indexed by vertex.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.graph.conflict_graph import ConflictGraph


@dataclass
class ColoringResult:
    """Outcome of one coloring run.

    Attributes:
        colors: ``colors[v]`` is the color of vertex ``v``.
        num_colors: Number of distinct colors used (``max(colors) + 1``, or 0
            for an empty graph).
        runtime_ms: Wall-clock time of the run in milliseconds.
        nodes_explored: Search nodes visited (0 for non-backtracking runs).
        completed: False if a node or time limit stopped the search early.
    """

    colors: list[int]
    num_colors: int
    runtime_ms: float
    nodes_explored: int
    completed: bool


def verify_coloring(graph: ConflictGraph, colors: list[int]) -> bool:
    """Return True if ``colors`` is a proper, complete coloring of ``graph``.

    A coloring is proper when it has one non-negative color per vertex and no
    edge joins two vertices of the same color.

    Time: O(V + E). Space: O(1).
    """
    if len(colors) != graph.n:
        return False
    for v in range(graph.n):
        if colors[v] < 0:
            return False
    for u in range(graph.n):
        for v in graph.adj[u]:
            if colors[u] == colors[v]:
                return False
    return True


def color_classes(colors: list[int], num_colors: int) -> list[list[int]]:
    """Group vertices by color.

    Returns ``classes`` where ``classes[k]`` lists the vertices of color ``k``
    in ascending vertex order.

    Time: O(V + num_colors). Space: O(V + num_colors).
    """
    classes: list[list[int]] = [[] for _ in range(num_colors)]
    for v in range(len(colors)):
        classes[colors[v]].append(v)
    return classes

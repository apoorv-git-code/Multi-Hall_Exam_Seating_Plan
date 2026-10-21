"""Backtracking graph coloring with pruning and safety limits.

The search looks for a coloring with the fewest colors. It is exact when it
finishes, and it never returns anything worse than Welsh-Powell, because the
Welsh-Powell coloring is the first "best known" solution.

Search model (depth-first, one vertex per level, vertices in a fixed order):
    * A search node is one tentative assignment of a color to a vertex.
      ``nodes_explored`` counts these.
    * Level ``d`` colors vertex ``order[d]``. Colors are tried in ascending order.

Pruning techniques (README section 3.4):
    1. Consistency check: a color is rejected if an already-colored neighbour
       has it (tracked with one bitmask of forbidden colors per level).
    2. Symmetry breaking: a vertex may use a brand-new color only if it is
       exactly ``max color used so far + 1``. The first vertex therefore always
       gets color 0, and permutations of the same partition are never revisited.
    3. Vertex ordering: a greedy clique is placed first, then the remaining
       vertices follow in descending degree (largest-first, custom merge sort).
       Clique vertices are pairwise adjacent, so they are forced into distinct
       colors immediately, and high-degree vertices fail early.
    4. Best-known cutoff: a branch is abandoned as soon as its colors used
       would reach the best complete coloring found so far.
    5. Safety limits: a node limit and a time limit. A run stopped by a limit
       returns the best coloring found with ``completed = False``.

Early exit: if the best coloring uses as many colors as the greedy clique found
(a lower bound on the chromatic number), it is optimal and the search stops with
``completed = True``.

The search is iterative (explicit level arrays), so graphs with thousands of
vertices do not hit Python's recursion limit.
"""

from __future__ import annotations

import time

from src.algorithms.coloring_result import ColoringResult
from src.algorithms.welsh_powell import color_welsh_powell
from src.graph.conflict_graph import ConflictGraph
from src.structures.sorting import merge_sort

# The clock is read once per this many nodes to keep timing overhead small.
_TIME_CHECK_INTERVAL = 64


def _greedy_clique(graph: ConflictGraph, by_degree: list[int]) -> list[int]:
    """Build a clique greedily, scanning vertices in the given order.

    A vertex joins the clique if it is adjacent to every vertex already in it.
    The clique size is a lower bound on the chromatic number.

    Time: O(V * k * log Delta) for a clique of size k. Space: O(k).
    """
    clique: list[int] = []
    for v in by_degree:
        joins = True
        for member in clique:
            if not graph.has_edge(v, member):
                joins = False
                break
        if joins:
            clique.append(v)
    return clique


def color_backtracking(
    graph: ConflictGraph, node_limit: int, time_limit_seconds: float
) -> ColoringResult:
    """Find a minimum coloring by backtracking, within node and time limits.

    Args:
        graph: The conflict graph.
        node_limit: Maximum number of search nodes (color assignments) to
            explore. Must be at least 1.
        time_limit_seconds: Maximum wall-clock time for the whole call, in
            seconds. Must be greater than 0.

    Returns:
        A ``ColoringResult``. ``completed`` is True when the search proved the
        result optimal (exhausted the search space or matched the clique lower
        bound) and False when a limit stopped it. ``colors`` is always a proper
        coloring and never uses more colors than Welsh-Powell.

    Raises:
        ValueError: If ``node_limit < 1`` or ``time_limit_seconds <= 0``.

    Complexity:
        Time: O(m^V * Delta) in the worst case for m colors (exponential),
        because each node costs O(Delta) to build its forbidden-color mask.
        Pruning improves practical speed but not this bound. The initial
        Welsh-Powell pass costs O(V log V + E) and the clique/order setup
        O(V * k * log Delta).
        Space: O(V) for the per-level arrays (graph storage is O(V + E)).
    """
    if node_limit < 1:
        raise ValueError("node_limit must be >= 1")
    if time_limit_seconds <= 0:
        raise ValueError("time_limit_seconds must be > 0")

    start = time.perf_counter()
    n = graph.n

    # Initial upper bound: the Welsh-Powell coloring is a valid first answer.
    initial = color_welsh_powell(graph)
    best_colors = list(initial.colors)
    best_num = initial.num_colors

    if n == 0:
        return ColoringResult([], 0, (time.perf_counter() - start) * 1000.0, 0, True)

    adj = graph.adj
    by_degree = merge_sort(list(range(n)), key=lambda v: len(adj[v]), reverse=True)
    clique = _greedy_clique(graph, by_degree)
    lower_bound = len(clique)

    nodes = 0
    completed = True

    if best_num > lower_bound:
        # Vertex order: clique first, then everything else by descending degree.
        in_clique = [False] * n
        for v in clique:
            in_clique[v] = True
        order = list(clique)
        for v in by_degree:
            if not in_clique[v]:
                order.append(v)

        colors = [-1] * n            # current partial coloring, by vertex
        forbidden = [0] * n          # forbidden[d]: bitmask of colors blocked at level d
        next_color = [0] * n         # next_color[d]: next color to try at level d
        max_before = [-1] * n        # max_before[d]: highest color used at levels < d
        deadline = start + time_limit_seconds

        d = 0
        mask = 0
        for u in adj[order[0]]:
            if colors[u] >= 0:
                mask |= 1 << colors[u]
        forbidden[0] = mask

        while d >= 0:
            v = order[d]

            # Best-known cutoff: this prefix already uses as many colors as best.
            if max_before[d] + 1 >= best_num:
                colors[v] = -1
                d -= 1
                continue

            # Highest color index worth trying: an existing color, or exactly
            # one new color (symmetry breaking), and strictly below best_num - 1.
            limit = max_before[d] + 1
            if best_num - 2 < limit:
                limit = best_num - 2
            color = next_color[d]
            mask = forbidden[d]
            while color <= limit and (mask >> color) & 1:
                color += 1

            if color > limit:
                colors[v] = -1
                d -= 1
                continue

            # About to explore a node: enforce the limits first.
            if nodes >= node_limit:
                completed = False
                break
            if nodes % _TIME_CHECK_INTERVAL == 0 and time.perf_counter() >= deadline:
                completed = False
                break

            nodes += 1
            colors[v] = color
            next_color[d] = color + 1
            highest = max_before[d] if max_before[d] > color else color

            if d == n - 1:
                # Complete coloring that is strictly better than the best known.
                best_colors = list(colors)
                best_num = highest + 1
                if best_num <= lower_bound:
                    break  # matches the clique lower bound: proven optimal
                continue   # retry this level; the tighter bound prunes siblings

            d += 1
            max_before[d] = highest
            next_color[d] = 0
            nxt = order[d]
            mask = 0
            for u in adj[nxt]:
                cu = colors[u]
                if cu >= 0:
                    mask |= 1 << cu
            forbidden[d] = mask

    elapsed_ms = (time.perf_counter() - start) * 1000.0
    return ColoringResult(
        colors=best_colors,
        num_colors=best_num,
        runtime_ms=elapsed_ms,
        nodes_explored=nodes,
        completed=completed,
    )

"""Degree and density metrics for a conflict graph.

These numbers feed the complexity discussion (``Delta + 1`` color bound) and
the experiments (edge count, density, lower bound on colors).

All functions are read-only and never print.
"""

from __future__ import annotations

from src.graph.conflict_graph import ConflictGraph
from src.models.student import Student


def degrees(graph: ConflictGraph) -> list[int]:
    """Return the degree of every vertex, indexed by vertex.

    Time: O(V). Space: O(V).
    """
    return [len(neighbours) for neighbours in graph.adj]


def max_degree(graph: ConflictGraph) -> int:
    """Return ``Delta``, the maximum degree (0 for an empty graph).

    Time: O(V). Space: O(1).
    """
    best = 0
    for neighbours in graph.adj:
        if len(neighbours) > best:
            best = len(neighbours)
    return best


def min_degree(graph: ConflictGraph) -> int:
    """Return the minimum degree (0 for an empty graph).

    Time: O(V). Space: O(1).
    """
    if graph.n == 0:
        return 0
    best = len(graph.adj[0])
    for neighbours in graph.adj:
        if len(neighbours) < best:
            best = len(neighbours)
    return best


def average_degree(graph: ConflictGraph) -> float:
    """Return ``2E / V`` (0.0 for an empty graph).

    Time: O(V). Space: O(1).
    """
    if graph.n == 0:
        return 0.0
    total = 0
    for neighbours in graph.adj:
        total += len(neighbours)
    return total / graph.n


def edge_count(graph: ConflictGraph) -> int:
    """Return the number of undirected edges ``E``.

    Time: O(V). Space: O(1).
    """
    return graph.num_edges()


def density(graph: ConflictGraph) -> float:
    """Return ``E / (V (V - 1) / 2)``, a value in [0, 1].

    A graph with fewer than two vertices has density 0.0.

    Time: O(V). Space: O(1).
    """
    if graph.n < 2:
        return 0.0
    possible = graph.n * (graph.n - 1) // 2
    return graph.num_edges() / possible


def isolated_count(graph: ConflictGraph) -> int:
    """Return how many vertices have no conflicts (degree 0).

    Time: O(V). Space: O(1).
    """
    count = 0
    for neighbours in graph.adj:
        if len(neighbours) == 0:
            count += 1
    return count


def degree_histogram(graph: ConflictGraph) -> list[int]:
    """Return ``counts`` where ``counts[d]`` is the number of vertices of degree ``d``.

    The list has length ``Delta + 1`` (length 1 for an empty graph).

    Time: O(V). Space: O(Delta).
    """
    counts = [0] * (max_degree(graph) + 1)
    for neighbours in graph.adj:
        counts[len(neighbours)] += 1
    return counts


def greedy_color_upper_bound(graph: ConflictGraph) -> int:
    """Return ``Delta + 1``, the color count any greedy ordering never exceeds.

    An empty graph returns 0.

    Time: O(V). Space: O(1).
    """
    if graph.n == 0:
        return 0
    return max_degree(graph) + 1


def course_clique_lower_bound(students: list[Student]) -> int:
    """Return the largest course enrolment, a lower bound on the chromatic number.

    All students of one course are pairwise adjacent (a clique), so they need
    pairwise different colors. Returns 0 for an empty student list.

    Time: O(V * c). Space: O(number of courses).
    """
    enrolment: dict[str, int] = {}
    best = 0
    for student in students:
        for course in student.courses:
            count = enrolment.get(course, 0) + 1
            enrolment[course] = count
            if count > best:
                best = count
    return best


def is_symmetric(graph: ConflictGraph) -> bool:
    """Return True if every edge ``u -> v`` is matched by ``v -> u``.

    Time: O(E log Delta). Space: O(1).
    """
    for u in range(graph.n):
        for v in graph.adj[u]:
            if not graph.has_edge(v, u):
                return False
    return True


def has_self_loop(graph: ConflictGraph) -> bool:
    """Return True if any vertex lists itself as a neighbour.

    Time: O(E). Space: O(1).
    """
    for u in range(graph.n):
        for v in graph.adj[u]:
            if v == u:
                return True
    return False


def connected_components_count(graph: ConflictGraph) -> int:
    """Return the number of connected components (iterative depth-first search).

    Time: O(V + E). Space: O(V).
    """
    visited = [False] * graph.n
    components = 0
    for start in range(graph.n):
        if visited[start]:
            continue
        components += 1
        visited[start] = True
        stack = [start]
        while stack:
            u = stack.pop()
            for v in graph.adj[u]:
                if not visited[v]:
                    visited[v] = True
                    stack.append(v)
    return components


def graph_summary(graph: ConflictGraph) -> dict:
    """Return the main metrics as a dictionary for reports and benchmarks.

    Keys: ``n_vertices``, ``n_edges``, ``max_degree``, ``min_degree``,
    ``average_degree``, ``density``, ``isolated``, ``components``,
    ``greedy_upper_bound``.

    Time: O(V + E). Space: O(1) beyond the DFS stack.
    """
    return {
        "n_vertices": graph.n,
        "n_edges": graph.num_edges(),
        "max_degree": max_degree(graph),
        "min_degree": min_degree(graph),
        "average_degree": average_degree(graph),
        "density": density(graph),
        "isolated": isolated_count(graph),
        "components": connected_components_count(graph),
        "greedy_upper_bound": greedy_color_upper_bound(graph),
    }

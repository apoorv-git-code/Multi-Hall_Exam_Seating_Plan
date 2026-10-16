"""Conflict graph construction.

Each student is a vertex. Two students are joined by an edge when they share at
least one course. A proper coloring of this graph partitions students into
groups whose members can safely sit next to each other.

Vertex ``i`` is the student at position ``i`` of the input list, so vertex
order equals student order. Adjacency lists are sorted ascending and contain no
duplicates and no self-loops, which makes every run deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.models.student import Student
from src.structures.sorting import merge_sort


@dataclass
class ConflictGraph:
    """Undirected simple graph stored as adjacency lists.

    Attributes:
        n: Number of vertices.
        adj: ``adj[v]`` is the ascending list of neighbours of vertex ``v``.
        sap_ids: ``sap_ids[v]`` is the SAP ID of the student at vertex ``v``.
    """

    n: int
    adj: list[list[int]]
    sap_ids: list[str]

    def degree(self, v: int) -> int:
        """Return the number of neighbours of ``v``.

        Time: O(1). Space: O(1).
        """
        return len(self.adj[v])

    def num_edges(self) -> int:
        """Return the number of undirected edges ``E``.

        Time: O(V). Space: O(1).
        """
        total = 0
        for neighbours in self.adj:
            total += len(neighbours)
        return total // 2

    def has_edge(self, u: int, v: int) -> bool:
        """Return True if ``u`` and ``v`` are adjacent (binary search).

        Relies on the sorted adjacency lists produced by
        ``build_conflict_graph``.

        Time: O(log deg(u)). Space: O(1).
        """
        neighbours = self.adj[u]
        low = 0
        high = len(neighbours) - 1
        while low <= high:
            mid = (low + high) // 2
            value = neighbours[mid]
            if value == v:
                return True
            if value < v:
                low = mid + 1
            else:
                high = mid - 1
        return False


def build_conflict_graph(students: list[Student]) -> ConflictGraph:
    """Build the conflict graph of a student list.

    Students are grouped by course, then every pair inside a group is
    connected. Because each course group is a clique, the cost depends on the
    course sizes ``n_k``.

    Args:
        students: Students with unique SAP IDs (validated by ``dataio``).

    Returns:
        A ``ConflictGraph`` where vertex ``i`` is ``students[i]``.

    Raises:
        ValueError: If two students share a SAP ID.

    Complexity:
        Time: O(sum of n_k^2) over courses, at most O(V^2), plus
        O(E log Delta) for sorting adjacency lists with merge sort.
        Space: O(V + E).
    """
    n = len(students)
    sap_ids = [student.sap_id for student in students]
    if len(set(sap_ids)) != n:
        raise ValueError("students must have unique sap_id values")

    # Group vertex indices by course (each list is already in index order).
    members_by_course: dict[str, list[int]] = {}
    for index, student in enumerate(students):
        for course in student.courses:
            if course in members_by_course:
                members_by_course[course].append(index)
            else:
                members_by_course[course] = [index]

    # Every member of a course neighbours every other member of that course.
    neighbour_sets: list[set[int]] = [set() for _ in range(n)]
    for members in members_by_course.values():
        for u in members:
            neighbour_sets[u].update(members)
    for u in range(n):
        neighbour_sets[u].discard(u)  # remove the self-loops added above

    adj = [merge_sort(list(neighbour_sets[u])) for u in range(n)]
    return ConflictGraph(n=n, adj=adj, sap_ids=sap_ids)

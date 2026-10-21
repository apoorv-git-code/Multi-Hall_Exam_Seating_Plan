"""Phase 2: map colored students onto hall seats.

Strategy (full description in docs/DESIGN.md):

    1. Seats of all halls form one visiting sequence: halls in input order,
       usable seats of each hall in snake order. Seating stops when every
       student is placed, so later seats and halls stay empty.
    2. A depth-first search walks the sequence, one seat per level. At each seat
       it collects up to ``CANDIDATES_PER_SEAT`` students that conflict with no
       already-seated neighbour. Candidates are taken from the color class of the
       previously seated student first (so color groups stay together), then from
       other classes in ascending color order. Candidates are ordered by the
       soft-constraint penalty they would add (lowest first).
    3. If a seat has no compatible student it is left empty as a **buffer**.
       Leaving a seat empty is allowed only while enough seats remain for the
       unseated students (hard constraint H5).
    4. If the search later runs out of seats, it backtracks locally: the most
       recent choices are undone and their next candidates tried. The number of
       tried options is capped (``S + backtracking.node_limit``). If the cap is
       reached, or the whole search space is exhausted,
       ``InfeasibleAllocationError`` is raised.

Because every placement is checked against the conflict graph before it is made,
the result never violates H4. A final call to ``validate_allocation`` confirms
all hard constraints.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.grid.constraints import validate_allocation
from src.grid.hall_grid import get_distance_two_seats, get_neighbors, snake_order
from src.grid.scoring import adjacent_pair_penalty, distance_two_pair_penalty
from src.graph.conflict_graph import ConflictGraph
from src.models.allocation import Allocation
from src.models.hall import Hall
from src.models.student import Student
from src.structures.sorting import merge_sort

if TYPE_CHECKING:  # type only: grid does not depend on algorithms at run time
    from src.algorithms.coloring_result import ColoringResult

#: Maximum number of compatible students considered at one seat.
CANDIDATES_PER_SEAT = 8


class InfeasibleAllocationError(Exception):
    """Raised when no valid allocation could be built (capacity or search limit)."""


def map_colors_to_seats(
    students: list[Student],
    graph: ConflictGraph,
    result: "ColoringResult",
    halls: list[Hall],
    config: dict,
) -> Allocation:
    """Place every student on a seat so that no neighbours share a course.

    Args:
        students: Students; vertex ``i`` of ``graph`` is ``students[i]``.
        graph: The conflict graph of ``students``.
        result: Phase 1 coloring of ``graph`` (any algorithm).
        halls: Available halls, used in the given order.
        config: Configuration dict. Used keys: ``weights`` (soft penalties),
            ``neighbourhood`` (default ``"4"``), ``backtracking.node_limit``
            (repair budget).

    Returns:
        A valid ``Allocation``. ``colors`` holds each student's Phase 1 color.

    Raises:
        ValueError: If inputs are inconsistent (sizes, SAP ID order, config).
        InfeasibleAllocationError: If capacity is too small or the search
            could not find a valid placement within its budget.

    Complexity:
        Time (typical): O(S * (R + K log K) * log Delta) where S is the number
        of seats, R the students scanned per seat and K = CANDIDATES_PER_SEAT.
        Worst case: exponential in the number of seats (local backtracking),
        capped by the option budget ``S + node_limit``.
        Space: O(S * K) for the per-level candidate lists, O(V + S) otherwise.
    """
    n = len(students)
    if graph.n != n or len(result.colors) != n:
        raise ValueError("students, graph and coloring must have the same size")
    for i in range(n):
        if graph.sap_ids[i] != students[i].sap_id:
            raise ValueError("graph vertex order must match the student list order")
    if "weights" not in config or "backtracking" not in config:
        raise ValueError("config must contain 'weights' and 'backtracking'")
    weights = config["weights"]
    neighbourhood = config.get("neighbourhood", "4")
    node_limit = config["backtracking"]["node_limit"]

    # Visiting sequence of every usable seat: (hall index, row, col).
    seats: list[tuple[int, int, int]] = []
    for h_index in range(len(halls)):
        for row, col in snake_order(halls[h_index]):
            seats.append((h_index, row, col))
    n_seats = len(seats)
    if n_seats < n:
        raise InfeasibleAllocationError(
            f"{n} students but only {n_seats} usable seats across {len(halls)} halls"
        )
    if neighbourhood not in ("4", "8"):
        raise ValueError(f"neighbourhood must be '4' or '8', got {neighbourhood!r}")

    # Color classes: members of class k, in ascending vertex order.
    colors = result.colors
    n_classes = 0
    for c in colors:
        if c + 1 > n_classes:
            n_classes = c + 1
    members: list[list[int]] = [[] for _ in range(n_classes)]
    pos_in_class = [0] * n
    for v in range(n):
        pos_in_class[v] = len(members[colors[v]])
        members[colors[v]].append(v)
    head = [0] * n_classes          # members[k][:head[k]] are all seated
    used = [False] * n

    occupied: dict[tuple[int, int, int], int] = {}   # (hall, row, col) -> vertex
    cands: list[list[int]] = [[] for _ in range(n_seats)]
    ptr = [0] * n_seats
    chosen = [-1] * n_seats
    last_class = [-1] * (n_seats + 1)   # class of the latest seated student before level
    budget = n_seats + node_limit
    options_tried = 0
    adj_has_edge = graph.has_edge

    def make_candidates(level: int, placed: int) -> list[int]:
        """Ordered options for ``level``: compatible students, then -1 (empty)."""
        h_index, row, col = seats[level]
        hall = halls[h_index]
        near: list[int] = []
        for n_row, n_col in get_neighbors(hall, row, col, neighbourhood):
            other = occupied.get((h_index, n_row, n_col))
            if other is not None:
                near.append(other)
        far: list[int] = []
        for n_row, n_col in get_distance_two_seats(hall, row, col):
            other = occupied.get((h_index, n_row, n_col))
            if other is not None:
                far.append(other)

        current = last_class[level]
        found: list[int] = []
        scan: list[int] = []
        if current >= 0:
            scan.append(current)
        for k in range(n_classes):
            if k != current:
                scan.append(k)
        for k in scan:
            group = members[k]
            idx = head[k]
            size = len(group)
            while idx < size:
                v = group[idx]
                idx += 1
                if used[v]:
                    continue
                compatible = True
                for w in near:
                    if adj_has_edge(v, w):
                        compatible = False
                        break
                if compatible:
                    found.append(v)
                    if len(found) >= CANDIDATES_PER_SEAT:
                        break
            if len(found) >= CANDIDATES_PER_SEAT:
                break

        def sort_key(v: int) -> tuple[int, float]:
            penalty = 0.0
            for w in near:
                penalty += adjacent_pair_penalty(students[v], students[w], weights)
            for w in far:
                penalty += distance_two_pair_penalty(students[v], students[w], weights)
            return (0 if colors[v] == current else 1, penalty)

        ordered = merge_sort(found, key=sort_key)
        # Leaving the seat empty is allowed only if enough seats remain afterwards.
        if n_seats - level - 1 >= n - placed:
            ordered.append(-1)
        return ordered

    placed = 0
    level = 0
    fresh = True
    while placed < n:
        in_range = True
        if fresh:
            if level >= n_seats:
                in_range = False
            else:
                cands[level] = make_candidates(level, placed)
                ptr[level] = 0
            fresh = False

        if in_range and ptr[level] < len(cands[level]):
            v = cands[level][ptr[level]]
            ptr[level] += 1
            options_tried += 1
            if options_tried > budget:
                raise InfeasibleAllocationError(
                    f"no valid allocation found within the search budget ({budget} options)"
                )
            chosen[level] = v
            if v >= 0:
                h_index, row, col = seats[level]
                used[v] = True
                occupied[(h_index, row, col)] = v
                k = colors[v]
                while head[k] < len(members[k]) and used[members[k][head[k]]]:
                    head[k] += 1
                placed += 1
                last_class[level + 1] = k
            else:
                last_class[level + 1] = last_class[level]
            level += 1
            fresh = True
            continue

        # Options at this level are exhausted: undo the previous level's choice.
        if level == 0:
            raise InfeasibleAllocationError(
                "no valid allocation exists for these halls and students "
                "(a buffer seat may be needed but capacity is too tight)"
            )
        level -= 1
        v = chosen[level]
        if v >= 0:
            h_index, row, col = seats[level]
            del occupied[(h_index, row, col)]
            used[v] = False
            k = colors[v]
            if pos_in_class[v] < head[k]:
                head[k] = pos_in_class[v]
            placed -= 1
        chosen[level] = -1

    allocation = Allocation()
    for (h_index, row, col), v in occupied.items():
        sap_id = students[v].sap_id
        allocation.seats[sap_id] = (halls[h_index].hall_id, row, col)
        allocation.colors[sap_id] = colors[v]

    problems = validate_allocation(allocation, students, halls, neighbourhood)
    if problems:
        raise RuntimeError("internal error, invalid allocation produced: " + "; ".join(problems))
    return allocation

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
       tried options per attempt is capped.
    5. Strategy ladder. Local backtracking cannot repair an early decision that
       used up too many buffer seats, so the mapper makes up to three attempts:
         a. quality first: candidates ordered by soft penalty, 8 per seat;
         b. hardest first: candidates ordered by conflict degree (highest
            first) so hard-to-place students are seated while many partners
            remain, then by penalty; 8 per seat;
         c. hardest first with 32 candidates per seat.
       The first attempt that seats everyone wins, so whenever quality-first
       works the result is the quality-first result. The budget
       per attempt is ``S + max(backtracking.node_limit // 3, 20000)``.
       If every attempt fails, ``InfeasibleAllocationError`` is raised.

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

#: Maximum number of compatible students considered at one seat (attempts a, b).
CANDIDATES_PER_SEAT = 8

#: Candidate cap used by the last, widest attempt (attempt c).
WIDE_CANDIDATES_PER_SEAT = 32

#: Smallest number of options one attempt may try (beyond the S seats). It keeps
#: Phase 2 usable when ``backtracking.node_limit`` is set very low for coloring.
MIN_REPAIR_OPTIONS = 20000

#: Attempts in order: (hardest_first, candidates per seat).
_LADDER: tuple[tuple[bool, int], ...] = (
    (False, CANDIDATES_PER_SEAT),
    (True, CANDIDATES_PER_SEAT),
    (True, WIDE_CANDIDATES_PER_SEAT),
)


class InfeasibleAllocationError(Exception):
    """Raised when no valid allocation could be built (capacity or search limit)."""


def _attempt(
    students: list[Student],
    graph: ConflictGraph,
    colors: list[int],
    halls: list[Hall],
    seats: list[tuple[int, int, int]],
    weights: dict,
    neighbourhood: str,
    hardest_first: bool,
    cap: int,
    budget: int,
) -> dict[tuple[int, int, int], int] | None:
    """Run one depth-first placement attempt.

    Args:
        seats: Visiting sequence of ``(hall index, row, col)``.
        hardest_first: If True, class members are scanned by descending conflict
            degree and candidates are ordered by (class, -degree, penalty);
            otherwise members are scanned in vertex order and candidates are
            ordered by (class, penalty).
        cap: Maximum compatible candidates collected per seat.
        budget: Maximum number of options tried before giving up.

    Returns:
        The occupancy map ``(hall index, row, col) -> vertex`` on success, or
        ``None`` if the search space was exhausted or the budget ran out.

    Time: see ``map_colors_to_seats``. Space: O(S * cap + V).
    """
    n = len(students)
    n_seats = len(seats)
    adj = graph.adj

    n_classes = 0
    for c in colors:
        if c + 1 > n_classes:
            n_classes = c + 1
    members: list[list[int]] = [[] for _ in range(n_classes)]
    for v in range(n):
        members[colors[v]].append(v)
    if hardest_first:
        for k in range(n_classes):
            members[k] = merge_sort(members[k], key=lambda v: len(adj[v]), reverse=True)
    pos_in_class = [0] * n
    for k in range(n_classes):
        for i in range(len(members[k])):
            pos_in_class[members[k][i]] = i
    head = [0] * n_classes          # members[k][:head[k]] are all seated
    used = [False] * n

    occupied: dict[tuple[int, int, int], int] = {}   # (hall, row, col) -> vertex
    cands: list[list[int]] = [[] for _ in range(n_seats)]
    ptr = [0] * n_seats
    chosen = [-1] * n_seats
    last_class = [-1] * (n_seats + 1)   # class of the latest seated student before level
    options_tried = 0
    has_edge = graph.has_edge

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
                    if has_edge(v, w):
                        compatible = False
                        break
                if compatible:
                    found.append(v)
                    if len(found) >= cap:
                        break
            if len(found) >= cap:
                break

        def sort_key(v: int) -> tuple[int, int, float]:
            penalty = 0.0
            for w in near:
                penalty += adjacent_pair_penalty(students[v], students[w], weights)
            for w in far:
                penalty += distance_two_pair_penalty(students[v], students[w], weights)
            hardness = -len(adj[v]) if hardest_first else 0
            return (0 if colors[v] == current else 1, hardness, penalty)

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
                return None
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
            return None
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
    return occupied


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
        InfeasibleAllocationError: If capacity is too small or every attempt of
            the strategy ladder failed within its budget.

    Complexity:
        Time (typical, one attempt, no backtracking): O(S * (R + K log K) * deg *
        log Delta) where S is the number of seats, R the students scanned per
        seat and K the candidate cap. Worst case: exponential in S, capped by
        ``S + max(node_limit // 3, 20000)`` options per attempt (at most 3 attempts).
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
    if neighbourhood not in ("4", "8"):
        raise ValueError(f"neighbourhood must be '4' or '8', got {neighbourhood!r}")
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

    colors = result.colors
    budget = n_seats + max(node_limit // len(_LADDER), MIN_REPAIR_OPTIONS)
    occupied: dict[tuple[int, int, int], int] | None = None
    for hardest_first, cap in _LADDER:
        occupied = _attempt(
            students, graph, colors, halls, seats, weights, neighbourhood,
            hardest_first, cap, budget,
        )
        if occupied is not None:
            break
    if occupied is None:
        raise InfeasibleAllocationError(
            f"no valid allocation found after {len(_LADDER)} placement attempts "
            f"(budget {budget} options each); capacity may be too tight for these conflicts"
        )

    allocation = Allocation()
    for (h_index, row, col), v in occupied.items():
        sap_id = students[v].sap_id
        allocation.seats[sap_id] = (halls[h_index].hall_id, row, col)
        allocation.colors[sap_id] = colors[v]

    problems = validate_allocation(allocation, students, halls, neighbourhood)
    if problems:
        raise RuntimeError("internal error, invalid allocation produced: " + "; ".join(problems))
    return allocation

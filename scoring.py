"""Soft-constraint scoring (README section 4.4). Lower is better.

    score = w_same_branch         * (#neighbour pairs, same branch)
          + w_consecutive_roll    * (#neighbour pairs, same branch, consecutive roll numbers)
          + w_distance_two_conflict * (#pairs two seats apart on a line sharing a course)
          + w_wasted_seat         * (#wasted seats)

Definitions used by this project (see docs/DESIGN.md):
    * Neighbour pairs use the same neighbourhood as the hard constraints.
    * Consecutive roll numbers are compared only inside one branch, because roll
      numbers of different branches are unrelated.
    * Distance two means ``(r, c)`` and ``(r, c + 2)``, or ``(r, c)`` and
      ``(r + 2, c)``. The seat in between may be blocked or empty.
    * Only halls that hold at least one student are considered. An empty usable
      seat in such a hall is a **buffer** if at least one neighbour is occupied
      (it separates students) and a **wasted** seat otherwise.
"""

from __future__ import annotations

from src.grid.constraints import students_conflict
from src.grid.hall_grid import (
    get_distance_two_seats,
    get_neighbors,
    usable_seats,
)
from src.models.allocation import Allocation
from src.models.hall import Hall
from src.models.student import Student


def adjacent_pair_penalty(a: Student, b: Student, weights: dict) -> float:
    """Penalty (S1 + S2) for two students on neighbouring seats.

    Time: O(1). Space: O(1).
    """
    penalty = 0.0
    if a.branch == b.branch:
        penalty += weights["w_same_branch"]
        if abs(a.roll_no - b.roll_no) == 1:
            penalty += weights["w_consecutive_roll"]
    return penalty


def distance_two_pair_penalty(a: Student, b: Student, weights: dict) -> float:
    """Penalty (S3) for two students two seats apart sharing a course.

    Time: O(c). Space: O(1).
    """
    if students_conflict(a, b):
        return weights["w_distance_two_conflict"]
    return 0.0


def soft_breakdown(
    allocation: Allocation,
    students: list[Student],
    halls: list[Hall],
    neighbourhood: str = "4",
) -> dict[str, int]:
    """Count every quantity that enters the soft score.

    Keys: ``same_branch_pairs``, ``consecutive_roll_pairs``,
    ``distance_two_pairs``, ``wasted_seats``, ``buffer_seats``, ``used_halls``,
    ``seated``. Seats that are invalid (unknown hall, outside the grid, blocked,
    duplicated) are ignored; ``validate_allocation`` reports those.

    Time: O(S * c). Space: O(V + S).
    """
    by_id = {student.sap_id: student for student in students}
    hall_by_id = {hall.hall_id: hall for hall in halls}

    occupant: dict[tuple[str, int, int], str] = {}
    for sap_id, (hall_id, row, col) in allocation.seats.items():
        hall = hall_by_id.get(hall_id)
        if sap_id not in by_id or hall is None:
            continue
        if not (0 <= row < hall.rows and 0 <= col < hall.cols):
            continue
        if (row, col) in hall.blocked:
            continue
        key = (hall_id, row, col)
        if key not in occupant:
            occupant[key] = sap_id

    same_branch = 0
    consecutive = 0
    distance_two = 0
    for (hall_id, row, col), sap_id in occupant.items():
        hall = hall_by_id[hall_id]
        a = by_id[sap_id]
        for n_row, n_col in get_neighbors(hall, row, col, neighbourhood):
            if (n_row, n_col) < (row, col):
                continue
            other_id = occupant.get((hall_id, n_row, n_col))
            if other_id is None:
                continue
            b = by_id[other_id]
            if a.branch == b.branch:
                same_branch += 1
                if abs(a.roll_no - b.roll_no) == 1:
                    consecutive += 1
        for n_row, n_col in get_distance_two_seats(hall, row, col):
            if (n_row, n_col) < (row, col):
                continue
            other_id = occupant.get((hall_id, n_row, n_col))
            if other_id is None:
                continue
            if students_conflict(a, by_id[other_id]):
                distance_two += 1

    used_halls = 0
    wasted = 0
    buffers = 0
    halls_in_use: set[str] = set()
    for hall_id, _row, _col in occupant:
        halls_in_use.add(hall_id)
    for hall in halls:
        if hall.hall_id not in halls_in_use:
            continue
        used_halls += 1
        for row, col in usable_seats(hall):
            if (hall.hall_id, row, col) in occupant:
                continue
            separates = False
            for n_row, n_col in get_neighbors(hall, row, col, neighbourhood):
                if (hall.hall_id, n_row, n_col) in occupant:
                    separates = True
                    break
            if separates:
                buffers += 1
            else:
                wasted += 1

    return {
        "same_branch_pairs": same_branch,
        "consecutive_roll_pairs": consecutive,
        "distance_two_pairs": distance_two,
        "wasted_seats": wasted,
        "buffer_seats": buffers,
        "used_halls": used_halls,
        "seated": len(occupant),
    }


def compute_soft_score(
    allocation: Allocation,
    students: list[Student],
    halls: list[Hall],
    weights: dict,
    neighbourhood: str = "4",
) -> float:
    """Return the weighted soft-constraint penalty (lower is better).

    Args:
        allocation: The seating plan.
        students: All students.
        halls: All halls.
        weights: Dict with ``w_same_branch``, ``w_consecutive_roll``,
            ``w_distance_two_conflict`` and ``w_wasted_seat``.
        neighbourhood: ``"4"`` (default) or ``"8"``.

    Time: O(S * c). Space: O(V + S).
    """
    counts = soft_breakdown(allocation, students, halls, neighbourhood)
    return (
        weights["w_same_branch"] * counts["same_branch_pairs"]
        + weights["w_consecutive_roll"] * counts["consecutive_roll_pairs"]
        + weights["w_distance_two_conflict"] * counts["distance_two_pairs"]
        + weights["w_wasted_seat"] * counts["wasted_seats"]
    )

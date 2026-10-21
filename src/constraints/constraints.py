"""Hard-constraint validation (README section 4.3).

``validate_allocation`` checks H1 to H5 and returns human-readable messages,
each starting with the constraint id. An empty list means the allocation is
valid.

    H1  every student has exactly one seat in exactly one hall
    H2  a seat holds at most one student
    H3  no blocked seat (or seat outside the grid, or unknown hall) is used
    H4  no two neighbouring occupied seats hold students who share a course
    H5  total hall capacity covers all students
"""

from __future__ import annotations

from src.grid.hall_grid import get_neighbors
from src.models.allocation import Allocation
from src.models.hall import Hall
from src.models.student import Student


def students_conflict(a: Student, b: Student) -> bool:
    """Return True if the two students share at least one course.

    Time: O(c). Space: O(1).
    """
    return not a.courses.isdisjoint(b.courses)


def validate_allocation(
    allocation: Allocation,
    students: list[Student],
    halls: list[Hall],
    neighbourhood: str = "4",
) -> list[str]:
    """Check hard constraints H1 to H5 and return every violation found.

    Args:
        allocation: The seating plan to check.
        students: All students that must be seated.
        halls: All halls.
        neighbourhood: ``"4"`` (default) or ``"8"``; decides which seats are
            neighbours for H4.

    Returns:
        A list of messages (empty if the allocation is valid).

    Complexity:
        Time: O(S * c) where S is the number of seats and c the maximum number
        of courses per student (each seat has at most 8 neighbours).
        Space: O(V + S) for the lookup tables.
    """
    errors: list[str] = []
    by_id = {student.sap_id: student for student in students}
    hall_by_id = {hall.hall_id: hall for hall in halls}

    # H1: every student seated, nobody unknown seated.
    for student in students:
        if student.sap_id not in allocation.seats:
            errors.append(f"H1: student {student.sap_id!r} has no seat")
    for sap_id in allocation.seats:
        if sap_id not in by_id:
            errors.append(f"H1: seat assigned to unknown student {sap_id!r}")

    # H5: total capacity.
    total_capacity = 0
    for hall in halls:
        total_capacity += hall.capacity()
    if total_capacity < len(students):
        errors.append(
            f"H5: {len(students)} students but only {total_capacity} usable seats"
        )

    # H2 and H3: build the occupancy table from valid seats only.
    occupant: dict[tuple[str, int, int], str] = {}
    for sap_id, (hall_id, row, col) in allocation.seats.items():
        if sap_id not in by_id:
            continue
        hall = hall_by_id.get(hall_id)
        if hall is None:
            errors.append(f"H3: student {sap_id!r} is in unknown hall {hall_id!r}")
            continue
        if not (0 <= row < hall.rows and 0 <= col < hall.cols):
            errors.append(
                f"H3: student {sap_id!r} seat ({row}, {col}) is outside hall {hall_id!r}"
            )
            continue
        if (row, col) in hall.blocked:
            errors.append(
                f"H3: student {sap_id!r} is on blocked seat ({row}, {col}) of hall {hall_id!r}"
            )
            continue
        key = (hall_id, row, col)
        if key in occupant:
            errors.append(
                f"H2: students {occupant[key]!r} and {sap_id!r} share seat "
                f"({row}, {col}) of hall {hall_id!r}"
            )
            continue
        occupant[key] = sap_id

    # H4: neighbouring occupied seats must not share a course. Each unordered
    # pair is examined once (only from the smaller coordinate).
    for (hall_id, row, col), sap_id in occupant.items():
        hall = hall_by_id[hall_id]
        for n_row, n_col in get_neighbors(hall, row, col, neighbourhood):
            if (n_row, n_col) < (row, col):
                continue
            other_id = occupant.get((hall_id, n_row, n_col))
            if other_id is None:
                continue
            if students_conflict(by_id[sap_id], by_id[other_id]):
                errors.append(
                    f"H4: neighbouring students {sap_id!r} at ({row}, {col}) and "
                    f"{other_id!r} at ({n_row}, {n_col}) in hall {hall_id!r} share a course"
                )
    return errors

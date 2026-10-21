"""Hall grid geometry: neighbours, usable seats, and seat visiting order.

Seat coordinates are ``(row, col)`` with ``(0, 0)`` at the front-left.

Neighbour rules (README section 4.2):
    * 4-neighbourhood (default): left ``(r, c-1)``, right ``(r, c+1)``,
      front ``(r-1, c)``, back ``(r+1, c)``.
    * 8-neighbourhood (optional extension): the four above plus the diagonals.
    * Cells outside the grid are ignored.
    * Blocked seats are gaps. They are never returned as neighbours, so they do
      not link the seats on either side of them.

This module only uses plain loops and lists. It never sorts.
"""

from __future__ import annotations

from src.models.hall import Hall

#: Offsets (d_row, d_col): left, right, front, back.
OFFSETS_4: tuple[tuple[int, int], ...] = ((0, -1), (0, 1), (-1, 0), (1, 0))

#: The four orthogonal offsets followed by the four diagonals.
OFFSETS_8: tuple[tuple[int, int], ...] = OFFSETS_4 + (
    (-1, -1), (-1, 1), (1, -1), (1, 1),
)

#: Seats exactly two steps away along a row or a column.
OFFSETS_DISTANCE_TWO: tuple[tuple[int, int], ...] = ((0, -2), (0, 2), (-2, 0), (2, 0))


def offsets_for(neighbourhood: str) -> tuple[tuple[int, int], ...]:
    """Return the neighbour offsets for ``"4"`` or ``"8"``.

    Raises:
        ValueError: For any other value.

    Time: O(1). Space: O(1).
    """
    if neighbourhood == "4":
        return OFFSETS_4
    if neighbourhood == "8":
        return OFFSETS_8
    raise ValueError(f"neighbourhood must be '4' or '8', got {neighbourhood!r}")


def in_bounds(hall: Hall, row: int, col: int) -> bool:
    """Return True if ``(row, col)`` lies inside the hall grid.

    Time: O(1). Space: O(1).
    """
    return 0 <= row < hall.rows and 0 <= col < hall.cols


def is_usable(hall: Hall, row: int, col: int) -> bool:
    """Return True if ``(row, col)`` is inside the grid and not blocked.

    Time: O(1). Space: O(1).
    """
    return in_bounds(hall, row, col) and (row, col) not in hall.blocked


def get_neighbors(
    hall: Hall, row: int, col: int, neighbourhood: str = "4"
) -> list[tuple[int, int]]:
    """Return the usable neighbouring seats of ``(row, col)``.

    The order is left, right, front, back (then the diagonals for ``"8"``).
    Cells outside the grid and blocked cells are omitted. A blocked seat itself
    has no neighbours, so it returns an empty list.

    Raises:
        ValueError: If ``(row, col)`` is outside the grid or ``neighbourhood``
            is not ``"4"`` or ``"8"``.

    Time: O(1) (at most 8 offsets). Space: O(1).
    """
    offsets = offsets_for(neighbourhood)
    if not in_bounds(hall, row, col):
        raise ValueError(
            f"seat ({row}, {col}) is outside hall {hall.hall_id!r} "
            f"({hall.rows}x{hall.cols})"
        )
    if (row, col) in hall.blocked:
        return []
    result: list[tuple[int, int]] = []
    for d_row, d_col in offsets:
        r = row + d_row
        c = col + d_col
        if is_usable(hall, r, c):
            result.append((r, c))
    return result


def get_distance_two_seats(hall: Hall, row: int, col: int) -> list[tuple[int, int]]:
    """Return usable seats exactly two steps away along the row or column.

    Order: two left, two right, two front, two back. The seat in between may be
    blocked or empty; only the endpoint must be usable.

    Time: O(1). Space: O(1).
    """
    result: list[tuple[int, int]] = []
    for d_row, d_col in OFFSETS_DISTANCE_TWO:
        r = row + d_row
        c = col + d_col
        if is_usable(hall, r, c):
            result.append((r, c))
    return result


def usable_seats(hall: Hall) -> list[tuple[int, int]]:
    """Return every usable seat in row-major order.

    Time: O(rows * cols). Space: O(capacity).
    """
    seats: list[tuple[int, int]] = []
    for r in range(hall.rows):
        for c in range(hall.cols):
            if (r, c) not in hall.blocked:
                seats.append((r, c))
    return seats


def snake_order(hall: Hall) -> list[tuple[int, int]]:
    """Return usable seats in snake (boustrophedon) order.

    Even rows run left to right and odd rows right to left, so consecutive seats
    in the order are always physical neighbours (unless a blocked seat
    intervenes). The seat mapper fills seats in this order.

    Time: O(rows * cols). Space: O(capacity).
    """
    seats: list[tuple[int, int]] = []
    for r in range(hall.rows):
        if r % 2 == 0:
            columns = range(hall.cols)
        else:
            columns = range(hall.cols - 1, -1, -1)
        for c in columns:
            if (r, c) not in hall.blocked:
                seats.append((r, c))
    return seats

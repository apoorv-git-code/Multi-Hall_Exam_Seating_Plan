"""Hall model.

A hall is a ``rows x cols`` grid of seats. Coordinates are ``(row, col)`` with
``(0, 0)`` at the front-left. Blocked seats are never assigned to students.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Hall:
    """One examination hall.

    Attributes:
        hall_id: Unique hall identifier.
        rows: Number of rows (at least 1).
        cols: Number of columns (at least 1).
        blocked: Set of ``(row, col)`` seats that cannot be used.
    """

    hall_id: str
    rows: int
    cols: int
    blocked: frozenset[tuple[int, int]]

    def capacity(self) -> int:
        """Return the number of usable seats: ``rows * cols - len(blocked)``.

        Time: O(1). Space: O(1).
        """
        return self.rows * self.cols - len(self.blocked)

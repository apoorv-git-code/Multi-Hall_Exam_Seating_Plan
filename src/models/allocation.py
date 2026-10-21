"""Allocation model: the final seating result.

``seats`` maps every seated student to a physical seat. ``colors`` records the
Phase 1 color class of each student. Both are keyed by ``sap_id``.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Allocation:
    """A (possibly partial) seating plan.

    Attributes:
        seats: ``sap_id -> (hall_id, row, col)``.
        colors: ``sap_id -> color class`` from Phase 1 coloring.
    """

    seats: dict[str, tuple[str, int, int]] = field(default_factory=dict)
    colors: dict[str, int] = field(default_factory=dict)

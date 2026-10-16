"""Student model.

A plain, immutable record. It holds no logic: conflict detection lives in
``src/graph/conflict_graph.py`` and seat-level checks live in ``src/grid/``.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Student:
    """One examinee.

    Attributes:
        sap_id: Unique student identifier (SAP ID).
        name: Student name.
        roll_no: Roll number (non-negative integer).
        branch: Branch or department code, for example ``"CSE"``.
        courses: Codes of the courses the student is enrolled in.
    """

    sap_id: str
    name: str
    roll_no: int
    branch: str
    courses: frozenset[str]

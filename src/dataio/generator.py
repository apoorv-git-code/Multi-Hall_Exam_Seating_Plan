"""Seeded synthetic dataset generator.

All randomness comes from ``random.Random(seed)`` instances, so the same
arguments always reproduce the same dataset (development rule 6).

Generated data conventions:
    * SAP IDs are unique: ``5001`` followed by a zero-padded running number.
    * Roll numbers run 1, 2, 3, ... within each branch (so two branches can
      share a roll number; consecutive-roll scoring should compare same-branch
      students only, or be refined in the Step 6 design).
    * Course codes are ``C001``, ``C002``, ...
    * Hall capacity totals roughly ``slack`` times the number of students, so
      the allocation is feasible and leaves room for buffer seats.

Complexity: ``generate_students`` is O(V * c). ``generate_halls`` is
O(total cells) because blocked seats are drawn from the full cell list.
"""

from __future__ import annotations

import csv
import random
from pathlib import Path

from src.models.hall import Hall
from src.models.student import Student

DEFAULT_BRANCHES: tuple[str, ...] = ("CSE", "IT", "ECE", "EEE", "ME", "CE")

_FIRST_NAMES: tuple[str, ...] = (
    "Aarav", "Aditi", "Ananya", "Arjun", "Diya", "Ishaan", "Kavya", "Karan",
    "Meera", "Neha", "Rahul", "Riya", "Rohan", "Sanya", "Tanvi", "Vikram",
)
_LAST_NAMES: tuple[str, ...] = (
    "Agarwal", "Bhatt", "Chauhan", "Dutta", "Gupta", "Joshi", "Kapoor",
    "Mehta", "Negi", "Rawat", "Sharma", "Singh", "Thakur", "Verma",
)


def generate_students(
    n_students: int,
    n_courses: int,
    seed: int,
    min_courses: int = 3,
    max_courses: int = 5,
    branches: tuple[str, ...] = DEFAULT_BRANCHES,
) -> list[Student]:
    """Generate ``n_students`` students with random course enrolments.

    Each student takes between ``min_courses`` and ``max_courses`` distinct
    courses (the upper bound is clamped to ``n_courses``).

    Raises:
        ValueError: If any size argument is out of range.

    Time: O(n_students * max_courses). Space: O(n_students).
    """
    if n_students < 1:
        raise ValueError("n_students must be >= 1")
    if n_courses < 1:
        raise ValueError("n_courses must be >= 1")
    if min_courses < 1 or max_courses < min_courses:
        raise ValueError("need 1 <= min_courses <= max_courses")
    if len(branches) == 0:
        raise ValueError("branches must not be empty")

    rng = random.Random(seed)
    course_codes = [f"C{index + 1:03d}" for index in range(n_courses)]
    high = min(max_courses, n_courses)
    low = min(min_courses, high)
    roll_counters: dict[str, int] = {branch: 0 for branch in branches}

    students: list[Student] = []
    for index in range(n_students):
        branch = rng.choice(branches)
        roll_counters[branch] += 1
        count = rng.randint(low, high)
        students.append(
            Student(
                sap_id=f"5001{index + 1:06d}",
                name=f"{rng.choice(_FIRST_NAMES)} {rng.choice(_LAST_NAMES)}",
                roll_no=roll_counters[branch],
                branch=branch,
                courses=frozenset(rng.sample(course_codes, count)),
            )
        )
    return students


def generate_halls(
    n_halls: int,
    n_students: int,
    seed: int,
    slack: float = 1.25,
    max_blocked_fraction: float = 0.06,
) -> list[Hall]:
    """Generate ``n_halls`` halls whose total capacity is at least ``n_students``.

    Hall widths are drawn from 6..12 columns. Heights are chosen so the grid
    cell total is about ``slack * n_students``, then a random fraction (at most
    ``max_blocked_fraction``) of seats is blocked. If the result still falls
    short of ``n_students``, rows are added round-robin until it fits.

    Raises:
        ValueError: If ``n_halls`` or ``n_students`` is below 1, ``slack`` is
            below 1.0, or ``max_blocked_fraction`` is outside [0, 0.5].

    Time: O(total cells). Space: O(total cells).
    """
    if n_halls < 1:
        raise ValueError("n_halls must be >= 1")
    if n_students < 1:
        raise ValueError("n_students must be >= 1")
    if slack < 1.0:
        raise ValueError("slack must be >= 1.0")
    if not (0.0 <= max_blocked_fraction <= 0.5):
        raise ValueError("max_blocked_fraction must be within [0, 0.5]")

    rng = random.Random(seed + 7919)  # separate stream from the student generator
    exact = n_students * slack
    target_cells = int(exact)
    if target_cells < exact:
        target_cells += 1  # ceiling
    per_hall = -(-target_cells // n_halls)  # ceiling division

    specs: list[list] = []  # each entry: [rows, cols, blocked_set]
    for _ in range(n_halls):
        cols = rng.randint(6, 12)
        rows = max(2, -(-per_hall // cols))
        cells = [(r, c) for r in range(rows) for c in range(cols)]
        max_blocked = int(len(cells) * max_blocked_fraction)
        n_blocked = rng.randint(0, max_blocked)
        blocked = set(rng.sample(cells, n_blocked))
        specs.append([rows, cols, blocked])

    total = sum(spec[0] * spec[1] - len(spec[2]) for spec in specs)
    turn = 0
    while total < n_students:
        spec = specs[turn % n_halls]
        spec[0] += 1  # a new row adds `cols` usable seats, blocked set stays valid
        total += spec[1]
        turn += 1

    return [
        Hall(
            hall_id=f"H{index + 1:02d}",
            rows=spec[0],
            cols=spec[1],
            blocked=frozenset(spec[2]),
        )
        for index, spec in enumerate(specs)
    ]


def write_students_csv(students: list[Student], path: str) -> None:
    """Write students to ``path`` in the ``students.csv`` format.

    Course codes are written in sorted order so output is deterministic.

    Time: O(V * c). Space: O(1) extra.
    """
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["sap_id", "name", "roll_no", "branch", "courses"])
        for student in students:
            writer.writerow([
                student.sap_id,
                student.name,
                student.roll_no,
                student.branch,
                ";".join(sorted(student.courses)),
            ])


def write_halls_csv(halls: list[Hall], path: str) -> None:
    """Write halls to ``path`` in the ``halls.csv`` format.

    Blocked seats are written as ``r:c`` in sorted order, separated by ``;``.

    Time: O(H + blocked seats). Space: O(1) extra.
    """
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["hall_id", "rows", "cols", "blocked"])
        for hall in halls:
            blocked_text = ";".join(f"{r}:{c}" for r, c in sorted(hall.blocked))
            writer.writerow([hall.hall_id, hall.rows, hall.cols, blocked_text])


def generate_dataset(
    n_students: int,
    n_courses: int,
    n_halls: int,
    seed: int,
    out_dir: str,
) -> tuple[str, str]:
    """Generate a full dataset and write ``students.csv`` and ``halls.csv``.

    Creates ``out_dir`` if needed. Returns the two file paths as
    ``(students_path, halls_path)``.

    Time: O(V * c + total cells). Space: same.
    """
    students = generate_students(n_students, n_courses, seed)
    halls = generate_halls(n_halls, n_students, seed)
    directory = Path(out_dir)
    directory.mkdir(parents=True, exist_ok=True)
    students_path = str(directory / "students.csv")
    halls_path = str(directory / "halls.csv")
    write_students_csv(students, students_path)
    write_halls_csv(halls, halls_path)
    return students_path, halls_path

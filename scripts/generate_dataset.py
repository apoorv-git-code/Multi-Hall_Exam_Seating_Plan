"""Generate a seeded synthetic dataset (students.csv and halls.csv).

    python scripts/generate_dataset.py --students 200 --courses 12 --halls 4 --seed 42 --out data/generated/
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.dataio.generator import generate_dataset  # noqa: E402
from src.dataio.parser import load_halls, load_students  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a seeded exam-seating dataset.")
    parser.add_argument("--students", type=int, default=200, help="number of students (default 200)")
    parser.add_argument("--courses", type=int, default=12, help="number of courses (default 12)")
    parser.add_argument("--halls", type=int, default=4, help="number of halls (default 4)")
    parser.add_argument("--seed", type=int, default=42, help="random seed (default 42)")
    parser.add_argument("--out", default="data/generated/", help="output folder (default data/generated/)")
    args = parser.parse_args(argv)
    try:
        students_path, halls_path = generate_dataset(
            args.students, args.courses, args.halls, args.seed, args.out
        )
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    n_students = len(load_students(students_path))
    capacity = sum(hall.capacity() for hall in load_halls(halls_path))
    print(f"Wrote {students_path} ({n_students} students)")
    print(f"Wrote {halls_path} ({args.halls} halls, {capacity} usable seats)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

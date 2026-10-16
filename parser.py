"""CSV and JSON readers for students, halls, and configuration.

Row-level problems (missing columns, non-integer numbers, bad seat
coordinates) are reported with the file name and line number. Cross-row
problems (duplicate SAP IDs, duplicate hall IDs) are reported by the
validator after parsing. Any problem raises ``DataFormatError``.

Complexity: every loader is O(L) time and O(L) space for L input lines (times
the small constant number of courses or blocked seats per line).
"""

from __future__ import annotations

import csv
import json

from src.dataio.validator import (
    DataFormatError,
    raise_if_errors,
    validate_config,
    validate_halls,
    validate_students,
)
from src.models.hall import Hall
from src.models.student import Student

STUDENT_COLUMNS: tuple[str, ...] = ("sap_id", "name", "roll_no", "branch", "courses")
HALL_COLUMNS: tuple[str, ...] = ("hall_id", "rows", "cols", "blocked")

#: Built-in configuration. Mirrors ``config/default_config.json``. Missing keys
#: in a user config file are filled in from here.
DEFAULT_CONFIG: dict = {
    "neighbourhood": "4",
    "weights": {
        "w_same_branch": 3.0,
        "w_consecutive_roll": 2.0,
        "w_distance_two_conflict": 1.0,
        "w_wasted_seat": 0.5,
    },
    "backtracking": {
        "node_limit": 200000,
        "time_limit_seconds": 10.0,
    },
    "random_seed": 42,
    "output_dir": "output",
}


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _read_rows(path: str, columns: tuple[str, ...]) -> list[tuple[int, dict[str, str]]]:
    """Read a CSV file and return ``(line_number, row_dict)`` pairs.

    Checks that the header contains every required column and that each data
    row has exactly the right number of fields. Blank lines are skipped.

    Raises:
        DataFormatError: If the file cannot be read or is malformed.
    """
    rows: list[tuple[int, dict[str, str]]] = []
    try:
        with open(path, "r", newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                raise DataFormatError(f"{path}: file is empty (no header row)")
            header = [name.strip() for name in reader.fieldnames]
            reader.fieldnames = header
            missing = [name for name in columns if name not in header]
            if missing:
                raise DataFormatError(f"{path}: missing required column(s) {missing}")
            for record in reader:
                line = reader.line_num
                if None in record:
                    raise DataFormatError(f"{path} line {line}: too many fields in row")
                clean: dict[str, str] = {}
                for name in columns:
                    value = record.get(name)
                    if value is None:
                        raise DataFormatError(f"{path} line {line}: missing value for {name!r}")
                    clean[name] = value.strip()
                rows.append((line, clean))
    except OSError as exc:
        raise DataFormatError(f"{path}: cannot read file ({exc})") from exc
    except csv.Error as exc:
        raise DataFormatError(f"{path}: malformed CSV ({exc})") from exc
    return rows


def _parse_int(text: str, field: str, where: str, minimum: int) -> int:
    """Parse ``text`` as an integer >= ``minimum`` or raise ``DataFormatError``."""
    try:
        value = int(text)
    except ValueError:
        raise DataFormatError(f"{where}: {field} must be an integer, got {text!r}") from None
    if value < minimum:
        raise DataFormatError(f"{where}: {field} must be >= {minimum}, got {value}")
    return value


def parse_courses(text: str, where: str) -> frozenset[str]:
    """Parse ``"CS201;MA101"`` into ``frozenset({"CS201", "MA101"})``.

    Empty tokens (for example from a trailing ``;``) are ignored. At least one
    course code must remain.

    Time: O(len(text)). Space: O(number of courses).
    """
    codes = {token.strip() for token in text.split(";") if token.strip() != ""}
    if not codes:
        raise DataFormatError(f"{where}: courses must list at least one course code")
    return frozenset(codes)


def parse_blocked(text: str, rows: int, cols: int, where: str) -> frozenset[tuple[int, int]]:
    """Parse ``"0:1;2:3"`` into ``frozenset({(0, 1), (2, 3)})``.

    An empty string means no blocked seats. Each token must look like ``r:c``
    with ``0 <= r < rows`` and ``0 <= c < cols``. Duplicate seats are rejected.

    Time: O(len(text)). Space: O(number of blocked seats).
    """
    blocked: set[tuple[int, int]] = set()
    if text == "":
        return frozenset()
    for token in text.split(";"):
        token = token.strip()
        if token == "":
            continue
        parts = token.split(":")
        if len(parts) != 2:
            raise DataFormatError(f"{where}: bad blocked seat {token!r}, expected 'row:col'")
        try:
            row = int(parts[0])
            col = int(parts[1])
        except ValueError:
            raise DataFormatError(
                f"{where}: bad blocked seat {token!r}, row and col must be integers"
            ) from None
        if not (0 <= row < rows and 0 <= col < cols):
            raise DataFormatError(
                f"{where}: blocked seat {token!r} is outside the {rows}x{cols} grid"
            )
        if (row, col) in blocked:
            raise DataFormatError(f"{where}: blocked seat {token!r} is listed twice")
        blocked.add((row, col))
    return frozenset(blocked)


def _merge_config(defaults: dict, override: dict) -> dict:
    """Return a new dict: ``defaults`` overlaid with ``override`` (recursive).

    Keys that only appear in ``override`` are kept so the validator can flag
    them as unknown.
    """
    merged: dict = {}
    for key, default_value in defaults.items():
        if key in override:
            given = override[key]
            if isinstance(default_value, dict) and isinstance(given, dict):
                merged[key] = _merge_config(default_value, given)
            else:
                merged[key] = given
        elif isinstance(default_value, dict):
            merged[key] = _merge_config(default_value, {})
        else:
            merged[key] = default_value
    for key, given in override.items():
        if key not in defaults:
            merged[key] = given
    return merged


# ---------------------------------------------------------------------------
# Public loaders
# ---------------------------------------------------------------------------

def load_students(path: str) -> list[Student]:
    """Load ``students.csv`` into a list of ``Student`` objects.

    Expected columns: ``sap_id, name, roll_no, branch, courses`` (courses
    separated by ``;``). File order is preserved.

    Raises:
        DataFormatError: On unreadable files, bad rows, or duplicate SAP IDs.

    Time: O(L * c). Space: O(L * c).
    """
    students: list[Student] = []
    for line, row in _read_rows(path, STUDENT_COLUMNS):
        where = f"{path} line {line}"
        for field in ("sap_id", "name", "branch"):
            if row[field] == "":
                raise DataFormatError(f"{where}: {field} must not be empty")
        students.append(
            Student(
                sap_id=row["sap_id"],
                name=row["name"],
                roll_no=_parse_int(row["roll_no"], "roll_no", where, 0),
                branch=row["branch"],
                courses=parse_courses(row["courses"], where),
            )
        )
    raise_if_errors(validate_students(students), f"{path}: invalid student data")
    return students


def load_halls(path: str) -> list[Hall]:
    """Load ``halls.csv`` into a list of ``Hall`` objects.

    Expected columns: ``hall_id, rows, cols, blocked`` (blocked seats written
    as ``r:c`` separated by ``;``, empty if none). File order is preserved.

    Raises:
        DataFormatError: On unreadable files, bad rows, bad seat coordinates,
            or duplicate hall IDs.

    Time: O(L + total blocked seats). Space: same.
    """
    halls: list[Hall] = []
    for line, row in _read_rows(path, HALL_COLUMNS):
        where = f"{path} line {line}"
        if row["hall_id"] == "":
            raise DataFormatError(f"{where}: hall_id must not be empty")
        rows = _parse_int(row["rows"], "rows", where, 1)
        cols = _parse_int(row["cols"], "cols", where, 1)
        halls.append(
            Hall(
                hall_id=row["hall_id"],
                rows=rows,
                cols=cols,
                blocked=parse_blocked(row["blocked"], rows, cols, where),
            )
        )
    raise_if_errors(validate_halls(halls), f"{path}: invalid hall data")
    return halls


def load_config(path: str) -> dict:
    """Load a JSON configuration file and fill in missing keys with defaults.

    The result always contains every key of ``DEFAULT_CONFIG``. Unknown keys,
    wrong types, and out-of-range values raise ``DataFormatError``.

    Time: O(1) after JSON parsing. Space: O(1).
    """
    try:
        with open(path, "r", encoding="utf-8-sig") as handle:
            loaded = json.load(handle)
    except OSError as exc:
        raise DataFormatError(f"{path}: cannot read file ({exc})") from exc
    except json.JSONDecodeError as exc:
        raise DataFormatError(f"{path}: invalid JSON ({exc})") from exc
    if not isinstance(loaded, dict):
        raise DataFormatError(f"{path}: configuration must be a JSON object")
    config = _merge_config(DEFAULT_CONFIG, loaded)
    raise_if_errors(validate_config(config), f"{path}: invalid configuration")
    return config

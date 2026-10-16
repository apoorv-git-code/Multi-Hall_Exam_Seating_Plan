"""Validation of in-memory input data (students, halls, configuration).

These checks work on already-parsed objects, so they apply equally to data
loaded from CSV/JSON and to data produced by the generator. Every ``validate_*``
function returns a list of human-readable error strings. An empty list means
the data is valid. Use ``raise_if_errors`` to turn a non-empty list into a
``DataFormatError``.

Complexity: each function is O(n) in the size of its input (students, halls,
or blocked seats), with O(n) extra space for the duplicate-detection set.
"""

from __future__ import annotations

from typing import Any

from src.models.hall import Hall
from src.models.student import Student

#: Allowed values for the ``neighbourhood`` configuration key.
VALID_NEIGHBOURHOODS: tuple[str, ...] = ("4", "8")

#: Keys that must appear in the ``weights`` configuration block.
WEIGHT_KEYS: tuple[str, ...] = (
    "w_same_branch",
    "w_consecutive_roll",
    "w_distance_two_conflict",
    "w_wasted_seat",
)

#: Keys that must appear in the ``backtracking`` configuration block.
BACKTRACKING_KEYS: tuple[str, ...] = ("node_limit", "time_limit_seconds")

#: Every allowed top-level configuration key.
CONFIG_KEYS: tuple[str, ...] = (
    "neighbourhood",
    "weights",
    "backtracking",
    "random_seed",
    "output_dir",
)


class DataFormatError(ValueError):
    """Raised when input data or configuration is malformed or invalid."""


def _is_int(value: Any) -> bool:
    """Return True for real integers (``bool`` is excluded)."""
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: Any) -> bool:
    """Return True for ints and floats (``bool`` is excluded)."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_nonempty_str(value: Any) -> bool:
    """Return True for strings that contain a non-whitespace character."""
    return isinstance(value, str) and value.strip() != ""


def raise_if_errors(errors: list[str], context: str) -> None:
    """Raise ``DataFormatError`` listing every message if ``errors`` is non-empty.

    Args:
        errors: Messages returned by a ``validate_*`` function.
        context: Short description of what was validated (used as a heading).
    """
    if errors:
        details = "\n".join("  - " + message for message in errors)
        raise DataFormatError(f"{context}:\n{details}")


def validate_students(students: list[Student]) -> list[str]:
    """Check a student list.

    Verified: list is non-empty; ``sap_id``, ``name`` and ``branch`` are
    non-empty strings; ``sap_id`` values are unique; ``roll_no`` is a
    non-negative integer; ``courses`` is a non-empty collection of non-empty
    strings.

    Returns:
        A list of error messages (empty if valid).

    Time: O(n * c). Space: O(n).
    """
    errors: list[str] = []
    if len(students) == 0:
        errors.append("no students provided")
        return errors

    seen: set[str] = set()
    for index, student in enumerate(students):
        label = f"student #{index + 1}"
        if not _is_nonempty_str(student.sap_id):
            errors.append(f"{label}: sap_id must be a non-empty string")
        else:
            label = f"student {student.sap_id!r}"
            if student.sap_id in seen:
                errors.append(f"{label}: duplicate sap_id")
            seen.add(student.sap_id)
        if not _is_nonempty_str(student.name):
            errors.append(f"{label}: name must be a non-empty string")
        if not _is_nonempty_str(student.branch):
            errors.append(f"{label}: branch must be a non-empty string")
        if not _is_int(student.roll_no) or student.roll_no < 0:
            errors.append(f"{label}: roll_no must be a non-negative integer")
        if len(student.courses) == 0:
            errors.append(f"{label}: must be enrolled in at least one course")
        else:
            for course in student.courses:
                if not _is_nonempty_str(course):
                    errors.append(f"{label}: course codes must be non-empty strings")
                    break
    return errors


def validate_halls(halls: list[Hall]) -> list[str]:
    """Check a hall list.

    Verified: list is non-empty; ``hall_id`` is a non-empty unique string;
    ``rows`` and ``cols`` are integers >= 1; every blocked seat lies inside the
    grid; the hall keeps at least one usable seat.

    Returns:
        A list of error messages (empty if valid).

    Time: O(H + total blocked seats). Space: O(H).
    """
    errors: list[str] = []
    if len(halls) == 0:
        errors.append("no halls provided")
        return errors

    seen: set[str] = set()
    for index, hall in enumerate(halls):
        label = f"hall #{index + 1}"
        if not _is_nonempty_str(hall.hall_id):
            errors.append(f"{label}: hall_id must be a non-empty string")
        else:
            label = f"hall {hall.hall_id!r}"
            if hall.hall_id in seen:
                errors.append(f"{label}: duplicate hall_id")
            seen.add(hall.hall_id)

        dims_ok = True
        if not _is_int(hall.rows) or hall.rows < 1:
            errors.append(f"{label}: rows must be an integer >= 1")
            dims_ok = False
        if not _is_int(hall.cols) or hall.cols < 1:
            errors.append(f"{label}: cols must be an integer >= 1")
            dims_ok = False
        if not dims_ok:
            continue

        bounds_ok = True
        for seat in hall.blocked:
            row, col = seat
            if not (0 <= row < hall.rows and 0 <= col < hall.cols):
                errors.append(
                    f"{label}: blocked seat {row}:{col} is outside the "
                    f"{hall.rows}x{hall.cols} grid"
                )
                bounds_ok = False
        if bounds_ok and hall.capacity() < 1:
            errors.append(f"{label}: every seat is blocked, no usable capacity")
    return errors


def check_capacity(students: list[Student], halls: list[Hall]) -> list[str]:
    """Check hard constraint H5: total capacity must cover all students.

    This is a necessary condition only. Later phases may still need buffer
    seats, which can make an allocation infeasible even when this check passes.

    Returns:
        A list with one message if capacity is insufficient, otherwise empty.

    Time: O(H). Space: O(1).
    """
    total = 0
    for hall in halls:
        total += hall.capacity()
    if total < len(students):
        return [
            f"infeasible: {len(students)} students but only {total} usable seats "
            f"across {len(halls)} halls"
        ]
    return []


def validate_config(config: dict) -> list[str]:
    """Check a configuration dictionary.

    Verified: top-level keys are known and present; ``neighbourhood`` is one of
    ``"4"`` or ``"8"``; ``weights`` holds the four weight keys as numbers >= 0;
    ``backtracking`` holds ``node_limit`` (int >= 1) and
    ``time_limit_seconds`` (number > 0); ``random_seed`` is an int;
    ``output_dir`` is a non-empty string.

    Returns:
        A list of error messages (empty if valid).

    Time: O(1) (fixed number of keys). Space: O(1).
    """
    errors: list[str] = []
    if not isinstance(config, dict):
        return ["configuration must be a JSON object"]

    for key in config:
        if key not in CONFIG_KEYS:
            errors.append(f"unknown configuration key {key!r}")
    for key in CONFIG_KEYS:
        if key not in config:
            errors.append(f"missing configuration key {key!r}")

    if "neighbourhood" in config and config["neighbourhood"] not in VALID_NEIGHBOURHOODS:
        errors.append(
            f"neighbourhood must be one of {list(VALID_NEIGHBOURHOODS)} (as strings), "
            f"got {config['neighbourhood']!r}"
        )

    if "weights" in config:
        weights = config["weights"]
        if not isinstance(weights, dict):
            errors.append("weights must be an object")
        else:
            for key in weights:
                if key not in WEIGHT_KEYS:
                    errors.append(f"unknown weight key {key!r}")
            for key in WEIGHT_KEYS:
                if key not in weights:
                    errors.append(f"missing weight key {key!r}")
                elif not _is_number(weights[key]) or weights[key] < 0:
                    errors.append(f"weight {key!r} must be a number >= 0")

    if "backtracking" in config:
        bt = config["backtracking"]
        if not isinstance(bt, dict):
            errors.append("backtracking must be an object")
        else:
            for key in bt:
                if key not in BACKTRACKING_KEYS:
                    errors.append(f"unknown backtracking key {key!r}")
            for key in BACKTRACKING_KEYS:
                if key not in bt:
                    errors.append(f"missing backtracking key {key!r}")
            if "node_limit" in bt and (not _is_int(bt["node_limit"]) or bt["node_limit"] < 1):
                errors.append("backtracking.node_limit must be an integer >= 1")
            if "time_limit_seconds" in bt and (
                not _is_number(bt["time_limit_seconds"]) or bt["time_limit_seconds"] <= 0
            ):
                errors.append("backtracking.time_limit_seconds must be a number > 0")

    if "random_seed" in config and not _is_int(config["random_seed"]):
        errors.append("random_seed must be an integer")
    if "output_dir" in config and not _is_nonempty_str(config["output_dir"]):
        errors.append("output_dir must be a non-empty string")
    return errors

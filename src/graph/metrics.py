"""Metrics for allocations and for repeated timings.

Pure computations only: nothing here prints or writes files.

Definitions (README section 4, benchmark_results.csv):
    * hall utilisation = seated students / total usable capacity of **all** halls.
    * valid = the allocation satisfies every hard constraint H1 to H5.
    * soft score = weighted penalty from ``grid.scoring`` (lower is better).
"""

from __future__ import annotations

from src.grid.constraints import validate_allocation
from src.grid.scoring import compute_soft_score, soft_breakdown
from src.models.allocation import Allocation
from src.models.hall import Hall
from src.models.student import Student
from src.structures.sorting import merge_sort


def hall_utilisation(allocation: Allocation, halls: list[Hall]) -> float:
    """Return seated students divided by the total usable capacity of all halls.

    Returns 0.0 when the halls have no usable seat.

    Time: O(H + seated). Space: O(1).
    """
    capacity = 0
    for hall in halls:
        capacity += hall.capacity()
    if capacity == 0:
        return 0.0
    return len(allocation.seats) / capacity


def evaluate_allocation(
    allocation: Allocation,
    students: list[Student],
    halls: list[Hall],
    config: dict,
) -> dict:
    """Validate an allocation and collect its quality numbers.

    Args:
        allocation: The seating plan.
        students: All students.
        halls: All halls.
        config: Configuration with ``weights`` and optional ``neighbourhood``.

    Returns:
        A dict with keys ``valid`` (bool), ``violations`` (list of messages),
        ``hall_utilisation``, ``soft_score``, and the counts
        ``same_branch_pairs``, ``consecutive_roll_pairs``, ``distance_two_pairs``,
        ``wasted_seats``, ``buffer_seats``, ``used_halls``, ``seated``.

    Time: O(S * c). Space: O(V + S).
    """
    neighbourhood = config.get("neighbourhood", "4")
    violations = validate_allocation(allocation, students, halls, neighbourhood)
    counts = soft_breakdown(allocation, students, halls, neighbourhood)
    result: dict = {
        "valid": len(violations) == 0,
        "violations": violations,
        "hall_utilisation": hall_utilisation(allocation, halls),
        "soft_score": compute_soft_score(
            allocation, students, halls, config["weights"], neighbourhood
        ),
    }
    result.update(counts)
    return result


def mean(values: list[float]) -> float:
    """Return the arithmetic mean (0.0 for an empty list).

    Time: O(n). Space: O(1).
    """
    if len(values) == 0:
        return 0.0
    total = 0.0
    for value in values:
        total += value
    return total / len(values)


def median(values: list[float]) -> float:
    """Return the median (0.0 for an empty list), using the custom merge sort.

    Time: O(n log n). Space: O(n).
    """
    if len(values) == 0:
        return 0.0
    ordered = merge_sort(values)
    middle = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return float(ordered[middle])
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def stdev(values: list[float]) -> float:
    """Return the sample standard deviation (0.0 for fewer than two values).

    Time: O(n). Space: O(1).
    """
    if len(values) < 2:
        return 0.0
    average = mean(values)
    total = 0.0
    for value in values:
        total += (value - average) ** 2
    return (total / (len(values) - 1)) ** 0.5


def summarize(values: list[float]) -> dict[str, float]:
    """Return ``mean``, ``median``, ``min``, ``max`` and ``stdev`` of ``values``.

    An empty list gives zeros.

    Time: O(n log n). Space: O(n).
    """
    if len(values) == 0:
        return {"mean": 0.0, "median": 0.0, "min": 0.0, "max": 0.0, "stdev": 0.0}
    low = values[0]
    high = values[0]
    for value in values:
        if value < low:
            low = value
        if value > high:
            high = value
    return {
        "mean": mean(values),
        "median": median(values),
        "min": float(low),
        "max": float(high),
        "stdev": stdev(values),
    }

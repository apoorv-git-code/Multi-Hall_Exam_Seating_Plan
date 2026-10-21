"""Custom merge sort.

Used wherever the project needs ordering inside ``algorithms/``, ``graph/`` and
``grid/`` (for example, Welsh-Powell degree ordering). The built-in sorting
helpers are not allowed in those packages (README section 2.3).

Properties:
    * Stable: elements with equal keys keep their original relative order,
      also when ``reverse=True``.
    * Non-destructive: the input list is never modified.
    * Iterative (bottom-up): no recursion, so no recursion-depth limit.
    * Only ``<`` and ``>`` are applied to keys, never to the items themselves.
"""

from __future__ import annotations

from typing import Any, Callable, Optional


def merge_sort(
    items: list,
    key: Optional[Callable[[Any], Any]] = None,
    reverse: bool = False,
) -> list:
    """Return a new list with ``items`` in sorted order.

    Args:
        items: The elements to order.
        key: Optional function mapping an element to its sort key. It is called
            exactly once per element. ``None`` means the element is its own key.
        reverse: If True, sort in descending key order. Equal keys still keep
            their original relative order (stable).

    Returns:
        A new sorted list. ``items`` is unchanged.

    Complexity:
        Time: O(n log n) in the best, average and worst case (n = len(items)),
        plus n calls to ``key``.
        Space: O(n) for two work buffers of (key, item) pairs.
    """
    n = len(items)
    if n < 2:
        return list(items)

    # Decorate once so ``key`` is evaluated n times only.
    if key is None:
        src: list = [(item, item) for item in items]
    else:
        src = [(key(item), item) for item in items]
    dst: list = [None] * n

    width = 1
    while width < n:
        lo = 0
        while lo < n:
            mid = lo + width
            if mid > n:
                mid = n
            hi = lo + 2 * width
            if hi > n:
                hi = n
            i = lo
            j = mid
            k = lo
            while i < mid and j < hi:
                # Take from the right run only when it must come strictly first;
                # on ties the left element wins, which keeps the sort stable.
                if reverse:
                    take_right = src[j][0] > src[i][0]
                else:
                    take_right = src[j][0] < src[i][0]
                if take_right:
                    dst[k] = src[j]
                    j += 1
                else:
                    dst[k] = src[i]
                    i += 1
                k += 1
            while i < mid:
                dst[k] = src[i]
                i += 1
                k += 1
            while j < hi:
                dst[k] = src[j]
                j += 1
                k += 1
            lo = hi
        src, dst = dst, src
        width *= 2

    return [pair[1] for pair in src]

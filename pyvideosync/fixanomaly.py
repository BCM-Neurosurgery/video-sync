import numpy as np
from typing import List, Tuple, Any, Optional


def fix_typei(arr: List[int]) -> List[int]:
    """
    If a lone 0 is flanked by two integers that differ by 2, replaces
    that 0 with the missing middle value. All other entries (including
    zeros at the edges or in larger gaps) are left unchanged.

    Args:
        arr: A list of integers, where 0 marks a single placeholder.

    Returns:
        A new list with any [x, 0, y] gaps turned into [x, x+1, y] if y−x == 2.
    """
    result = arr.copy()
    # skip first and last index since they can't be “between” two numbers
    for i in range(1, len(arr) - 1):
        if arr[i] == 0 and arr[i - 1] + 2 == arr[i + 1]:
            result[i] = arr[i - 1] + 1
    return result


def fix_typeiv(arr: List[int]) -> List[int]:
    """
    Fills leading placeholder values (marked as anything < 128) by counting
    backward from the first “real” value (>= 128).

    Treats all values < 128 as missing (-1).  If the entire list is empty
    returns empty list.  If the maximum value in the list is ≤ 127, assumes
    the sequence is already “just 0..127” and returns a shallow copy.

    Args:
        arr: List[int] — the original sequence, where any x < 128 is a placeholder.

    Returns:
        List[int] — a new list where any leading placeholders have been replaced
        by a backwards-counting sequence ending at the first real value.  All
        subsequent entries (including any interior placeholders) are left as-is
        (i.e. ≥128 remain unchanged, <128 become -1).
    """
    seq = arr.copy()
    if not seq:
        return []
    # if everything is ≤ 127, nothing to do
    if max(seq) <= 127:
        return seq.copy()

    # step 1: map placeholders
    rep: List[int] = [x if x >= 128 else -1 for x in seq]
    # step 2: find first real value
    first_valid_idx: Optional[int] = next(
        (i for i, x in enumerate(rep) if x != -1), None
    )
    if first_valid_idx is None:
        # no real values at all
        return []

    first_val = rep[first_valid_idx]
    result: List[int] = []

    # fill any leading placeholders by counting backward
    for k in range(first_valid_idx):
        result.append(first_val - (first_valid_idx - k))

    # append the first real value
    result.append(first_val)

    # append the rest unchanged
    result.extend(rep[first_valid_idx + 1 :])

    return result


def fix_discontinuities(arr: List[int]) -> List[int]:
    """
    Repairs type I to type IV anomalies in a 1-D integer list.

    Anomalies:
        1. Type I: [20323583, 0, 20323585]
        2. Type II: [20332543, 0, 1, 2, 3, ..., 127, 0, 20332673, 20332674]
        3. Type III: [30133802, 30133804, 30133805]
        4. Type IV: [-1, 20323572]

    Observation:
        1. The anomalies usually go from -1 to 127, the maximum is 127.
        2. There shouldn't be adjacent 0s.
        3. -1 appears at the beginning of the list; there can be adjacent -1s.

    Heuristic approach:
        - Replace everything < 128 with -1.
        - If max value ≤ 127, or list is empty, return early.
        - Fill leading -1s based on the first valid number.
        - Fill -1 gaps in the middle exhaustively between surrounding valid numbers.
        - Gaps between valid numbers > 1 are filled exhaustively.

    Args:
        arr (List[int]): 1-D list of integers.

    Returns:
        List[int]: Gap-filled integer sequence.
    """
    # Copy to avoid mutating the input
    seq = arr.copy()
    if not seq:
        return []

    # If everything is ≤ 127, assume it's already "just 0..127" and do nothing
    if max(seq) <= 127:
        return seq.copy()

    # Step 1: replace small values with -1
    rep = [-1 if x < 128 else x for x in seq]
    n = len(rep)
    result: List[int] = []

    # Step 2: find the first real value (> -1)
    first_valid_idx = next((i for i, x in enumerate(rep) if x != -1), None)
    if first_valid_idx is None:
        return []

    first_val = rep[first_valid_idx]
    # Fill any leading -1s by counting backward from the first valid
    for k in range(first_valid_idx):
        result.append(first_val - (first_valid_idx - k))
    result.append(first_val)

    prev = first_val
    i = first_valid_idx + 1

    # Step 3: walk through the rest
    while i < n:
        cur = rep[i]
        if cur == -1:
            # find next valid
            j = i + 1
            while j < n and rep[j] == -1:
                j += 1
            if j < n:
                next_val = rep[j]
                # fill all the in‑between values
                for fill in range(prev + 1, next_val):
                    result.append(fill)
                result.append(next_val)
                prev = next_val
                i = j + 1
            else:
                # trailing -1s: fill forward from prev
                trailing_count = n - i
                for offset in range(1, trailing_count + 1):
                    result.append(prev + offset)
                break
        else:
            # a real value; if there's a numeric gap, fill it
            if cur > prev + 1:
                for fill in range(prev + 1, cur):
                    result.append(fill)
            result.append(cur)
            prev = cur
            i += 1

    return result


def fix_discontinuities_with_fill(
    arr: List[int], arr2: List[Any], fill_number: Any
) -> Tuple[List[int], List[Any]]:
    """Fixes discontinuities in one array and fills corresponding positions in a second array.

    Wherever `arr` is “fixed” or interpolated by `fix_discontinuities()`, this function
    will insert `fill_number` into `arr2` at the same positions.

    Args:
        arr (List[int]): Original list of integers, possibly with gaps.
        arr2 (List[Any]): A parallel list (same length as `arr`) whose values should be
                          carried over when `arr` values match, or replaced by `fill_number`
                          for each inserted/interpolated entry.
        fill_number (Any): The value to insert into the second list wherever `arr` was
                           interpolated.

    Returns:
        List[Any]:
            - The second element is a new list the same length as the fixed array, where
              original `arr2` values are preserved when `arr` wasn't changed, and
              `fill_number` is used for each new/interpolated entry.

    Raises:
        ValueError: If `arr` and `arr2` are not the same length.
    """
    if len(arr) != len(arr2):
        raise ValueError("`arr` and `arr2` must be the same length")

    # Assume fix_discontinuities is already defined elsewhere
    fixed_arr = fix_discontinuities(arr)

    filled_arr2: List[Any] = []
    j = 0  # pointer into the original arr/arr2
    n_orig = len(arr)

    for v in fixed_arr:
        if j < n_orig and v == arr[j]:
            # this value came from the original array: carry over arr2[j]
            filled_arr2.append(arr2[j])
            j += 1
        else:
            # this value was interpolated/inserted: use fill_number
            filled_arr2.append(fill_number)

    return filled_arr2

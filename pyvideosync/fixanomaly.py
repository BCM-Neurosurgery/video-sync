import numpy as np
from typing import List


def fix_discontinuities_heuristic(arr: List[int]) -> List[int]:
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


def fix_discontinuities(arr: np.array) -> list:
    """Repairs incremental discontinuities in a 1-D integer array.

    The function identifies and fixes two specific anomaly types in an otherwise incrementally increasing integer array:

    - **Type I Discontinuity**: Single zero occurring between two integers that differ by exactly 2.
      Example: `[1, 2, 3, 0, 5]` becomes `[1, 2, 3, 4, 5]`.

    - **Type II Discontinuity**: Sequence reset starting from zero and incrementally counting up again from 1.
      Example: `[7, 8, 0, 1, 2]` becomes `[7, 8, 9, 10, 11]`.

    Args:
        arr (list or np.ndarray): The input array containing integer values. It is expected
            to be primarily incremental but may contain anomalies as described above.

    Returns:
        list: A corrected array with discontinuities repaired, maintaining incremental continuity.

    Examples:
        >>> fix_discontinuities([1, 2, 3, 0, 5, 6, 7, 0, 9])
        [1, 2, 3, 4, 5, 6, 7, 8, 9]

        >>> fix_discontinuities([5, 6, 7, 8, 0, 1, 2, 3, 4])
        [5, 6, 7, 8, 9, 10, 11, 12, 13]

        >>> fix_discontinuities([2, 0, 4, 0, 6])
        [2, 3, 4, 5, 6]

    Notes:
        - If the discontinuity cannot be resolved (e.g., zero at the very end with no following numbers),
          the function leaves the original value(s) unchanged.
        - The function makes a copy of the input array to avoid side-effects.
    """
    arr = np.array(arr, dtype=int).copy()
    n = len(arr)
    i = 1

    while i < n - 1:
        # Detect Type I discontinuity
        if (
            arr[i] == 0
            and arr[i - 1] != 0
            and arr[i + 1] != 0
            and arr[i + 1] - arr[i - 1] == 2
        ):
            arr[i] = arr[i - 1] + 1
            i += 1
            continue

        # Detect Type II discontinuity
        if arr[i] == 0 and arr[i + 1] == 1:
            # Found start of type II discontinuity
            fix_start = i
            fix_val = arr[i - 1] + 1
            j = i
            while j < n and arr[j] == (j - i):
                arr[j] = fix_val
                fix_val += 1
                j += 1
            i = j
            continue

        i += 1

    return arr.tolist()


def fill_array_gaps(arr: np.ndarray) -> list:
    """Fills numeric gaps in an integer array, handling zeros and negative placeholders.

    Given a 1-D integer array possibly containing gaps, zeros, or placeholder negatives (-1),
    this function returns a fully continuous integer sequence from the first valid (positive)
    number to the last number, filling in all missing intermediate integers.

    Args:
        arr (Union[List[int], np.ndarray]): Array potentially containing zeros, gaps, or -1 placeholders.

    Returns:
        List[int]: Continuous sequence of integers from first valid number to the last number.

    Examples:
        >>> fill_array_gaps([2844396, 2844399, 2844401])
        [2844396, 2844397, 2844398, 2844399, 2844400, 2844401]

        >>> fill_array_gaps([2844411, 0, 2844418, 2844420])
        [2844411, 2844412, 2844413, 2844414, 2844415, 2844416, 2844417, 2844418, 2844419, 2844420]

        >>> fill_array_gaps([-1, -1, -1, 4, 5, 6, 7, 0, 12])
        [4, 5, 6, 7, 8, 9, 10, 11, 12]

        >>> fill_array_gaps([-1, 0, -1, 0])
        []
    """
    arr = np.array(arr)

    # Identify the first valid positive integer as the starting point
    valid_indices = np.where(arr > 0)[0]

    if valid_indices.size == 0:
        # No valid starting point found
        return []

    start_index = valid_indices[0]
    start = arr[start_index]
    end = arr[valid_indices[-1]]

    filled_array = np.arange(start, end + 1).tolist()

    return filled_array

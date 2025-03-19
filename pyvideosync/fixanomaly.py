import numpy as np


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

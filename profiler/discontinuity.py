def detect_discontinuities(data):
    """
    Detect discontinuities in a sequence of numerical data.

    This function processes a list of numerical data, identifies zeros as discontinuities,
    and classifies them into Type I, Type II, and Type III discontinuities based on the values
    immediately following the zero or the difference between consecutive numbers. It also records
    the lengths of continuous non-zero sections between the discontinuities.

    - **Type I discontinuity**: Occurs when the data drops to zero and then increases to a value greater than 1.
    - **Type II discontinuity**: Occurs when the data resets from zero to 1.
    - **Type III discontinuity**: Occurs when the difference between the next number and the current number is greater than 1.

    Parameters
    ----------
    data : list of int or float
        The input data sequence to analyze.

    Returns
    -------
    type_i_count : int
        The number of Type I discontinuities detected.
    type_ii_count : int
        The number of Type II discontinuities detected.
    type_iii_count : int
        The number of Type III discontinuities detected.
    type_iii_differences : dict
        A dictionary mapping the jump sizes to their counts for Type III discontinuities.
    continuous_sections : list of int
        A list containing the lengths of continuous non-zero sections between the discontinuities.
    """
    type_i_count = 0
    type_ii_count = 0
    type_iii_count = 0
    type_iii_differences = {}
    i = 0
    while i < len(data) - 1:
        if data[i] == 0:
            if data[i + 1] > 0:
                if data[i + 1] == 1:
                    type_ii_count += 1
                else:
                    type_i_count += 1

        else:
            diff = data[i + 1] - data[i]
            if diff > 1:
                type_iii_count += 1
                diff = int(diff)
                if diff in type_iii_differences:
                    type_iii_differences[diff] += 1
                else:
                    type_iii_differences[diff] = 1
        i += 1
    return type_i_count, type_ii_count, type_iii_count, type_iii_differences

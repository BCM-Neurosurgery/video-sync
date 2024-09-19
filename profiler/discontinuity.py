def detect_discontinuities(data):
    """
    Detect discontinuities in a sequence of numerical data.

    This function processes a list of numerical data, identifies zeros, -1s, and large differences as discontinuities,
    and classifies them into Type I, Type II, Type III, and Type IV discontinuities based on specific conditions.
    It also records the lengths of continuous non-zero sections between the discontinuities.

    - **Type I discontinuity**: Occurs when the data drops to zero and then increases to a value greater than 1.
    - **Type II discontinuity**: Occurs when the data resets from zero to 1.
    - **Type III discontinuity**: Occurs when the difference between consecutive numbers is greater than 1.
    - **Type IV discontinuity**: Occurs when the data hits -1.

    Parameters
    ----------
    data : list of int or float
        The input data sequence to analyze.

    Returns
    -------
    results : dict
        A dictionary containing counts, gap lengths, and differences for each type of discontinuity.
    """
    results = {
        "type_i": {"count": 0, "gaps": []},
        "type_ii": {"count": 0, "gaps": []},
        "type_iii": {"count": 0, "gaps": [], "differences": {}},
        "type_iv": {"count": 0, "gaps": []},
    }

    continuous_length = 0
    last_discontinuity_type = None  # Track the type of the last detected discontinuity

    i = 0
    while i < len(data) - 1:
        continuous_length += 1
        if data[i] == 0:
            if data[i + 1] > 0:
                if data[i + 1] == 1:
                    results["type_ii"]["count"] += 1
                    results["type_ii"]["gaps"].append(continuous_length)
                    last_discontinuity_type = "type_ii"
                else:
                    results["type_i"]["count"] += 1
                    results["type_i"]["gaps"].append(continuous_length)
                    last_discontinuity_type = "type_i"
            continuous_length = 0
        elif data[i] == -1:
            results["type_iv"]["count"] += 1
            results["type_iv"]["gaps"].append(continuous_length)
            last_discontinuity_type = "type_iv"
            continuous_length = 0
        else:
            diff = data[i + 1] - data[i]
            if diff > 1:
                results["type_iii"]["count"] += 1
                diff = int(diff)
                if diff in results["type_iii"]["differences"]:
                    results["type_iii"]["differences"][diff] += 1
                else:
                    results["type_iii"]["differences"][diff] = 1
                results["type_iii"]["gaps"].append(continuous_length)
                last_discontinuity_type = "type_iii"
                continuous_length = 0
        i += 1

    # Handle the last continuous segment
    if continuous_length > 0 and last_discontinuity_type:
        # Append to the last detected discontinuity type
        results[last_discontinuity_type]["gaps"].append(continuous_length)

    return results

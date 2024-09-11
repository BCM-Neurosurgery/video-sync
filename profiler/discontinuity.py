def detect_discontinuities(data):
    type_i_count = 0
    type_ii_count = 0
    continuous_sections = []

    start_idx = 0
    for i in range(1, len(data)):
        if data[i] == 0:
            # Check if this is a Type I or Type II discontinuity
            if i + 1 < len(data) and data[i + 1] > 0:
                if data[i + 1] == 1:
                    type_ii_count += 1  # Reset from 0 and increase
                else:
                    type_i_count += 1  # Dropped to 0, but not reset from 0

            # Record the length of the continuous section
            continuous_sections.append(i - start_idx)
            start_idx = i + 1  # Move to the next section

    # Add the last section if it's continuous till the end
    if start_idx < len(data):
        continuous_sections.append(len(data) - start_idx)

    return type_i_count, type_ii_count, continuous_sections

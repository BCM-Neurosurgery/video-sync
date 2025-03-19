from pyvideosync.fixanomaly import fix_discontinuities


def test_type_i_discontinuity():
    arr = [1, 2, 3, 0, 5, 6, 7, 0, 9]
    fixed = fix_discontinuities(arr)
    assert fixed == [1, 2, 3, 4, 5, 6, 7, 8, 9]


def test_type_ii_discontinuity():
    arr = [1, 2, 3, 4, 5, 6, 7, 8, 0, 1, 2, 3, 4, 0, 15, 16, 17]
    fixed = fix_discontinuities(arr)
    assert fixed == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17]


def test_combined_discontinuities():
    arr = [10, 11, 0, 13, 14, 0, 1, 2, 3, 4, 0, 21]
    fixed = fix_discontinuities(arr)
    assert fixed == [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21]


def test_no_discontinuities():
    arr = [5, 6, 7, 8, 9, 10]
    fixed = fix_discontinuities(arr)
    assert fixed == [5, 6, 7, 8, 9, 10]


def test_edge_case_at_end():
    arr = [1, 2, 3, 4, 0]
    fixed = fix_discontinuities(arr)
    assert fixed == [
        1,
        2,
        3,
        4,
        0,
    ]  # Cannot fix last element alone; no changes expected


def test_multiple_type_i():
    arr = [2, 0, 4, 0, 6, 0, 8]
    fixed = fix_discontinuities(arr)
    assert fixed == [2, 3, 4, 5, 6, 7, 8]


def test_real_case_1():
    arr = [2775934, 2775935, 0, 2775937, 2775938, 2775939]
    fixed = fix_discontinuities(arr)
    assert fixed == [2775934, 2775935, 2775936, 2775937, 2775938, 2775939]

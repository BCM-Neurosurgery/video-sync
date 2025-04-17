from pyvideosync.fixanomaly import fix_discontinuities_heuristic
import numpy as np
import pytest

### Edge Case
empty_case = []
empty_case_expected = []
empty_case_2 = [0]
empty_case_2_expected = [0]
negative_case = [-1, -1, -1, -1, -1]
negative_case_expected = [-1, -1, -1, -1, -1]
small_case_1 = [1, 2, 3, 4, 5]
small_case_1_expected = [1, 2, 3, 4, 5]

### TYPE I
type_i_case_1 = [20323583, 0, 20323585]
type_i_case_1_expected = [20323583, 20323584, 20323585]

type_i_case_2 = [20323583, 0, 20323585, 0, 20323587]
type_i_case_2_expected = [20323583, 20323584, 20323585, 20323586, 20323587]

### TYPE II
type_ii_case_1 = [20332543] + [i for i in range(128)] + [0] + [20332673]
type_ii_case_1_expected = [i for i in range(20332543, 20332673 + 1)]

type_ii_case_2 = [5537789] + [i for i in range(3, 124, 3)] + [5537923]
type_ii_case_2_expected = [i for i in range(5537789, 5537923 + 1)]

### TYPE III
type_iii_case_1 = [20323583, 20323585, 20323589, 20323592]
type_iii_case_1_expected = [i for i in range(20323583, 20323592 + 1)]

### TYPE IV
type_iv_case_1 = [-1, -1, 20323572]
type_iv_case_1_expected = [i for i in range(20323570, 20323572 + 1)]

type_iv_case_2 = [-1, 20323572]
type_iv_case_2_expected = [i for i in range(20323571, 20323572 + 1)]

### Comprehensive Test Cases
comp_test_1 = (
    [-1, -1, 20323583, 0, 20323585, 0, 20323587, 20323588, 20323589, 20323592, 20323597]
    + [i for i in range(1, 128, 3)]
    + [20323723]
)
comp_test_1_expected = [i for i in range(20323581, 20323723 + 1)]

comp_test_2 = (
    [-1, -1, -1, 20323587, 0, 20323589, 20323592, 20323597]
    + [i for i in range(2, 128, 2)]
    + [20323723]
)
comp_test_2_expected = [i for i in range(20323584, 20323723 + 1)]

comp_test_3 = [127, 0, 20323585, 20323586, 20323587]
comp_test_3_expected = [i for i in range(20323583, 20323587 + 1)]

comp_test_4 = [5685247] + [i for i in range(127)]
comp_test_4_expected = [5685247] + [5685248 + i for i in range(127)]


@pytest.mark.parametrize(
    "arr, expected",
    [
        (empty_case, empty_case_expected),
        (empty_case_2, empty_case_2_expected),
        (negative_case, negative_case_expected),
        (small_case_1, small_case_1_expected),
        (type_i_case_1, type_i_case_1_expected),
        (type_i_case_2, type_i_case_2_expected),
        (type_ii_case_1, type_ii_case_1_expected),
        (type_ii_case_2, type_ii_case_2_expected),
        (type_iii_case_1, type_iii_case_1_expected),
        (type_iv_case_1, type_iv_case_1_expected),
        (type_iv_case_2, type_iv_case_2_expected),
        (comp_test_1, comp_test_1_expected),
        (comp_test_2, comp_test_2_expected),
        (comp_test_3, comp_test_3_expected),
        (comp_test_4, comp_test_4_expected),
    ],
)
def test_fix_discontinuities(arr, expected):
    result = fix_discontinuities_heuristic(arr)
    assert result == expected

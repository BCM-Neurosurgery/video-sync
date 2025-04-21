from pyvideosync.fixanomaly import fix_discontinuities_with_fill
import pytest

### TYPE II
type_ii_case_1_serial = [20332543] + [i for i in range(128)] + [0] + [20332673]
type_ii_case_1_frame = [10] + [i + 11 for i in range(128)] + [139] + [140]
fill_number = 0
type_ii_case_1_frame_expected = [10] + [0] * 128 + [139] + [140]

type_ii_case_2_serial = [5537789] + [i for i in range(3, 124, 3)] + [5537923]
type_ii_case_2_frame = [150] + [i + 151 for i in range(41)] + [192]
fill_number = 0
type_ii_case_2_frame_expected = [150] + [0] * 41 + [192]

### TYPE III
type_iii_case_1_serial = [20323583, 20323585, 20323589, 20323592]
type_iii_case_1_frame = [101, 102, 103, 104]
fill_number = 0
type_iii_case_1_frame_expected = [101, 0, 102, 0, 0, 0, 103, 0, 0, 104]


@pytest.mark.parametrize(
    "arr, arr2, fill_number, expected_filled",
    [
        (
            type_ii_case_1_serial,
            type_ii_case_1_frame,
            fill_number,
            type_ii_case_1_frame_expected,
        ),
        (
            type_ii_case_2_serial,
            type_ii_case_2_frame,
            fill_number,
            type_ii_case_2_frame_expected,
        ),
    ],
)
def test_fix_discontinuities_with_fill(arr, arr2, fill_number, expected_filled):
    filled2 = fix_discontinuities_with_fill(arr, arr2, fill_number)
    assert filled2 == expected_filled

import pytest
from pyvideosync.fixanomaly import fix_typeiv


@pytest.mark.parametrize(
    "input_list, expected",
    [
        # empty list
        ([], []),
        # all values ≤ 127 → returned as-is
        ([0, 1, 2, 3], [0, 1, 2, 3]),
        ([50, 127, 10], [50, 127, 10]),
        # single real value
        ([129], [129]),
        # leading -1s filled backward from first real (130)
        ([0, 0, 130, 131, 132], [128, 129, 130, 131, 132]),
        # mix of small placeholders and interior -1
        ([5, 10, 200, 201, 0, 202], [198, 199, 200, 201, -1, 202]),
        # placeholder in middle after filling leading
        ([0, 0, 130, 0, 131], [128, 129, 130, -1, 131]),
        # first real at position 1
        ([127, 128], [127, 128]),
    ],
)
def test_fix_typeiv(input_list, expected):
    assert fix_typeiv(input_list) == expected

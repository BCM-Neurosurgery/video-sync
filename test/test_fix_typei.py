import pytest
from pyvideosync.fixanomaly import fix_typei


@pytest.mark.parametrize(
    "input_list, expected",
    [
        # basic single‐zero gap
        ([100, 0, 102], [100, 101, 102]),
        # two single‐zero gaps in one list
        ([100, 0, 102, 0, 104], [100, 101, 102, 103, 104]),
        # gap ≠ 2 → leave zero alone
        ([100, 0, 103], [100, 0, 103]),
        # zeros at edges: no fill
        ([0, 2], [0, 2]),
        # no zeros → unchanged
        ([1, 2, 3, 4], [1, 2, 3, 4]),
        # empty or single‐element lists
        ([], []),
        ([0], [0]),
        ([42], [42]),
        # consecutive zeros → unchanged
        ([200, 0, 0, 203], [200, 0, 0, 203]),
        # zero in middle but neighbors don’t differ by 2
        ([10, 0, 12, 0, 15], [10, 11, 12, 0, 15]),
    ],
)
def test_fix_typei(input_list, expected):
    assert fix_typei(input_list) == expected

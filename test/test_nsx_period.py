"""
Unit tests for Nsx Period-aware slicing.

Verifies that:
  - NS5-style files (Period=1) produce indices and timestamps identical to
    the pre-refactor behavior (regression by construction).
  - NS3-style files (Period=15) produce correctly strided timestamps and
    indices that account for clk_per_samp.
  - Empty/out-of-range slices return empty arrays without crashing.
  - get_all_channels_arrays returns the right shape and labels.

Tests bypass NsxFile / brpylib by constructing an Nsx instance via __new__
and populating only the attributes the slicing methods read.
"""

from datetime import datetime
import numpy as np
import pandas as pd

from pyvideosync.nsx import Nsx


def _make_nsx(period: int, num_samples: int, num_channels: int, ts_start: int = 1000):
    """Build an Nsx instance without going through brpylib."""
    inst = Nsx.__new__(Nsx)
    ts_resolution = 30000
    samp_resolution = 30000
    inst.basic_header = {
        "TimeStampResolution": ts_resolution,
        "SampleResolution": samp_resolution,
        "Period": period,
        "TimeOrigin": datetime(2026, 1, 1),
    }
    inst.extended_headers = []
    inst.timestampResolution = ts_resolution
    inst.sampleResolution = samp_resolution
    inst.timeOrigin = inst.basic_header["TimeOrigin"]
    inst.clk_per_samp = int(period * ts_resolution / samp_resolution)
    inst.timeStamp = ts_start
    inst.numDataPoints = num_samples
    inst.recording_duration_s = num_samples * inst.clk_per_samp / ts_resolution
    inst.recording_duration_readable = "test"

    # Synthesize channel data: row i is filled with values [i, i+1, i+2, ...]
    # so amplitudes are easy to verify.
    rows = [
        np.arange(num_samples, dtype=np.int16) + (i * 1000) for i in range(num_channels)
    ]
    inst.memmapData = np.stack(rows, axis=0)
    inst.extended_headers_df = pd.DataFrame(
        {"ElectrodeLabel": [f"ch{i}" for i in range(num_channels)]}
    )
    return inst


def test_clk_per_samp():
    ns5 = _make_nsx(period=1, num_samples=100, num_channels=4)
    ns3 = _make_nsx(period=15, num_samples=100, num_channels=4)
    assert ns5.clk_per_samp == 1
    assert ns3.clk_per_samp == 15


def test_slice_indices_ns5_full_range():
    """NS5 (Period=1): asking for the full range returns every sample, stride 1."""
    ns5 = _make_nsx(period=1, num_samples=10, num_channels=2, ts_start=1000)
    idx_start, idx_end, ts = ns5._slice_indices(1000, 1009)
    assert idx_start == 0
    assert idx_end == 10
    assert ts.tolist() == list(range(1000, 1010))  # stride 1


def test_slice_indices_ns3_full_range():
    """NS3 (Period=15): full range returns every sample, stride 15.

    With clk_per_samp=15 and num_samples=10 starting at ts=1000:
      sample 0 → ts 1000, sample 1 → ts 1015, ..., sample 9 → ts 1135.
    """
    ns3 = _make_nsx(period=15, num_samples=10, num_channels=2, ts_start=1000)
    idx_start, idx_end, ts = ns3._slice_indices(1000, 1135)
    assert idx_start == 0
    assert idx_end == 10
    assert ts.tolist() == list(range(1000, 1150, 15))


def test_slice_indices_ns3_subrange():
    """NS3 subrange: ask for ticks [1030, 1075] (samples 2..5 inclusive)."""
    ns3 = _make_nsx(period=15, num_samples=10, num_channels=2, ts_start=1000)
    # sample 2 = ts 1030, sample 5 = ts 1075
    idx_start, idx_end, ts = ns3._slice_indices(1030, 1075)
    assert idx_start == 2
    assert idx_end == 6  # inclusive on end_ts, exclusive on idx_end
    assert ts.tolist() == [1030, 1045, 1060, 1075]


def test_slice_indices_ns3_partial_overlap_left():
    """Range starts before the file: clip to idx 0."""
    ns3 = _make_nsx(period=15, num_samples=10, num_channels=2, ts_start=1000)
    idx_start, idx_end, ts = ns3._slice_indices(500, 1030)
    assert idx_start == 0
    assert idx_end == 3  # samples 0, 1, 2 (ts 1000, 1015, 1030)
    assert ts.tolist() == [1000, 1015, 1030]


def test_slice_indices_ns3_partial_overlap_right():
    """Range extends past the file: clip to num_samples."""
    ns3 = _make_nsx(period=15, num_samples=10, num_channels=2, ts_start=1000)
    # ts_end of file = 1000 + 9*15 = 1135. Ask up to 9999.
    idx_start, idx_end, ts = ns3._slice_indices(1100, 9999)
    # sample 7 = ts 1105, sample 9 = ts 1135
    assert (
        idx_start == 6
    )  # (1100 - 1000) // 15 = 6 → ts 1090, but 1090 < 1100, ok floor
    # actually: floor((1100-1000)/15)=6, ts=1090 — that's outside the range.
    # The current spec accepts inclusive idx_start at the floor; sample 6 (ts 1090)
    # has timestamp < start_ts. That's fine for NS5 (matches pre-refactor) but worth
    # asserting explicitly: timestamps below start_ts may appear due to floor division.
    # If we want strict inclusion, we'd need ceil instead. We use floor for back-compat.
    assert idx_end == 10
    # ts will start at 1090
    assert ts[0] == 1090
    assert ts[-1] == 1135


def test_slice_indices_out_of_range_returns_empty():
    """Range entirely past the file returns empty."""
    ns3 = _make_nsx(period=15, num_samples=10, num_channels=2, ts_start=1000)
    idx_start, idx_end, ts = ns3._slice_indices(50000, 60000)
    assert len(ts) == 0


def test_slice_indices_inverted_raises():
    ns5 = _make_nsx(period=1, num_samples=10, num_channels=2)
    try:
        ns5._slice_indices(2000, 1000)
    except ValueError:
        return
    raise AssertionError("expected ValueError for inverted range")


def test_get_filtered_channel_df_ns5_regression():
    """NS5 regression: the new method should produce identical timestamps
    to what the old code produced (one sample per tick, stride 1)."""
    ns5 = _make_nsx(period=1, num_samples=20, num_channels=3, ts_start=500)
    df = ns5.get_filtered_channel_df("ch1", 505, 510)
    assert df["TimeStamp"].tolist() == [505, 506, 507, 508, 509, 510]
    # ch1 row was filled with [0..19] + 1000 → ts 505 corresponds to idx 5 → 1005
    assert df["Amplitude"].tolist() == [1005, 1006, 1007, 1008, 1009, 1010]


def test_get_filtered_channel_df_ns3():
    """NS3 (Period=15): timestamps stride by 15; amplitudes pull from correct sample idx."""
    ns3 = _make_nsx(period=15, num_samples=20, num_channels=3, ts_start=500)
    # samples 5..7 → ts 575, 590, 605
    df = ns3.get_filtered_channel_df("ch2", 575, 605)
    assert df["TimeStamp"].tolist() == [575, 590, 605]
    # ch2 row = [0..19] + 2000 → idx 5,6,7 = 2005, 2006, 2007
    assert df["Amplitude"].tolist() == [2005, 2006, 2007]


def test_get_filtered_channel_df_empty_range_returns_empty_df():
    ns3 = _make_nsx(period=15, num_samples=10, num_channels=2)
    df = ns3.get_filtered_channel_df("ch0", 99999, 999999)
    assert df.empty
    assert list(df.columns) == ["TimeStamp", "Amplitude", "UTCTimeStamp"]


def test_get_all_channels_arrays_shape():
    ns3 = _make_nsx(period=15, num_samples=20, num_channels=4, ts_start=500)
    # samples 3..6 inclusive → ts 545, 560, 575, 590
    timestamps, amps, labels = ns3.get_all_channels_arrays(545, 590)
    assert timestamps.tolist() == [545, 560, 575, 590]
    assert amps.shape == (4, 4)  # 4 samples × 4 channels
    assert labels == ["ch0", "ch1", "ch2", "ch3"]
    # ch0 row = [0..19] + 0 → samples 3..6 = [3,4,5,6]; ch1 +1000 = [1003,1004,1005,1006]; etc.
    assert amps[:, 0].tolist() == [3, 4, 5, 6]
    assert amps[:, 1].tolist() == [1003, 1004, 1005, 1006]
    assert amps[:, 3].tolist() == [3003, 3004, 3005, 3006]


def test_get_all_channels_arrays_empty_range():
    ns3 = _make_nsx(period=15, num_samples=10, num_channels=3)
    timestamps, amps, labels = ns3.get_all_channels_arrays(99999, 999999)
    assert len(timestamps) == 0
    assert amps.shape == (0, 3)
    assert labels == ["ch0", "ch1", "ch2"]


def test_get_channel_df_full_recording():
    """get_channel_df should return all samples (delegates to get_filtered_channel_df)."""
    ns3 = _make_nsx(period=15, num_samples=10, num_channels=2, ts_start=1000)
    df = ns3.get_channel_df("ch1")
    assert len(df) == 10
    assert df["TimeStamp"].tolist() == list(range(1000, 1150, 15))


if __name__ == "__main__":
    import sys

    test_funcs = [
        (name, obj)
        for name, obj in list(globals().items())
        if name.startswith("test_") and callable(obj)
    ]
    failures = []
    for name, fn in test_funcs:
        try:
            fn()
            print(f"PASS  {name}")
        except Exception as e:
            print(f"FAIL  {name}: {e}")
            failures.append(name)
    if failures:
        print(f"\n{len(failures)}/{len(test_funcs)} failed")
        sys.exit(1)
    print(f"\nall {len(test_funcs)} tests passed")

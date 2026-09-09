"""
Round-trip and validation tests for write_ns3_sidecar.

No NSP files needed — uses synthetic numpy arrays.
"""

import os
import tempfile

import h5py
import numpy as np

from pyvideosync.sidecar import write_ns3_sidecar


def _make_synthetic(n_samples=400, n_channels=5, ts_start=1000, period=15):
    timestamps = np.arange(
        ts_start, ts_start + n_samples * period, period, dtype=np.uint64
    )
    amplitudes = np.random.randint(
        -1000, 1000, size=(n_samples, n_channels), dtype=np.int16
    )
    labels = [f"elec{i:02d}" for i in range(n_channels)]
    attrs = {
        "samp_per_s": 2000.0,
        "period": period,
        "timestamp_resolution": 30000,
        "time_origin": "2026-01-01T00:00:00",
    }
    return timestamps, amplitudes, labels, attrs


def test_round_trip():
    timestamps, amplitudes, labels, attrs = _make_synthetic()
    with tempfile.NamedTemporaryFile(suffix=".h5", delete=False) as tmp:
        path = tmp.name
    try:
        write_ns3_sidecar(path, timestamps, amplitudes, labels, attrs)

        with h5py.File(path, "r") as f:
            ts = f["timestamps"][:]
            amps = f["amplitudes"][:]
            chan_labels = [
                s.decode() if isinstance(s, bytes) else s
                for s in f["amplitudes"].attrs["channel_labels"]
            ]
            for k, v in attrs.items():
                assert f.attrs[k] == v, f"attr {k} mismatch"

        assert ts.dtype == np.uint64
        assert amps.dtype == np.int16
        assert ts.tolist() == timestamps.tolist()
        np.testing.assert_array_equal(amps, amplitudes)
        assert chan_labels == labels
    finally:
        os.unlink(path)


def test_compression_actually_compresses():
    """Gzip compression should noticeably shrink the on-disk size."""
    timestamps, amplitudes, labels, attrs = _make_synthetic(
        n_samples=20000, n_channels=32
    )
    # Make the data more compressible (constant-ish per channel)
    amplitudes = np.tile(np.arange(32, dtype=np.int16), (20000, 1))
    with tempfile.NamedTemporaryFile(suffix=".h5", delete=False) as tmp:
        path = tmp.name
    try:
        write_ns3_sidecar(path, timestamps, amplitudes, labels, attrs)
        size_on_disk = os.path.getsize(path)
        raw_bytes = amplitudes.nbytes  # 20000 * 32 * 2 = ~1.28 MB
        # Should be at least 5x smaller for repetitive data
        assert (
            size_on_disk < raw_bytes // 5
        ), f"compression weak: {size_on_disk} >= {raw_bytes // 5}"
    finally:
        os.unlink(path)


def test_shape_mismatch_raises():
    timestamps, amplitudes, labels, attrs = _make_synthetic()
    with tempfile.NamedTemporaryFile(suffix=".h5", delete=False) as tmp:
        path = tmp.name
    try:
        # Truncate timestamps so row counts disagree
        try:
            write_ns3_sidecar(path, timestamps[:10], amplitudes, labels, attrs)
        except ValueError:
            return
        raise AssertionError("expected ValueError for row mismatch")
    finally:
        if os.path.exists(path):
            os.unlink(path)


def test_label_count_mismatch_raises():
    timestamps, amplitudes, labels, attrs = _make_synthetic()
    with tempfile.NamedTemporaryFile(suffix=".h5", delete=False) as tmp:
        path = tmp.name
    try:
        try:
            write_ns3_sidecar(path, timestamps, amplitudes, labels[:2], attrs)
        except ValueError:
            return
        raise AssertionError("expected ValueError for label count mismatch")
    finally:
        if os.path.exists(path):
            os.unlink(path)


def test_1d_amplitudes_raises():
    timestamps, _, labels, attrs = _make_synthetic()
    with tempfile.NamedTemporaryFile(suffix=".h5", delete=False) as tmp:
        path = tmp.name
    try:
        try:
            write_ns3_sidecar(
                path,
                timestamps,
                np.zeros(len(timestamps), dtype=np.int16),
                labels,
                attrs,
            )
        except ValueError:
            return
        raise AssertionError("expected ValueError for 1D amplitudes")
    finally:
        if os.path.exists(path):
            os.unlink(path)


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

"""Synthetic tests for persisted frame-to-neural mappings."""

from datetime import datetime
import os
import tempfile

import pandas as pd

from pyvideosync.sidecar import (
    FRAME_MAPPING_COLUMNS,
    build_frame_mapping,
)


def test_build_frame_mapping_preserves_final_video_order():
    joined_frames = pd.DataFrame(
        {
            "TimeStamps": [1000, 1002, 1003],
            "UTCTimeStamp": [
                datetime(2026, 1, 2, 3, 4, 6),
                datetime(2026, 1, 2, 3, 4, 6, 2000),
                datetime(2026, 1, 2, 3, 4, 6, 3000),
            ],
            "chunk_serial": [500, 501, 502],
            "mp4_frame_idx": [7, -1, 9],
            "mp4_file": ["a.mp4", "a.mp4", "b.mp4"],
        }
    )
    mapping = build_frame_mapping(
        joined_frames,
        camera_serial="23512014",
        ns5_start_timestamp=900,
        ns5_clk_per_sample=1,
        ns5_path="/data/example.ns5",
    )

    assert list(mapping.columns) == FRAME_MAPPING_COLUMNS
    assert mapping["synced_frame_idx"].tolist() == [0, 1, 2]
    assert mapping["nev_serial_timestamp"].tolist() == [1000, 1002, 1003]
    assert mapping["ns5_sample_idx"].tolist() == [100, 102, 103]
    assert mapping["chunk_serial"].tolist() == [500, 501, 502]
    assert mapping["source_mp4_frame_idx"].tolist() == [7, -1, 9]
    assert mapping["source_frame_available"].tolist() == [True, False, True]
    assert mapping["nev_utc_time"].iloc[0] == "2026-01-02T03:04:06+00:00"
    assert mapping["ns5_file"].unique().tolist() == ["/data/example.ns5"]


def test_frame_mapping_csv_round_trip():
    joined_frames = pd.DataFrame(
        {
            "TimeStamps": [10],
            "UTCTimeStamp": [datetime(2026, 1, 1, 0, 0, 1)],
            "chunk_serial": [20],
            "mp4_frame_idx": [30],
            "mp4_file": ["source.mp4"],
        }
    )
    mapping = build_frame_mapping(
        joined_frames,
        camera_serial="cam",
        ns5_start_timestamp=0,
        ns5_clk_per_sample=1,
        ns5_path="/data/source.ns5",
    )
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
        path = tmp.name
    try:
        mapping.to_csv(path, index=False)
        loaded = pd.read_csv(path)
        assert list(loaded.columns) == FRAME_MAPPING_COLUMNS
        assert "Unnamed: 0" not in loaded.columns
        assert loaded.loc[0, "synced_frame_idx"] == 0
    finally:
        os.unlink(path)


def test_build_frame_mapping_rejects_unaligned_ns5_timestamp():
    joined_frames = pd.DataFrame(
        {
            "TimeStamps": [1001],
            "UTCTimeStamp": [datetime(2026, 1, 1)],
            "chunk_serial": [20],
            "mp4_frame_idx": [30],
            "mp4_file": ["source.mp4"],
        }
    )
    try:
        build_frame_mapping(
            joined_frames,
            camera_serial="cam",
            ns5_start_timestamp=1000,
            ns5_clk_per_sample=2,
            ns5_path="/data/source.ns5",
        )
    except ValueError as exc:
        assert "sample boundaries" in str(exc)
        return
    raise AssertionError("expected ValueError for an unaligned NS5 timestamp")


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
        except Exception as exc:
            print(f"FAIL  {name}: {exc}")
            failures.append(name)
    if failures:
        print(f"\n{len(failures)}/{len(test_funcs)} failed")
        sys.exit(1)
    print(f"\nall {len(test_funcs)} tests passed")

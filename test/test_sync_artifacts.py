"""Synthetic tests for persisted frame-to-neural mappings."""

from datetime import datetime
import os
import tempfile

import pandas as pd

from pyvideosync.sidecar import (
    FRAME_MAPPING_COLUMNS,
    build_frame_mapping,
    combine_frame_mappings,
    concatenate_frame_mappings,
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


def test_combine_frame_mappings_preserves_camera_order_and_frame_indices():
    def mapping_for(camera_serial, timestamps):
        return build_frame_mapping(
            pd.DataFrame(
                {
                    "TimeStamps": timestamps,
                    "UTCTimeStamp": [datetime(2026, 1, 1)] * len(timestamps),
                    "chunk_serial": timestamps,
                    "mp4_frame_idx": range(len(timestamps)),
                    "mp4_file": [f"{camera_serial}.mp4"] * len(timestamps),
                }
            ),
            camera_serial=camera_serial,
            ns5_start_timestamp=0,
            ns5_clk_per_sample=1,
            ns5_path="/data/source.ns5",
        )

    combined = combine_frame_mappings(
        [mapping_for("18486638", [10, 11]), mapping_for("23512014", [20])]
    )

    assert list(combined.columns) == FRAME_MAPPING_COLUMNS
    assert combined["camera_serial"].tolist() == [
        "18486638",
        "18486638",
        "23512014",
    ]
    assert combined["synced_frame_idx"].tolist() == [0, 1, 0]
    assert not combined.duplicated(["camera_serial", "synced_frame_idx"]).any()


def test_concatenate_frame_mappings_renumbers_neural_fragments():
    first = build_frame_mapping(
        pd.DataFrame(
            {
                "TimeStamps": [100, 101],
                "UTCTimeStamp": [datetime(2026, 1, 1)] * 2,
                "chunk_serial": [500, 501],
                "mp4_frame_idx": [0, 1],
                "mp4_file": ["source.mp4"] * 2,
            }
        ),
        camera_serial="18486638",
        ns5_start_timestamp=100,
        ns5_clk_per_sample=1,
        ns5_path="first.ns5",
    )
    second = build_frame_mapping(
        pd.DataFrame(
            {
                "TimeStamps": [200, 201],
                "UTCTimeStamp": [datetime(2026, 1, 1)] * 2,
                "chunk_serial": [502, 503],
                "mp4_frame_idx": [2, 3],
                "mp4_file": ["source.mp4"] * 2,
            }
        ),
        camera_serial="18486638",
        ns5_start_timestamp=200,
        ns5_clk_per_sample=1,
        ns5_path="second.ns5",
    )

    combined = concatenate_frame_mappings([first, second])

    assert combined["synced_frame_idx"].tolist() == [0, 1, 2, 3]
    assert combined["ns5_file"].tolist() == [
        "first.ns5",
        "first.ns5",
        "second.ns5",
        "second.ns5",
    ]
    assert combined["ns5_sample_idx"].tolist() == [0, 1, 0, 1]


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

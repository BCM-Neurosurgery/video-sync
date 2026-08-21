"""Tests for stitched-time calibration and camera discovery."""

from datetime import datetime
import json
import logging
from pathlib import Path
import tempfile

import pandas as pd

from pyvideosync.main import _find_overlapping_camera_timestamps
from pyvideosync.nev import Nev


LOGGER = logging.getLogger(__name__)


def _write_camera_json(path: Path, serial_values, real_times):
    rows = len(serial_values)
    path.write_text(
        json.dumps(
            {
                "serials": ["23512014"],
                "timestamps": [[index] for index in range(rows)],
                "chunk_serial_data": [[value] for value in serial_values],
                "frame_id": [[index] for index in range(rows)],
                "real_times": real_times,
            }
        ),
        encoding="utf-8",
    )


def test_nev_utc_uses_first_raw_nev_anchor():
    nev = Nev.__new__(Nev)
    nev.timestampResolution = 1000
    nev.timeOrigin = datetime(2026, 1, 10)
    nev.has_unparsed_data = lambda: True
    nev.get_cleaned_digital_events_df = lambda: pd.DataFrame(
        {
            "TimeStamps": [1500, 1501, 1502, 1503, 1504],
            "UnparsedData": [1, 0, 0, 0, 0],
        }
    )

    result = nev.get_chunk_serial_df(
        reference_time_origin=datetime(2026, 1, 1),
        reference_start_timestamp=1000,
    )

    assert result.loc[0, "TimeStamps"] == 1500
    assert result.loc[0, "UTCTimeStamp"] == datetime(2026, 1, 1, 0, 0, 0, 500000)


def test_time_discovery_prefers_realtime_over_repeated_serials():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        old_json = tmp_path / "YFZDatafile_20260727_120000.json"
        match_json = tmp_path / "YFZDatafile_20260801_124632.json"
        _write_camera_json(
            old_json,
            [100, 101],
            ["2026-07-27 17:00:00.000", "2026-07-27 17:00:00.033"],
        )
        _write_camera_json(
            match_json,
            [100, 101],
            ["2026-08-01 17:46:32.835", "2026-08-01 17:56:33.654"],
        )
        old_timestamp = datetime(2026, 7, 27, 12, 0, 0)
        match_timestamp = datetime(2026, 8, 1, 12, 46, 32)

        result = _find_overlapping_camera_timestamps(
            {
                old_timestamp: [str(old_json)],
                match_timestamp: [str(match_json)],
            },
            ["23512014"],
            100,
            101,
            LOGGER,
            nev_start_utc=datetime(2026, 8, 1, 17, 50, 51),
            nev_end_utc=datetime(2026, 8, 1, 17, 55, 4),
        )

        assert result == [match_timestamp]


def test_serial_fallback_scans_past_nonmonotonic_range():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        high_json = tmp_path / "YFZDatafile_20260727_120000.json"
        match_json = tmp_path / "YFZDatafile_20260801_124632.json"
        _write_camera_json(
            high_json,
            [500, 501],
            ["2026-07-27 17:00:00.000", "2026-07-27 17:00:00.033"],
        )
        _write_camera_json(
            match_json,
            [150, 210],
            ["2026-08-01 17:46:32.835", "2026-08-01 17:56:33.654"],
        )
        high_timestamp = datetime(2026, 7, 27, 12, 0, 0)
        match_timestamp = datetime(2026, 8, 1, 12, 46, 32)

        result = _find_overlapping_camera_timestamps(
            {
                high_timestamp: [str(high_json)],
                match_timestamp: [str(match_json)],
            },
            ["23512014"],
            160,
            200,
            LOGGER,
        )

        assert result == [match_timestamp]


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

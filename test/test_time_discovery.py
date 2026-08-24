"""Tests for stitched-time calibration and camera discovery."""

from datetime import datetime, timedelta
import json
import logging
from pathlib import Path
import tempfile
from unittest.mock import Mock, patch

import pandas as pd

from pyvideosync.data_pool import DataPool, VideoFilesPool
from pyvideosync.main import (
    _find_overlapping_camera_timestamps,
    _get_nev_chunk_serial_df,
)
from pyvideosync.nev import Nev
from pyvideosync.pathutils import PathUtils

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


def test_nev_utc_uses_explicit_timestamp_anchor():
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


def test_flat_raw_utc_uses_paired_ns5_anchor():
    expected = pd.DataFrame({"chunk_serial": [123]})
    nev = Mock()
    nev.get_chunk_serial_df.return_value = expected
    ns5 = Mock()
    ns5.path = "/data/NSP1-session-001.ns5"
    ns5.get_timeOrigin.return_value = datetime(2026, 2, 17, 15, 19, 6, 735000)
    ns5.get_start_timestamp.return_value = 1319438729

    result, utc_calibrated = _get_nev_chunk_serial_df(nev, ns5, None, True, LOGGER)

    assert result is expected
    assert utc_calibrated is True
    nev.get_chunk_serial_df.assert_called_once_with(
        reference_time_origin=datetime(2026, 2, 17, 15, 19, 6, 735000),
        reference_start_timestamp=1319438729,
    )


def test_legacy_mode_without_anchor_preserves_nev_timestamps():
    expected = pd.DataFrame({"chunk_serial": [123]})
    nev = Mock()
    nev.get_chunk_serial_df.return_value = expected

    result, utc_calibrated = _get_nev_chunk_serial_df(nev, Mock(), None, False, LOGGER)

    assert result is expected
    assert utc_calibrated is False
    nev.get_chunk_serial_df.assert_called_once_with()


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


def test_time_discovery_binary_searches_camera_groups():
    base_time = datetime(2026, 8, 1)
    camera_files = {
        base_time + timedelta(minutes=index): [f"camera_{index}.json"]
        for index in range(1024)
    }
    opened = []

    class FakeVideojson:
        def __init__(self, path):
            self.index = int(Path(path).stem.rsplit("_", 1)[1])
            opened.append(self.index)

        def is_valid(self):
            return True

        def get_realtime_bounds(self):
            start = base_time + timedelta(minutes=self.index)
            return start, start + timedelta(seconds=30)

        def get_camera_serials(self):
            return ["23512014"]

    window_start = base_time + timedelta(minutes=900)
    with patch("pyvideosync.main.Videojson", FakeVideojson):
        result = _find_overlapping_camera_timestamps(
            camera_files,
            ["23512014"],
            0,
            0,
            LOGGER,
            nev_start_utc=window_start,
            nev_end_utc=window_start + timedelta(seconds=10),
        )

    assert result == [window_start]
    assert len(opened) < 20


def test_video_file_pool_indexes_root_and_date_subdirectories_once():
    with tempfile.TemporaryDirectory() as tmp_dir:
        camera_dir = Path(tmp_dir)
        date_dir = camera_dir / "20260217"
        date_dir.mkdir()
        root_json = camera_dir / "YFVDatafile_20260217_091000.json"
        nested_video = date_dir / "YFVDatafile_20260217_091000.18486638.mp4"
        ignored_file = date_dir / "notes.txt"
        root_json.touch()
        nested_video.touch()
        ignored_file.touch()

        video_file_pool = VideoFilesPool.from_directory(str(camera_dir))
        groups = video_file_pool.list_groups()

        assert len(groups) == 1
        assert next(iter(groups.values())) == sorted(
            [str(root_json.resolve()), str(nested_video.resolve())]
        )

        with patch.object(
            VideoFilesPool,
            "from_directory",
            side_effect=AssertionError("camera directory was indexed again"),
        ):
            datapool = DataPool(
                str(camera_dir),
                str(camera_dir),
                nev_path="session.nev",
                ns5_path="session.ns5",
                video_file_pool=video_file_pool,
            )

        assert datapool.get_video_file_pool() is video_file_pool


def test_flat_batch_discovers_every_matching_nev_ns5_pair():
    with tempfile.TemporaryDirectory() as tmp_dir:
        flat_dir = Path(tmp_dir)
        for filename in [
            "NSP1-session-002.nev",
            "NSP1-session-002.ns5",
            "NSP1-session-001.nev",
            "NSP1-session-001.ns5",
            "NSP1-session-001.ns3",
            "NSP2-session-001.nev",
            "NSP2-session-001.ns5",
        ]:
            (flat_dir / filename).touch()

        pathutils = PathUtils.__new__(PathUtils)
        sessions = pathutils.get_flat_nev_session_files(
            str(flat_dir), keywords=["NSP1-"]
        )

        assert [session[0] for session in sessions] == [
            "NSP1-session-001",
            "NSP1-session-002",
        ]
        assert sessions[0][3] == str(flat_dir / "NSP1-session-001.ns3")
        assert sessions[1][3] is None


def test_flat_batch_rejects_unpaired_nev_or_ns5_files():
    with tempfile.TemporaryDirectory() as tmp_dir:
        flat_dir = Path(tmp_dir)
        (flat_dir / "NSP1-missing-ns5.nev").touch()
        (flat_dir / "NSP1-missing-nev.ns5").touch()

        pathutils = PathUtils.__new__(PathUtils)
        try:
            pathutils.get_flat_nev_session_files(str(flat_dir), keywords=["NSP1-"])
        except ValueError as exc:
            assert "NSP1-missing-nev" in str(exc)
            assert "NSP1-missing-ns5" in str(exc)
            return
        raise AssertionError("expected ValueError for unpaired NEV/NS5 files")


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

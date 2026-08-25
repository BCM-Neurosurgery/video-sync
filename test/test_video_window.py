"""Synthetic tests for video-defined synchronization windows."""

from datetime import datetime, timedelta
import json
import logging
from unittest.mock import patch

import pandas as pd
import pytest

from pyvideosync.main import (
    _NeuralContext,
    _align_camera_fragments,
    _camera_timestamps,
    _select_neural_segments,
)
from pyvideosync.sessions import (
    NeuralSegmentSpec,
    SyncJobSpec,
    TimeAnchor,
    VideoSelection,
)


class _FakeNs5:
    def __init__(self, path, start_timestamp):
        self.path = str(path)
        self.timeStamp = start_timestamp
        self.clk_per_samp = 1

    def get_filtered_channel_df(self, _channel, start_timestamp, end_timestamp):
        timestamps = list(range(start_timestamp, end_timestamp + 1))
        return pd.DataFrame(
            {"TimeStamp": timestamps, "Amplitude": [1] * len(timestamps)}
        )


def _context(tmp_path, name, serials, timestamps):
    segment = NeuralSegmentSpec(
        name=name,
        nev_path=tmp_path / f"{name}.nev",
        ns5_path=tmp_path / f"{name}.ns5",
        time_anchor=TimeAnchor(kind="paired_ns5"),
    )
    utc_start = datetime(2026, 2, 17, 9, 13, 20)
    frame_times = [
        utc_start + timedelta(seconds=index / 30) for index in range(len(serials))
    ]
    chunk_serial_df = pd.DataFrame(
        {
            "TimeStamps": timestamps,
            "chunk_serial": serials,
            "UTCTimeStamp": frame_times,
        }
    )
    return _NeuralContext(
        segment=segment,
        ns5=_FakeNs5(segment.ns5_path, timestamps[0]),
        chunk_serial_df=chunk_serial_df,
        start_serial=min(serials),
        end_serial=max(serials),
        start_utc=min(frame_times),
        end_utc=max(frame_times),
        utc_calibrated=True,
    )


def _video_job(tmp_path, contexts):
    json_path = tmp_path / "YFVDatafile_20260217_091320.json"
    mp4_path = tmp_path / "YFVDatafile_20260217_091320.18486638.mp4"
    json_path.write_text(
        json.dumps(
            {
                "serials": ["18486638"],
                "timestamps": [[0], [1], [2], [3]],
                "real_times": [
                    "2026-02-17 09:13:20.000000",
                    "2026-02-17 09:13:20.033333",
                    "2026-02-17 09:13:20.066667",
                    "2026-02-17 09:13:20.100000",
                ],
                "chunk_serial_data": [[500], [501], [502], [503]],
                "frame_id": [[0], [1], [2], [3]],
            }
        ),
        encoding="utf-8",
    )
    mp4_path.touch()
    job = SyncJobSpec(
        name="ten-minute-video",
        window="video",
        neural_segments=tuple(context.segment for context in contexts),
        video=VideoSelection(
            kind="explicit",
            camera_serials=("18486638",),
            json_paths=(json_path,),
            mp4_paths=(mp4_path,),
        ),
        coverage="require_full",
    )
    return job, {datetime(2026, 2, 17, 9, 13, 20): [str(json_path), str(mp4_path)]}


def test_video_window_combines_frame_mappings_from_multiple_ns5_files(tmp_path):
    contexts = [
        _context(tmp_path, "NSP1-001", [500, 501], [100, 101]),
        _context(tmp_path, "NSP1-002", [502, 503], [200, 201]),
    ]
    job, camera_files = _video_job(tmp_path, contexts)

    fragments, mapping = _align_camera_fragments(
        job,
        contexts,
        camera_files,
        list(camera_files),
        "18486638",
        "RoomMic2",
        logging.getLogger(__name__),
    )

    assert len(fragments) == 2
    assert mapping["synced_frame_idx"].tolist() == [0, 1, 2, 3]
    assert mapping["source_mp4_frame_idx"].tolist() == [0, 1, 2, 3]
    assert mapping["ns5_file"].tolist() == [
        str(tmp_path / "NSP1-001.ns5"),
        str(tmp_path / "NSP1-001.ns5"),
        str(tmp_path / "NSP1-002.ns5"),
        str(tmp_path / "NSP1-002.ns5"),
    ]
    assert mapping["ns5_sample_idx"].tolist() == [0, 1, 0, 1]


def test_video_window_requires_every_target_frame_to_have_neural_coverage(tmp_path):
    contexts = [_context(tmp_path, "NSP1-001", [500, 501], [100, 101])]
    job, camera_files = _video_job(tmp_path, contexts)

    with pytest.raises(RuntimeError, match="does not fully cover"):
        _align_camera_fragments(
            job,
            contexts,
            camera_files,
            list(camera_files),
            "18486638",
            "RoomMic2",
            logging.getLogger(__name__),
        )


def test_video_window_selects_adjacent_ns5_segments_for_full_coverage(tmp_path):
    contexts = [
        _context(tmp_path, "NSP1-001", [500, 501], [100, 101]),
        _context(tmp_path, "NSP1-002", [502, 503], [200, 201]),
    ]
    job, _ = _video_job(tmp_path, contexts)
    start = datetime(2026, 2, 17, 9, 13, 20)
    sample = timedelta(seconds=1 / 30000)

    with patch(
        "pyvideosync.main._segment_utc_bounds",
        side_effect=[
            (start, start + timedelta(seconds=0.05), sample),
            (start + timedelta(seconds=0.05), start + timedelta(seconds=0.1), sample),
        ],
    ):
        selected = _select_neural_segments(job, logging.getLogger(__name__))

    assert selected == tuple(context.segment for context in contexts)


def test_video_window_rejects_a_gap_between_ns5_segments(tmp_path):
    contexts = [
        _context(tmp_path, "NSP1-001", [500, 501], [100, 101]),
        _context(tmp_path, "NSP1-002", [502, 503], [200, 201]),
    ]
    job, _ = _video_job(tmp_path, contexts)
    start = datetime(2026, 2, 17, 9, 13, 20)
    sample = timedelta(seconds=1 / 30000)

    with (
        patch(
            "pyvideosync.main._segment_utc_bounds",
            side_effect=[
                (start, start + timedelta(seconds=0.04), sample),
                (
                    start + timedelta(seconds=0.06),
                    start + timedelta(seconds=0.1),
                    sample,
                ),
            ],
        ),
        pytest.raises(RuntimeError, match="UTC coverage gap"),
    ):
        _select_neural_segments(job, logging.getLogger(__name__))


def test_legacy_serial_only_job_does_not_use_uncalibrated_utc(tmp_path):
    context = _context(tmp_path, "stitched", [500, 501], [100, 101])
    context.utc_calibrated = False
    job = SyncJobSpec(
        name="stitched",
        window="neural",
        neural_segments=(context.segment,),
        video=VideoSelection(kind="discover", recording_dir=tmp_path),
    )

    with patch(
        "pyvideosync.main._find_overlapping_camera_timestamps",
        return_value=[],
    ) as find_timestamps:
        _camera_timestamps(job, {}, context, logging.getLogger(__name__))

    assert find_timestamps.call_args.kwargs["nev_start_utc"] is None
    assert find_timestamps.call_args.kwargs["nev_end_utc"] is None

"""Binary-fixture regressions for recording-start UTC and split-file discovery."""

from datetime import datetime, timedelta
import json
import logging
from pathlib import Path
from struct import pack_into
from unittest.mock import patch

import pytest

from pyvideosync.main import (
    _get_nev_chunk_serial_df,
    _segment_utc_bounds,
    _select_neural_segments,
)
from pyvideosync.nev import Nev
from pyvideosync.nev_timing import read_nev_recording_anchor
from pyvideosync.nsx import read_nsx_time_bounds
from pyvideosync.sessions import (
    NeuralSegmentSpec,
    SyncJobSpec,
    TimeAnchor,
    VideoSelection,
)

ORIGIN = datetime(2026, 1, 1, 16, 40, 42, 754000)
START = 818100
LOGGER = logging.getLogger(__name__)


def _system_time(origin):
    return (
        origin.year,
        origin.month,
        0,
        origin.day,
        origin.hour,
        origin.minute,
        origin.second,
        origin.microsecond // 1000,
    )


def _write_nev(path, events, origin=ORIGIN, resolution=30000, version=(3, 0)):
    header = bytearray(336)
    header[:8] = b"BREVENTS"
    header[8:10] = bytes(version)
    pack_into("<HIIII", header, 10, 1, 336, 108, resolution, 30000)
    pack_into("<8H", header, 28, *_system_time(origin))
    with path.open("wb") as stream:
        stream.write(header)
        for tick, packet_id, reason, value in events:
            packet = bytearray(108)
            pack_into("<QHHH", packet, 0, tick, packet_id, reason, value)
            stream.write(packet)
    return path


def _reference(tmp_path, start=START):
    return _write_nev(
        tmp_path / "first.nev",
        [
            (start, 65529, 0, 0),
            (start + 460, 0, 1, 0),
            (start + 1087, 0, 129, 1),
        ],
    )


def _write_ns5(path, first_tick, count, origin, version=(3, 0), extra_packets=()):
    header = bytearray(380)  # basic header + one channel
    header[:8] = b"BRSMPGRP"
    header[8:10] = bytes(version)
    pack_into("<I", header, 10, 380)
    pack_into("<II", header, 286, 1, 30000)
    pack_into("<8H", header, 294, *_system_time(origin))
    pack_into("<I", header, 310, 1)
    header[314:316] = b"CC"
    with path.open("wb") as stream:
        stream.write(header)
        for tick, points in [(first_tick, count), *extra_packets]:
            packet = bytearray(13 if version[0] >= 3 else 9)
            packet[0] = 1
            pack_into("<QI" if version[0] >= 3 else "<II", packet, 1, tick, points)
            stream.write(packet)
            # Sparse signal payload: discovery must seek past it, never load it.
            stream.seek(points * 2 - 1, 1)
            stream.write(b"\0")
    return path


def _segment(tmp_path, name, reference, first_tick, last_tick, header_origin):
    nev = _write_nev(
        tmp_path / f"{name}.nev",
        [
            (first_tick, 0, 1, 0),
            (last_tick, 0, 1, 0),
        ],
        origin=header_origin,
    )
    ns5 = _write_ns5(
        tmp_path / f"{name}.ns5", first_tick, last_tick - first_tick + 1, header_origin
    )
    return NeuralSegmentSpec(name, nev, ns5, TimeAnchor("first_raw_nev", reference))


def test_recording_start_is_not_the_first_digital_or_serial_event(tmp_path):
    reference = _reference(tmp_path)
    anchor = read_nev_recording_anchor(reference, reference)
    assert anchor.start_timestamp == START
    assert anchor.to_utc(START) == ORIGIN
    assert anchor.to_utc(START + 460) == ORIGIN + timedelta(microseconds=15333)
    assert anchor.to_utc(START + 1087) == ORIGIN + timedelta(microseconds=36233)


@pytest.mark.parametrize("start", [0, 2**32 + START])
def test_zero_and_64_bit_recording_start_ticks(tmp_path, start):
    reference = _reference(tmp_path, start=start)
    anchor = read_nev_recording_anchor(reference, reference)
    assert anchor.start_timestamp == start
    assert anchor.to_utc(start + 30000) == ORIGIN + timedelta(seconds=1)


def test_reference_without_any_digital_events_is_valid(tmp_path):
    reference = _write_nev(tmp_path / "first.nev", [(START, 65529, 0, 0)])
    assert read_nev_recording_anchor(reference, reference).start_timestamp == START


@pytest.mark.parametrize(
    "events",
    [
        [(START, 0, 1, 0)],
        [(START, 65529, 2, 0), (START + 1, 65529, 3, 0)],
        [(START, 65529, 0, 0), (START + 30000, 65529, 0, 0)],
    ],
)
def test_missing_or_multiple_recording_starts_fail(tmp_path, events):
    reference = _write_nev(tmp_path / "first.nev", events)
    with pytest.raises(ValueError, match="exactly one recording-start"):
        read_nev_recording_anchor(reference, reference)


@pytest.mark.parametrize(
    "events, resolution, message",
    [
        ([(START + 100, 0, 1, 0), (START + 99, 0, 1, 0)], 30000, "timestamp reset"),
        ([(START - 1, 0, 1, 0)], 30000, "precede recording start"),
        ([(START + 100, 0, 1, 0)], 1000, "resolution differs"),
        ([(START + 100, 65529, 0, 0)], 30000, "different recording start"),
    ],
)
def test_incompatible_target_clock_fails(tmp_path, events, resolution, message):
    reference = _reference(tmp_path)
    target = _write_nev(tmp_path / "later.nev", events, resolution=resolution)
    with pytest.raises(ValueError, match=message):
        read_nev_recording_anchor(reference, target)


def test_reset_between_scan_buffers_fails(tmp_path):
    reference = _reference(tmp_path)
    events = [(START + i, 0, 1, 0) for i in range(16384)]
    events.append((START + 1, 0, 1, 0))
    target = _write_nev(tmp_path / "reset.nev", events)
    with pytest.raises(ValueError, match="timestamp reset"):
        read_nev_recording_anchor(reference, target)


@pytest.mark.parametrize(
    "damage, message",
    [
        ("header", "truncated NEV header"),
        ("packet", "truncated NEV packet data"),
        ("version", "requires NEV 3.0"),
        ("resolution", "invalid NEV timing"),
        ("packet_size", "invalid NEV timing"),
    ],
)
def test_invalid_reference_fails(tmp_path, damage, message):
    reference = _reference(tmp_path)
    data = bytearray(reference.read_bytes())
    if damage == "header":
        data = data[:100]
    elif damage == "packet":
        data = data[:-1]
    elif damage == "version":
        data[8:10] = bytes((2, 3))
    elif damage == "resolution":
        pack_into("<I", data, 20, 0)
    else:
        pack_into("<I", data, 16, 8)
    reference.write_bytes(data)
    with pytest.raises(ValueError, match=message):
        read_nev_recording_anchor(reference, reference)


def test_real_serial_conversion_uses_recording_start(tmp_path):
    reference = _reference(tmp_path)
    tick = 236277809
    serial = 5604461
    events = [(tick - 1, 0, 1, 0)] + [
        (tick + i * 3, 0, 129, (serial >> (7 * i)) & 127) for i in range(5)
    ]
    path = _write_nev(
        tmp_path / "later.nev", events, origin=datetime(2026, 1, 1, 18, 50, 43, 791000)
    )
    result, calibrated = _get_nev_chunk_serial_df(
        Nev(str(path)), None, TimeAnchor("first_raw_nev", reference), LOGGER
    )
    assert calibrated
    assert result.iloc[0]["chunk_serial"] == serial
    assert result.iloc[0]["TimeStamps"] == tick
    assert result.iloc[0]["UTCTimeStamp"] == datetime(2026, 1, 1, 18, 51, 31, 410967)


def test_discovery_and_mapping_use_the_same_reference(tmp_path):
    reference = _reference(tmp_path)
    segment = _segment(
        tmp_path,
        "later",
        reference,
        234839819,
        252842698,
        datetime(2026, 1, 1, 18, 50, 43, 800000),
    )
    events = []
    for index, tick in enumerate((234839819, 252842698)):
        events.append((tick - 1, 0, 1, 0))
        events.extend(
            (tick + i * 3, 0, 129, ((128 + index) >> (7 * i)) & 127) for i in range(5)
        )
    _write_nev(
        segment.nev_path, events, origin=datetime(2026, 1, 1, 18, 50, 43, 791000)
    )
    mapping, _ = _get_nev_chunk_serial_df(
        Nev(str(segment.nev_path)), None, segment.time_anchor, LOGGER
    )
    start, end, _ = _segment_utc_bounds(segment, LOGGER)
    assert (
        start
        == mapping["UTCTimeStamp"].iloc[0]
        == datetime(2026, 1, 1, 18, 50, 43, 477967)
    )
    assert (
        end
        == mapping["UTCTimeStamp"].iloc[-1]
        == datetime(2026, 1, 1, 19, 0, 43, 573933)
    )


def test_video_window_spans_split_boundary_without_loading_signals(tmp_path):
    reference = _reference(tmp_path)
    segments = (
        _segment(
            tmp_path,
            "014",
            reference,
            234839819,
            252842698,
            datetime(2026, 1, 1, 18, 50, 43, 800000),
        ),
        _segment(
            tmp_path,
            "015",
            reference,
            252842699,
            270840798,
            datetime(2026, 1, 1, 19, 0, 43, 974000),
        ),
    )
    json_path = tmp_path / "camera.json"
    json_path.write_text(
        json.dumps(
            {
                "serials": ["18486638"],
                "timestamps": [[0], [1]],
                "chunk_serial_data": [[5604461], [5622460]],
                "frame_id": [[1], [2]],
                "real_times": ["2026-01-01 18:51:27.243", "2026-01-01 19:01:28.029"],
            }
        )
    )
    video = VideoSelection(
        "explicit",
        camera_serials=("18486638",),
        json_paths=(json_path,),
        mp4_paths=(tmp_path / "camera.18486638.mp4",),
    )
    job = SyncJobSpec("video", "video", segments, video, "require_full")
    with patch("pyvideosync.main.Nsx", side_effect=AssertionError("loaded signals")):
        assert _select_neural_segments(job, LOGGER) == segments
    end = _segment_utc_bounds(segments[0], LOGGER)[1]
    start = _segment_utc_bounds(segments[1], LOGGER)[0]
    assert start - end == timedelta(microseconds=34)  # datetime rounds each endpoint


def test_paired_ns5_rejects_3_0_in_mapping_and_discovery(tmp_path):
    reference = _reference(tmp_path)
    segment = _segment(
        tmp_path,
        "later",
        reference,
        START + 1,
        START + 100,
        ORIGIN + timedelta(seconds=1),
    )
    legacy = NeuralSegmentSpec(
        segment.name, segment.nev_path, segment.ns5_path, TimeAnchor("paired_ns5")
    )
    with pytest.raises(ValueError, match="use first_raw_nev"):
        _segment_utc_bounds(legacy, LOGGER)
    with pytest.raises(ValueError, match="use first_raw_nev"):
        _get_nev_chunk_serial_df(
            Nev(str(segment.nev_path)), None, legacy.time_anchor, LOGGER
        )


def test_legacy_paired_discovery_uses_offset_from_first_sample(tmp_path):
    ns5 = _write_ns5(tmp_path / "legacy.ns5", 100000, 30001, ORIGIN, version=(2, 3))
    segment = NeuralSegmentSpec(
        "legacy", tmp_path / "legacy.nev", ns5, TimeAnchor("paired_ns5")
    )
    start, end, _ = _segment_utc_bounds(segment, LOGGER)
    assert start == ORIGIN
    assert end == ORIGIN + timedelta(seconds=1)


def test_ns5_packet_clock_reset_fails(tmp_path):
    path = _write_ns5(tmp_path / "reset.ns5", 100, 10, ORIGIN, extra_packets=[(10, 10)])
    with pytest.raises(ValueError, match="NSx timestamp reset"):
        read_nsx_time_bounds(path)


def test_ns5_resolution_must_match_reference(tmp_path):
    reference = _reference(tmp_path)
    segment = _segment(tmp_path, "later", reference, START + 1, START + 100, ORIGIN)
    with segment.ns5_path.open("r+b") as stream:
        stream.seek(290)
        stream.write((60000).to_bytes(4, "little"))
    with pytest.raises(ValueError, match="resolution differs"):
        _segment_utc_bounds(segment, LOGGER)

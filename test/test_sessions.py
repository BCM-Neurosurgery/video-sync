"""Tests for normalized single-session and batch configuration."""

from pathlib import Path

import pytest
import yaml

from pyvideosync.pathutils import PathUtils
from pyvideosync.main import _get_video_file_pool
from pyvideosync.sessions import (
    SessionSpec,
    TimeAnchor,
    VideoSelection,
    resolve_run_spec,
)


def _write_config(tmp_path: Path, config: dict) -> Path:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    return config_path


def _touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()
    return path


def test_explicit_session_selects_one_mp4_and_json(tmp_path):
    nev_path = _touch(tmp_path / "data" / "NSP1-session-001.nev")
    ns5_path = _touch(tmp_path / "data" / "NSP1-session-001.ns5")
    json_path = _touch(tmp_path / "video" / "YFVDatafile_20260217_091320.json")
    mp4_path = _touch(tmp_path / "video" / "YFVDatafile_20260217_091320.18486638.mp4")
    config_path = _write_config(
        tmp_path,
        {
            "output_dir": str(tmp_path / "output"),
            "channel_name": "RoomMic2",
            "video": {
                "kind": "explicit",
                "json_path": str(json_path),
                "mp4_paths": {"18486638": str(mp4_path)},
            },
            "sessions": [
                {
                    "name": "raw-001",
                    "nev_path": str(nev_path),
                    "ns5_path": str(ns5_path),
                    "time_anchor": {"kind": "paired_ns5"},
                }
            ],
        },
    )

    run_spec = resolve_run_spec(PathUtils(str(config_path), timestamp=None))
    session = run_spec.sessions[0]

    assert session.name == "raw-001"
    assert session.time_anchor == TimeAnchor(kind="paired_ns5")
    assert session.video.kind == "explicit"
    assert session.video.camera_serials == ("18486638",)
    assert session.video.json_paths == (json_path,)
    assert session.video.mp4_paths == (mp4_path,)


def test_legacy_flat_directory_resolves_all_raw_pairs(tmp_path):
    data_dir = tmp_path / "data"
    video_dir = tmp_path / "video"
    video_dir.mkdir()
    for stem in ["NSP1-session-001", "NSP1-session-002"]:
        _touch(data_dir / f"{stem}.nev")
        _touch(data_dir / f"{stem}.ns5")
    config_path = _write_config(
        tmp_path,
        {
            "flat_dir": str(data_dir),
            "keywords": ["NSP1-"],
            "cam_recording_dir": str(video_dir),
            "cam_serial": ["18486638", "23512014"],
            "output_dir": str(tmp_path / "output"),
            "channel_name": "RoomMic2",
        },
    )

    run_spec = resolve_run_spec(PathUtils(str(config_path), timestamp=None))

    assert [session.name for session in run_spec.sessions] == [
        "NSP1-session-001",
        "NSP1-session-002",
    ]
    assert all(
        session.time_anchor == TimeAnchor(kind="paired_ns5")
        for session in run_spec.sessions
    )
    assert run_spec.sessions[0].video is run_spec.sessions[1].video


def test_legacy_single_stitched_directory_resolves_first_raw_nev(tmp_path):
    stitched_dir = tmp_path / "stitched" / "EMU-0159_convo"
    video_dir = tmp_path / "video"
    video_dir.mkdir()
    _touch(stitched_dir / "EMU-0159_convo-NSP-1.nev")
    _touch(stitched_dir / "EMU-0159_convo-NSP-1.ns5")
    first_nev_path = _touch(tmp_path / "raw" / "NSP1-raw-001.nev")
    config_path = _write_config(
        tmp_path,
        {
            "nsp_dir": str(stitched_dir),
            "first_nev_path": str(first_nev_path),
            "cam_recording_dir": str(video_dir),
            "output_dir": str(tmp_path / "output"),
            "channel_name": "RoomMic2",
        },
    )

    run_spec = resolve_run_spec(PathUtils(str(config_path), timestamp=None))

    assert len(run_spec.sessions) == 1
    assert run_spec.sessions[0].name == "EMU-0159_convo"
    assert run_spec.sessions[0].time_anchor == TimeAnchor(
        kind="first_raw_nev", reference_path=first_nev_path
    )


def test_stitched_batch_resolves_a_distinct_anchor_per_session(tmp_path):
    stitched_root = tmp_path / "stitched"
    video_dir = tmp_path / "video"
    video_dir.mkdir()
    anchors = {}
    for name, raw_name in [("task-a", "raw-001.nev"), ("task-b", "raw-017.nev")]:
        task_dir = stitched_root / name
        _touch(task_dir / f"{name}-NSP-1.nev")
        _touch(task_dir / f"{name}-NSP-1.ns5")
        anchors[name] = str(_touch(tmp_path / "raw" / raw_name))
    config_path = _write_config(
        tmp_path,
        {
            "base_dir": str(stitched_root),
            "keywords": ["task-"],
            "first_nev_paths": anchors,
            "cam_recording_dir": str(video_dir),
            "output_dir": str(tmp_path / "output"),
            "channel_name": "RoomMic2",
        },
    )

    run_spec = resolve_run_spec(PathUtils(str(config_path), timestamp=None))

    assert [session.name for session in run_spec.sessions] == ["task-a", "task-b"]
    assert [session.time_anchor.reference_path for session in run_spec.sessions] == [
        Path(anchors["task-a"]),
        Path(anchors["task-b"]),
    ]


def test_stitched_batch_rejects_missing_per_session_anchor(tmp_path):
    stitched_root = tmp_path / "stitched"
    video_dir = tmp_path / "video"
    video_dir.mkdir()
    for name in ["task-a", "task-b"]:
        task_dir = stitched_root / name
        _touch(task_dir / f"{name}-NSP-1.nev")
        _touch(task_dir / f"{name}-NSP-1.ns5")
    config_path = _write_config(
        tmp_path,
        {
            "base_dir": str(stitched_root),
            "keywords": ["task-"],
            "first_nev_path": str(_touch(tmp_path / "raw" / "legacy-global.nev")),
            "first_nev_paths": {
                "task-a": str(_touch(tmp_path / "raw" / "raw-001.nev"))
            },
            "cam_recording_dir": str(video_dir),
            "output_dir": str(tmp_path / "output"),
            "channel_name": "RoomMic2",
        },
    )

    with pytest.raises(ValueError, match="missing selected stitched sessions: task-b"):
        resolve_run_spec(PathUtils(str(config_path), timestamp=None))


def test_explicit_session_rejects_missing_video_file(tmp_path):
    nev_path = _touch(tmp_path / "NSP1-session.nev")
    ns5_path = _touch(tmp_path / "NSP1-session.ns5")
    config_path = _write_config(
        tmp_path,
        {
            "output_dir": str(tmp_path / "output"),
            "channel_name": "RoomMic2",
            "sessions": [
                {
                    "name": "raw",
                    "nev_path": str(nev_path),
                    "ns5_path": str(ns5_path),
                    "time_anchor": "paired_ns5",
                    "video": {
                        "kind": "explicit",
                        "json_path": str(tmp_path / "YFVDatafile_20260217_091320.json"),
                        "mp4_paths": [
                            str(tmp_path / "YFVDatafile_20260217_091320.18486638.mp4")
                        ],
                    },
                }
            ],
        },
    )

    with pytest.raises(ValueError, match="explicit video file does not exist"):
        resolve_run_spec(PathUtils(str(config_path), timestamp=None))


def test_first_raw_nev_anchor_requires_reference_path():
    with pytest.raises(ValueError, match="requires reference_path"):
        TimeAnchor(kind="first_raw_nev")


@pytest.mark.parametrize(
    "name",
    ["../outside", "/outside", ".", "..", "group/session", "group\\session", " "],
)
def test_session_name_must_be_one_safe_path_component(tmp_path, name):
    with pytest.raises(ValueError, match="path-safe"):
        SessionSpec(
            name=name,
            nev_path=tmp_path / "session.nev",
            ns5_path=tmp_path / "session.ns5",
            time_anchor=TimeAnchor(kind="paired_ns5"),
            video=VideoSelection(kind="discover", recording_dir=tmp_path),
        )


def test_explicit_mp4_list_infers_selected_camera_serials(tmp_path):
    config_path = _write_config(
        tmp_path,
        {
            "output_dir": str(tmp_path / "output"),
            "channel_name": "RoomMic2",
            "sessions": [
                {
                    "name": "raw",
                    "nev_path": str(_touch(tmp_path / "raw.nev")),
                    "ns5_path": str(_touch(tmp_path / "raw.ns5")),
                    "time_anchor": {"kind": "paired_ns5"},
                    "video": {
                        "kind": "explicit",
                        "json_path": str(
                            _touch(tmp_path / "YFVDatafile_20260217_091320.json")
                        ),
                        "mp4_paths": [
                            str(
                                _touch(
                                    tmp_path
                                    / "YFVDatafile_20260217_091320.18486638.mp4"
                                )
                            )
                        ],
                    },
                }
            ],
        },
    )

    run_spec = resolve_run_spec(PathUtils(str(config_path), timestamp=None))

    assert run_spec.sessions[0].video.camera_serials == ("18486638",)


def test_explicit_mp4_mapping_rejects_mismatched_camera_key(tmp_path):
    config_path = _write_config(
        tmp_path,
        {
            "output_dir": str(tmp_path / "output"),
            "channel_name": "RoomMic2",
            "sessions": [
                {
                    "name": "raw",
                    "nev_path": str(_touch(tmp_path / "raw.nev")),
                    "ns5_path": str(_touch(tmp_path / "raw.ns5")),
                    "time_anchor": {"kind": "paired_ns5"},
                    "video": {
                        "kind": "explicit",
                        "json_path": str(
                            _touch(tmp_path / "YFVDatafile_20260217_091320.json")
                        ),
                        "mp4_paths": {
                            "23512014": str(
                                _touch(
                                    tmp_path
                                    / "YFVDatafile_20260217_091320.18486638.mp4"
                                )
                            )
                        },
                    },
                }
            ],
        },
    )

    with pytest.raises(ValueError, match="key 23512014 does not match"):
        resolve_run_spec(PathUtils(str(config_path), timestamp=None))


def test_explicit_video_selection_rejects_wrong_file_types(tmp_path):
    with pytest.raises(ValueError, match="only JSON files"):
        VideoSelection(
            kind="explicit",
            json_paths=(tmp_path / "recording.txt",),
            mp4_paths=(tmp_path / "recording.123.mp4",),
        )


def test_video_selection_rejects_duplicate_camera_serials(tmp_path):
    with pytest.raises(ValueError, match="must be unique"):
        VideoSelection(
            kind="discover",
            recording_dir=tmp_path,
            camera_serials=("18486638", "18486638"),
        )


def test_explicit_video_selection_builds_and_reuses_one_index(tmp_path):
    json_path = _touch(tmp_path / "YFVDatafile_20260217_091320.json")
    mp4_path = _touch(tmp_path / "YFVDatafile_20260217_091320.18486638.mp4")
    selection = VideoSelection(
        kind="explicit",
        json_paths=(json_path,),
        mp4_paths=(mp4_path,),
        camera_serials=("18486638",),
    )
    cache = {}

    first = _get_video_file_pool(selection, cache)
    second = _get_video_file_pool(selection, cache)

    assert first is second
    assert list(first.list_groups().values()) == [[str(json_path), str(mp4_path)]]

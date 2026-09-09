"""Validated sync-job models and configuration normalization."""

from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Literal

from pyvideosync.data_pool import VideoFilesPool, resolve_nsp_file
from pyvideosync.utils import extract_cam_serial

AnchorKind = Literal[
    "paired_ns5",
    "first_raw_nev",
    "embedded",
    "serial_only",
]
VideoKind = Literal["discover", "explicit"]
WindowKind = Literal["neural", "video"]
CoverageKind = Literal["overlap", "require_full"]


@dataclass(frozen=True)
class TimeAnchor:
    """Describe how NEV timestamps are converted to UTC."""

    kind: AnchorKind
    reference_path: Path | None = None

    def __post_init__(self) -> None:
        if self.reference_path is not None:
            object.__setattr__(self, "reference_path", Path(self.reference_path))
        if self.kind not in {
            "paired_ns5",
            "first_raw_nev",
            "embedded",
            "serial_only",
        }:
            raise ValueError(f"Unsupported time anchor: {self.kind}")
        if self.kind == "first_raw_nev" and self.reference_path is None:
            raise ValueError("first_raw_nev requires reference_path")
        if self.kind != "first_raw_nev" and self.reference_path is not None:
            raise ValueError(f"{self.kind} does not accept reference_path")


@dataclass(frozen=True)
class VideoSelection:
    """Select camera files by directory discovery or explicit file paths."""

    kind: VideoKind
    recording_dir: Path | None = None
    camera_serials: tuple[str, ...] | None = None
    json_paths: tuple[Path, ...] = ()
    mp4_paths: tuple[Path, ...] = ()

    def __post_init__(self) -> None:
        if self.recording_dir is not None:
            object.__setattr__(self, "recording_dir", Path(self.recording_dir))
        object.__setattr__(
            self, "json_paths", tuple(Path(path) for path in self.json_paths)
        )
        object.__setattr__(
            self, "mp4_paths", tuple(Path(path) for path in self.mp4_paths)
        )
        if self.kind not in {"discover", "explicit"}:
            raise ValueError(f"Unsupported video selection: {self.kind}")

        if self.camera_serials is not None:
            normalized = tuple(str(serial) for serial in self.camera_serials)
            if not all(normalized):
                raise ValueError("video.camera_serials cannot contain empty values")
            if len(normalized) != len(set(normalized)):
                raise ValueError("video.camera_serials must be unique")
            object.__setattr__(self, "camera_serials", normalized)

        if self.kind == "discover":
            if self.recording_dir is None:
                raise ValueError("discover video selection requires recording_dir")
            if self.json_paths or self.mp4_paths:
                raise ValueError(
                    "discover video selection does not accept explicit files"
                )
        else:
            if self.recording_dir is not None:
                raise ValueError(
                    "explicit video selection does not accept recording_dir"
                )
            if not self.json_paths or not self.mp4_paths:
                raise ValueError("explicit video selection requires JSON and MP4 paths")
            if any(path.suffix.lower() != ".json" for path in self.json_paths):
                raise ValueError("video.json_paths must contain only JSON files")
            if any(path.suffix.lower() != ".mp4" for path in self.mp4_paths):
                raise ValueError("video.mp4_paths must contain only MP4 files")


@dataclass(frozen=True)
class NeuralSegmentSpec:
    """One exact NEV/NS5 segment available to a synchronization job."""

    name: str
    nev_path: Path
    ns5_path: Path
    time_anchor: TimeAnchor
    ns3_path: Path | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "nev_path", Path(self.nev_path))
        object.__setattr__(self, "ns5_path", Path(self.ns5_path))
        if self.ns3_path is not None:
            object.__setattr__(self, "ns3_path", Path(self.ns3_path))
        _validate_output_name(self.name, "neural segment")
        if self.nev_path.suffix.lower() != ".nev":
            raise ValueError(f"Expected a NEV path: {self.nev_path}")
        if self.ns5_path.suffix.lower() != ".ns5":
            raise ValueError(f"Expected an NS5 path: {self.ns5_path}")
        if self.ns3_path is not None and self.ns3_path.suffix.lower() != ".ns3":
            raise ValueError(f"Expected an NS3 path: {self.ns3_path}")


@dataclass(frozen=True)
class SyncJobSpec:
    """One final output window and all candidate inputs needed to build it."""

    name: str
    window: WindowKind
    neural_segments: tuple[NeuralSegmentSpec, ...]
    video: VideoSelection
    coverage: CoverageKind = "overlap"

    def __post_init__(self) -> None:
        _validate_output_name(self.name, "job")
        if self.window not in {"neural", "video"}:
            raise ValueError(f"Unsupported job window: {self.window}")
        if self.coverage not in {"overlap", "require_full"}:
            raise ValueError(f"Unsupported coverage policy: {self.coverage}")
        if self.window == "neural" and self.coverage != "overlap":
            raise ValueError("neural-window jobs support only coverage: overlap")
        if not self.neural_segments:
            raise ValueError(f"job {self.name} has no neural segments")
        if self.window == "neural" and len(self.neural_segments) != 1:
            raise ValueError(
                f"neural-window job {self.name} must resolve to one neural segment"
            )
        if self.window == "video" and self.video.kind != "explicit":
            raise ValueError(
                f"video-window job {self.name} must resolve to explicit video files"
            )


@dataclass(frozen=True)
class SessionSpec:
    """Compatibility view of a neural-window job with one neural segment."""

    name: str
    nev_path: Path
    ns5_path: Path
    time_anchor: TimeAnchor
    video: VideoSelection
    ns3_path: Path | None = None

    def __post_init__(self) -> None:
        segment = NeuralSegmentSpec(
            name=self.name,
            nev_path=self.nev_path,
            ns5_path=self.ns5_path,
            ns3_path=self.ns3_path,
            time_anchor=self.time_anchor,
        )
        object.__setattr__(self, "nev_path", segment.nev_path)
        object.__setattr__(self, "ns5_path", segment.ns5_path)
        object.__setattr__(self, "ns3_path", segment.ns3_path)

    def to_job(self) -> SyncJobSpec:
        return SyncJobSpec(
            name=self.name,
            window="neural",
            neural_segments=(
                NeuralSegmentSpec(
                    name=self.name,
                    nev_path=self.nev_path,
                    ns5_path=self.ns5_path,
                    ns3_path=self.ns3_path,
                    time_anchor=self.time_anchor,
                ),
            ),
            video=self.video,
            coverage="overlap",
        )


@dataclass(frozen=True)
class RunSpec:
    """Shared processing options and one or more normalized output jobs."""

    output_dir: Path
    channel_name: str
    jobs: tuple[SyncJobSpec, ...]
    keep_intermediates: bool = True
    ns3_sidecar: bool = False
    gpu_enabled: bool = False
    gpu_type: str = "nvidia"

    def __post_init__(self) -> None:
        object.__setattr__(self, "output_dir", Path(self.output_dir))
        if not self.jobs:
            raise ValueError("run must contain at least one job")
        names = [job.name for job in self.jobs]
        if len(names) != len(set(names)):
            raise ValueError("job names must be unique")
        if not self.channel_name:
            raise ValueError("channel_name cannot be empty")

    @property
    def sessions(self) -> tuple[SessionSpec, ...]:
        """Return the historical view for callers using neural-window configs."""
        sessions = []
        for job in self.jobs:
            if job.window != "neural":
                raise ValueError("video-window jobs do not have a SessionSpec view")
            segment = job.neural_segments[0]
            sessions.append(
                SessionSpec(
                    name=job.name,
                    nev_path=segment.nev_path,
                    ns5_path=segment.ns5_path,
                    ns3_path=segment.ns3_path,
                    time_anchor=segment.time_anchor,
                    video=job.video,
                )
            )
        return tuple(sessions)


def _validate_output_name(name, label: str) -> None:
    if not isinstance(name, str) or not name:
        raise ValueError(f"{label} name cannot be empty")
    if name != name.strip() or name in {".", ".."} or "/" in name or "\\" in name:
        raise ValueError(
            f"{label} name must be a single path-safe output directory name"
        )


def _as_path(value, field_name: str) -> Path:
    if not value:
        raise ValueError(f"{field_name} is required")
    return Path(value)


def _parse_time_anchor(config) -> TimeAnchor:
    if isinstance(config, str):
        return TimeAnchor(kind=config)
    if not isinstance(config, dict):
        raise ValueError("time_anchor must be a string or mapping")
    reference_path = config.get("reference_path")
    return TimeAnchor(
        kind=config.get("kind"),
        reference_path=Path(reference_path) if reference_path else None,
    )


def _parse_video_selection(config) -> VideoSelection:
    if not isinstance(config, dict):
        raise ValueError("video selection must be a mapping")

    kind = config.get("kind", "directory")
    camera_serials = config.get("camera_serials")
    if camera_serials is not None and not isinstance(camera_serials, list):
        raise ValueError("video.camera_serials must be a list")

    if kind in {"discover", "directory"}:
        return VideoSelection(
            kind="discover",
            recording_dir=_as_path(
                config.get("directory", config.get("recording_dir")),
                "video.directory",
            ),
            camera_serials=(
                tuple(str(serial) for serial in camera_serials)
                if camera_serials is not None
                else None
            ),
        )

    if kind == "file":
        mp4_path = _as_path(config.get("mp4_path"), "video.mp4_path")
        json_path = config.get("json_path")
        if json_path is None:
            json_path = _infer_json_path(mp4_path)
        config = {
            **config,
            "kind": "explicit",
            "json_path": json_path,
            "mp4_paths": [mp4_path],
        }
        kind = "explicit"
    elif kind == "group":
        kind = "explicit"
    elif kind != "explicit":
        raise ValueError(f"Unsupported video selection: {kind}")

    json_paths = config.get("json_paths")
    if json_paths is None and config.get("json_path"):
        json_paths = [config["json_path"]]
    if json_paths is not None and not isinstance(json_paths, list):
        raise ValueError("video.json_paths must be a list")
    mp4_paths = config.get("mp4_paths")
    if isinstance(mp4_paths, dict):
        mapped_serials = tuple(str(serial) for serial in mp4_paths)
        mapped_paths = tuple(Path(path) for path in mp4_paths.values())
        for mapped_serial, path in zip(mapped_serials, mapped_paths):
            actual_serial = _extract_mp4_camera_serial(path)
            if actual_serial != mapped_serial:
                raise ValueError(
                    f"video.mp4_paths key {mapped_serial} does not match "
                    f"camera serial {actual_serial} in {path.name}"
                )
        if camera_serials is None:
            camera_serials = list(mapped_serials)
        mp4_paths = list(mapped_paths)
    if mp4_paths is not None and not isinstance(mp4_paths, list):
        raise ValueError("video.mp4_paths must be a list or camera mapping")
    if isinstance(mp4_paths, list):
        inferred_serials = tuple(
            dict.fromkeys(_extract_mp4_camera_serial(path) for path in mp4_paths)
        )
        if camera_serials is None:
            camera_serials = list(inferred_serials)
        missing_serials = sorted(set(map(str, camera_serials)) - set(inferred_serials))
        if missing_serials:
            raise ValueError(
                "video.camera_serials have no matching explicit MP4: "
                + ", ".join(missing_serials)
            )

    return VideoSelection(
        kind=kind,
        camera_serials=(
            tuple(str(serial) for serial in camera_serials)
            if camera_serials is not None
            else None
        ),
        json_paths=tuple(Path(path) for path in json_paths or []),
        mp4_paths=tuple(Path(path) for path in mp4_paths or []),
    )


def _extract_mp4_camera_serial(path) -> str:
    try:
        return extract_cam_serial(str(path))
    except ValueError as exc:
        raise ValueError(
            f"cannot infer camera serial from explicit MP4 filename: {path}"
        ) from exc


def _infer_json_path(mp4_path: Path) -> Path:
    """Derive the recording-group JSON next to a camera-specific MP4."""
    _extract_mp4_camera_serial(mp4_path)
    parts = mp4_path.name.rsplit(".", 2)
    if len(parts) != 3:
        raise ValueError(f"cannot infer JSON path from MP4 filename: {mp4_path}")
    return mp4_path.with_name(f"{parts[0]}.json")


def _legacy_video_selection(config: dict) -> VideoSelection:
    return VideoSelection(
        kind="discover",
        recording_dir=_as_path(config.get("cam_recording_dir"), "cam_recording_dir"),
        camera_serials=(
            tuple(str(serial) for serial in config["cam_serial"])
            if config.get("cam_serial") is not None
            else None
        ),
    )


def _parse_neural_segments(config, default_name: str | None) -> list[NeuralSegmentSpec]:
    if not isinstance(config, dict):
        raise ValueError("neural selection must be a mapping")

    kind = config.get("kind")
    if kind == "pair":
        nev_path = _as_path(config.get("nev_path"), "neural.nev_path")
        ns5_path = _as_path(config.get("ns5_path"), "neural.ns5_path")
        ns3_path = config.get("ns3_path")
        return [
            NeuralSegmentSpec(
                name=default_name or nev_path.stem,
                nev_path=nev_path,
                ns5_path=ns5_path,
                ns3_path=Path(ns3_path) if ns3_path else None,
                time_anchor=_parse_time_anchor(config.get("time_anchor")),
            )
        ]
    if kind != "directory":
        raise ValueError(f"Unsupported neural selection: {kind}")

    root = _as_path(config.get("directory"), "neural.directory")
    if not root.is_dir():
        raise ValueError(f"neural directory does not exist: {root}")
    recursive = config.get("recursive", False)
    if not isinstance(recursive, bool):
        raise ValueError("neural.recursive must be true or false")
    include = config.get("include")
    if include is not None and (
        not isinstance(include, list)
        or not include
        or not all(isinstance(pattern, str) and pattern for pattern in include)
    ):
        raise ValueError("neural.include must be a non-empty list of glob patterns")
    name_from = config.get("name_from", "stem")
    if name_from not in {"stem", "parent"}:
        raise ValueError("neural.name_from must be 'stem' or 'parent'")

    iterator = root.rglob("*") if recursive else root.iterdir()
    by_pair: dict[tuple[Path, str], dict[str, Path]] = {}
    for path in iterator:
        if not path.is_file() or path.suffix.lower() not in {".nev", ".ns5", ".ns3"}:
            continue
        relative_stem = path.relative_to(root).with_suffix("").as_posix()
        if include and not any(
            fnmatchcase(path.stem, pattern) or fnmatchcase(relative_stem, pattern)
            for pattern in include
        ):
            continue
        by_pair.setdefault((path.parent, path.stem), {})[path.suffix.lower()] = path

    selected = [
        (key, files)
        for key, files in sorted(
            by_pair.items(), key=lambda item: (str(item[0][0]), item[0][1])
        )
        if ".nev" in files or ".ns5" in files
    ]
    if not selected:
        raise ValueError(f"no NEV/NS5 files matched neural directory: {root}")
    unpaired = [
        str((parent / stem).relative_to(root))
        for (parent, stem), files in selected
        if ".nev" not in files or ".ns5" not in files
    ]
    if unpaired:
        raise ValueError(
            "unpaired NEV/NS5 files in neural directory: " + ", ".join(unpaired)
        )

    anchor_config = config.get("time_anchor")
    if not isinstance(anchor_config, (str, dict)):
        raise ValueError("neural.time_anchor must be a string or mapping")
    anchor_kind = (
        anchor_config if isinstance(anchor_config, str) else anchor_config.get("kind")
    )
    reference_paths = (
        anchor_config.get("reference_paths", {})
        if isinstance(anchor_config, dict)
        else {}
    )
    if not isinstance(reference_paths, dict):
        raise ValueError("neural.time_anchor.reference_paths must be a mapping")

    segments = []
    for (parent, stem), files in selected:
        name = stem if name_from == "stem" else parent.name
        if anchor_kind == "first_raw_nev":
            reference_path = reference_paths.get(name)
            if not reference_path:
                raise ValueError(
                    "neural.time_anchor.reference_paths is missing selected "
                    f"segment: {name}"
                )
            anchor = TimeAnchor(
                kind="first_raw_nev", reference_path=Path(reference_path)
            )
        else:
            anchor = _parse_time_anchor(anchor_config)
        segments.append(
            NeuralSegmentSpec(
                name=name,
                nev_path=files[".nev"],
                ns5_path=files[".ns5"],
                ns3_path=files.get(".ns3"),
                time_anchor=anchor,
            )
        )
    return segments


def _expand_video_window_selections(config) -> list[tuple[str, VideoSelection]]:
    if not isinstance(config, dict):
        raise ValueError("video selection must be a mapping")
    if config.get("kind") not in {"directory", "discover"}:
        selection = _parse_video_selection(config)
        files = (*selection.json_paths, *selection.mp4_paths)
        if len(VideoFilesPool.from_files(files).list_groups()) != 1:
            raise ValueError(
                "a video-window file or group selection must contain one "
                "recording timestamp"
            )
        return [(_video_selection_name(selection), selection)]

    selection = _parse_video_selection(config)
    if not selection.recording_dir.is_dir():
        raise ValueError(f"video directory does not exist: {selection.recording_dir}")
    include = config.get("include")
    if include is not None and (
        not isinstance(include, list)
        or not include
        or not all(isinstance(pattern, str) and pattern for pattern in include)
    ):
        raise ValueError("video.include must be a non-empty list of glob patterns")

    pool = VideoFilesPool.from_directory(str(selection.recording_dir))
    expanded = []
    for _, files in pool.list_groups().items():
        json_paths = tuple(Path(path) for path in files if path.endswith(".json"))
        mp4_paths = tuple(Path(path) for path in files if path.endswith(".mp4"))
        if len(json_paths) != 1:
            raise ValueError(
                "each video recording group must contain exactly one JSON file"
            )
        name = json_paths[0].stem
        if include and not any(fnmatchcase(name, pattern) for pattern in include):
            continue
        if selection.camera_serials:
            wanted = set(selection.camera_serials)
            mp4_paths = tuple(
                path for path in mp4_paths if _extract_mp4_camera_serial(path) in wanted
            )
        if not mp4_paths:
            continue
        camera_serials = tuple(
            dict.fromkeys(_extract_mp4_camera_serial(path) for path in mp4_paths)
        )
        expanded.append(
            (
                name,
                VideoSelection(
                    kind="explicit",
                    camera_serials=camera_serials,
                    json_paths=json_paths,
                    mp4_paths=mp4_paths,
                ),
            )
        )
    if not expanded:
        raise ValueError(
            f"no video recording groups matched directory: {selection.recording_dir}"
        )
    return expanded


def _video_selection_name(selection: VideoSelection) -> str:
    if selection.kind != "explicit" or not selection.json_paths:
        raise ValueError("cannot infer a video-window job name from discovery inputs")
    if len(selection.json_paths) != 1:
        raise ValueError("video-window group must contain exactly one JSON file")
    return selection.json_paths[0].stem


def _explicit_jobs(config: dict) -> list[SyncJobSpec]:
    job_configs = config.get("jobs")
    if not isinstance(job_configs, list) or not job_configs:
        raise ValueError("jobs must be a non-empty list")

    jobs = []
    for job_config in job_configs:
        if not isinstance(job_config, dict):
            raise ValueError("each job must be a mapping")
        window = job_config.get("window")
        if window not in {"neural", "video"}:
            raise ValueError("job.window must be 'neural' or 'video'")
        configured_name = job_config.get("name")
        neural_segments = _parse_neural_segments(
            job_config.get("neural"), configured_name
        )
        video_config = job_config.get("video", config.get("video"))
        if video_config is None:
            raise ValueError(
                f"job {configured_name or '<unnamed>'} has no video selection"
            )
        coverage = job_config.get(
            "coverage", "require_full" if window == "video" else "overlap"
        )

        if window == "neural":
            if len(neural_segments) > 1 and configured_name is not None:
                raise ValueError(
                    "a neural-directory job that expands to multiple outputs must "
                    "omit job.name"
                )
            video = _parse_video_selection(video_config)
            jobs.extend(
                SyncJobSpec(
                    name=configured_name or segment.name,
                    window="neural",
                    neural_segments=(segment,),
                    video=video,
                    coverage=coverage,
                )
                for segment in neural_segments
            )
            continue

        video_selections = _expand_video_window_selections(video_config)
        if len(video_selections) > 1 and configured_name is not None:
            raise ValueError(
                "a video-directory job that expands to multiple outputs must omit "
                "job.name"
            )
        jobs.extend(
            SyncJobSpec(
                name=configured_name or inferred_name,
                window="video",
                neural_segments=tuple(neural_segments),
                video=video,
                coverage=coverage,
            )
            for inferred_name, video in video_selections
        )
    return jobs


def _explicit_sessions(config: dict, default_video) -> list[SessionSpec]:
    session_configs = config.get("sessions")
    if not isinstance(session_configs, list) or not session_configs:
        raise ValueError("sessions must be a non-empty list")

    sessions = []
    for session_config in session_configs:
        if not isinstance(session_config, dict):
            raise ValueError("each session must be a mapping")
        video_config = session_config.get("video")
        video = (
            _parse_video_selection(video_config)
            if video_config is not None
            else default_video
        )
        if video is None:
            raise ValueError(
                f"session {session_config.get('name', '<unnamed>')} has no video selection"
            )
        ns3_path = session_config.get("ns3_path")
        sessions.append(
            SessionSpec(
                name=session_config.get("name", ""),
                nev_path=_as_path(session_config.get("nev_path"), "nev_path"),
                ns5_path=_as_path(session_config.get("ns5_path"), "ns5_path"),
                ns3_path=Path(ns3_path) if ns3_path else None,
                time_anchor=_parse_time_anchor(session_config.get("time_anchor")),
                video=video,
            )
        )
    return sessions


def _legacy_sessions(pathutils, video: VideoSelection) -> list[SessionSpec]:
    config = pathutils.config
    if video is None:
        raise ValueError("legacy configuration requires cam_recording_dir")
    if pathutils.is_flat_batch_mode():
        flat_dir = config["flat_dir"]
        keywords = config.get("keywords", config.get("keyword"))
        return [
            SessionSpec(
                name=name,
                nev_path=Path(nev_path),
                ns5_path=Path(ns5_path),
                ns3_path=Path(ns3_path) if ns3_path else None,
                time_anchor=TimeAnchor(kind="paired_ns5"),
                video=video,
            )
            for name, nev_path, ns5_path, ns3_path in pathutils.get_flat_nev_session_files(
                flat_dir, keywords
            )
        ]

    if pathutils.is_batch_mode():
        task_dirs = pathutils.get_matching_task_dirs(
            config["base_dir"], config["keywords"]
        )
        anchor_paths = config.get("first_nev_paths", {})
        if not isinstance(anchor_paths, dict):
            raise ValueError("first_nev_paths must map session names to NEV paths")
        task_names = [Path(task_dir).name for task_dir in task_dirs]
        if "first_nev_paths" in config:
            missing_anchors = sorted(set(task_names) - set(anchor_paths))
            if missing_anchors:
                raise ValueError(
                    "first_nev_paths is missing selected stitched sessions: "
                    + ", ".join(missing_anchors)
                )
        sessions = []
        for task_dir in task_dirs:
            name = Path(task_dir).name
            nev_path = resolve_nsp_file(task_dir, ".nev")
            ns5_path = resolve_nsp_file(task_dir, ".ns5")
            ns3_path = resolve_nsp_file(task_dir, ".ns3")
            reference_path = (
                anchor_paths[name]
                if "first_nev_paths" in config
                else config.get("first_nev_path")
            )
            anchor = (
                TimeAnchor(kind="first_raw_nev", reference_path=Path(reference_path))
                if reference_path
                else TimeAnchor(kind="serial_only")
            )
            sessions.append(
                SessionSpec(
                    name=name,
                    nev_path=_as_path(nev_path, f"{name} NEV"),
                    ns5_path=_as_path(ns5_path, f"{name} NS5"),
                    ns3_path=Path(ns3_path) if ns3_path else None,
                    time_anchor=anchor,
                    video=video,
                )
            )
        return sessions

    nsp_dir = config["nsp_dir"]
    nev_path = resolve_nsp_file(nsp_dir, ".nev")
    ns5_path = resolve_nsp_file(nsp_dir, ".ns5")
    ns3_path = resolve_nsp_file(nsp_dir, ".ns3")
    reference_path = config.get("first_nev_path")
    anchor = (
        TimeAnchor(kind="first_raw_nev", reference_path=Path(reference_path))
        if reference_path
        else TimeAnchor(kind="serial_only")
    )
    return [
        SessionSpec(
            name=Path(nsp_dir).name,
            nev_path=_as_path(nev_path, "NEV"),
            ns5_path=_as_path(ns5_path, "NS5"),
            ns3_path=Path(ns3_path) if ns3_path else None,
            time_anchor=anchor,
            video=video,
        )
    ]


def resolve_run_spec(pathutils) -> RunSpec:
    """Normalize job, session, or legacy YAML into one run model."""
    config = pathutils.config
    modes = [
        field
        for field in ("jobs", "sessions", "nsp_dir", "flat_dir", "base_dir")
        if field in config
    ]
    if len(modes) != 1:
        raise ValueError(
            "configure exactly one of jobs, sessions, nsp_dir, flat_dir, or base_dir"
        )
    if "jobs" in config:
        jobs = _explicit_jobs(config)
    else:
        default_video = (
            _parse_video_selection(config["video"])
            if "video" in config
            else (
                _legacy_video_selection(config)
                if config.get("cam_recording_dir")
                else None
            )
        )
        sessions = (
            _explicit_sessions(config, default_video)
            if "sessions" in config
            else _legacy_sessions(pathutils, default_video)
        )
        jobs = [session.to_job() for session in sessions]
    run_spec = RunSpec(
        output_dir=_as_path(config.get("output_dir"), "output_dir"),
        channel_name=config.get("channel_name", ""),
        jobs=tuple(jobs),
        keep_intermediates=bool(config.get("keep_intermediates", True)),
        ns3_sidecar=bool(config.get("ns3_sidecar", False)),
        gpu_enabled=bool(config.get("gpu_enabled", False)),
        gpu_type=config.get("gpu_type", "nvidia"),
    )
    _validate_run_paths(run_spec)
    return run_spec


def _validate_run_paths(run_spec: RunSpec) -> None:
    """Fail configuration preflight before any expensive processing starts."""
    checked_videos = set()
    for job in run_spec.jobs:
        for segment in job.neural_segments:
            required_files = {
                "NEV": segment.nev_path,
                "NS5": segment.ns5_path,
            }
            if segment.ns3_path is not None:
                required_files["NS3"] = segment.ns3_path
            if segment.time_anchor.reference_path is not None:
                required_files["time anchor"] = segment.time_anchor.reference_path
            for label, path in required_files.items():
                if not path.is_file():
                    raise ValueError(f"{label} file does not exist: {path}")

        if job.video in checked_videos:
            continue
        checked_videos.add(job.video)
        if job.video.kind == "discover":
            if not job.video.recording_dir.is_dir():
                raise ValueError(
                    "video recording directory does not exist: "
                    f"{job.video.recording_dir}"
                )
        else:
            for path in (*job.video.json_paths, *job.video.mp4_paths):
                if not path.is_file():
                    raise ValueError(f"explicit video file does not exist: {path}")

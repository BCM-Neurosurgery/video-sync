"""Validated run/session models and configuration normalization."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pyvideosync.data_pool import resolve_nsp_file
from pyvideosync.utils import extract_cam_serial

AnchorKind = Literal[
    "paired_ns5",
    "first_raw_nev",
    "embedded",
    "serial_only",
]
VideoKind = Literal["discover", "explicit"]


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
class SessionSpec:
    """All resolved inputs required to synchronize one neural session."""

    name: str
    nev_path: Path
    ns5_path: Path
    time_anchor: TimeAnchor
    video: VideoSelection
    ns3_path: Path | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "nev_path", Path(self.nev_path))
        object.__setattr__(self, "ns5_path", Path(self.ns5_path))
        if self.ns3_path is not None:
            object.__setattr__(self, "ns3_path", Path(self.ns3_path))
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("session name cannot be empty")
        if (
            self.name != self.name.strip()
            or self.name in {".", ".."}
            or "/" in self.name
            or "\\" in self.name
        ):
            raise ValueError(
                "session name must be a single path-safe output directory name"
            )
        if self.nev_path.suffix.lower() != ".nev":
            raise ValueError(f"Expected a NEV path: {self.nev_path}")
        if self.ns5_path.suffix.lower() != ".ns5":
            raise ValueError(f"Expected an NS5 path: {self.ns5_path}")
        if self.ns3_path is not None and self.ns3_path.suffix.lower() != ".ns3":
            raise ValueError(f"Expected an NS3 path: {self.ns3_path}")


@dataclass(frozen=True)
class RunSpec:
    """Shared processing options and one or more normalized sessions."""

    output_dir: Path
    channel_name: str
    sessions: tuple[SessionSpec, ...]
    keep_intermediates: bool = True
    ns3_sidecar: bool = False
    gpu_enabled: bool = False
    gpu_type: str = "nvidia"

    def __post_init__(self) -> None:
        object.__setattr__(self, "output_dir", Path(self.output_dir))
        if not self.sessions:
            raise ValueError("run must contain at least one session")
        names = [session.name for session in self.sessions]
        if len(names) != len(set(names)):
            raise ValueError("session names must be unique")
        if not self.channel_name:
            raise ValueError("channel_name cannot be empty")


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

    kind = config.get("kind", "discover")
    camera_serials = config.get("camera_serials")
    if camera_serials is not None and not isinstance(camera_serials, list):
        raise ValueError("video.camera_serials must be a list")

    if kind == "discover":
        return VideoSelection(
            kind="discover",
            recording_dir=_as_path(config.get("recording_dir"), "recording_dir"),
            camera_serials=(
                tuple(str(serial) for serial in camera_serials)
                if camera_serials is not None
                else None
            ),
        )

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
    """Normalize new or legacy YAML configuration into one run model."""
    config = pathutils.config
    if "sessions" in config and any(
        field in config for field in ("nsp_dir", "flat_dir", "base_dir")
    ):
        raise ValueError(
            "sessions cannot be combined with nsp_dir, flat_dir, or base_dir"
        )
    default_video = (
        _parse_video_selection(config["video"])
        if "video" in config
        else (
            _legacy_video_selection(config) if config.get("cam_recording_dir") else None
        )
    )
    sessions = (
        _explicit_sessions(config, default_video)
        if "sessions" in config
        else _legacy_sessions(pathutils, default_video)
    )
    run_spec = RunSpec(
        output_dir=_as_path(config.get("output_dir"), "output_dir"),
        channel_name=config.get("channel_name", ""),
        sessions=tuple(sessions),
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
    for session in run_spec.sessions:
        required_files = {
            "NEV": session.nev_path,
            "NS5": session.ns5_path,
        }
        if session.ns3_path is not None:
            required_files["NS3"] = session.ns3_path
        if session.time_anchor.reference_path is not None:
            required_files["time anchor"] = session.time_anchor.reference_path
        for label, path in required_files.items():
            if not path.is_file():
                raise ValueError(f"{label} file does not exist: {path}")

        if session.video in checked_videos:
            continue
        checked_videos.add(session.video)
        if session.video.kind == "discover":
            if not session.video.recording_dir.is_dir():
                raise ValueError(
                    "video recording directory does not exist: "
                    f"{session.video.recording_dir}"
                )
        else:
            for path in (*session.video.json_paths, *session.video.mp4_paths):
                if not path.is_file():
                    raise ValueError(f"explicit video file does not exist: {path}")

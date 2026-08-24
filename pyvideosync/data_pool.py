from __future__ import annotations
import os
from collections import defaultdict
from pyvideosync.utils import extract_timestamp, extract_cam_serial
from pathlib import Path


class DataPool:
    """Manages NSP and video data for integrity verification and statistics.

    Attributes:
        nsp_dir (str): Directory containing NSP files.
        cam_recording_dir (str): Directory containing camera recordings.
        nev_pool (NevPool): Stores NEV files.
        nsx_pool (NsxPool): Stores NS5/NS3 files.
        video_pool (VideoPool): Stores video files.
        video_json_pool (VideoJsonPool): Stores video metadata.
        video_file_pool (VideoFilesPool): Stores all video-related files.
    """

    def __init__(
        self,
        nsp_dir: str,
        cam_recording_dir: str,
        nev_path: str | None = None,
        ns5_path: str | None = None,
        ns3_path: str | None = None,
        video_file_pool: VideoFilesPool | None = None,
    ) -> None:
        """Initializes the DataPool class.

        Args:
            nsp_dir (str): Path to the NSP directory (used for file discovery
                when explicit per-extension paths are not provided).
            cam_recording_dir (str): Path to the camera recording directory.
            nev_path (str, optional): Explicit NEV file path. When set,
                directory-based discovery for the NEV is bypassed.
            ns5_path (str, optional): Explicit NS5 file path. When set,
                directory-based discovery for the NS5 is bypassed.
            ns3_path (str, optional): Explicit NS3 file path. When set,
                directory-based discovery for the NS3 is bypassed.
            video_file_pool (VideoFilesPool, optional): Pre-indexed camera
                files shared across batch sessions.
        """
        self.nsp_dir = nsp_dir
        self.cam_recording_dir = cam_recording_dir
        # Per-extension overrides; when an entry is set, get_nsp_path(ext)
        # returns it directly without scanning the directory.
        self._explicit_paths: dict[str, str | None] = {
            ".nev": nev_path,
            ".ns5": ns5_path,
            ".ns3": ns3_path,
        }
        self.video_file_pool = (
            video_file_pool
            if video_file_pool is not None
            else VideoFilesPool.from_directory(self.cam_recording_dir)
        )

    def _resolve_nsp_file(self, extension: str) -> str:
        """Pick a single NSP file by extension.

        Prefers files ending in `NSP-1.<ext>` so stitched dirs containing both
        NSP-1 and NSP-2 files resolve to NSP-1. Falls back to any single file
        with the given extension (TRD-style single-file dirs).
        """
        ext = extension.lower()
        suffix_match = []
        any_match = []
        for file in os.listdir(self.nsp_dir):
            full_path = os.path.join(self.nsp_dir, file)
            if not os.path.isfile(full_path):
                continue
            lower = file.lower()
            if lower.endswith(ext):
                any_match.append(full_path)
                if lower.endswith(f"nsp-1{ext}"):
                    suffix_match.append(full_path)

        if len(suffix_match) == 1:
            return suffix_match[0]
        if not suffix_match and len(any_match) == 1:
            return any_match[0]
        return ""

    def verify_integrity(self) -> bool:
        """Verifies a NEV and NS5 file are resolvable for this session.

        Accepts stitched naming (`*NSP-1.nev` / `*NSP-1.ns5`, possibly
        alongside NSP-2 siblings), a single arbitrarily-named `.nev` + `.ns5`,
        or explicit paths supplied via the constructor. NS3 is optional and
        not part of the integrity check.
        """
        return bool(self.get_nev_path()) and bool(self.get_ns5_path())

    def get_nsp_path(self, ext: str) -> str:
        """Resolve the NSP file with the given extension.

        Honors any explicit-path override passed to the constructor first,
        then falls back to suffix-aware directory discovery.
        Returns an empty string if no file resolves.
        """
        explicit = self._explicit_paths.get(ext)
        if explicit:
            return explicit
        return self._resolve_nsp_file(ext)

    def get_nev_path(self) -> str:
        """Resolved NEV file path, or empty string if none."""
        return self.get_nsp_path(".nev")

    def get_ns5_path(self) -> str:
        """Resolved NS5 file path, or empty string if none."""
        return self.get_nsp_path(".ns5")

    def get_ns3_path(self) -> str:
        """Resolved NS3 file path, or empty string if none."""
        return self.get_nsp_path(".ns3")

    def get_video_file_pool(self) -> "VideoFilesPool":
        """Retrieves the video file pool.

        Returns:
            VideoFilesPool: The video file pool object.
        """
        return self.video_file_pool


class VideoFilesPool:
    """Stores all video-related files grouped by timestamp."""

    def __init__(self) -> None:
        self.files = defaultdict(list)

    @classmethod
    def from_directory(cls, camera_dir: str) -> "VideoFilesPool":
        """Index camera JSON/MP4 files once from a root or date subdirectories."""
        pool = cls()
        root = Path(camera_dir)
        for entry in sorted(root.iterdir()):
            candidates = sorted(entry.iterdir()) if entry.is_dir() else [entry]
            for file_path in candidates:
                if not file_path.is_file() or file_path.suffix.lower() not in {
                    ".json",
                    ".mp4",
                }:
                    continue
                try:
                    pool.add_file(str(file_path.resolve()))
                except ValueError:
                    continue
        return pool

    def add_file(self, file: str):
        """Adds a video-related file to the pool.

        Args:
            file (str): File name to be added.
        """
        timestamp = extract_timestamp(file)
        self.files[timestamp].append(file)

    def list_groups(self) -> dict[str, list[str]]:
        """Lists groups of files sorted by timestamp.

        Returns:
            dict[str, list[str]]: A dictionary where keys are timestamps (str)
            and values are lists of file names (str).
        """
        return {timestamp: self.files[timestamp] for timestamp in sorted(self.files)}

    def find_one_random_json(self) -> str | None:
        """Finds a random JSON file in the pool.

        Returns:
            str: A JSON file name if found, otherwise None.
        """
        for files in self.files.values():
            for file in files:
                if file.endswith(".json"):
                    return file
        return None

    def get_unique_cam_serials(self) -> set[str]:
        """
        Returns a set of all unique camera serial numbers found in the filenames.

        Returns:
            set[str]: A set of unique camera serial numbers.
        """
        serials = set()
        for files in self.files.values():
            for file in files:
                if file.endswith(".mp4"):
                    serial = extract_cam_serial(file)
                    if serial:
                        serials.add(serial)
        return serials

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
    ) -> None:
        """Initializes the DataPool class.

        Args:
            nsp_dir (str): Path to the NSP directory (used for file discovery
                when explicit nev/ns5 paths are not provided).
            cam_recording_dir (str): Path to the camera recording directory.
            nev_path (str, optional): Explicit NEV file path. When set,
                directory-based discovery for the NEV is bypassed.
            ns5_path (str, optional): Explicit NS5 file path. When set,
                directory-based discovery for the NS5 is bypassed.
        """
        self.nsp_dir = nsp_dir
        self.cam_recording_dir = cam_recording_dir
        self._explicit_nev = nev_path
        self._explicit_ns5 = ns5_path
        self.video_file_pool = VideoFilesPool()
        self.init_pools()

    def init_pools(self):
        """Initializes the pools by:

        Grouping the files in the video pool by timestamp.
        """
        for datefolder_path in Path(self.cam_recording_dir).iterdir():
            if datefolder_path.is_dir():
                for file_path in datefolder_path.iterdir():
                    self.video_file_pool.add_file(str(file_path.resolve()))

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

        Accepts either stitched naming (`*NSP-1.nev` / `*NSP-1.ns5`, possibly
        alongside NSP-2 siblings), a single arbitrarily-named `.nev` + `.ns5`,
        or explicit paths supplied via the constructor.
        """
        return bool(self.get_nev_path()) and bool(self.get_ns5_path())

    def get_nev_path(self) -> str:
        """Returns the resolved NEV file path, or an empty string if none."""
        if self._explicit_nev:
            return self._explicit_nev
        return self._resolve_nsp_file(".nev")

    def get_ns5_path(self) -> str:
        """Returns the resolved NS5 file path, or an empty string if none."""
        if self._explicit_ns5:
            return self._explicit_ns5
        return self._resolve_nsp_file(".ns5")

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

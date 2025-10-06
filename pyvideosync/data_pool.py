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

    def __init__(self, nsp_dir: str, cam_recording_dir: str) -> None:
        """Initializes the DataPool class.

        Args:
            nsp_dir (str): Path to the NSP directory.
            cam_recording_dir (str): Path to the camera recording directory.
        """
        self.nsp_dir = nsp_dir
        self.cam_recording_dir = cam_recording_dir
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

    def verify_integrity(self) -> bool:
        """Verifies the NSP directory has exactly one `.nev` file and one `.ns5` file."""
        nev_files = self._find_files_by_extension(".nev")
        ns5_files = self._find_files_by_extension(".ns5")
        return len(nev_files) == 1 and len(ns5_files) == 1

    def get_nev_path(self) -> str:
        """Returns the single `.nev` file path if present, otherwise an empty string."""
        nev_files = self._find_files_by_extension(".nev")
        return nev_files[0] if len(nev_files) == 1 else ""

    def get_ns5_path(self) -> str:
        """Returns the single `.ns5` file path if present, otherwise an empty string."""
        ns5_files = self._find_files_by_extension(".ns5")
        return ns5_files[0] if len(ns5_files) == 1 else ""

    def _find_files_by_extension(self, extension: str) -> list[str]:
        """List files in the NSP directory that match an extension."""
        matches = []
        for file in os.listdir(self.nsp_dir):
            full_path = os.path.join(self.nsp_dir, file)
            if os.path.isfile(full_path) and file.lower().endswith(extension.lower()):
                matches.append(full_path)
        return matches

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

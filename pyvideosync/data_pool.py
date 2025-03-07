from __future__ import annotations
import os
from collections import defaultdict
from pyvideosync.utils import extract_timestamp, extract_cam_serial
import fnmatch
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
        self.nev_pool = NevPool()
        self.nsx_pool = NsxPool()
        self.video_pool = VideoPool()
        self.video_json_pool = VideoJsonPool()
        self.video_file_pool = VideoFilesPool()
        self.init_pools()

    def init_pools(self):
        """Initializes the pools by:

        1. Populating NEV and NSX pools with corresponding files.
        2. Grouping the files in the video pool by timestamp.
        """
        for file_path in Path(self.nsp_dir).iterdir():
            if file_path.suffix == ".nev":
                self.nev_pool.add_file(file_path.name)
            elif file_path.suffix in {".ns5", ".ns3"}:
                self.nsx_pool.add_file(file_path.name)

        for datefolder_path in Path(self.cam_recording_dir).iterdir():
            if datefolder_path.is_dir():
                for file_path in datefolder_path.iterdir():
                    self.video_file_pool.add_file(str(file_path.resolve()))

    def verify_integrity(self) -> bool:
        """Verifies the integrity of the directory by ensuring it contains exactly one of each required file.

        Required files:
            - One file matching pattern `*NSP-1.nev`
            - One file matching pattern `*NSP-1.ns3`
            - One file matching pattern `*NSP-1.ns5`
            - One file matching pattern `*NSP-2.nev`

        Returns:
            bool: True if exactly one of each required file is found, otherwise False.
        """
        required_files = {
            "*NSP-1.nev": 0,
            "*NSP-1.ns3": 0,
            "*NSP-1.ns5": 0,
            "*NSP-2.nev": 0,
        }

        for file in os.listdir(self.nsp_dir):
            for pattern in required_files.keys():
                if fnmatch.fnmatch(file, pattern):
                    required_files[pattern] += 1

        return all(count == 1 for count in required_files.values())

    def get_nsp1_nev_path(self) -> str:
        """Finds the NSP-1 NEV file path.

        Returns:
            str: The full path of the matching file if found, otherwise an empty string.
        """
        pattern = "*NSP-1.nev"

        for file in os.listdir(self.nsp_dir):
            if fnmatch.fnmatch(file, pattern):
                return os.path.join(self.nsp_dir, file)

        return ""

    def get_nsp1_ns5_path(self) -> str:
        """Finds the NSP-1 NS5 file path.

        Returns:
            str: The full path of the matching file if found, otherwise an empty string.
        """
        pattern = "*NSP-1.ns5"

        for file in os.listdir(self.nsp_dir):
            if fnmatch.fnmatch(file, pattern):
                return os.path.join(self.nsp_dir, file)

        return ""

    def get_video_file_pool(self) -> "VideoFilesPool":
        """Retrieves the video file pool.

        Returns:
            VideoFilesPool: The video file pool object.
        """
        return self.video_file_pool


class NevPool:
    """Stores NEV files grouped by suffix."""

    def __init__(self) -> None:
        self.files = defaultdict(list)

    def add_file(self, file: str):
        """Adds a NEV file to the pool.

        Args:
            file (str): File name to be added.
        """
        suffix = file.split("-")[-1]
        self.files[suffix].append(file)


class NsxPool:
    """Stores NS5 and NS3 files grouped by suffix."""

    def __init__(self) -> None:
        self.files = defaultdict(list)

    def add_file(self, file: str):
        """Adds an NS5/NS3 file to the pool.

        Args:
            file (str): File name to be added.
        """
        suffix = file.split("-")[-1]
        self.files[suffix].append(file)


class VideoPool:
    """Stores video files grouped by timestamp."""

    def __init__(self) -> None:
        self.files = defaultdict(list)

    def add_file(self, file: str):
        """Adds a video file to the pool.

        Args:
            file (str): File name to be added.
        """
        timestamp = file.split("_")[-1].split(".")[0]
        self.files[timestamp].append(file)


class VideoJsonPool:
    """Stores video metadata JSON files grouped by timestamp."""

    def __init__(self) -> None:
        self.files = defaultdict(list)

    def add_file(self, file: str):
        timestamp = file.split("_")[-1].split(".")[0]
        self.files[timestamp].append(file)

    def list_groups(self) -> dict[str, list[str]]:
        """Lists all groups of video metadata files.

        Returns:
            dict[str, list[str]]: A dictionary where keys are timestamps (str)
            and values are lists of file names (str).
        """
        return {timestamp: files for timestamp, files in self.files.items()}


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

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

        Grouping the files in the video pool by timestamp.
        """
        for taskfolder_path in Path(self.cam_recording_dir).iterdir():
            if taskfolder_path.is_dir():
                for datefolder_path in taskfolder_path.iterdir():
                    if datefolder_path.is_dir():
                        for file_path in datefolder_path.iterdir():
                            self.video_file_pool.add_file(str(file_path.resolve()))

    def verify_integrity(self) -> bool:
        """Verifies the integrity of the directory by ensuring it contains exactly one `.nev` file and one `.ns5` file.

        Returns:
            bool: True if exactly one `.nev` file and exactly one `.ns5` file are found, otherwise False.
        """
        nev_count = 0
        ns5_count = 0

        for file in os.listdir(self.nsp_dir):
            if fnmatch.fnmatch(file, "*.nev"):
                nev_count += 1
            elif fnmatch.fnmatch(file, "*.ns5"):
                ns5_count += 1

        return nev_count == 1 and ns5_count == 1

    def get_nev_path(self) -> str:
        """Finds the first NEV file in the directory.

        Returns:
            str: The full path of the first matching `.nev` file if found, otherwise an empty string.
        """
        for file in os.listdir(self.nsp_dir):
            if fnmatch.fnmatch(file, "*.nev"):
                return os.path.join(self.nsp_dir, file)

        return ""

    def get_ns5_path(self) -> str:
        """Finds the first NS5 file in the directory.

        Returns:
            str: The full path of the first matching `.ns5` file if found, otherwise an empty string.
        """
        for file in os.listdir(self.nsp_dir):
            if fnmatch.fnmatch(file, "*.ns5"):
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
        """
        Adds a file to the internal dictionary, grouping by its timestamp.

        The timestamp is extracted from the file name as the portion after the last underscore (`_`)
        and before the file extension (`.`).

        Example:
            Given file names:
            - "utsw_TRD011_day_1_20240716_154737.23512011.mp4"
            - "utsw_TRD011_day_1_20240716_152736.json"

            The extracted timestamps would be:
            - "154737" from "utsw_TRD011_day_1_20240716_154737.23512011.mp4"
            - "152736" from "utsw_TRD011_day_1_20240716_152736.json"

            These files are then grouped by their extracted timestamp.

        Args:
            file (str): The file name including its extension.

        """
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

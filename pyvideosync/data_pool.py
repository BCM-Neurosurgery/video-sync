import os
from collections import defaultdict
from pyvideosync.utils import extract_timestamp
import fnmatch


class DataPool:
    """This class does the following to the NSP data:
    1. verify integrity
    2. get basic statistics
    """

    def __init__(self, nsp_dir: str, cam_recording_dir: str) -> None:
        self.nsp_dir = nsp_dir
        self.cam_recording_dir = cam_recording_dir
        self.nsp_files = os.listdir(nsp_dir)
        self.cam_files = os.listdir(cam_recording_dir)
        self.nev_pool = NevPool()
        self.nsx_pool = NsxPool()
        self.video_pool = VideoPool()
        self.video_json_pool = VideoJsonPool()
        self.video_file_pool = VideoFilesPool()
        self.init_pools()

    def init_pools(self):
        """Do the following:
        1. Initialize nevpool and nsxpool
        2. Create mapping which allows constant access between:
            - nev-ns5-ns3
            - previous and next file of nev/ns5/ns3
        """
        for file in self.nsp_files:
            if file.endswith(".nev"):
                self.nev_pool.add_file(file)
            elif file.endswith(".ns5") or file.endswith(".ns3"):
                self.nsx_pool.add_file(file)

        for file in self.cam_files:
            self.video_file_pool.add_file(file)
            if file.endswith(".mp4"):
                self.video_pool.add_file(file)
            elif file.endswith(".json"):
                self.video_json_pool.add_file(file)

    def verify_integrity(self) -> bool:
        """
        Verifies the integrity of a directory by checking if it contains exactly one of each required file:
        - One file matching pattern `*NSP-1.nev`
        - One file matching pattern `*NSP-1.ns3`
        - One file matching pattern `*NSP-1.ns5`
        - One file matching pattern `*NSP-2.nev`

        Args:
            directory (str): The path to the directory to check.

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
        """
        Searches for a file matching the pattern '*NSP-1.nev' in the specified directory and returns its path.

        Args:
            directory (str): The path to the directory to search.

        Returns:
            str: The full path of the matching file if found, otherwise an empty string.
        """
        pattern = "*NSP-1.nev"

        for file in os.listdir(self.nsp_dir):
            if fnmatch.fnmatch(file, pattern):
                return os.path.join(self.nsp_dir, file)

        return ""

    def get_nsp1_ns5_path(self) -> str:
        """
        Searches for a file matching the pattern '*NSP-1.ns5' in the specified directory and returns its path.

        Args:
            directory (str): The path to the directory to search.

        Returns:
            str: The full path of the matching file if found, otherwise an empty string.
        """
        pattern = "*NSP-1.ns5"

        for file in os.listdir(self.nsp_dir):
            if fnmatch.fnmatch(file, pattern):
                return os.path.join(self.nsp_dir, file)

        return ""

    def get_video_file_pool(self):
        return self.video_file_pool


class NevPool:
    def __init__(self) -> None:
        self.files = defaultdict(list)

    def add_file(self, file: str):
        suffix = file.split("-")[-1]
        self.files[suffix].append(file)


class NsxPool:
    def __init__(self) -> None:
        self.files = defaultdict(list)

    def add_file(self, file: str):
        suffix = file.split("-")[-1]
        self.files[suffix].append(file)


class VideoPool:
    def __init__(self) -> None:
        self.files = defaultdict(list)

    def add_file(self, file: str):
        timestamp = file.split("_")[-1].split(".")[0]
        self.files[timestamp].append(file)


class VideoJsonPool:
    def __init__(self) -> None:
        self.files = defaultdict(list)

    def add_file(self, file: str):
        timestamp = file.split("_")[-1].split(".")[0]
        self.files[timestamp].append(file)

    def list_groups(self):
        return {timestamp: files for timestamp, files in self.files.items()}


class VideoFilesPool:
    def __init__(self) -> None:
        self.files = defaultdict(list)

    def add_file(self, file: str):
        timestamp = extract_timestamp(file)
        self.files[timestamp].append(file)

    def list_groups(self):
        """
        Returns a dictionary of sorted timestamps and corresponding files.
        """
        return {timestamp: self.files[timestamp] for timestamp in sorted(self.files)}

    def find_one_random_json(self):
        for files in self.files.values():
            for file in files:
                if file.endswith(".json"):
                    return file
        return None

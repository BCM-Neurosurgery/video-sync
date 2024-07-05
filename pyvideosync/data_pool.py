"""
Example usage:
nsp_manager = NspPool('/path/to/nsp_directory', '/path/to/cam_recording_directory')
print(nsp_manager.nev_pool.get_num_nsp1_nev())
print(nsp_manager.nev_pool.get_num_nsp2_nev())
print(nsp_manager.nsx_pool.get_num_nsp1_ns5())
print(nsp_manager.nsx_pool.get_num_nsp2_ns5())
print(nsp_manager.nsx_pool.get_num_nsp1_ns3())
print(nsp_manager.nsx_pool.get_num_nsp2_ns3())
print(nsp_manager.verify_integrity())
print(nsp_manager.nev_pool.list_groups())
print(nsp_manager.nsx_pool.list_groups())
print(nsp_manager.video_pool.list_groups())
print(nsp_manager.video_json_pool.list_groups())
"""

import os
from collections import defaultdict


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
            if file.endswith(".mp4"):
                self.video_pool.add_file(file)
            elif file.endswith(".json"):
                self.video_json_pool.add_file(file)

    def verify_integrity(self):
        """Verify integrity of NSP data"""
        # Group files by their suffix (the last part of the name)
        groups = defaultdict(list)
        for file in self.nsp_files:
            suffix = file.split("-")[-1]
            groups[suffix].append(file)

        # Check if each group contains one nev, one ns5, and one ns3 file
        for group in groups.values():
            has_nev = any(file.endswith(".nev") for file in group)
            has_ns5 = any(file.endswith(".ns5") for file in group)
            has_ns3 = any(file.endswith(".ns3") for file in group)
            if not (has_nev and has_ns5 and has_ns3):
                return False
        return True

    def get_nev_pool(self):
        return self.nev_pool

    def get_nsx_pool(self):
        return self.nsx_pool

    def get_video_pool(self):
        return self.video_pool

    def get_video_json_pool(self):
        return self.video_json_pool


class NevPool:
    def __init__(self) -> None:
        self.files = defaultdict(list)

    def add_file(self, file: str):
        suffix = file.split("-")[-1]
        self.files[suffix].append(file)

    def get_num(self, prefix: str) -> int:
        return sum(
            1
            for files in self.files.values()
            for file in files
            if file.startswith(prefix)
        )

    def get_num_nsp1_nev(self) -> int:
        return self.get_num("NSP1")

    def get_num_nsp2_nev(self) -> int:
        return self.get_num("NSP2")

    def list_nsp1_nev(self):
        return [
            file
            for files in self.files.values()
            for file in files
            if file.startswith("NSP1")
        ]

    def list_nsp2_nev(self):
        return [
            file
            for files in self.files.values()
            for file in files
            if file.startswith("NSP2")
        ]

    def list_groups(self):
        return {suffix: files for suffix, files in self.files.items()}


class NsxPool:
    def __init__(self) -> None:
        self.files = defaultdict(list)

    def add_file(self, file: str):
        suffix = file.split("-")[-1]
        self.files[suffix].append(file)

    def get_num(self, prefix: str, suffix: str) -> int:
        return sum(
            1
            for files in self.files.values()
            for file in files
            if file.startswith(prefix) and file.endswith(suffix)
        )

    def get_num_nsp1_ns5(self) -> int:
        return self.get_num("NSP1", ".ns5")

    def get_num_nsp2_ns5(self) -> int:
        return self.get_num("NSP2", ".ns5")

    def get_num_nsp1_ns3(self) -> int:
        return self.get_num("NSP1", ".ns3")

    def get_num_nsp2_ns3(self) -> int:
        return self.get_num("NSP2", ".ns3")

    def list_files(self, prefix: str, suffix: str):
        return [
            file
            for files in self.files.values()
            for file in files
            if file.startswith(prefix) and file.endswith(suffix)
        ]

    def list_nsp1_ns5(self):
        return self.list_files("NSP1", ".ns5")

    def list_nsp2_ns5(self):
        return self.list_files("NSP2", ".ns5")

    def list_nsp1_ns3(self):
        return self.list_files("NSP1", ".ns3")

    def list_nsp2_ns3(self):
        return self.list_files("NSP2", ".ns3")

    def list_groups(self):
        return {suffix: files for suffix, files in self.files.items()}


class VideoPool:
    def __init__(self) -> None:
        self.files = defaultdict(list)

    def add_file(self, file: str):
        timestamp = file.split("_")[-1].split(".")[0]
        self.files[timestamp].append(file)

    def list_groups(self):
        return {timestamp: files for timestamp, files in self.files.items()}


class VideoJsonPool:
    def __init__(self) -> None:
        self.files = defaultdict(list)

    def add_file(self, file: str):
        timestamp = file.split("_")[-1].split(".")[0]
        self.files[timestamp].append(file)

    def list_groups(self):
        return {timestamp: files for timestamp, files in self.files.items()}

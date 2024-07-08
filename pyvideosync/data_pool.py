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

TODO:
1. verify integrity
 - each NSP1 group should have exactly 1 nev/ns5/ns3
 - 
"""

import os
from collections import defaultdict
from pathlib import Path


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
        groups = self.get_nsp1_file_groups()
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

    def _group_files(self, prefix=None):
        """Helper method to group files by base name with
        an optional prefix filter"""
        groups = defaultdict(list)
        for file in self.nsp_files:
            base_name = Path(file).stem
            if prefix is None or base_name.startswith(prefix):
                groups[base_name].append(file)
        return groups

    def get_file_groups(self):
        """Get groups of files in nsp_dir with the same base
        name but different formats"""
        return self._group_files()

    def get_nsp1_file_groups(self):
        """Get groups of NSP1 files in nsp_dir with the same
        base name but different formats"""
        return self._group_files(prefix="NSP1")

    def get_mp4_filelist(self, cam_serial: str) -> list:
        """Get list of MP4 files matching the given camera serial numbers"""
        mp4_files = []
        for file in self.cam_files:
            if file.endswith(".mp4"):
                if cam_serial in file:
                    mp4_files.append(file)
        return mp4_files


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

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
from pyvideosync.videojson import Videojson
from pyvideosync.video import Video
from pyvideosync.nev import Nev
from pyvideosync.nsx import Nsx
import re
from typing import List, Dict
from pyvideosync.utils import extract_timestamp


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

    def get_video_file_pool(self):
        return self.video_file_pool

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
        """Get list of MP4 files matching the given camera serial numbers and sort them by timestamp."""

        def get_timestamp(file: str) -> int:
            """Extract timestamp from file to int

            Args:
                file (str): e.g. 15min_7_3_24_synctest_20240703_160408.23512908.mp4

            Returns:
                int: 160408
            """
            match = re.match(r".*_(\d{6})\.\d+\..*", file)

            if match:
                return match.group(1)
            else:
                raise ValueError("mp4 filenames parsed error!")

        mp4_files = []
        for file in self.cam_files:
            if file.endswith(".mp4") and cam_serial in file:
                mp4_files.append(file)

        mp4_files.sort(key=lambda x: get_timestamp(x))
        return mp4_files

    def find_ns5_associated_files(self, ns5_file: str, cam_serial: str):
        """Find associated files for the given ns5_file

        Args:
            ns5_file (str): e.g. NSP1-20240328-202820-001.ns5
            cam_serial (str): e.g. 23512908

        Returns:
            dict: {
                "NEV": [{
                    "nev_rel_path": xxx,
                    "nev_start_chunk_serial": xxx,
                    "nev_end_chunk_serial": xxx,
                    "nev_time_origin": xxx,
                    "nev_start_timestamp": xxx,
                    "nev_duration_readable": xxx,
                }],
                "VIDEO": [{
                    "mp4_rel_path": xxx,
                    "frame_count": xxx,
                }],
                "JSON": [{
                    "json_rel_path": xxx,
                    "json_start_chunk_serial": xxx,
                    "json_end_chunk_serial": xxx,
                    "json_time_origin": xxx,
                    "json_duration_readable": xxx,
                }],
            }
        """
        res = defaultdict(list)
        ns5_basename = ns5_file.split(".")[0]
        nev_rel_path = f"{ns5_basename}.nev"
        nev_abs_path = os.path.join(self.nsp_dir, nev_rel_path)
        nev = Nev(nev_abs_path)
        nev_serial_df = nev.get_chunk_serial_df()
        nev_start_serial = nev_serial_df.iloc[0]["chunk_serial"]
        nev_end_serial = nev_serial_df.iloc[-1]["chunk_serial"]

        res["NEV"].append(
            {
                "nev_rel_path": nev_rel_path,
                "nev_start_chunk_serial": nev_start_serial,
                "nev_end_chunk_serial": nev_end_serial,
                "nev_time_origin": nev.get_time_origin(),
                "nev_start_timestamp": nev.get_start_timestamp(),
                "nev_duration_readable": nev.get_duration_readable(),
            }
        )

        for file in os.listdir(self.cam_recording_dir):
            if file.endswith(".json"):
                abs_json_path = os.path.join(self.cam_recording_dir, file)
                videojson = Videojson(abs_json_path)
                videojson_start_chunk = videojson.get_start_chunk_serial(cam_serial)
                videojson_end_chunk = videojson.get_end_chunk_serial(cam_serial)
                if (
                    videojson_start_chunk > nev_end_serial
                    or videojson_end_chunk < nev_start_serial
                ):
                    continue
                else:
                    videojson_basename = file.split(".")[0]
                    video_rel_path = f"{videojson_basename}.{cam_serial}.mp4"
                    video_abs_path = os.path.join(
                        self.cam_recording_dir, video_rel_path
                    )
                    video = Video(video_abs_path)
                    res["VIDEO"].append(
                        {
                            "mp4_rel_path": video_rel_path,
                            "frame_count": video.get_frame_count(),
                        }
                    )
                    res["JSON"].append(
                        {
                            "json_rel_path": file,
                            "json_start_chunk_serial": videojson_start_chunk,
                            "json_end_chunk_serial": videojson_end_chunk,
                            "json_time_origin": videojson.get_time_origin(),
                            "json_duration_readable": videojson.get_duration_readable(),
                        }
                    )

    def get_nev_serial_range(self):
        """Return min and max of nev serial range for all nev files

        Returns:
            tuple: (min, max) of nev serial range
        """
        min_serial = float("inf")
        max_serial = float("-inf")
        for nev_file in self.nev_pool.list_nsp1_nev():
            nev = Nev(os.path.join(self.nsp_dir, nev_file))
            nev_serial_df = nev.get_chunk_serial_df()
            nev_start_serial = nev_serial_df.iloc[0]["chunk_serial"]
            nev_end_serial = nev_serial_df.iloc[-1]["chunk_serial"]
            min_serial = min(min_serial, nev_start_serial)
            max_serial = max(max_serial, nev_end_serial)
        return min_serial, max_serial

    def find_mp4_associated_files(self, mp4_file: str):
        """Find associated files for the given mp4_file.

        Args:
            mp4_file (str): e.g. 15min_7_3_24_synctest_20240703_160408.23512908.mp4

        Returns:
            dict: {"JSON": [{}]
                   "NEV": [{}, {}],
                   "NS5": [{}, {}]}
        """
        associated_json = self._find_associated_json(mp4_file)
        associated_nev, associated_ns5 = self._find_associated_nev_and_ns5(
            associated_json
        )

        return {
            "JSON": associated_json,
            "NEV": associated_nev,
            "NS5": associated_ns5,
        }

    def _find_associated_json(self, mp4_file):
        mp4_basename = mp4_file.split(".")[0]
        cam_serial = self._extract_cam_serial(mp4_file)
        json_path = os.path.join(self.cam_recording_dir, f"{mp4_basename}.json")
        videojson = Videojson(json_path)
        return [
            {
                "json_rel_path": f"{mp4_basename}.json",
                "json_start_chunk_serial": videojson.get_start_chunk_serial(cam_serial),
                "json_end_chunk_serial": videojson.get_end_chunk_serial(cam_serial),
                "json_time_origin": videojson.get_time_origin(),
                "json_duration_readable": videojson.get_duration_readable(),
            }
        ]

    def get_abs_json_path(self, mp4_rel_path: str) -> str:
        """Given mp4_rel_path, return abs json path

        Args:
            mp4_rel_path (str): e.g. 15min_7_3_24_synctest_20240703_160709.18486634.mp4
        """
        mp4_basename = mp4_rel_path.split(".")[0]
        return os.path.join(self.cam_recording_dir, f"{mp4_basename}.json")

    def get_abs_nev_path(self, nev_rel_path: str):
        return os.path.join(self.nsp_dir, nev_rel_path)

    def get_abs_ns5_path(self, ns5_rel_path: str):
        return os.path.join(self.nsp_dir, ns5_rel_path)

    def get_mp4_abs_frame_range(self, cur_mp4_rel_path: str, cam_serial: str) -> int:
        """Get abs start frame of mp4 video

        Args:
            mp4_rel_path (str): 15min_7_3_24_synctest_20240703_155508.23512906.mp4
            cam_serial (str): 18486644
        Returns:
            start, end
        """
        mp4_files = self.get_mp4_filelist(cam_serial)
        running_frame_count = 0
        for mp4_file in mp4_files:
            if mp4_file == cur_mp4_rel_path:
                break
            mp4_abs_path = os.path.join(self.cam_recording_dir, mp4_file)
            video = Video(mp4_abs_path)
            running_frame_count += video.get_frame_count()

        abs_start_frame = running_frame_count + 1
        cur_mp4_abs_path = os.path.join(self.cam_recording_dir, cur_mp4_rel_path)
        video = Video(cur_mp4_abs_path)
        abs_end_frame = abs_start_frame + video.get_frame_count() - 1
        return abs_start_frame, abs_end_frame

    def _extract_cam_serial(self, mp4_file):
        return mp4_file.rsplit(".", 2)[-2]

    def _find_associated_nev_and_ns5(self, associated_json: List[Dict]):
        if len(associated_json) != 1:
            raise ValueError("JSON list length != 1")

        json_start_serial = associated_json[0]["json_start_chunk_serial"]
        json_end_serial = associated_json[0]["json_end_chunk_serial"]

        associated_nev = []
        associated_ns5 = []

        for nev_file in self.get_nev_pool().list_nsp1_nev():
            nev = Nev(os.path.join(self.nsp_dir, nev_file))
            nev_serial_df = nev.get_chunk_serial_df()
            nev_start_serial = nev_serial_df.iloc[0]["chunk_serial"]
            nev_end_serial = nev_serial_df.iloc[-1]["chunk_serial"]

            if nev_end_serial < json_start_serial or nev_start_serial > json_end_serial:
                continue
            else:
                associated_nev.append(
                    {
                        "nev_rel_path": nev_file,
                        "nev_start_chunk_serial": nev_start_serial,
                        "nev_end_chunk_serial": nev_end_serial,
                        "nev_time_origin": nev.get_time_origin(),
                        "nev_start_timestamp": nev.get_start_timestamp(),
                        "nev_duration_readable": nev.get_duration_readable(),
                    }
                )
                nev_basename = Path(nev_file).stem
                ns5_path = os.path.join(self.nsp_dir, f"{nev_basename}.ns5")
                ns5 = Nsx(ns5_path)

                associated_ns5.append(
                    {
                        "ns5_rel_path": f"{nev_basename}.ns5",
                        "ns5_time_origin": ns5.get_timeOrigin(),
                        "ns5_start_timestamp": ns5.get_start_timestamp(),
                        "ns5_duration_readable": ns5.get_duration_readable(),
                    }
                )

        return associated_nev, associated_ns5


class NevPool:
    def __init__(self) -> None:
        self.files = defaultdict(list)

    def add_file(self, file: str):
        suffix = file.split("-")[-1]
        self.files[suffix].append(file)

    def _extract_number(self, file: str) -> int:
        match = re.search(r"-(\d{3})\.", file)
        return int(match.group(1)) if match else 0

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
        return sorted(
            [
                file
                for files in self.files.values()
                for file in files
                if "NSP-1" in file
            ],
            key=self._extract_number,
        )

    def list_nsp2_nev(self):
        return sorted(
            [
                file
                for files in self.files.values()
                for file in files
                if file.startswith("NSP2")
            ],
            key=self._extract_number,
        )

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

    def get_stitched_ns5_file(self):
        return self.files["1.ns5"][0]


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

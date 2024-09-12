import json
import pandas as pd
import numpy as np
from datetime import datetime
from .utils import (
    replace_zeros,
)


class Videojson:
    """
    Wrapper of video json file
    """

    def __init__(self, json_path) -> None:
        self.json_path = json_path
        with open(json_path, "r", encoding="utf-8") as f:
            self.dic = json.load(f)
        self.init_vars()

    def init_vars(self):
        self.num_cameras = self.get_num_cameras()
        self.length_of_recording = self.get_length_of_recording()
        self.timeOrigin = self.dic["real_times"][0]
        self.duration_readable = self.calculate_duration(self.dic["real_times"])

    def calculate_duration(self, real_times) -> str:
        start_time = datetime.strptime(real_times[0], "%Y-%m-%d %H:%M:%S.%f")
        end_time = datetime.strptime(real_times[-1], "%Y-%m-%d %H:%M:%S.%f")
        return str(end_time - start_time)

    def get_duration_readable(self):
        return self.duration_readable

    def get_time_origin(self):
        return self.timeOrigin

    def get_num_cameras(self):
        return len(self.dic["serials"])

    def get_length_of_recording(self):
        return len(self.dic["timestamps"])

    def get_camera_serials(self) -> list:
        return list(self.dic["serials"])

    def get_camera_df(self, cam_serial: int):
        """
        Reader df with one camera
        header
        chunk_serial_data timestamp frame_id real_times
        """
        assert (
            cam_serial in self.get_camera_serials()
        ), "Camera serial not found in JSON"
        cam_idx = self.get_camera_serials().index(cam_serial)
        headers = [
            "chunk_serial_data",
            "frame_id",
        ]
        res = []
        for i in range(self.get_length_of_recording()):
            temp = {}
            for header in headers:
                if header == "real_times":
                    temp[header] = self.dic[header][i]
                else:
                    temp[header] = self.dic[header][i][cam_idx]
            res.append(temp)
        df = pd.DataFrame.from_records(res)
        df = self.reconstruct_frame_id(df)
        df = replace_zeros(df, "chunk_serial_data")
        return df

    def get_chunk_serial_list(self, cam_serial):
        """Return the list of chunk serial"""
        assert (
            cam_serial in self.get_camera_serials()
        ), "Camera serial not found in JSON"
        cam_idx = self.get_camera_serials().index(cam_serial)
        res = []
        for chunk_serial in self.dic["chunk_serial_data"]:
            res.append(chunk_serial[cam_idx])
        return res

    def get_frame_ids_list(self, cam_serial):
        assert (
            cam_serial in self.get_camera_serials()
        ), "Camera serial not found in JSON"
        cam_idx = self.get_camera_serials().index(cam_serial)
        res = []
        for frame_ids in self.dic["frame_id"]:
            res.append(frame_ids[cam_idx])
        return res

    def get_unique_frame_ids(self):
        """
        Get unique frame IDs for the initialized camera.
        """
        return self.camera_df["frame_id"].unique()

    def reconstruct_frame_id(self, df):
        """
        work on frame_id column so that it continus after 65535 instead of
        rolling over

        Algo:
        - the only place when frame id no longer increases is when it rolls over
        - initialize counter = 0
        - go through rows, whenever there is a drop, increment counter by 1
        - add 65535 * counter
        """
        frame_ids = df["frame_id"].to_numpy()
        counters = [0]
        counter = 0
        for i in range(1, len(frame_ids)):
            if frame_ids[i - 1] > frame_ids[i]:
                counter += 1
            counters.append(counter)
        frame_ids = frame_ids + 65535 * np.array(counters)
        df["frame_ids_reconstructed"] = frame_ids
        return df

    def get_start_chunk_serial(self, cam_serial):
        """Get the first chunk serial data for cam_serial camera that is not 0 or -1.

        Args:
            cam_serial (str): e.g. "18486644"

        Returns:
            int: The first chunk serial data that is not 0 or -1, or None if not found.
        """
        try:
            # Find the index of the cam_serial in the 'serials' list
            index = self.dic["serials"].index(cam_serial)
            # Iterate through the chunk_serial_data for the given camera serial
            for serial_list in self.dic["chunk_serial_data"]:
                serial = serial_list[index]
                if serial != 0 and serial != -1:
                    return serial
            return None
        except ValueError:
            return None

    def get_end_chunk_serial(self, cam_serial):
        """Get the last chunk serial data for cam_serial camera that is not 0 or -1.

        Args:
            cam_serial (str): e.g. "18486644"

        Returns:
            int: The last chunk serial data that is not 0 or -1, or None if not found.
        """
        try:
            # Find the index of the cam_serial in the 'serials' list
            index = self.dic["serials"].index(cam_serial)
            # Iterate through the chunk_serial_data for the given camera serial in reverse
            for serial_list in reversed(self.dic["chunk_serial_data"]):
                serial = serial_list[index]
                if serial != 0 and serial != -1:
                    return serial
            return None
        except ValueError:
            return None

import json
import pandas as pd
import numpy as np


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
            "timestamps",
            "frame_id",
            "real_times",
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
        return df

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

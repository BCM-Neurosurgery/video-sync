import json
import pandas as pd


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
        # df["hr_time"] = df["timestamps"].apply(lambda x: utils.jsonts2datetime(x))
        return df

    def get_unique_frame_ids(self):
        """
        Get unique frame IDs for the initialized camera.
        """
        return self.camera_df["frame_id"].unique()

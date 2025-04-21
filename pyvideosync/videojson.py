import json
import pandas as pd
import numpy as np
from datetime import datetime
from pyvideosync.fixanomaly import (
    fix_typei,
    fix_typeiv,
    fix_discontinuities,
)
from typing import List


class Videojson:
    """
    Wrapper of video json file
    """

    def __init__(self, json_path) -> None:
        self.json_path = json_path
        self.dic = None

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    print(
                        f"Warning: JSON file '{json_path}' is empty. Initializing empty dictionary."
                    )
                    return
                self.dic = json.loads(content)
        except json.JSONDecodeError:
            print(
                f"Warning: JSON file '{json_path}' is invalid. Initializing empty dictionary."
            )
            return

        self.init_vars()

    def is_valid(self) -> bool:
        """Checks if the JSON was loaded successfully."""
        return self.dic is not None

    def init_vars(self):
        self.num_cameras = self.get_num_cameras()
        self.length_of_recording = self.get_length_of_recording()
        self.timeOrigin = self.dic["real_times"][0] if self.dic["real_times"] else None
        self.duration_readable = (
            self.calculate_duration(self.dic["real_times"])
            if self.dic["real_times"]
            else None
        )

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
        """Returns a DataFrame containing corrected data for a specified camera.

        Extracts the camera-specific data from internal JSON records, reconstructs the
        frame IDs, replaces zeros, and fixes discontinuities in the `chunk_serial_data`
        column using the `fix_discontinuities` function.

        The resulting DataFrame contains at least the following columns:

            - `chunk_serial_data`: Corrected incremental chunk serial numbers.
            - `frame_id`: Reconstructed frame IDs.

        Args:
            cam_serial (int): Serial number identifying the camera whose data is requested.

        Returns:
            pd.DataFrame: A DataFrame with corrected camera data, ensuring incremental
                continuity in the `chunk_serial_data` column.

        Raises:
            AssertionError: If the provided camera serial number does not exist in the data.

        Examples:
            >>> videojson.get_camera_df(123456)
            # Returns DataFrame with chunk_serial_data and frame_id columns for camera 123456

        """
        if cam_serial not in self.get_camera_serials():
            raise AssertionError(
                "Camera serial not found in JSON. Please check the serial number."
            )
        chunk_serial = self.get_chunk_serial_list(cam_serial)
        frame_ids = self.get_frame_ids_list(cam_serial)

        # now create another array for mp4 relative frame ids
        # we don't really need to fix the overflow in frame ids
        # because they are just counter from cam buffer
        mp4_frame_idx = np.arange(len(frame_ids))

        # fix type i and type iv in chunk serial
        # now there should only be type ii and type iii left
        chunk_serial_fixed = fix_typei(chunk_serial)
        chunk_serial_fixed = fix_typeiv(chunk_serial_fixed)

        # now the remaining discontinuities
        # in chunk serial should only be
        # type ii or type iii (jumps)
        df = pd.DataFrame(
            {
                "chunk_serial_data": chunk_serial_fixed,
                "mp4_frame_idx": mp4_frame_idx,
            }
        )

        if max(chunk_serial_fixed) < 128:
            return df

        # otherwise, let's first remove all
        # remaining cases of type ii and turn them into type iii
        df = self.interpolate_stream(df)
        return df

    def interpolate_stream(
        self, df: pd.DataFrame, threshold: int = 128, method: str = "fill"
    ) -> pd.DataFrame:
        """
        Filters out chunk_serial_data < threshold, then fills in every missing
        chunk_serial_data between the new min and max with -1

        Parameters
        ----------
        df : pd.DataFrame
            Must contain columns 'chunk_serial_data', 'frame_ids_reconstructed', 'mp4_frame_idx'.
        threshold : int, optional
            Drop any chunk_serial_data below this value (default=128).

        Returns
        -------
        pd.DataFrame
            With columns:
            - chunk_serial_data : every integer from new min→max
            - mp4_frame_idx : interpolated & rounded
        """
        # 1. keep only chunk_serial_data ≥ threshold
        df2 = df[df["chunk_serial_data"] >= threshold].copy()
        if df2.empty:
            return pd.DataFrame(
                columns=[
                    "chunk_serial_data",
                    "mp4_frame_idx",
                ]
            )

        x_orig = df2["chunk_serial_data"].to_numpy()
        y_mp4 = df2["mp4_frame_idx"].to_numpy()

        x_full = np.arange(x_orig.min(), x_orig.max() + 1)

        if method == "fill":
            # Create a mapping from chunk_serial_data to mp4_frame_idx
            idx_map = dict(zip(x_orig, y_mp4))
            y_mp4_full = np.array([idx_map.get(x, -1) for x in x_full])

        elif method == "linear":
            # Interpolate the missing values linearly
            y_mp4_full = np.interp(x_full, x_orig, y_mp4)
            y_mp4_full = np.round(y_mp4_full).astype(int)

        # 5. build result
        return pd.DataFrame(
            {
                "chunk_serial_data": x_full,
                "mp4_frame_idx": y_mp4_full,
            }
        )

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

    def fix_frame_id_overflow(self, frame_ids: List[int]) -> np.ndarray:
        """
        Reconstructs a list of frame IDs by correcting for rollover at 65535.

        When frame IDs reach 65535, they roll over to 0. This function detects
        such rollovers and reconstructs a monotonically increasing sequence by
        adding 65535 * rollover_count to each value after a rollover.

        Args:
            frame_ids (List[int]): A list of frame IDs with potential rollovers.

        Returns:
            np.ndarray: A corrected list of frame IDs as a NumPy array.

        Algorithm:
        - Initialize a rollover counter.
        - Iterate through the list; whenever a frame ID is less than the previous one,
        increment the counter.
        - Add 65535 * counter to each frame ID to correct for rollovers.
        """
        counter = 0
        counters = [0]
        for i in range(1, len(frame_ids)):
            if frame_ids[i - 1] > frame_ids[i]:
                counter += 1
            counters.append(counter)

        frame_ids = np.array(frame_ids)
        corrected_ids = frame_ids + 65535 * np.array(counters)
        return corrected_ids

    def get_min_max_chunk_serial(self):
        """
        Get the minimum and maximum chunk serial data fast.

        Assumption:
            - the serial data does not vary a lot among cameras

        Important:
            when we get the min and max, we can't use functions to interporlate data,
            which can potentially lead to matching with wrong jsons

        Returns:
            tuple: (min_serial, max_serial), or (None, None) if no valid data is found.
        """
        if not self.dic or "chunk_serial_data" not in self.dic:
            return None, None

        min_chunk_serial = None
        max_chunk_serial = None

        for camera_serial in self.get_camera_serials():
            chunk_serial = self.get_chunk_serial_list(camera_serial)
            chunk_serial_filtered = [i for i in chunk_serial if i >= 128]
            min_chunk_serial = min(chunk_serial_filtered)
            max_chunk_serial = max(chunk_serial_filtered)
            if min_chunk_serial != 0 and max_chunk_serial != 0:
                break

        if not min_chunk_serial or not max_chunk_serial:
            return None, None

        return min_chunk_serial, max_chunk_serial

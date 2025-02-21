import pandas as pd
from brpylib import NsxFile
from typing import List
import numpy as np
from pyvideosync import utils
import matplotlib.pyplot as plt
import os


class Nsx:
    def __init__(self, path) -> None:
        self.path = path
        self.nsxObj = NsxFile(path)
        self.nsxDict = vars(self.nsxObj)
        self.nsxData = self.nsxObj.getdata()
        self.nsxObj.close()
        self.init_vars()

    def init_vars(self):
        self.basic_header = self.nsxDict["basic_header"]
        self.extended_headers = self.nsxDict["extended_headers"]
        self.timestampResolution = self.basic_header["TimeStampResolution"]
        self.sampleResolution = self.basic_header["SampleResolution"]
        self.timeOrigin = self.basic_header["TimeOrigin"]
        self.extended_headers_df = pd.DataFrame.from_records(
            self.get_extended_headers()
        )
        self.data = self.nsxData
        self.memmapData = self.data["data"][0]
        # TODO: the data header might have multiple timestamps
        self.timeStamp = self.data["data_headers"][0]["Timestamp"]
        self.numDataPoints = self.data["data_headers"][0]["NumDataPoints"]
        self.recording_duration_s = self.data["data_headers"][0]["data_time_s"]
        self.recording_duration_readable = utils.ts2min(self.recording_duration_s, 1)

    def get_start_timestamp(self):
        return self.timeStamp

    def get_timeOrigin(self):
        return self.timeOrigin

    def get_duration_readable(self):
        return self.recording_duration_readable

    def get_basic_header(self):
        return self.basic_header

    def get_data(self):
        return self.data

    def get_extended_headers(self) -> List[dict]:
        return self.extended_headers

    def get_extended_headers_df(self) -> pd.DataFrame:
        return self.extended_headers_df

    def get_sample_resolution(self):
        return self.sampleResolution

    def get_num_data_points(self):
        return self.numDataPoints

    def get_recording_duration_s(self):
        return self.recording_duration_s

    def get_channel_array(self, channel: str):
        """
        Args:
            channel: e.g. "RoomMic2"
        """
        row_index = self.extended_headers_df[
            self.extended_headers_df["ElectrodeLabel"] == channel
        ].index.item()
        return self.memmapData[row_index]

    def get_channel_df(self, channel: str):
        """
        headers
        TimeStamps, Amplitude, UTCTimeStamp
        0           425        2024-04-16 22:28:17.310167
        """
        channel_data = self.get_channel_array(channel)
        num_samples = len(channel_data)
        channel_df = pd.DataFrame(channel_data, columns=["Amplitude"])
        channel_df["TimeStamp"] = np.arange(
            self.timeStamp, self.timeStamp + num_samples
        )
        channel_df["UTCTimeStamp"] = channel_df["TimeStamp"].apply(
            lambda x: utils.ts2unix(self.timeOrigin, self.timestampResolution, x)
        )
        # reordering
        channel_df = channel_df[["TimeStamp", "Amplitude", "UTCTimeStamp"]]
        return channel_df

    def plot_channel_array(self, channel: str, save_path: str):
        channel_array = self.get_channel_array(channel)
        plt.plot(channel_array)
        plt.title(channel)
        plt.xlabel("TimeStamps")
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        plt.savefig(save_path)
        plt.close()

    def get_channel_df_between_ts(
        self, channel_df: pd.DataFrame, start_ts: int, end_ts: int
    ) -> pd.DataFrame:
        """
        Get a slice of the ns5 channel DataFrame between start_ts and end_ts.

        Args:
            channel_df (pd.DataFrame): DataFrame containing channel data.
            start_ts (int): Start timestamp.
            end_ts (int): End timestamp.

        Returns:
            pd.DataFrame: Sliced DataFrame between start_ts and end_ts.
        """
        if start_ts > end_ts:
            raise ValueError("start_ts must be less than or equal to end_ts")

        sliced_df = channel_df[
            (channel_df["TimeStamp"] >= start_ts) & (channel_df["TimeStamp"] <= end_ts)
        ]

        return sliced_df

    def get_filtered_channel_df(
        self, channel: str, start_ts: int, end_ts: int
    ) -> pd.DataFrame:
        """
        Retrieve a filtered DataFrame of a specific channel within a timestamp range
        without creating the entire DataFrame.

        Args:
            channel (str): Name of the channel to extract.
            start_ts (int): Start timestamp.
            end_ts (int): End timestamp.

        Returns:
            pd.DataFrame: Sliced DataFrame containing only the necessary data.
        """
        if start_ts > end_ts:
            raise ValueError("start_ts must be less than or equal to end_ts")

        # Retrieve channel data
        channel_data = self.get_channel_array(channel)
        num_samples = len(channel_data)
        ts_start = self.timeStamp  # Starting timestamp for the data

        # Determine valid index range
        idx_start = int(max(0, start_ts - ts_start))
        idx_end = int(min(num_samples, end_ts - ts_start + 1))

        if idx_start >= num_samples or idx_end <= 0:
            # No valid data in the given timestamp range
            return pd.DataFrame(columns=["TimeStamp", "Amplitude", "UTCTimeStamp"])

        # Slice only the required data
        sliced_data = channel_data[idx_start:idx_end]
        timestamps = np.arange(ts_start + idx_start, ts_start + idx_end)

        # Construct minimal DataFrame
        sliced_df = pd.DataFrame(
            {
                "TimeStamp": timestamps,
                "Amplitude": sliced_data,
                "UTCTimeStamp": [
                    utils.ts2unix(self.timeOrigin, self.timestampResolution, ts)
                    for ts in timestamps
                ],
            }
        )

        return sliced_df

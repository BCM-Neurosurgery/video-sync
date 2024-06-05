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
        plt.show()
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

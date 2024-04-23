import pandas as pd
from brpylib import NsxFile
from typing import List
import utils

class Nsx:
    def __init__(self, path) -> None:
        self.path = path
        self.nsxObj = NsxFile(path)
        self.nsxDict = vars(self.nsxObj)
        self.nsxData = self.nsxObj.getdata()
        self.nsxObj.close()
        self.init_vars()

    def init_vars(self):
        self.timestampResolution = self.get_basic_header()["TimeStampResolution"]
        self.timeOrigin = self.get_basic_header()["TimeOrigin"]
        self.extended_headers_df = self.get_extended_headers_df()
        self.memmapData = self.get_data()["data"][0]

    def get_basic_header(self):
        return self.nsxDict["basic_header"]

    def get_data(self):
        return self.nsxData


    def get_extended_headers(self) -> List[dict]:
        return self.nsxDict["extended_headers"]
    
    
    def get_extended_headers_df(self) -> pd.DataFrame:
        """
        get extended headers in pd.DataFrame
        """
        return pd.DataFrame.from_records(self.get_extended_headers())

    
    def get_df_channel(self, channel: str):
        """
        headers
        TimeStamps, Amplitude, UTCTimeStamp
        0           425        2024-04-16 22:28:17.310167
        """
        # 1st, find index of that row
        row_index = self.extended_headers_df[self.extended_headers_df['ElectrodeLabel'] == channel].index.item()
        # find the data
        channel_data = self.memmapData[row_index]
        channel_df = pd.DataFrame(channel_data, columns=["Amplitude"])
        channel_df["TimeStamp"] = channel_df.index
        channel_df["UTCTimeStamps"] = channel_df["TimeStamp"].map(lambda x: utils.ts2unix(self.timeOrigin, self.timestampResolution, x))
        # reordering
        channel_df = channel_df[['TimeStamp', 'Amplitude', 'UTCTimeStamps']]
        return channel_df

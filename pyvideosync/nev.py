import json
import os
from brpylib import NevFile
import pandas as pd
import numpy as np
from pyvideosync import utils


class Nev:
    """
    Read NEV file into object
    """

    def __init__(self, path):
        self.path = path
        self.nevObj = NevFile(path)
        self.nevDict = vars(self.nevObj)
        self.nevData = self.nevObj.getdata()
        self.nevObj.close()
        self.init_vars()

    def init_vars(self):
        """
        Initialize other variables
        """
        self.timestampResolution = self.get_basic_header()["TimeStampResolution"]
        self.timeOrigin = self.get_basic_header()["TimeOrigin"]

    def get_basic_header(self) -> dict:
        return self.nevDict["basic_header"]

    def get_extended_headers(self) -> list:
        return self.nevDict["extended_headers"]

    def get_num_electrodeID(self):
        """
        Return number of distinct ElectrodeID
        """
        electrodeIDset = set()
        for extended_header in self.nevDict["extended_headers"]:
            if "ElectrodeID" in extended_header:
                electrodeIDset.add(extended_header["ElectrodeID"])
        return len(electrodeIDset)

    def get_num_channels(self):
        """
        Get number of channels from spike_events
        """
        return len(set(self.nevData["spike_events"]["Channel"]))

    def get_time_origin(self):
        """
        Return the time origin
        """
        return self.get_basic_header()["TimeOrigin"]

    def get_data(self):
        return self.nevData

    def bits_to_decimal(self, nums: list) -> int:
        """
        nums: [19, 101, 37, 0, 0]

        Returns:
        619155
        """
        # Convert each number to a 7-bit binary string with leading zeros
        binary_strings = [format(num, "07b") for num in nums][::-1]
        # Concatenate all binary strings into one long binary string
        full_binary_string = "".join(binary_strings)
        # Convert the concatenated binary string to a decimal number
        return int(full_binary_string, 2)

    def get_digital_events_df(self):
        """
        Just get the unmodified digital_events in df
        Returns
                InsertionReason 	TimeStamps 	UnparsedData
        0 	1 	                1345817 	65319
        1 	1 	                1345818 	65535
        2 	129 	            1345819 	40
        3 	129 	            1345822 	76
        4 	129 	            1345825 	35
        """
        return pd.DataFrame.from_records(self.get_data()["digital_events"])

    def get_cleaned_digital_events_df(self):
        """
        only keep the rows which satisfy
        1. InsertionReason == 129
        2. the length of such group is 5
        3. 0 <= UnparsedData <= 127 (should be true enforced by hardware)

        Returns
            InsertionReason 	TimeStamps 	UnparsedData
        2 	129 	            1345819 	40
        3 	129 	            1345822 	76
        4 	129 	            1345825 	35
        5 	129 	            1345828 	0
        6 	129 	            1345831 	0
        """
        digital_events_df = self.get_digital_events_df()
        # True indicates a change from 1 -> 129 or 129 -> 1
        digital_events_df["group"] = (
            digital_events_df["InsertionReason"]
            != digital_events_df["InsertionReason"].shift(1)
        ).cumsum()
        # Count the size of each group and assign True where the group size
        # is 5 and the reason is 129
        digital_events_df["keeprows"] = digital_events_df.groupby("group")[
            "InsertionReason"
        ].transform(lambda x: (x == 129) & (x.size == 5))
        digital_events_df = digital_events_df[digital_events_df["keeprows"] == True]
        digital_events_df = digital_events_df.drop(["group", "keeprows"], axis=1)
        return digital_events_df

    def get_chunk_serial_df(self):
        """
        From the cleaned digital_events_df, group by every 5 rows
        and reconstruct

        Returns:
            TimeStamps 	    chunk_serial 	UTCTimeStamp
        0 	1345819 	    583208 	        2024-04-16 21:48:17.194633
        1 	1346821 	    583209 	        2024-04-16 21:48:17.228033
        """
        assert self.has_unparsed_data()
        df = self.get_cleaned_digital_events_df()
        results = []
        for i in range(0, len(df), 5):
            group = df.iloc[i : i + 5]
            if len(group) == 5:
                nums = [x for x in group["UnparsedData"]]
                decimal_number = self.bits_to_decimal(nums)
                timestamp = group["TimeStamps"].iloc[0]
                unixTime = utils.ts2unix(
                    self.timeOrigin, self.timestampResolution, timestamp
                )
                results.append((timestamp, decimal_number, unixTime))
        return pd.DataFrame.from_records(
            results, columns=["TimeStamps", "chunk_serial", "UTCTimeStamp"]
        )

    def has_unparsed_data(self):
        """
        Return True if nev file has UnparsedData
        """
        if (
            "digital_events" in self.get_data()
            and "UnparsedData" in self.get_data()["digital_events"]
            and len(self.get_data()["digital_events"]["UnparsedData"]) > 0
        ):
            return True
        return False

import json
import os
from brpylib import NevFile
import pandas as pd
import numpy as np
import utils


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

    def reconstruct_from_dataframe(self, df) -> pd.DataFrame:
        """
        TimeStamps 	InsertionReason UnparsedData
        37347213 	1 	            65316
        37347214 	1 	            65535
        37347215 	129 	        19
        37347218 	129 	        101
        37347221 	129 	        37

        TODO:
        - no way to reconstruct if not multiple of 5

        Returns:
        TimeStamps  chunk_serial UTCTimeStamp
        37347215    619155       2024-04-16 22:28:17.310167
        """
        df = df[df["InsertionReason"] == 129]
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

    def get_chunk_serial_df(self):
        """
        Returns:
        TimeStamps  chunk_serial UTCTimeStamp
        37347215    619155       2024-04-16 22:28:17.310167
        """
        # 1st, check there's UnparsedData
        assert self.has_unparsed_data()
        # 2nd, get df
        df = pd.DataFrame.from_records(self.get_data()["digital_events"])
        return self.reconstruct_from_dataframe(df)

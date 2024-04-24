import pandas as pd


class Match:
    """
    Matches signals between nev and ns5
    """

    def __init__(self, nevObj, nsxObj) -> None:
        self.nevObj = nevObj
        self.nsxObj = nsxObj

    def get_chunk_serial_merged_df(self, channel: str):
        """
        Merge nev df and ns5 df
        nev df:
        TimeStamps  chunk_serial UTCTimeStamp
        37347215    619155       2024-04-16 22:28:17.310167

        ns5 df:
        TimeStamps, Amplitude, UTCTimeStamp
        0           425        2024-04-16 22:28:17.310167

        Returns
        chunk_serial Amplitude  UTCTimeStamp
        619155       425        2024-04-16 22:28:17.310167
        """
        nev_chunk_serial_df = self.nevObj.get_chunk_serial_df()
        ns5_chunk_serial_df = self.nsxObj.get_channel_df(channel)
        merged_df = pd.merge(
            nev_chunk_serial_df, ns5_chunk_serial_df, on="UTCTimeStamp", how="inner"
        )
        result_df = merged_df[["chunk_serial", "Amplitude", "UTCTimeStamp"]]
        return result_df

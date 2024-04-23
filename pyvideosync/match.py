class Match:
    """
    Matches signals between nev and ns5
    """
    def __init__(self, nevObj, nsxObj) -> None:
        self.nevObj = nevObj
        self.nsxObj = nsxObj

    
    def get_chunk_serial_merged_df(self, col: str):
        """
        Get merged df with hearders
        TimeStamps  chunk_serial col
        """


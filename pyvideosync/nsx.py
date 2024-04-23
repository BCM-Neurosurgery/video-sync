import pandas as pd
from brpylib import NsxFile
from typing import List

class Nsx:
    def __init__(self, path) -> None:
        self.path = path
        self.nsxObj = NsxFile(path)
        self.nsxDict = vars(self.nsxObj)
        self.nsxData = self.nsxObj.getdata()
        self.nsxObj.close()

    def get_data(self):
        return self.nsxData


    def get_extended_headers(self) -> List[dict]:
        return self.nsxDict["extended_headers"]
    
    
    def get_extended_headers_df(self) -> pd.DataFrame:
        """
        get extended headers in pd.DataFrame
        """
        return pd.DataFrame.from_records(self.get_extended_headers())

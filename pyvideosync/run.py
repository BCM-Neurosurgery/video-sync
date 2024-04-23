import pandas as pd
import numpy as np
import json
from pyvideosync.nev import Nev
from pyvideosync.nsx import Nsx



if __name__ == "__main__":
    # load nev
    nev_path = "/home/yewen/BCM/videosync/04222024/nsp/NSP1-20240416-164732-003.nev"
    nev = Nev(nev_path)

    # test 
    chunk_serial_df = nev.get_chunk_serial_df()
    print(chunk_serial_df.head())

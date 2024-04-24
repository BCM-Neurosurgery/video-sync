import pandas as pd
import numpy as np
import json
from pyvideosync.nev import Nev
from pyvideosync.nsx import Nsx
from pyvideosync.match import Match


if __name__ == "__main__":
    ### Test nev files
    # load nev
    nev_path = "/home/yewen/BCM/videosync/04222024/nsp/NSP1-20240416-164732-003.nev"
    nev = Nev(nev_path)

    # # test
    # chunk_serial_df = nev.get_chunk_serial_df()
    # print(chunk_serial_df.head())

    ### Test nsx files
    ns5_path = "/home/yewen/BCM/videosync/04222024/nsp/NSP1-20240416-164732-003.ns5"
    ns5 = Nsx(ns5_path)
    # print(ns5.get_channel_df("RoomMic2").head())

    ### Test merge
    match = Match(nev, ns5)
    print(match.get_chunk_serial_merged_df("RoomMic2"))

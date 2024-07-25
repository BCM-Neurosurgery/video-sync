from pyvideosync.dataframebase import DataFrameBase


class NevChunkSerialDF(DataFrameBase):
    def get_name(self) -> str:
        return "NEV Chunk Serial DataFrame"

    def get_columns_to_check(self):
        return ["chunk_serial"]


class CameraJSONDF(DataFrameBase):
    def get_name(self) -> str:
        return "Camera JSON DataFrame"

    def get_columns_to_check(self):
        return ["chunk_serial_data", "frame_ids_reconstructed"]


class NS5ChannelDF(DataFrameBase):
    def get_name(self) -> str:
        return "NS5 Channel DataFrame"

    def get_columns_to_check(self):
        return ["TimeStamps"]


class ChunkSerialJoinedDF(DataFrameBase):
    """
    The merged dataframe from Camera JSON INNER JOIN NEV Chunk Serial DF ON chunk serial
    """

    def get_name(self) -> str:
        return "Chunk Serial Joined DataFrame"

    def get_columns_to_check(self):
        return ["chunk_serial", "frame_ids_reconstructed"]


class AllMergeDF(DataFrameBase):
    """
    All merged dataframe by NS5ChannelDF LEFT JOIN ChunkSerialJoinedDF ON TimeStamps
    """

    def get_name(self) -> str:
        return "All Merged DataFrame"

    def get_columns_to_check(self):
        return ["frame_ids_reconstructed", "chunk_serial"]


class AllMergeConcatDF(AllMergeDF):
    """
    All merged concatenated dataframe
    """

    def get_name(self) -> str:
        return "All Merged Concat DataFrame"

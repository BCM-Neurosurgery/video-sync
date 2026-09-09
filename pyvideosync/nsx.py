import pandas as pd
from brpylib import NsxFile
from dataclasses import dataclass
from datetime import datetime
from struct import unpack
from typing import List
import numpy as np
from pyvideosync import utils
import matplotlib.pyplot as plt
import os


@dataclass(frozen=True)
class NsxTimeBounds:
    """Header-only timing metadata for one NSx file."""

    time_origin: datetime
    timestamp_resolution: int
    sample_resolution: int
    period: int
    start_timestamp: int
    end_timestamp: int

    @property
    def clk_per_sample(self) -> int:
        return int(self.period * self.timestamp_resolution / self.sample_resolution)

    @property
    def start_utc(self) -> datetime:
        return utils.ts2unix(
            self.time_origin, self.timestamp_resolution, self.start_timestamp
        )

    @property
    def end_utc(self) -> datetime:
        return utils.ts2unix(
            self.time_origin, self.timestamp_resolution, self.end_timestamp
        )


def read_nsx_time_bounds(path) -> NsxTimeBounds:
    """Read UTC/sample bounds without mapping or loading the signal payload."""
    nsx_file = NsxFile(str(path))
    try:
        header = nsx_file.basic_header
        time_origin = header.get("TimeOrigin")
        if time_origin is None:
            raise ValueError(f"NSx file has no TimeOrigin: {path}")
        timestamp_resolution = int(header["TimeStampResolution"])
        sample_resolution = int(header["SampleResolution"])
        period = int(header["Period"])
        if timestamp_resolution <= 0 or sample_resolution <= 0 or period <= 0:
            raise ValueError(f"NSx file has invalid timing metadata: {path}")
        clk_per_sample = int(period * timestamp_resolution / sample_resolution)
        if clk_per_sample <= 0:
            raise ValueError(f"NSx file has invalid sample clock period: {path}")

        datafile = nsx_file.datafile
        data_start = int(header["BytesInHeader"])
        datafile.seek(0, os.SEEK_END)
        file_size = datafile.tell()
        channel_count = int(header["ChannelCount"])
        bytes_per_sample = channel_count * np.dtype(np.int16).itemsize

        if header["FileSpec"] == "2.1":
            point_count = (file_size - data_start) // bytes_per_sample
            if point_count <= 0:
                raise ValueError(f"NSx file contains no samples: {path}")
            return NsxTimeBounds(
                time_origin=time_origin,
                timestamp_resolution=timestamp_resolution,
                sample_resolution=sample_resolution,
                period=period,
                start_timestamp=0,
                end_timestamp=(point_count - 1) * clk_per_sample,
            )

        major_version = int(str(header["FileSpec"]).split(".", 1)[0])
        timestamp_format = "<Q" if major_version >= 3 else "<I"
        timestamp_size = 8 if major_version >= 3 else 4
        first_timestamp = None
        last_timestamp = None
        datafile.seek(data_start)
        while datafile.tell() < file_size:
            packet_header = datafile.read(1)
            if not packet_header:
                break
            if packet_header != b"\x01":
                raise ValueError(f"invalid NSx packet header: {path}")
            timestamp_bytes = datafile.read(timestamp_size)
            point_count_bytes = datafile.read(4)
            if len(timestamp_bytes) != timestamp_size or len(point_count_bytes) != 4:
                raise ValueError(f"truncated NSx packet header: {path}")
            timestamp = int(unpack(timestamp_format, timestamp_bytes)[0])
            point_count = int(unpack("<I", point_count_bytes)[0])
            packet_bytes = point_count * bytes_per_sample
            packet_end = datafile.tell() + packet_bytes
            if packet_end > file_size:
                raise ValueError(f"NSx packet extends beyond end of file: {path}")
            if point_count:
                if first_timestamp is None:
                    first_timestamp = timestamp
                last_timestamp = timestamp + (point_count - 1) * clk_per_sample
            datafile.seek(packet_end)

        if first_timestamp is None or last_timestamp is None:
            raise ValueError(f"NSx file contains no non-empty data packets: {path}")
        return NsxTimeBounds(
            time_origin=time_origin,
            timestamp_resolution=timestamp_resolution,
            sample_resolution=sample_resolution,
            period=period,
            start_timestamp=first_timestamp,
            end_timestamp=last_timestamp,
        )
    finally:
        nsx_file.datafile.close()


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
        self.numDataPoints = self.data["data_headers"][0]["NumDataPoints"]
        self.recording_duration_s = self.data["data_headers"][0]["data_time_s"]
        self.recording_duration_readable = utils.ts2min(self.recording_duration_s, 1)
        # Master-clock ticks between consecutive samples.
        # NS5: Period=1 → clk_per_samp=1; NS3: Period=15 → clk_per_samp=15.
        # Sample i sits at timeStamp + i * clk_per_samp in NSP-tick units.
        self.clk_per_samp = int(
            self.basic_header["Period"]
            * self.timestampResolution
            / self.sampleResolution
        )

    def get_start_timestamp(self):
        return self.timeStamp

    def get_timeOrigin(self):
        return self.timeOrigin

    def get_duration_readable(self):
        return self.recording_duration_readable

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

    def get_num_data_points(self):
        return self.numDataPoints

    def get_recording_duration_s(self):
        return self.recording_duration_s

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
        Full-recording DataFrame for one channel.

        headers: TimeStamp, Amplitude, UTCTimeStamp
        """
        end_ts = self.timeStamp + self.numDataPoints * self.clk_per_samp - 1
        return self.get_filtered_channel_df(channel, self.timeStamp, end_ts)

    def plot_channel_array(self, channel: str, save_path: str):
        channel_array = self.get_channel_array(channel)
        plt.plot(channel_array)
        plt.title(channel)
        plt.xlabel("TimeStamps")
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        plt.savefig(save_path)
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

    def _slice_indices(self, start_ts: int, end_ts: int) -> tuple[int, int, np.ndarray]:
        """Return (idx_start, idx_end, timestamps) for an NSP-tick range.

        Honors `clk_per_samp` so the math is correct for any NSx Period
        (NS5=1, NS3=15, etc.). NS5 collapses to one-sample-per-tick.

        `timestamps` is empty if the requested range falls outside the file.
        """
        if start_ts > end_ts:
            raise ValueError("start_ts must be less than or equal to end_ts")

        period = self.clk_per_samp
        num_samples = self.numDataPoints

        idx_start = int(max(0, (start_ts - self.timeStamp) // period))
        idx_end = int(min(num_samples, (end_ts - self.timeStamp) // period + 1))

        if idx_start >= num_samples or idx_end <= 0 or idx_end <= idx_start:
            return idx_start, idx_end, np.empty(0, dtype=np.int64)

        timestamps = np.arange(
            self.timeStamp + idx_start * period,
            self.timeStamp + idx_end * period,
            period,
            dtype=np.int64,
        )
        return idx_start, idx_end, timestamps

    def get_filtered_channel_df(
        self, channel: str, start_ts: int, end_ts: int
    ) -> pd.DataFrame:
        """
        Single-channel DataFrame sliced to [start_ts, end_ts] (NSP-tick units).

        Returns columns: TimeStamp, Amplitude, UTCTimeStamp.
        """
        idx_start, idx_end, timestamps = self._slice_indices(start_ts, end_ts)
        if len(timestamps) == 0:
            return pd.DataFrame(columns=["TimeStamp", "Amplitude", "UTCTimeStamp"])

        sliced_data = self.get_channel_array(channel)[idx_start:idx_end]
        return pd.DataFrame(
            {
                "TimeStamp": timestamps,
                "Amplitude": sliced_data,
                "UTCTimeStamp": [
                    utils.ts2unix(self.timeOrigin, self.timestampResolution, ts)
                    for ts in timestamps
                ],
            }
        )

    def get_all_channels_arrays(
        self, start_ts: int, end_ts: int
    ) -> tuple[np.ndarray, np.ndarray, list[str]]:
        """
        Multi-channel slice as numpy arrays (no pandas overhead).

        Returns:
            timestamps: shape (N,), NSP master-clock ticks, stride = clk_per_samp.
            amplitudes: shape (N, num_channels), int16, channel-major from memmap.
            channel_labels: ElectrodeLabels in column order of `amplitudes`.

        Empty arrays if [start_ts, end_ts] falls outside the file.
        """
        idx_start, idx_end, timestamps = self._slice_indices(start_ts, end_ts)
        labels = list(self.extended_headers_df["ElectrodeLabel"])
        if len(timestamps) == 0:
            return timestamps, np.empty((0, len(labels)), dtype=np.int16), labels
        # memmapData is (num_channels, num_samples); transpose to (N, num_channels)
        amplitudes = np.asarray(self.memmapData[:, idx_start:idx_end].T, dtype=np.int16)
        return timestamps, amplitudes, labels

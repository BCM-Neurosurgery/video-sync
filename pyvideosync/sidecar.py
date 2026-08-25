"""Frame-mapping and optional NS3 sidecar exporters."""

from __future__ import annotations

import h5py
import numpy as np
import pandas as pd

FRAME_MAPPING_COLUMNS = [
    "synced_frame_idx",
    "camera_serial",
    "nev_serial_timestamp",
    "nev_utc_time",
    "ns5_sample_idx",
    "chunk_serial",
    "source_mp4_frame_idx",
    "source_frame_available",
    "source_mp4",
    "ns5_file",
]


def build_frame_mapping(
    joined_frames: pd.DataFrame,
    camera_serial: str,
    ns5_start_timestamp: int,
    ns5_clk_per_sample: int,
    ns5_path: str,
) -> pd.DataFrame:
    """Build the compact final-video-frame to NSP-time mapping.

    ``joined_frames`` is the existing NEV-to-camera join accumulated in final
    video order. This function assigns final frame indices and converts each
    NEV timestamp to its zero-based sample index in the source NS5.

    ``source_mp4_frame_idx == -1`` is retained deliberately: the video renderer
    emits a blank frame for a missing source frame, so it is still a real frame
    in the final synced MP4.
    """
    required = {
        "TimeStamps",
        "UTCTimeStamp",
        "chunk_serial",
        "mp4_frame_idx",
        "mp4_file",
    }
    missing = sorted(required - set(joined_frames.columns))
    if missing:
        raise ValueError(f"joined_frames is missing columns: {', '.join(missing)}")
    if ns5_clk_per_sample <= 0:
        raise ValueError("ns5_clk_per_sample must be positive")

    if joined_frames.empty:
        return pd.DataFrame(columns=FRAME_MAPPING_COLUMNS)

    frame_rows = joined_frames.reset_index(drop=True)
    nev_timestamps = frame_rows["TimeStamps"].astype("int64")
    sample_offsets = nev_timestamps - int(ns5_start_timestamp)
    if (sample_offsets < 0).any():
        raise ValueError("frame mapping contains timestamps before the NS5 start")
    if (sample_offsets % ns5_clk_per_sample != 0).any():
        raise ValueError("frame timestamps do not align to NS5 sample boundaries")

    mapping = pd.DataFrame(
        {
            "synced_frame_idx": np.arange(len(frame_rows), dtype=np.int64),
            "camera_serial": str(camera_serial),
            "nev_serial_timestamp": nev_timestamps,
            "nev_utc_time": pd.to_datetime(frame_rows["UTCTimeStamp"], utc=True).map(
                lambda timestamp: timestamp.isoformat()
            ),
            "ns5_sample_idx": sample_offsets // ns5_clk_per_sample,
            "chunk_serial": frame_rows["chunk_serial"].astype("int64"),
            "source_mp4_frame_idx": frame_rows["mp4_frame_idx"].astype("int64"),
            "source_mp4": frame_rows["mp4_file"].astype(str),
            "ns5_file": str(ns5_path),
        }
    )
    mapping["source_frame_available"] = mapping["source_mp4_frame_idx"] >= 0
    return mapping[FRAME_MAPPING_COLUMNS]


def combine_frame_mappings(frame_mappings: list[pd.DataFrame]) -> pd.DataFrame:
    """Combine per-camera mappings into one task-level mapping."""
    if not frame_mappings:
        return pd.DataFrame(columns=FRAME_MAPPING_COLUMNS)

    combined = pd.concat(frame_mappings, ignore_index=True)
    missing = sorted(set(FRAME_MAPPING_COLUMNS) - set(combined.columns))
    if missing:
        raise ValueError(f"frame mapping is missing columns: {', '.join(missing)}")
    if combined.duplicated(["camera_serial", "synced_frame_idx"]).any():
        raise ValueError(
            "frame mapping contains duplicate camera_serial/synced_frame_idx pairs"
        )

    return combined[FRAME_MAPPING_COLUMNS]


def concatenate_frame_mappings(frame_mappings: list[pd.DataFrame]) -> pd.DataFrame:
    """Concatenate ordered neural fragments for one camera and renumber frames."""
    if not frame_mappings:
        return pd.DataFrame(columns=FRAME_MAPPING_COLUMNS)

    combined = pd.concat(frame_mappings, ignore_index=True)
    missing = sorted(set(FRAME_MAPPING_COLUMNS) - set(combined.columns))
    if missing:
        raise ValueError(f"frame mapping is missing columns: {', '.join(missing)}")
    cameras = combined["camera_serial"].astype(str).unique()
    if len(cameras) != 1:
        raise ValueError("ordered frame fragments must belong to one camera")
    if combined.duplicated(["source_mp4", "chunk_serial"]).any():
        raise ValueError("neural fragments map the same source video frame twice")

    combined["synced_frame_idx"] = np.arange(len(combined), dtype=np.int64)
    return combined[FRAME_MAPPING_COLUMNS]


def write_ns3_sidecar(
    h5_path: str,
    timestamps: np.ndarray,
    amplitudes: np.ndarray,
    channel_labels: list[str],
    attrs: dict,
) -> None:
    """Write an NS3 sidecar HDF5.

    Layout:
        /timestamps   uint64,  shape (N,)            — NSP master-clock ticks
        /amplitudes   int16,   shape (N, num_chans)  — gzip-compressed
                      .attrs["channel_labels"]       — UTF-8 labels in column order
        file.attrs                                   — keys/values from `attrs`

    Args:
        h5_path: destination .h5 path; overwritten if it exists.
        timestamps: 1D array of NSP ticks (stride = clk_per_samp of the NS3 file).
        amplitudes: 2D array (N, num_channels) matching `channel_labels` order.
        channel_labels: ElectrodeLabel for each column of `amplitudes`.
        attrs: file-level metadata (e.g. samp_per_s, period, time_origin).
    """
    if amplitudes.ndim != 2:
        raise ValueError(
            f"amplitudes must be 2D (N, num_channels); got shape {amplitudes.shape}"
        )
    if amplitudes.shape[0] != len(timestamps):
        raise ValueError(
            f"timestamps and amplitudes row count disagree: "
            f"{len(timestamps)} vs {amplitudes.shape[0]}"
        )
    if amplitudes.shape[1] != len(channel_labels):
        raise ValueError(
            f"amplitudes column count disagrees with channel_labels: "
            f"{amplitudes.shape[1]} vs {len(channel_labels)}"
        )

    with h5py.File(h5_path, "w") as f:
        f.create_dataset("timestamps", data=np.asarray(timestamps, dtype=np.uint64))
        amps_ds = f.create_dataset(
            "amplitudes",
            data=np.asarray(amplitudes, dtype=np.int16),
            compression="gzip",
            compression_opts=4,
        )
        # Channel labels live as an attribute of /amplitudes, not as a separate
        # dataset, so loaders can grab columns + their names in one read.
        amps_ds.attrs["channel_labels"] = np.array(
            channel_labels, dtype=h5py.string_dtype()
        )
        for key, value in attrs.items():
            f.attrs[key] = value

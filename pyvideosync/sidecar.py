"""
Sidecar exporters that emit data products alongside the synced video.

Currently only NS3: a wide HDF5 file with all NS3 channels sliced to the
NSP master-clock time range covered by the session's NEV. The file is
loadable from Python (h5py / pandas) and natively from MATLAB (`h5read`).
"""

from __future__ import annotations

import h5py
import numpy as np


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

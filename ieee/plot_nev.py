from pyvideosync.nev import Nev
import matplotlib.pyplot as plt
from pyvideosync.utils import (
    to_16bit_binary,
    fill_missing_data,
)
import seaborn as sns
import numpy as np
import pandas as pd
from matplotlib.ticker import MaxNLocator


def plot_cam_exposure_all(
    nev: Nev,
    save_path: str = None,
    start: int = None,
    end: int = None,
    ax=None,
    dpi: int = 300,
    bit_idx: int = None,
    show_labels: bool = True,
    show_legend: bool = True,
) -> None:
    """Plot a single camera exposure signal in a subplot-ready format."""

    # Get digital events and filter for exposures
    digital_events_df = nev.get_digital_events_df()
    digital_events_df = digital_events_df[digital_events_df["InsertionReason"] == 1]

    # Optionally slice the DataFrame
    if start is not None and end is not None:
        digital_events_df = digital_events_df.iloc[start:end].copy()

    # Convert raw data to binary representation
    digital_events_df["UnparsedDataBin"] = digital_events_df["UnparsedData"].apply(
        to_16bit_binary
    )

    # Create axes if not provided
    if ax is None:
        fig, ax = plt.subplots(figsize=(6, 2))

    # Determine which bit contains the exposure signal
    candidate_bits = range(16) if bit_idx is None else [bit_idx]
    selected_bit = None
    for i in candidate_bits:
        filled_df = fill_missing_data(digital_events_df, bit_number=i)
        signal = filled_df[f"Bit{i}"]
        if signal.nunique() > 1:
            selected_bit = i
            break
    if selected_bit is None:
        raise ValueError("No active exposure signal found in any bit.")

    # Align timestamps to start at zero and convert to integer milliseconds
    times = filled_df["TimeStamps"] - filled_df["TimeStamps"].iloc[0]
    times = times / 1e3  # Convert to milliseconds
    # times = times.astype(int)

    # Plot the exposure signal
    ax.plot(
        times,
        signal,
        linewidth=1.2,
        label=f"Exposure (Bit {selected_bit})",
    )

    # Set y-axis limits and ticks
    ax.set_ylim(-0.2, 1.4)
    ax.set_yticks([0, 1])

    # Configure x-axis: integer ticks starting at zero
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_xlim(0, times.max())

    # Add labels or hide them
    if show_labels:
        ax.set_xlabel("Time (ms)", fontsize=10)
        ax.set_ylabel("Signal", fontsize=10)
    else:
        ax.set_xticks([])
        ax.set_yticks([])

    # Add legend if desired
    if show_legend:
        ax.legend(loc="upper right", fontsize=8, frameon=False)

    # Remove unnecessary spines
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # Save figure if path provided
    if save_path:
        plt.tight_layout()
        plt.savefig(save_path, dpi=dpi)

    # Close the figure if we created it
    if ax is None:
        plt.close()


def plot_chunk_serial_diff_histogram(
    nev,
    save_path: str = None,
    ax=None,
    figsize=(6, 3),
    range_min: int = -3,
    range_max: int = 5,
    color: str = "#4c72b0",  # Default matplotlib blue
    bar_width: float = 0.5,  # Thinner bar
):
    """
    Histogram of chunk serial diffs using matplotlib with bars centered and thin.
    """
    # Get data
    df = nev.get_chunk_serial_df()
    diffs = df["chunk_serial"].diff().dropna()

    # Define bin centers and edges
    bin_centers = np.arange(range_min, range_max + 1)
    bin_edges = bin_centers - 0.5

    # Create axis if not provided
    created_fig = False
    if ax is None:
        fig, ax = plt.subplots(figsize=figsize)
        created_fig = True

    # Histogram data
    counts, _ = np.histogram(diffs, bins=np.append(bin_edges, bin_edges[-1] + 1))

    # Bar plot (centered and narrower)
    ax.bar(
        bin_centers,
        counts,
        width=bar_width,
        color=color,
        edgecolor="white",
        linewidth=0.5,
        align="center",
    )

    # Vertical reference line at expected increment
    ax.axvline(
        1,
        color="crimson",
        linestyle="--",
        linewidth=1.2,
        label="Expected Increment (1)",
    )

    # X-axis ticks
    ax.set_xticks(bin_centers)

    # Labels and grid
    ax.set_title("Distribution of Chunk Serial Increments", fontsize=13, weight="bold")
    ax.set_xlabel("Δ Chunk Serial", fontsize=11)
    ax.set_ylabel("Frequency", fontsize=11)
    ax.tick_params(labelsize=9)
    ax.grid(True, linestyle="--", alpha=0.3)

    # Move legend outside top-right
    ax.legend(
        loc="upper left",
        bbox_to_anchor=(1.01, 1),
        borderaxespad=0,
        fontsize=9,
    )

    # Save if needed
    if save_path and created_fig:
        plt.tight_layout()
        fig.savefig(save_path, dpi=300, bbox_inches="tight")
    if created_fig:
        plt.close(fig)


def plot_chunk_interval_distribution(
    nev,
    save_path: str,
    ax=None,
    figsize=(6, 3),
    nominal_rate_hz: float = 30.0,
    sampling_rate: int = 30000,
):
    """
    Plot a histogram of inter-chunk time intervals to demonstrate that chunks are
    spaced at ~30 Hz based on 30 kHz timestamp data.

    Args:
        nev: Nev object with .get_chunk_serial_df() that returns a DataFrame
             with 'chunk_serial' and 'TimeStamps' columns.
        save_path: Path to save the plot (PNG, PDF, etc.).
        ax: Optional matplotlib Axes for subplot support.
        figsize: Figure size if ax is None.
        nominal_rate_hz: Expected chunk rate (default 30 Hz).
        sampling_rate: Timestamp base rate (default 30 000 Hz).
        bins: Number of histogram bins.
    """
    # 1. Pull timestamps & compute Δt in seconds
    df = nev.get_chunk_serial_df()
    stamps = df["TimeStamps"].values
    dt_seconds = np.diff(stamps) / sampling_rate

    # 2. Nominal interval (s)
    nominal_interval = 1.0 / nominal_rate_hz

    # 3. Create figure/axis if needed
    created_fig = False
    if ax is None:
        fig, ax = plt.subplots(figsize=figsize)
        created_fig = True

    # 4. Plot histogram
    ax.hist(
        dt_seconds,
        color="black",
        edgecolor="white",
    )
    # 5. Vertical line at expected interval
    # ax.axvline(
    #     nominal_interval,
    #     color="red",
    #     linestyle="--",
    #     linewidth=1.2,
    #     label=f"Nominal {nominal_rate_hz:.0f} Hz → {nominal_interval:.4f} s",
    # )

    # 6. Formatting
    ax.set_title("Distribution of Time Between Chunk Serials", fontsize=12)
    ax.set_xlabel("Interval Duration (s)", fontsize=10)
    ax.set_ylabel("Count", fontsize=10)
    ax.grid(True, linestyle="--", alpha=0.3)
    ax.legend(loc="upper right", fontsize=8)

    # 7. Save
    if save_path:
        fig_to_save = ax.figure
        fig_to_save.tight_layout()
        fig_to_save.savefig(save_path, dpi=300)

    # 8. Clean up if we created the figure
    if created_fig:
        plt.close(fig)


def plot_exposure_interval_distribution(
    csv_path: str,
    save_path: str,
    ax=None,
    figsize=(6, 3),
    sampling_rate: int = 30000,
    nominal_rate_hz: float = 30.0,
):
    """
    Reads a CSV of exposure pulses and plots the distribution of time intervals
    between the first '1' in each group of Bit8.  This demonstrates that
    exposures occur at ~30 Hz.

    Args:
        csv_path: Path to the CSV file. Must have columns:
            - "TimeStamps": integer sample indices at 'sampling_rate' Hz
            - "Bit8": 0/1 indicating exposure pulse
        save_path: Path to save the resulting PNG/PDF figure.
        ax: Optional matplotlib Axes to plot onto. If None, a new figure is created.
        figsize: Figure size when creating a new Axes.
        sampling_rate: Sampling rate of the TimeStamps (default 30 kHz).
        nominal_rate_hz: Expected exposure rate (default 30 Hz).
        bins: Number of histogram bins.
    """
    # 1. Load data
    df = pd.read_csv(csv_path)
    stamps = df["TimeStamps"].to_numpy()
    bits = df["Bit8"].to_numpy().astype(int)

    # 2. Find the first index of each 1‑group (rising edges)
    ones = np.where(bits == 1)[0]
    if ones.size == 0:
        raise ValueError("No exposure pulses (Bit8==1) found in CSV.")
    # A rising edge is where the gap to the previous '1' is >1 sample
    edges = ones[np.insert(np.diff(ones) > 1, 0, True)]
    edge_times = stamps[edges]

    # 3. Compute inter‑edge intervals in seconds
    intervals = np.diff(edge_times) / sampling_rate
    nominal_interval = 1.0 / nominal_rate_hz

    # 4. Prepare axes
    if ax is None:
        fig, ax = plt.subplots(figsize=figsize)

    # 5. Plot histogram
    ax.hist(intervals, color="black", edgecolor="white")
    # ax.axvline(
    #     nominal_interval,
    #     color="red",
    #     linestyle="--",
    #     linewidth=1.2,
    #     label=f"Nominal {nominal_rate_hz:.0f} Hz → {nominal_interval:.4f} s",
    # )

    # 6. Formatting for IEEE style
    ax.set_title("Exposure-Pulse Interval Distribution", fontsize=12)
    ax.set_xlabel("Interval (s)", fontsize=10)
    ax.set_ylabel("Count", fontsize=10)
    ax.grid(True, linestyle="--", alpha=0.3)
    # ax.legend(loc="upper right", fontsize=8)

    # 7. Save and clean up
    if ax.figure:
        ax.figure.tight_layout()
        ax.figure.savefig(save_path, dpi=300)
        if ax is None:
            plt.close(ax.figure)


if __name__ == "__main__":
    nev_path = (
        "/home/auto/CODE/utils/video-sync/ieeener/data/nev/NSP1-20240723-111254-003.nev"
    )
    filled_df_path = "/home/auto/CODE/utils/video-sync/ieeener/data/intermediate_results/filled_df.csv"

    cam_exposure_png_save = (
        "/home/auto/CODE/utils/video-sync/ieeener/data/plot/cam_exposure.png"
    )
    serial_diff_dist_png = "/home/auto/CODE/utils/video-sync/ieeener/data/plot/serial_diff_distribution.png"
    serial_time_diff_distribution_png = "/home/auto/CODE/utils/video-sync/ieeener/data/plot/serial_time_diff_distribution.png"
    cam_exposure_time_diff_distribution_png = "/home/auto/CODE/utils/video-sync/ieeener/data/plot/cam_exposure_time_diff_distribution.png"

    nev = Nev(nev_path)

    # plot_cam_exposure_all(
    #     nev=nev,
    #     save_path=cam_exposure_png_save,
    #     start=0,
    #     end=50,
    #     ax=None,
    #     dpi=300,
    #     show_labels=True,
    #     show_legend=True,
    # )

    plot_chunk_serial_diff_histogram(
        nev=nev,
        save_path=serial_diff_dist_png,
        ax=None,
        range_min=0,
        range_max=2,
    )

    # plot_chunk_interval_distribution(
    #     nev=nev,
    #     save_path=nev_serial_time_diff_distribution_png_save,
    #     ax=None,
    # )

    # plot_exposure_interval_distribution(
    #     csv_path=filled_df_path,
    #     save_path=nev_cam_exposure_time_diff_distribution_png_save,
    #     ax=None,
    #     figsize=(6, 3),
    #     sampling_rate=30000,
    #     nominal_rate_hz=30.0,
    # )

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
    save_path: str = None,
    ax=None,
    figsize=(6, 3),
    sampling_rate: int = 30000,
    bins: int = 100,
    bar_width: float = 0.5,  # thickness of each bar
    x_spacing: float = 1,  # distance between bar centers
    color: str = "#4c72b0",  # professional default blue
):
    """
    Plot only the non-zero-frequency bars, with adjustable bar width and spacing.

    Args:
        nev: Nev object with .get_chunk_serial_df() containing 'TimeStamps'.
        save_path: Where to save the figure (optional).
        ax: Optional matplotlib axis.
        figsize: Figure size if ax is None.
        sampling_rate: Sampling rate of timestamps (Hz).
        bins: Number of bins for the histogram.
        bar_width: Fractional width of each bar (in the same units as x_spacing).
        x_spacing: Spacing between consecutive bar centers (default = 1.0).
        color: Histogram fill color.
    """
    # 1) compute frequencies
    df = nev.get_chunk_serial_df()
    stamps = df["TimeStamps"].values
    dt_s = np.diff(stamps) / sampling_rate
    freqs = 1.0 / dt_s

    # 2) histogram & filter zeros
    counts, edges = np.histogram(freqs, bins=bins)
    centers = (edges[:-1] + edges[1:]) / 2
    mask = counts > 0
    counts = counts[mask]
    centers = centers[mask]

    # 3) x positions = 0, x_spacing, 2*x_spacing, ...
    x = np.arange(len(counts)) * x_spacing

    # 4) axis setup
    created = False
    if ax is None:
        fig, ax = plt.subplots(figsize=figsize)
        created = True

    # 5) draw bars (log(1+count))
    ax.bar(
        x,
        np.log1p(counts),
        width=bar_width,
        align="center",
        color=color,
        edgecolor="white",
        linewidth=0.5,
    )

    # 6) tick at each bar center, label with true Hz
    ax.set_xticks(x)
    ax.set_xticklabels([f"{c:.1f} Hz" for c in centers], rotation=45, ha="right")

    # 7) formatting
    ax.set_title("Inter-Chunk Frequency Distribution", fontsize=13, weight="bold")
    ax.set_xlabel("Chunk Frequency", fontsize=11)
    ax.set_ylabel("log(Count + 1)", fontsize=11)
    ax.tick_params(labelsize=9)
    ax.grid(True, linestyle="--", alpha=0.3)

    # 8) save & cleanup
    if save_path:
        fig = ax.figure
        fig.tight_layout()
        fig.savefig(save_path, dpi=300, bbox_inches="tight")
    if created:
        plt.close(fig)


def plot_exposure_interval_distribution(
    csv_path: str,
    save_path: str,
    ax=None,
    figsize=(6, 3),
    sampling_rate: int = 30000,
    bins: int = 100,
    bar_width: float = 0.3,
    x_spacing: float = 1.0,
    color: str = "#dd8452",  # professional orange
):
    """
    Reads exposure pulses from CSV and plots the distribution of intervals
    (in Hz) using log-scaled counts. Only non-zero bars are shown.

    Args:
        csv_path: CSV file with "TimeStamps" and "Bit8" columns.
        save_path: Output path for the plot.
        ax: Optional axis to plot into.
        figsize: Figure size if ax is None.
        sampling_rate: Timestamps per second (Hz).
        bins: Number of histogram bins for frequency.
        bar_width: Width of each bar.
        x_spacing: Distance between bar centers.
        color: Color of the histogram bars.
    """
    # 1. Load exposure timestamps from rising edges
    df = pd.read_csv(csv_path)
    stamps = df["TimeStamps"].to_numpy()
    bits = df["Bit8"].to_numpy().astype(int)

    ones = np.where(bits == 1)[0]
    if ones.size == 0:
        raise ValueError("No exposure pulses (Bit8==1) found in CSV.")
    edges = ones[np.insert(np.diff(ones) > 1, 0, True)]
    edge_times = stamps[edges]
    intervals_s = np.diff(edge_times) / sampling_rate
    freqs = 1.0 / intervals_s

    # 2. Histogram and filter out empty bins
    counts, edges = np.histogram(freqs, bins=bins)
    centers = (edges[:-1] + edges[1:]) / 2
    mask = counts > 0
    counts = counts[mask]
    centers = centers[mask]

    # 3. Categorical x for adjacent bars
    x = np.arange(len(counts)) * x_spacing

    # 4. Setup axis
    created_fig = False
    if ax is None:
        fig, ax = plt.subplots(figsize=figsize)
        created_fig = True

    # 5. Plot bars
    ax.bar(
        x,
        np.log1p(counts),
        width=bar_width,
        align="center",
        color=color,
        edgecolor="white",
        linewidth=0.5,
    )

    # 6. X ticks and labels
    ax.set_xticks(x)
    ax.set_xticklabels([f"{c:.1f} Hz" for c in centers], rotation=45, ha="right")

    # 7. Aesthetics
    ax.set_title("Exposure-Pulse Frequency Distribution", fontsize=13, weight="bold")
    ax.set_xlabel("Frequency (Hz)", fontsize=11)
    ax.set_ylabel("log(Count + 1)", fontsize=11)
    ax.tick_params(labelsize=9)
    ax.grid(True, linestyle="--", alpha=0.3)

    # 8. Save
    if save_path:
        fig = ax.figure
        fig.tight_layout()
        fig.savefig(save_path, dpi=300, bbox_inches="tight")
    if created_fig:
        plt.close(fig)


if __name__ == "__main__":
    nev_path = (
        "/home/auto/CODE/utils/video-sync/ieee/data/nev/NSP1-20240723-111254-003.nev"
    )
    filled_df_path = (
        "/home/auto/CODE/utils/video-sync/ieee/data/intermediate_results/filled_df.csv"
    )

    cam_exposure_png_save = (
        "/home/auto/CODE/utils/video-sync/ieee/plot/cam_exposure.png"
    )
    serial_diff_dist_png = (
        "/home/auto/CODE/utils/video-sync/ieee/plot/serial_diff_distribution.png"
    )
    serial_time_diff_distribution_png = (
        "/home/auto/CODE/utils/video-sync/ieee/plot/serial_time_diff_distribution.png"
    )
    cam_exposure_time_diff_distribution_png = "/home/auto/CODE/utils/video-sync/ieee/plot/cam_exposure_time_diff_distribution.png"

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

    # plot_chunk_serial_diff_histogram(
    #     nev=nev,
    #     save_path=serial_diff_dist_png,
    #     ax=None,
    #     range_min=0,
    #     range_max=2,
    # )

    # plot_chunk_interval_distribution(
    #     nev=nev,
    #     save_path=serial_time_diff_distribution_png,
    #     ax=None,
    #     figsize=(4, 3),
    #     bar_width=0.2,
    #     x_spacing=0.5,
    # )

    plot_exposure_interval_distribution(
        csv_path=filled_df_path,
        save_path=cam_exposure_time_diff_distribution_png,
        ax=None,
        figsize=(6, 3),
        sampling_rate=30000,
        bar_width=0.3,
        x_spacing=0.5,
    )

"""
Profile NEVs

Plots
- Cam exposure
- Basic Statistics
-
"""

from pyvideosync.nev import Nev
import argparse
import os
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.pyplot as plt
import pandas as pd
from profiler.discontinuity import detect_discontinuities


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Plot NEV cam exposure and chunk serial data."
    )
    parser.add_argument("nev_path", type=str, help="Path to NEV file")
    parser.add_argument("out_dir", type=str, help="Output directory to save the PDF")
    return parser.parse_args()


def create_profile_plot(nev_path: str, pdf):
    nev = Nev(nev_path)

    # Create a figure for the plots (3 rows for each plot)
    fig = plt.figure(figsize=(10, 12))

    # Row 1: Camera exposure plot
    ax1 = plt.subplot2grid((3, 2), (0, 0), colspan=2)
    nev.plot_cam_exposure_all(
        save_path=None,  # We will save to the PDF later, so no need for save_path here
        start=0,
        end=200,
        ax=ax1,  # Plot camera exposure on the first row
    )
    ax1.set_title("Camera Exposure Plot")
    ax1.grid(True)

    # Row 2: Chunk serial plot
    ax2 = plt.subplot2grid((3, 2), (1, 0), colspan=2)
    chunk_serial_df = nev.get_chunk_serial_df()
    ax2.plot(chunk_serial_df.index, chunk_serial_df["chunk_serial"], color="blue")
    ax2.set_title("Chunk Serial Plot")
    ax2.set_ylabel("Chunk Serial")
    ax2.set_xlabel("Index")
    ax2.grid(True)

    chunk_type_i, chunk_type_ii, chunk_durations = detect_discontinuities(
        chunk_serial_df["chunk_serial"]
    )

    ax2.text(
        0.95,
        0.9,
        f"Type I: {chunk_type_i}, Type II: {chunk_type_ii}",
        transform=ax2.transAxes,
        fontsize=10,
        verticalalignment="top",
        bbox=dict(facecolor="white", alpha=0.5),
    )

    # Row 3: DataFrame preview on the left and distribution plot on the right
    ax3_hist = plt.subplot2grid((3, 2), (2, 0), colspan=2)
    ax3_hist.hist(chunk_durations, bins=20, alpha=0.7, color="green")
    ax3_hist.set_title("Distribution of Continuous Sections (Chunk Serial)")
    ax3_hist.set_xlabel("Section Length")
    ax3_hist.set_ylabel("Frequency")
    ax3_hist.grid(True)

    # Adjust layout and save to PDF
    plt.tight_layout()
    pdf.savefig(fig)
    plt.close()


def detect_continuous_sections(chunk_serial):
    """Detect continuous sections in chunk_serial where a discontinuity is defined
    as when the next number is smaller than the previous number."""
    if len(chunk_serial) == 0:
        return []

    continuous_sections = []
    start_idx = 0

    for i in range(1, len(chunk_serial)):
        if chunk_serial[i] < chunk_serial[i - 1]:  # Detect discontinuity
            # Record the length of the continuous section
            continuous_sections.append(i - start_idx)
            start_idx = i  # Move the start index to the new discontinuous point

    # Add the last section if it continues till the end
    continuous_sections.append(len(chunk_serial) - start_idx)

    return continuous_sections


def main():
    args = parse_arguments()

    out_path = os.path.join(args.out_dir, f"nev_report.pdf")
    with PdfPages(out_path) as pdf:
        create_profile_plot(
            args.nev_path,
            pdf,
        )

    print(f"Report generated to {out_path}")


if __name__ == "__main__":
    main()

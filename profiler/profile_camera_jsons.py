"""
Profile camera JSONs

Usage
- python profile_camera_jsons.py <camera_json> <json_file> <out_dir>
"""

import argparse
from pyvideosync.videojson import Videojson
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import os
from profiler.discontinuity import detect_discontinuities


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Plot chunk serial number and frame id for a camera."
    )
    parser.add_argument("camera_serial", type=str, help="Camera serial number")
    parser.add_argument("json_file", type=str, help="Path to the JSON file")
    parser.add_argument("out_dir", type=str, help="Output Directory to save Pdf")
    return parser.parse_args()


def extract_data_from_json(json_file, camera_serial=None):
    videojson = Videojson(json_file)
    chunk_serials = videojson.get_chunk_serial_list(camera_serial)
    frame_ids = videojson.get_frame_ids_list(camera_serial)
    return chunk_serials, frame_ids


def create_profile_plot(chunk_serials, frame_ids, pdf):
    chunk_type_i, chunk_type_ii, chunk_durations = detect_discontinuities(chunk_serials)

    frame_type_i, frame_type_ii, frame_durations = detect_discontinuities(frame_ids)

    indices = list(range(len(chunk_serials)))

    # Create a figure with 3 rows: first two rows spanning the entire row, third row with side-by-side histograms
    fig = plt.figure(figsize=(12, 10))

    # First row: chunk serial plot, expanding across the full width
    ax1 = plt.subplot2grid((3, 2), (0, 0), colspan=2)
    ax1.plot(indices, chunk_serials, color="blue", label="Chunk Serial Numbers")
    ax1.set_ylabel("Chunk Serial Numbers")
    ax1.set_title("Chunk Serial Numbers Plot")
    ax1.grid(True)

    ax1.text(
        0.95,
        0.9,
        f"Type I: {chunk_type_i}, Type II: {chunk_type_ii}",
        transform=ax1.transAxes,
        fontsize=10,
        verticalalignment="top",
        bbox=dict(facecolor="white", alpha=0.5),
    )

    # Second row: frame ID plot, expanding across the full width
    ax2 = plt.subplot2grid((3, 2), (1, 0), colspan=2)
    ax2.plot(indices, frame_ids, color="red", label="Frame IDs")
    ax2.set_ylabel("Frame IDs")
    ax2.set_xlabel("Indices")
    ax2.set_title("Frame IDs Plot")
    ax2.grid(True)

    ax2.text(
        0.95,
        0.9,
        f"Type I: {frame_type_i}, Type II: {frame_type_ii}",
        transform=ax2.transAxes,
        fontsize=10,
        verticalalignment="top",
        bbox=dict(facecolor="white", alpha=0.5),
    )

    # Third row: side-by-side histograms
    ax3 = plt.subplot2grid((3, 2), (2, 0))
    ax3.hist(chunk_durations, bins=20, alpha=0.7, color="blue")
    ax3.set_title("Chunk Serial Durations Histogram")
    ax3.set_xlabel("Duration Length")
    ax3.set_ylabel("Frequency")
    ax3.grid(True)

    ax4 = plt.subplot2grid((3, 2), (2, 1))
    ax4.hist(frame_durations, bins=20, alpha=0.7, color="red")
    ax4.set_title("Frame ID Durations Histogram")
    ax4.set_xlabel("Duration Length")
    ax4.set_ylabel("Frequency")
    ax4.grid(True)

    # Adjust layout to fit all subplots nicely
    plt.tight_layout()

    # Save the combined plot to the PDF
    pdf.savefig(fig)
    plt.close()


def main():
    args = parse_arguments()

    chunk_serials, frame_ids = extract_data_from_json(
        args.json_file, args.camera_serial
    )

    out_path = os.path.join(args.out_dir, f"cam_{args.camera_serial}_json_report.pdf")
    with PdfPages(out_path) as pdf:
        create_profile_plot(
            chunk_serials,
            frame_ids,
            pdf,
        )

    print(f"Report generated to {out_path}")


if __name__ == "__main__":
    main()

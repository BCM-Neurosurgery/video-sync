"""
Benchmark Camera files from a directory
"""

from pyvideosync.videojson import Videojson
from pyvideosync.video import Video
import argparse
import os
from profiler.discontinuity import detect_discontinuities
from profiler.profile_camera_jsons import create_profile_plot
import re
import json
from datetime import datetime
from matplotlib.backends.backend_pdf import PdfPages


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Benchmark camera JSONs/MP4s from a directory."
    )
    parser.add_argument(
        "cam_dir", type=str, help="Path to camera acquisition directory"
    )
    parser.add_argument("out_dir", type=str, help="Output directory to save the JSON")
    parser.add_argument("cam_serial", type=str, help="Camera Serial Number")
    parser.add_argument(
        "--profile_cam_json",
        action="store_true",
        help="Flag to indicate whether to profile the JSON",
    )
    return parser.parse_args()


def get_sorted_json_files(directory):
    """
    Retrieves and returns a list of JSON files from the given directory,
    sorted in chronological order based on the timestamp embedded at the
    end of each filename. The filenames are expected to follow the pattern
    'description_YYYYMMDD_HHMMSS.json', where the final
    'YYYYMMDD_HHMMSS' represents the timestamp.

    Args:
        directory (str): The path to the directory containing the JSON files.

    Returns:
        list: A list of JSON filenames sorted by the timestamp in chronological order.

    Example:
        If the directory contains files named:
            - '20240906_long_weekend_test_20240906_153615.json'
            - '20240906_long_weekend_test_20240906_154616.json'
            - '20240906_long_weekend_test_20240906_155617.json'

        The function will return:
            [
                '20240906_long_weekend_test_20240906_153615.json',
                '20240906_long_weekend_test_20240906_154616.json',
                '20240906_long_weekend_test_20240906_155617.json'
            ]
    """
    # Regex to match the timestamp at the end of the JSON file names
    timestamp_pattern = r"\d{8}_\d{6}"

    # List to store tuples of (filename, timestamp)
    json_files_with_timestamps = []

    # Iterate through the files in the given directory
    for file in os.listdir(directory):
        if file.endswith(".json"):
            # Extract the timestamp using the regex
            match = re.search(timestamp_pattern, file)
            if match:
                timestamp_str = match.group(0)
                # Parse the timestamp into a datetime object for sorting
                timestamp = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                json_files_with_timestamps.append((file, timestamp))

    # Sort the files based on the extracted timestamp
    sorted_json_files = sorted(json_files_with_timestamps, key=lambda x: x[1])

    # Return only the filenames in sorted order
    return [file for file, timestamp in sorted_json_files]


def find_corresponding_mp4(directory, json_filename, cam_serial):
    """
    Given a directory, a JSON filename, and a camera serial number,
    this function returns the full path to the corresponding .mp4 file
    that shares the same timestamp as the JSON file and ends with the specified cam_serial.

    Args:
        directory (str): The path to the directory containing both the JSON and mp4 files.
        json_filename (str): The name of the JSON file to find the corresponding mp4 for.
        cam_serial (str): The camera serial number to match with the mp4 filename.

    Returns:
        str: The full path to the corresponding .mp4 file if found, or None if not found.

    Example:
        If the directory contains the files:
            - '20240906_long_weekend_test_20240906_154616.json'
            - '20240906_long_weekend_test_20240906_154616.23512908.mp4'

        Calling the function with:
            find_corresponding_mp4('/path/to/dir', '20240906_long_weekend_test_20240906_154616.json', '23512908')

        Will return:
            '/path/to/dir/20240906_long_weekend_test_20240906_154616.23512908.mp4'
    """
    # Extract the timestamp from the JSON filename
    timestamp_pattern = r"\d{8}_\d{6}"
    match = re.search(timestamp_pattern, json_filename)

    if not match:
        raise ValueError(
            "The provided JSON filename does not contain a valid timestamp."
        )

    # Get the timestamp part from the JSON file (e.g., '20240906_154616')
    timestamp_str = match.group(0)

    # Construct the expected mp4 filename pattern with the cam_serial number
    mp4_pattern = f"{timestamp_str}.{cam_serial}.mp4"

    # Search for the corresponding mp4 file in the directory
    for file in os.listdir(directory):
        if file.endswith(".mp4") and mp4_pattern in file:
            return os.path.join(directory, file)

    # If no matching file is found
    return None


def benchmark(cam_dir: str, output_dir: str, cam_serial: str, profile_cam_json: bool):
    """
    Benchmarks Camera files by detecting discontinuities in the chunk serial data
    and frame ids, and saves the results to a JSON file.

    Args:
        cam_dir (str): Directory containing the Camera files.
        output_dir (str): Directory to save the results JSON and optional reports.
        cam_serial (str): Camera Serial Number to process.
        profile_cam_json (bool): Flag to indicate whether to generate a profiling report.
    """
    jsons = get_sorted_json_files(cam_dir)

    output_json = os.path.join(output_dir, f"cam_benchmark_results_{cam_serial}.json")
    if os.path.exists(output_json):
        with open(output_json, "r") as f:
            results = json.load(f)
    else:
        results = {}

    for json_file in jsons:

        if profile_cam_json:
            pdf_out_dir = os.path.join(output_dir, f"cam_{cam_serial}_json_report")
            os.makedirs(pdf_out_dir, exist_ok=True)
            out_path = os.path.join(pdf_out_dir, f"{os.path.basename(json_file)}.pdf")
            with PdfPages(out_path) as pdf:
                create_profile_plot(
                    chunk_serial,
                    frame_ids,
                    pdf,
                )

        if json_file in results:
            continue

        print(f"Processing {json_file}")
        json_path = os.path.join(cam_dir, json_file)
        mp4_path = find_corresponding_mp4(cam_dir, json_file, cam_serial)
        if mp4_path is None:
            results[json_file] = {"error": "Corresponding MP4 file not found."}
            continue

        try:
            jsonfile = Videojson(json_path)
            chunk_serial = jsonfile.get_chunk_serial_list(cam_serial)
            frame_ids = jsonfile.get_frame_ids_list(cam_serial)

            chunk_discontinuities = detect_discontinuities(chunk_serial)
            frame_discontinuities = detect_discontinuities(frame_ids)

            mp4_file = Video(mp4_path)

            results[json_file] = {
                "chunk_discontinuities": chunk_discontinuities,
                "frame_discontinuities": frame_discontinuities,
                "json_recording_duration": jsonfile.get_duration_readable(),
                "mp4_frame_count": mp4_file.get_frame_count(),
            }

        except Exception as e:
            results[json_file] = {"error": str(e)}

        with open(output_json, "w") as json_to_save:
            json.dump(results, json_to_save, indent=4)


def main():
    args = parse_arguments()

    os.makedirs(args.out_dir, exist_ok=True)

    benchmark(args.cam_dir, args.out_dir, args.cam_serial, args.profile_cam_json)


if __name__ == "__main__":
    main()

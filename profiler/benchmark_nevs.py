"""
Benchmark NEVs from a directory
"""

from pyvideosync.nev import Nev
import argparse
import os
from profiler.discontinuity import detect_discontinuities
import re
import json


def parse_arguments():
    parser = argparse.ArgumentParser(description="Benchmark NEVs from a directory.")
    parser.add_argument("nev_dir", type=str, help="Path to NEV directory")
    parser.add_argument("out_dir", type=str, help="Output directory to save the JSON")
    return parser.parse_args()


def get_sorted_nev_files(folder_path):
    """
    Returns a sorted list of .nev files based on their sequence numbers.

    The function scans a specified folder for .nev files with filenames in the
    format 'NSP2-YYYYMMDD-HHMMSS-XXX.nev' and sorts them by the numeric sequence
    (XXX) part of the filename.

    Args:
        folder_path (str): The path to the folder containing the .nev files.

    Returns:
        List[str]: A list of .nev filenames sorted by their sequence number.

    Example:
        folder_path = '/path/to/your/folder'
        sorted_nev_files = get_sorted_nev_files(folder_path)
        print(sorted_nev_files)
    """
    nev_pattern = re.compile(r"NSP2-\d{8}-\d{6}-(\d+)\.nev")
    all_files = os.listdir(folder_path)
    nev_files = [f for f in all_files if nev_pattern.match(f)]
    sorted_nev_files = sorted(
        nev_files, key=lambda x: int(nev_pattern.match(x).group(1))
    )
    return sorted_nev_files


def benchmark(nev_dir: str, output_json: str):
    """
    Benchmarks NEV files by detecting discontinuities in the chunk serial data
    and saving the results (chunk_type_i, chunk_type_ii) into a JSON file.

    Args:
        nev_dir (str): Directory containing the NEV files.
        output_json (str): Path to the output JSON file.
    """
    nev_files = get_sorted_nev_files(nev_dir)

    if os.path.exists(output_json):
        with open(output_json, "r") as f:
            results = json.load(f)
    else:
        results = {}

    for nev_file in nev_files:
        if nev_file in results:
            continue

        nev_path = os.path.join(nev_dir, nev_file)

        try:
            nev = Nev(nev_path)

            chunk_serial_df = nev.get_chunk_serial_df_original()

            chunk_type_i, chunk_type_ii, chunk_type_iii, chunk_durations = (
                detect_discontinuities(chunk_serial_df["chunk_serial"])
            )

            results[nev_file] = {
                "chunk_type_i": chunk_type_i,
                "chunk_type_ii": chunk_type_ii,
                "chunk_type_iii": chunk_type_iii,
                "chunk_durations": chunk_durations,
                "recording_duration": nev.get_duration_readable(),
            }

        except Exception as e:
            # Log the error into the JSON file under the nev_file key
            results[nev_file] = {"error": str(e)}

        # Save the results to the JSON file after each file is processed
        with open(output_json, "w") as json_file:
            json.dump(results, json_file, indent=4)


def main():
    args = parse_arguments()

    # Ensure the output directory exists
    os.makedirs(args.out_dir, exist_ok=True)

    # Define the output JSON file path
    output_json = os.path.join(args.out_dir, "nev_benchmark_results.json")

    # Run the benchmark process
    benchmark(args.nev_dir, output_json)


if __name__ == "__main__":
    main()

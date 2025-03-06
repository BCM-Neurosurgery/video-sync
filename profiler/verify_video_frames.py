import argparse
import json
from pathlib import Path
from pyvideosync.video import Video
from pyvideosync.videojson import Videojson
from pyvideosync.data_pool import VideoFilesPool


def detect_jumps(df, column):
    """
    Detect jumps in a specified column of a DataFrame and return results as a list of dictionaries.

    Args:
        df (pd.DataFrame): The DataFrame containing the data.
        column (str): The column to analyze for jumps.

    Returns:
        list[dict]: A list of dictionaries with details on detected jumps.
    """
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found in DataFrame.")

    df = df.sort_index()  # Ensure DataFrame is sorted by index
    prev_values = df[column].shift(
        1
    )  # Shift values down by 1 to compare with previous row
    jumps = df[column] - prev_values  # Calculate jump size

    jump_indices = jumps[jumps > 1].index  # Find where jumps occur

    # Create a list of dictionaries to store jump details
    jumps_list = [
        {
            "index": idx,
            "prev_value": prev_values.loc[idx],
            "new_value": df.loc[idx, column],
            "jump_size": jumps.loc[idx],
        }
        for idx in jump_indices
    ]

    return jumps_list


def process_directory(video_dir):
    results = {}

    video_file_pool = VideoFilesPool()

    for datefolder_path in Path(video_dir).iterdir():
        if datefolder_path.is_dir():
            for file_path in datefolder_path.iterdir():
                video_file_pool.add_file(str(file_path.resolve()))

    camera_files = video_file_pool.list_groups()
    camera_serials = video_file_pool.get_unique_cam_serials()

    for camera_serial in camera_serials:
        print(f"Camera serial: {camera_serial}")
        print("-")
        for timestamp, camera_file_group in camera_files.items():
            json_files = [
                file for file in camera_file_group if file.lower().endswith(".json")
            ]

            json_path = json_files[0] if len(json_files) == 1 else None
            if json_path is None:
                continue

            videojson = Videojson(json_path)
            duration = videojson.get_duration_readable()
            if duration is None:
                print(f"  No duration found for timestamp: {timestamp}")
                continue

            camera_df = videojson.get_camera_df(camera_serial)
            json_frames = len(camera_df)
            jump_list = detect_jumps(camera_df, "frame_ids_reconstructed")

            mp4_files = [
                file
                for file in camera_file_group
                if file.lower().endswith(".mp4") and camera_serial in file
            ]
            video_path = mp4_files[0] if len(mp4_files) == 1 else None
            if video_path is None:
                print(f"  No video file found for timestamp: {timestamp}")
                continue

            video = Video(video_path)
            frame_count = video.get_frame_count()
            results[mp4_files[0]] = {
                "file": mp4_files[0],
                "json_frames": json_frames,
                "actual_frames": frame_count,
                "json_discontinuities": jump_list,
            }

            print(f"    Timestamp: {timestamp}")
            print(f"    JSON frames: {json_frames}")
            print(f"    Actual frames: {frame_count}")
            print(f"    JSON discontinuities: {jump_list}")

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Process video and JSON files to check frame consistency and save results."
    )
    parser.add_argument(
        "directory",
        type=str,
        help="Path to the video directory containing subdirectories of video and JSON files.",
    )
    parser.add_argument("output", type=str, help="Path to save the output JSON file.")
    args = parser.parse_args()

    results = process_directory(args.directory)

    # Save results to JSON file
    with open(args.output, "w") as json_file:
        json.dump(results, json_file, indent=4)
    print(f"Results saved to {args.output}")


if __name__ == "__main__":
    main()

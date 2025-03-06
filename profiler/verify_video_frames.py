import argparse
import logging
from pathlib import Path
from pyvideosync.video import Video
from pyvideosync.videojson import Videojson
from pyvideosync.data_pool import VideoFilesPool
import pandas as pd


# Configure logging to log to both a file and console
def setup_logging(log_file):
    logger = logging.getLogger("VideoProcessor")
    logger.setLevel(logging.INFO)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # File handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.INFO)

    # Formatter
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)

    # Add handlers to logger
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


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

    return [
        {
            "index": int(idx),
            "prev_value": (
                int(prev_values.loc[idx]) if pd.notna(prev_values.loc[idx]) else None
            ),
            "new_value": int(df.loc[idx, column]),
            "jump_size": int(jumps.loc[idx]),
        }
        for idx in jump_indices
    ]


def process_directory(video_dir, logger):
    video_file_pool = VideoFilesPool()

    for datefolder_path in Path(video_dir).iterdir():
        if datefolder_path.is_dir():
            for file_path in datefolder_path.iterdir():
                video_file_pool.add_file(str(file_path.resolve()))

    camera_files = video_file_pool.list_groups()
    camera_serials = video_file_pool.get_unique_cam_serials()

    for camera_serial in camera_serials:
        logger.info(f"Processing Camera Serial: {camera_serial}")
        logger.info("-" * 50)

        for timestamp, camera_file_group in camera_files.items():
            json_files = [
                file for file in camera_file_group if file.lower().endswith(".json")
            ]

            json_path = json_files[0] if len(json_files) == 1 else None
            if json_path is None:
                logger.warning(f"  No JSON file found for timestamp: {timestamp}")
                continue

            videojson = Videojson(json_path)
            duration = videojson.get_duration_readable()
            if duration is None:
                logger.warning(f"  No duration found for timestamp: {timestamp}")
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
                logger.warning(f"  No video file found for timestamp: {timestamp}")
                continue

            video = Video(video_path)
            frame_count = video.get_frame_count()

            logger.info(f"    Timestamp: {timestamp}")
            logger.info(f"    JSON frames: {json_frames}")
            logger.info(f"    Actual frames: {frame_count}")
            logger.info(f"    JSON discontinuities: {jump_list}")


def main():
    parser = argparse.ArgumentParser(
        description="Process video and JSON files to check frame consistency and log results."
    )
    parser.add_argument(
        "directory",
        type=str,
        help="Path to the video directory containing subdirectories of video and JSON files.",
    )
    parser.add_argument("logfile", type=str, help="Path to save the log file.")
    args = parser.parse_args()

    # Setup logging
    logger = setup_logging(args.logfile)
    logger.info(f"Starting processing of directory: {args.directory}")

    try:
        process_directory(args.directory, logger)
        logger.info("Processing complete.")
    except Exception as e:
        logger.error(f"An error occurred: {e}", exc_info=True)


if __name__ == "__main__":
    main()

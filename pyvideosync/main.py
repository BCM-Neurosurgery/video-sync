"""
Main function to orchestrate the loading, processing, and merging of NEV, NS5, and camera data,
and aligning the audio with the video.
"""

import os
from pyvideosync.data_pool import DataPool
import pandas as pd
from pyvideosync.logging_config import (
    get_current_ts,
    configure_logging,
)
from pyvideosync.pathutils import PathUtils
from pyvideosync.process import (
    ffmpeg_concat_mp4s,
    make_synced_subclip_ffmpeg,
    make_synced_subclip_moviepy,
)
from pyvideosync.utils import (
    load_timestamps,
    save_timestamps,
    sort_timestamps,
    get_column_min_max,
    get_json_file,
    get_mp4_file,
)
from pyvideosync.videojson import Videojson
from pyvideosync.nev import Nev
from pyvideosync.nsx import Nsx
import argparse
import shutil
import uuid


def main():
    parser = argparse.ArgumentParser(
        description="Video synchronization tool for neural data and camera recordings."
    )
    parser.add_argument(
        "-c",
        "--config",
        required=True,
        help="Path to YAML configuration file",
        type=str,
    )

    args = parser.parse_args()
    config_path = args.config

    timestamp = get_current_ts()

    pathutils = PathUtils(config_path, timestamp)
    logger = configure_logging(pathutils.output_dir)

    if not pathutils.is_config_valid():
        logger.error("Config not valid, exiting to inital screen...")
        return

    # Check if we're in batch processing mode
    if pathutils.is_batch_mode():
        logger.info("Running in batch processing mode")

        # Get all matching task directories
        matching_dirs = pathutils.get_matching_task_dirs()

        if not matching_dirs:
            logger.error("No matching task directories found")
            return

        logger.info(f"Found {len(matching_dirs)} matching directories:")
        for dir_path in matching_dirs:
            logger.info(f"  - {dir_path}")

        # Process each directory
        success_count = 0
        nsp_dirs_to_process = matching_dirs
    else:
        # Single directory mode (existing behavior)
        logger.info("Running in single directory mode")
        nsp_dirs_to_process = [pathutils.nsp_dir]
        success_count = 0

    # Process all directories (either single or batch)
    for nsp_dir in nsp_dirs_to_process:
        if pathutils.is_batch_mode():
            logger.info(f"Processing directory: {nsp_dir}")

        try:
            # Create datapool with current nsp_dir
            datapool = DataPool(nsp_dir, pathutils.cam_recording_dir)

            # Create output directory for this specific NSP directory
            # Always create a subdirectory named after the NSP directory (task name)
            nsp_dirname = os.path.basename(nsp_dir)
            current_output_dir = os.path.join(pathutils.output_dir, nsp_dirname)

            os.makedirs(current_output_dir, exist_ok=True)

            if not datapool.verify_integrity():
                logger.error(
                    "File integrity check failed: Missing or duplicate NSP files detected. "
                    "Please verify the directory structure and try again. Returning to the initial screen."
                )
                if pathutils.is_batch_mode():
                    continue
                else:
                    return

            # 1. Get NEV serial start and end
            nsp1_nev_path = datapool.get_nev_path()
            nev = Nev(nsp1_nev_path)
            nev_chunk_serial_df = nev.get_chunk_serial_df()
            logger.info(f"NEV dataframe\n: {nev_chunk_serial_df}")
            nev_start_serial, nev_end_serial = get_column_min_max(
                nev_chunk_serial_df, "chunk_serial"
            )
            logger.info(
                f"Start serial: {nev_start_serial}, End serial: {nev_end_serial}"
            )

            # 2. Find all JSON files and MP4 files
            camera_files = datapool.get_video_file_pool().list_groups()
            if not camera_files:
                logger.error("No camera files found")
                if pathutils.is_batch_mode():
                    continue
                else:
                    return

            # 3. load camera serials from the config file
            camera_serials = pathutils.cam_serial
            logger.info(f"Camera serials loaded from config: {camera_serials}")

            # 4. Go through all JSON files and find the ones that
            # are within the NEV serial range
            # read timestamps if available
            timestamps_path = os.path.join(current_output_dir, "timestamps.json")
            timestamps = load_timestamps(timestamps_path, logger)
            if timestamps:
                logger.info(f"Loaded timestamps: {timestamps}")
            else:
                logger.info("No timestamps found")
                timestamps = []
                for timestamp, camera_file_group in camera_files.items():

                    json_path = get_json_file(camera_file_group, pathutils)
                    if json_path is None:
                        logger.error(f"No JSON file found in group {timestamp}")
                        continue

                    videojson = Videojson(json_path)
                    if not videojson.is_valid():
                        logger.error(f"Invalid JSON file: {json_path}")
                        continue

                    start_serial, end_serial = videojson.get_min_max_chunk_serial()
                    if start_serial is None or end_serial is None:
                        logger.error(
                            f"No chunk serials found in JSON file: {json_path}"
                        )
                        continue

                    if start_serial > nev_end_serial:
                        logger.info(f"Past end serial: {timestamp}")
                        break

                    if end_serial < nev_start_serial:
                        logger.info(f"No overlap found: {timestamp}")
                        continue

                    elif start_serial <= nev_end_serial:
                        logger.info(f"Overlap found, timestamp: {timestamp}")
                        timestamps.append(timestamp)

                    else:
                        logger.info(f"Break: {timestamp}")
                        break
                logger.info(f"timestamps: {timestamps}")
                save_timestamps(timestamps_path, timestamps)

            sorted_timestamps = sort_timestamps(timestamps)

            # process NS5 channel data
            ns5_path = datapool.get_ns5_path()
            ns5 = Nsx(ns5_path)

            # 5. Go through the timestamps and process the videos
            for camera_serial in camera_serials:
                all_merged_list = []

                for i, timestamp in enumerate(sorted_timestamps):
                    camera_file_group = camera_files[timestamp]

                    json_path = get_json_file(camera_file_group, pathutils)
                    if json_path is None:
                        logger.error(f"No JSON file found in group {timestamp}")
                        continue

                    videojson = Videojson(json_path)
                    camera_df = videojson.get_camera_df(camera_serial)

                    camera_df = camera_df.loc[
                        (camera_df["chunk_serial_data"] >= nev_start_serial)
                        & (camera_df["chunk_serial_data"] <= nev_end_serial)
                    ]

                    chunk_serial_joined = nev_chunk_serial_df.merge(
                        camera_df,
                        left_on="chunk_serial",
                        right_on="chunk_serial_data",
                        how="inner",
                    )

                    logger.info("Processing ns5 filtered channel df...")
                    ns5_slice = ns5.get_filtered_channel_df(
                        pathutils.ns5_channel,
                        chunk_serial_joined.iloc[0]["TimeStamps"],
                        chunk_serial_joined.iloc[-1]["TimeStamps"],
                    )

                    logger.info("Merging ns5 and chunk serial df...")
                    all_merged = ns5_slice.merge(
                        chunk_serial_joined,
                        left_on="TimeStamp",
                        right_on="TimeStamps",
                        how="left",
                    )

                    all_merged = all_merged[
                        [
                            "TimeStamp",
                            "Amplitude",
                            "chunk_serial",
                            "mp4_frame_idx",  # we only need the mp4_frame_idx
                        ]
                    ]

                    mp4_path = get_mp4_file(camera_file_group, camera_serial, pathutils)
                    if mp4_path is None:
                        logger.error(f"No MP4 file found in group {timestamp}")
                        continue

                    all_merged["mp4_file"] = mp4_path
                    all_merged_list.append(all_merged)

                if not all_merged_list:
                    logger.warning(f"No valid merged data for {camera_serial}")
                    continue

                all_merged_df = pd.concat(all_merged_list, ignore_index=True)
                logger.info(
                    f"Final merged DataFrame for {camera_serial} head:\n{all_merged_df.head()}"
                )
                logger.info(
                    f"Final merged DataFrame for {camera_serial} tail:\n{all_merged_df.tail()}"
                )

                # process the videos
                video_output_dir = os.path.join(current_output_dir, camera_serial)
                os.makedirs(video_output_dir, exist_ok=True)

                session_uuid = str(uuid.uuid4())[:8]
                subclip_paths = []
                for mp4_path in all_merged_df["mp4_file"].unique():
                    df_sub = all_merged_df[all_merged_df["mp4_file"] == mp4_path]

                    # Build a subclip from the relevant frames, attach audio
                    subclip = make_synced_subclip_moviepy(
                        df_sub,
                        mp4_path,
                        os.path.join(current_output_dir, camera_serial),
                        session_uuid,
                    )
                    subclip_paths.append(subclip)

                # Create final path based on the nsp directory name
                final_video_name = f"{os.path.basename(nsp_dir)}.mp4"

                final_path = os.path.join(
                    current_output_dir, camera_serial, final_video_name
                )
                # Now 'subclip_paths' has each final MP4 subclip
                # If we have only one, just rename or copy it
                if len(subclip_paths) == 1:
                    shutil.move(subclip_paths[0], final_path)
                else:
                    ffmpeg_concat_mp4s(subclip_paths, final_path)

                logger.info(f"Saved {camera_serial} to {final_path}")

            # Track success for batch mode
            if pathutils.is_batch_mode():
                success_count += 1
                logger.info(f"Successfully processed: {nsp_dir}")

        except Exception as e:
            if pathutils.is_batch_mode():
                logger.error(f"Error processing {nsp_dir}: {str(e)}")
            else:
                logger.error(f"Error processing: {str(e)}")
                raise

    # Log batch processing results
    if pathutils.is_batch_mode():
        logger.info(
            f"Batch processing complete. Successfully processed {success_count}/{len(nsp_dirs_to_process)} directories"
        )


if __name__ == "__main__":
    main()

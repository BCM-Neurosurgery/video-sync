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
)
from pyvideosync.utils import (
    load_timestamps,
    save_timestamps,
    sort_timestamps,
    get_column_min_max,
)
from pyvideosync.videojson import Videojson
from pyvideosync.nev import Nev
from pyvideosync.nsx import Nsx
import argparse


def log_associated_files(associated_files, logger):
    associated_json_df = pd.DataFrame.from_records(associated_files["JSON"])
    associated_nev_df = pd.DataFrame.from_records(associated_files["NEV"])
    associated_ns5_df = pd.DataFrame.from_records(associated_files["NS5"])

    logger.debug(f"Associated JSON:\n{associated_json_df}")
    logger.debug(f"Associated NEV:\n{associated_nev_df}")
    logger.debug(f"Associated NS5:\n{associated_ns5_df}")


def main(config_path):
    timestamp = get_current_ts()

    pathutils = PathUtils(config_path, timestamp)
    logger = configure_logging(pathutils.output_dir)

    if not pathutils.is_config_valid():
        logger.error("Config not valid, exiting to inital screen...")
        return

    datapool = DataPool(pathutils.nsp_dir, pathutils.cam_recording_dir)

    if not datapool.verify_integrity():
        logger.error(
            "File integrity check failed: Missing or duplicate NSP files detected. "
            "Please verify the directory structure and try again. Returning to the initial screen."
        )
        return

    # 1. Get NEV serial start and end
    nsp1_nev_path = datapool.get_nsp1_nev_path()
    nev = Nev(nsp1_nev_path)
    nev_chunk_serial_df = nev.get_chunk_serial_df()
    logger.info(f"NEV dataframe\n: {nev_chunk_serial_df}")
    nev_start_serial, nev_end_serial = get_column_min_max(
        nev_chunk_serial_df, "chunk_serial"
    )
    logger.info(f"Start serial: {nev_start_serial}, End serial: {nev_end_serial}")

    # 2. Find all JSON files and MP4 files
    camera_files = datapool.get_video_file_pool().list_groups()

    # 3. load camera serials from the config file
    camera_serials = pathutils.cam_serial
    logger.info(f"Camera serials loaded from config: {camera_serials}")

    # 4. Go through all JSON files and find the ones that
    # are within the NEV serial range
    # read timestamps if available
    timestamps_path = os.path.join(pathutils.output_dir, "timestamps.json")
    timestamps = load_timestamps(timestamps_path, logger)
    if timestamps:
        logger.info(f"Loaded timestamps: {timestamps}")
    else:
        logger.info("No timestamps found")
        timestamps = []
        for timestamp, camera_file_group in camera_files.items():
            # get the json file in the camera_file_group
            try:
                json_file = [
                    file for file in camera_file_group if file.endswith(".json")
                ][0]
            except IndexError:
                logger.error(f"No JSON file found in group {timestamp}")
                continue

            # read in the json file and see if the serial in json
            # is within the range of NEV serial
            json_path = os.path.join(pathutils.cam_recording_dir, json_file)
            videojson = Videojson(json_path)
            start_serial, end_serial = videojson.get_min_max_chunk_serial()

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
    ns5_path = datapool.get_nsp1_ns5_path()
    ns5 = Nsx(ns5_path)

    # 5. Go through the timestamps and process the videos
    for camera_serial in camera_serials:
        all_merged_list = []

        for i, timestamp in enumerate(sorted_timestamps):
            camera_file_group = camera_files[timestamp]

            # get a json file
            try:
                json_file = [
                    file for file in camera_file_group if file.endswith(".json")
                ][0]
            except IndexError:
                logger.error(f"No JSON file found in group {timestamp}")
                continue
            json_path = os.path.join(pathutils.cam_recording_dir, json_file)
            videojson = Videojson(json_path)
            camera_df = videojson.get_camera_df(camera_serial)
            camera_df["frame_ids_relative"] = (
                camera_df["frame_ids_reconstructed"]
                - camera_df["frame_ids_reconstructed"].iloc[0]
                + 1
            )

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
                    "frame_id",
                    "frame_ids_reconstructed",
                    "frame_ids_relative",
                ]
            ]

            # find the associated mp4 files
            try:
                mp4_file = [
                    file
                    for file in camera_file_group
                    if camera_serial in file and file.endswith(".mp4")
                ][0]
            except IndexError:
                logger.error(
                    f"No MP4 with serial {camera_serial} found in group {timestamp}"
                )

            all_merged["mp4_file"] = os.path.join(pathutils.cam_recording_dir, mp4_file)
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
        video_output_dir = os.path.join(pathutils.output_dir, camera_serial)
        os.makedirs(video_output_dir, exist_ok=True)
        video_output_path = os.path.join(video_output_dir, "output.mp4")

        subclip_paths = []
        for mp4_path in all_merged_df["mp4_file"].unique():
            df_sub = all_merged_df[all_merged_df["mp4_file"] == mp4_path]

            # Build a subclip from the relevant frames, attach audio
            subclip = make_synced_subclip_ffmpeg(
                df_sub,
                mp4_path,
                fps_audio=30000,  # 30kHz
                out_dir=os.path.join(pathutils.output_dir, camera_serial),
            )
            subclip_paths.append(subclip)

        # Now 'subclip_paths' has each final MP4 subclip
        # If we have only one, just rename or copy it
        if len(subclip_paths) == 1:
            final_path = subclip_paths[0]
        else:
            final_path = os.path.join(
                pathutils.output_dir, camera_serial, "ALL_subclips_merged.mp4"
            )
            ffmpeg_concat_mp4s(subclip_paths, final_path)

        logger.info(f"Saved {camera_serial} to {video_output_path}")


if __name__ == "__main__":
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
    main(args.config)

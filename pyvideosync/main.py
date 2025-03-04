"""
Main function to orchestrate the loading, processing, and merging of NEV, NS5, and camera data,
and aligning the audio with the video.
"""

import os
from pyvideosync.data_pool import DataPool
import yaml
import pandas as pd
import time
from pyvideosync.logging_config import (
    get_current_ts,
    configure_logging,
)
from pyvideosync.dataframes import (
    AllMergeConcatDF,
)
from pyvideosync.pathutils import PathUtils
from pyvideosync.process import (
    process_video,
    process_camera_json,
    process_nev_chunk_serial,
    process_ns5_channel_data,
    nev_inner_join_camera_json,
    ns5_leftjoin_joined,
    extract_and_save_frames,
    export_audio,
    export_video_variable_fps,
    save_frame_duration_to_file,
    combine_video_audio,
    align_audio_video,
    ffmpeg_concat_mp4s,
    make_synced_subclip_ffmpeg,
)
from pyvideosync.ui import (
    welcome_screen,
    select_config,
    clear_screen,
    prompt_user_for_video_file,
    mode_selection_screen,
    select_csv_file,
)
from pyvideosync.utils import (
    extract_basename,
    keep_valid_audio,
    analog2audio,
    load_timestamps,
    save_timestamps,
)
from pyvideosync.videojson import Videojson
from pyvideosync.video import Video
from pyvideosync.nev import Nev
from pyvideosync.nsx import Nsx
import argparse


def print_and_sleep(msg):
    print(msg)
    time.sleep(2)


def log_associated_files(associated_files, logger):
    associated_json_df = pd.DataFrame.from_records(associated_files["JSON"])
    associated_nev_df = pd.DataFrame.from_records(associated_files["NEV"])
    associated_ns5_df = pd.DataFrame.from_records(associated_files["NS5"])

    logger.debug(f"Associated JSON:\n{associated_json_df}")
    logger.debug(f"Associated NEV:\n{associated_nev_df}")
    logger.debug(f"Associated NS5:\n{associated_ns5_df}")


def main(config_path):
    while True:
        choice = welcome_screen()
        if choice == "1":
            while True:
                timestamp = get_current_ts()

                pathutils = PathUtils(config_path, timestamp)
                if not pathutils.is_config_valid():
                    print_and_sleep("Config not valid, exiting to inital screen...")
                    break

                datapool = DataPool(pathutils.nsp_dir, pathutils.cam_recording_dir)

                init_file_integrity_check = datapool.verify_integrity()
                if not init_file_integrity_check:
                    print_and_sleep(
                        "Initial file integrity check failed, exiting to initial screen."
                    )
                    break

                # TODO: add a selection
                # 1. prompt a window to select a CSV file
                # 2. sync an existing video
                mode = mode_selection_screen()
                if mode == "0":
                    break

                elif mode == "1":
                    while True:
                        csv_path = select_csv_file()

                        speech_segment_df = pd.read_csv(csv_path)

                        for ns5_rel_path in speech_segment_df["filename"].unique():

                            # for each unique NS5 in speech_segment_df
                            # create a output dir
                            pathutils.set_ns5_paths(ns5_rel_path)
                            os.makedirs(pathutils.video_output_dir_ns5, exist_ok=True)

                            # configure logging
                            logger = configure_logging(pathutils.video_output_dir_ns5)

                            # load this NS5
                            ns5, ns5_channel_df = process_ns5_channel_data(
                                pathutils, logger
                            )

                            # Find associated files for this NS5
                            associated_files = datapool.find_ns5_associated_files(
                                ns5_rel_path, pathutils.cam_serial
                            )

                            logger.info(f"Associated files: {associated_files}")

                            # get the part of df with that NS5 and save to CSV
                            logger.info("Getting specific speech segment df...")
                            speech_segment_ns5_df = speech_segment_df[
                                speech_segment_df["filename"] == ns5_rel_path
                            ].copy()
                            csv_save_path = os.path.join(
                                pathutils.video_output_dir_ns5, "segment.csv"
                            )
                            speech_segment_ns5_df.to_csv(csv_save_path)

                            # process NEV because there's only 1 associated NEV
                            pathutils.set_nev_paths(
                                associated_files["NEV"]["nev_rel_path"]
                            )
                            nev_chunk_serial_df = process_nev_chunk_serial(
                                pathutils, logger
                            )

                            # iterate through associated files and get a concat merged df
                            for i, (video_dict, json_dict) in enumerate(
                                zip(associated_files["VIDEO"], associated_files["JSON"])
                            ):
                                logger.info(f"Entering {i+1}th iteration...")
                                pathutils.set_chunk_output_dir(i)

                                logger.info(
                                    f"Processig {video_dict['mp4_rel_path']} and {json_dict['json_rel_path']}...",
                                )

                                pathutils.video_to_process = video_dict["mp4_rel_path"]
                                camera_df = process_camera_json(pathutils, logger)

                                chunk_serial_joined = nev_inner_join_camera_json(
                                    nev_chunk_serial_df, camera_df, logger
                                )
                                all_merged = ns5_leftjoin_joined(
                                    chunk_serial_joined, ns5, ns5_channel_df, logger
                                )

                                abs_start_frame, abs_end_frame = (
                                    datapool.get_mp4_abs_frame_range(
                                        video_to_process, pathutils.cam_serial
                                    )
                                )

                                video = process_video(
                                    abs_start_frame, abs_end_frame, pathutils, logger
                                )

                                frame_list = extract_and_save_frames(
                                    video, pathutils, logger
                                )

                                # for each utc_start and utc_end in speech_segment_ns5_df
                                # extract the frames and save video
                                for index, row in speech_segment_ns5_df.iterrows():
                                    utc_start = row["utc_start"]
                                    utc_end = row["utc_end"]

                                    all_merged_concat_df = all_merged[
                                        (all_merged["UTCTimeStamp_x"] >= utc_start)
                                        & (all_merged["UTCTimeStamp_x"] <= utc_end)
                                    ].copy()

                                    save_frame_duration_to_file(
                                        all_merged_concat_df,
                                        frame_list,
                                        abs_start_frame,
                                        pathutils,
                                        logger,
                                    )

                                    export_video_variable_fps(pathutils, logger)
                                    export_audio(
                                        all_merged_concat_df, pathutils, logger
                                    )
                                    combine_video_audio(pathutils, logger)

                elif mode == "2":
                    while True:
                        clear_screen()
                        cam_mp4_files = datapool.get_mp4_filelist(pathutils.cam_serial)
                        video_to_process = prompt_user_for_video_file(cam_mp4_files)
                        if not video_to_process:
                            break
                        pathutils.video_to_process = video_to_process
                        pathutils.video_output_dir = os.path.join(
                            pathutils.output_dir,
                            extract_basename(video_to_process),
                        )
                        os.makedirs(pathutils.video_output_dir, exist_ok=True)
                        pathutils.make_frames_output_dir()

                        # configure logging
                        logger = configure_logging(pathutils.video_output_dir)
                        logger.debug(f"Configuration:\n{yaml.dump(pathutils.config)}")

                        # find associated nev, ns5, json file to that video
                        logger.info(f"You selected {video_to_process}")

                        abs_start_frame, abs_end_frame = (
                            datapool.get_mp4_abs_frame_range(
                                video_to_process, pathutils.cam_serial
                            )
                        )

                        video = process_video(
                            abs_start_frame, abs_end_frame, pathutils, logger
                        )

                        camera_df = process_camera_json(pathutils, logger)

                        logger.info("Scanning folders to find associated files...")
                        associated_files = datapool.find_mp4_associated_files(
                            video_to_process
                        )

                        all_merged_dfs = []
                        for i, (nev_dict, ns5_dict) in enumerate(
                            zip(associated_files["NEV"], associated_files["NS5"])
                        ):
                            logger.info(f"Entering {i+1}th iteration...")
                            logger.info(
                                f"Processig {nev_dict['nev_rel_path']} and {ns5_dict['ns5_rel_path']}...",
                            )
                            pathutils.set_chunk_output_dir(i)
                            pathutils.set_nev_paths(nev_dict["nev_rel_path"])
                            pathutils.set_ns5_paths(ns5_dict["ns5_rel_path"])

                            nev_chunk_serial_df = process_nev_chunk_serial(
                                pathutils, logger
                            )
                            ns5, ns5_channel_df = process_ns5_channel_data(
                                pathutils, logger
                            )
                            chunk_serial_joined = nev_inner_join_camera_json(
                                nev_chunk_serial_df, camera_df, logger
                            )
                            all_merged = ns5_leftjoin_joined(
                                chunk_serial_joined, ns5, ns5_channel_df, logger
                            )

                            all_merged_dfs.append(all_merged)

                        # concat all_merged_dfs
                        all_merged_concat_df = pd.concat(
                            all_merged_dfs, ignore_index=True
                        )
                        AllMergeConcatDF(
                            all_merged_concat_df, logger
                        ).log_dataframe_info()

                        running_total_frame_id = (
                            all_merged_concat_df["frame_id"]
                            .dropna()
                            .astype(int)
                            .to_numpy()
                        )

                        logger.info("Processing valid audio...")
                        valid_audio = keep_valid_audio(all_merged_concat_df)
                        analog2audio(
                            valid_audio,
                            ns5.get_sample_resolution(),
                            pathutils.audio_out_path,
                        )

                        logger.info(f"Saved sliced audio to {pathutils.audio_out_path}")

                        logger.info("Slicing video...")
                        output_fps = len(running_total_frame_id) / (
                            len(valid_audio) / ns5.get_sample_resolution()
                        )
                        logger.debug(
                            f"Input video frame count: {video.get_frame_count()}"
                        )
                        logger.debug(f"Input video fps: {video.get_fps()}")
                        logger.debug(f"Output video fps: {output_fps}")
                        offset_frame_id = running_total_frame_id - (abs_start_frame - 1)
                        video.slice_video(
                            pathutils.video_out_path, offset_frame_id, output_fps
                        )
                        logger.info(f"Saved sliced video to {pathutils.video_out_path}")

                        logger.info("Aligning audio and video...")
                        align_audio_video(
                            pathutils.video_out_path,
                            pathutils.audio_out_path,
                            pathutils.final_video_out_path,
                        )

                        time.sleep(30)

                elif mode == "3":
                    while True:
                        clear_screen()

                        # configure logging
                        logger = configure_logging(pathutils.output_dir)

                        # 1. Get NEV serial start and end
                        nev_files = datapool.get_nev_pool().list_nsp1_nev()
                        logger.info(f"NEV files found: {nev_files}")
                        nev_start_serial, nev_end_serial = (
                            datapool.get_nev_serial_range()
                        )
                        logger.info(
                            "Start serial: %s, End serial: %s",
                            nev_start_serial,
                            nev_end_serial,
                        )

                        # 2. Find all JSON files and MP4 files
                        camera_files = datapool.get_video_file_pool().list_groups()

                        # 3. load camera serials from the config file
                        camera_serials = pathutils.cam_serial
                        logger.info(f"Camera serials found: {camera_serials}")

                        # 4. Go through all JSON files and find the ones that
                        # are within the NEV serial range
                        # read timestamps if available
                        timestamps_path = os.path.join(
                            pathutils.output_dir, "timestamps.json"
                        )
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
                                        file
                                        for file in camera_file_group
                                        if file.endswith(".json")
                                    ][0]
                                except IndexError:
                                    logger.error(
                                        f"No JSON file found in group {timestamp}"
                                    )
                                    continue

                                # read in the json file and see if the serial in json
                                # is within the range of NEV serial
                                json_path = os.path.join(
                                    pathutils.cam_recording_dir, json_file
                                )
                                videojson = Videojson(json_path)
                                start_serial, end_serial = (
                                    videojson.get_min_max_chunk_serial()
                                )

                                if end_serial < nev_start_serial:
                                    logger.info(f"No overlap found: {timestamp}")
                                    continue

                                elif start_serial <= nev_end_serial:
                                    logger.info(
                                        f"Overlap found, timestamp: {timestamp}"
                                    )
                                    timestamps.append(timestamp)

                                else:
                                    logger.info(f"Break: {timestamp}")
                                    break
                            logger.info(f"timestamps: {timestamps}")
                            save_timestamps(timestamps_path, timestamps)

                        # process NEV chunk serial df
                        nev_path = datapool.get_nev_pool().list_nsp1_nev()[0]
                        nev_path = os.path.join(pathutils.nsp_dir, nev_path)
                        nev = Nev(nev_path)
                        nev_chunk_serial_df = nev.get_chunk_serial_df()
                        logger.info(f"NEV chunk serials found\n: {nev_chunk_serial_df}")

                        # process NS5 channel data
                        ns5_path = datapool.get_nsx_pool().get_stitched_ns5_file()
                        ns5_path = os.path.join(pathutils.nsp_dir, ns5_path)
                        ns5 = Nsx(ns5_path)

                        # 5. Go through the timestamps and process the videos
                        for camera_serial in camera_serials:
                            all_merged_list = []

                            for i, timestamp in enumerate(timestamps):
                                camera_file_group = camera_files[timestamp]

                                # get a json file
                                try:
                                    json_file = [
                                        file
                                        for file in camera_file_group
                                        if file.endswith(".json")
                                    ][0]
                                except IndexError:
                                    logger.error(
                                        f"No JSON file found in group {timestamp}"
                                    )
                                    continue
                                json_path = os.path.join(
                                    pathutils.cam_recording_dir, json_file
                                )
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
                                        if camera_serial in file
                                        and file.endswith(".mp4")
                                    ][0]
                                except IndexError:
                                    logger.error(
                                        f"No MP4 with serial {camera_serial} found in group {timestamp}"
                                    )

                                all_merged["mp4_file"] = os.path.join(
                                    pathutils.cam_recording_dir, mp4_file
                                )
                                all_merged_list.append(all_merged)

                            if not all_merged_list:
                                logger.warning(
                                    f"No valid merged data for {camera_serial}"
                                )
                                continue

                            all_merged_df = pd.concat(
                                all_merged_list, ignore_index=True
                            )
                            logger.info(
                                f"Final merged DataFrame for {camera_serial} head:\n{all_merged_df.head()}"
                            )
                            logger.info(
                                f"Final merged DataFrame for {camera_serial} tail:\n{all_merged_df.tail()}"
                            )

                            # process the videos
                            video_output_dir = os.path.join(
                                pathutils.output_dir, camera_serial
                            )
                            os.makedirs(video_output_dir, exist_ok=True)
                            video_output_path = os.path.join(
                                video_output_dir, "output.mp4"
                            )

                            # If you want the final order strictly to follow how mp4_file appears in df:
                            mp4_files_order = all_merged_df["mp4_file"].unique()

                            subclip_paths = []
                            for mp4_path in mp4_files_order:
                                df_sub = all_merged_df[
                                    all_merged_df["mp4_file"] == mp4_path
                                ]

                                # Build a subclip from the relevant frames, attach audio
                                subclip = make_synced_subclip_ffmpeg(
                                    df_sub,
                                    mp4_path,
                                    fps_audio=30000,  # 30kHz
                                    out_dir=os.path.join(
                                        pathutils.output_dir, camera_serial
                                    ),
                                )
                                subclip_paths.append(subclip)

                            # Now 'subclip_paths' has each final MP4 subclip
                            # If we have only one, just rename or copy it
                            if len(subclip_paths) == 1:
                                final_path = subclip_paths[0]
                            else:
                                final_path = os.path.join(
                                    pathutils.output_dir, "ALL_subclips_merged.mp4"
                                )
                                ffmpeg_concat_mp4s(subclip_paths, final_path)

                            logger.info(f"Saved {camera_serial} to {video_output_path}")
                        time.sleep(20)

        elif choice == "2":
            print("Exiting program. Goodbye!")
            break
        else:
            print("Invalid choice. Please try again.")


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

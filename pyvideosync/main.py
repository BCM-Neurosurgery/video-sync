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
)
from pyvideosync.ui import (
    welcome_screen,
    select_config,
    clear_screen,
    prompt_user_for_video_file,
)


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


def main():
    while True:
        choice = welcome_screen()
        if choice == "1":
            while True:
                timestamp = get_current_ts()

                config_path = select_config()
                if not config_path:
                    print_and_sleep(
                        "You have not selected a config file, exiting to initial screen..."
                    )
                    break

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

                while True:
                    clear_screen()
                    cam_mp4_files = datapool.get_mp4_filelist(pathutils.cam_serial)
                    video_to_process = prompt_user_for_video_file(cam_mp4_files)
                    if not video_to_process:
                        print_and_sleep("Returning to previous screen...")
                        break
                    pathutils.video_to_process = video_to_process
                    os.makedirs(pathutils.video_output_dir, exist_ok=True)
                    pathutils.make_frames_output_dir()

                    # configure logging
                    logger = configure_logging(pathutils.video_output_dir)
                    logger.debug(f"Configuration:\n{yaml.dump(pathutils.config)}")

                    # find associated nev, ns5, json file to that video
                    logger.info(f"You selected {video_to_process}")

                    abs_start_frame, abs_end_frame = datapool.get_mp4_abs_frame_range(
                        video_to_process, pathutils.cam_serial
                    )

                    video = process_video(
                        abs_start_frame, abs_end_frame, pathutils, logger
                    )

                    camera_df = process_camera_json(pathutils, logger)

                    logger.info("Scanning folders to find associated files...")
                    associated_files = datapool.find_associated_files(video_to_process)

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
                    all_merged_concat_df = pd.concat(all_merged_dfs, ignore_index=True)
                    AllMergeConcatDF(all_merged_concat_df, logger).log_dataframe_info()

                    frame_list = extract_and_save_frames(video, pathutils, logger)

                    save_frame_duration_to_file(
                        all_merged_concat_df,
                        frame_list,
                        abs_start_frame,
                        pathutils,
                        logger,
                    )

                    export_video_variable_fps(pathutils, logger)
                    export_audio(all_merged_concat_df, pathutils, logger)
                    combine_video_audio(pathutils, logger)

                    time.sleep(30)

        elif choice == "2":
            print("Exiting program. Goodbye!")
            break
        else:
            print("Invalid choice. Please try again.")


if __name__ == "__main__":
    main()

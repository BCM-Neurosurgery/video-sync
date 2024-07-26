"""
Main function to orchestrate the loading, processing, and merging of NEV, NS5, and camera data,
and aligning the audio with the video.
"""

import os
import logging
import pytz
from datetime import datetime
import numpy as np
import matplotlib.pyplot as plt
from pyvideosync.nev import Nev
from pyvideosync.nsx import Nsx
from pyvideosync.videojson import Videojson
from pyvideosync.video import Video
from pyvideosync.data_pool import DataPool
from pyvideosync import utils
from moviepy.editor import VideoFileClip, AudioFileClip
import yaml
import sys
import pandas as pd
from pathlib import Path
import tkinter as tk
from tkinter import filedialog
import time
from scipy.io.wavfile import write
from pyvideosync.logging_config import (
    get_current_ts,
    configure_logging,
)
from pyvideosync.dataframes import (
    NevChunkSerialDF,
    CameraJSONDF,
    NS5ChannelDF,
    ChunkSerialJoinedDF,
    AllMergeDF,
    AllMergeConcatDF,
)
from pyvideosync.pathutils import PathUtils


def plot_histogram(data, column, save_path, color="skyblue", alpha=0.7):
    """
    Plot a histogram of the differences in the specified column of the DataFrame.

    Args:
        data (pd.DataFrame): DataFrame containing the data to plot.
        column (str): Column name to calculate differences and plot histogram.
        save_path (str): Path to save plot.
        color (str): Color of the histogram bars.
        alpha (float): Transparency level of the histogram bars.
    """
    df = data.copy()
    df[f"{column}_diff"] = df[column].diff()
    ax = df[f"{column}_diff"].plot.hist(color=color, alpha=alpha, edgecolor="black")
    for rect in ax.patches:
        height = rect.get_height()
        plt.text(
            rect.get_x() + rect.get_width() / 2,
            height,
            f"{int(height)}",
            ha="center",
            va="bottom",
        )
    plt.title(column)
    plt.savefig(save_path)
    plt.close()


def prompt_user_for_video_file(cam_mp4_files):
    """Prompt the user to select a video file from the list."""
    if not cam_mp4_files:
        print("No video files found.")
        return None

    print("Available video files:")
    for idx, file in enumerate(cam_mp4_files):
        print(f"{idx + 1}: {file}")

    while True:
        try:
            choice = int(
                input(
                    "Enter the number of the file you want to process, or type 0 to go back to previous menu: "
                )
            )
            if choice == 0:
                return choice
            elif 1 <= choice <= len(cam_mp4_files):
                return cam_mp4_files[choice - 1]
            else:
                print(f"Please enter a number between 0 and {len(cam_mp4_files)}.")
        except ValueError:
            print("Invalid input. Please enter a number.")


def select_config_file():
    root = tk.Tk()
    root.withdraw()
    config_file_path = filedialog.askopenfilename(
        title="Select Configuration File",
        filetypes=(("YAML files", "*.yaml"), ("All files", "*.*")),
    )
    root.destroy()
    return config_file_path


def clear_screen():
    if os.name == "nt":
        os.system("cls")
    else:
        os.system("clear")


def remove_file(file_path):
    try:
        os.remove(file_path)
    except Exception as e:
        print(f"Error removing file: {e}")


def welcome_screen():
    clear_screen()
    print("\nWelcome to Video Sync Program v1.0")
    print("Please select an option:")
    print("1. Load a config file")
    print("2. Exit")
    choice = input("Enter your choice: ")
    return choice


def select_and_validate_config():
    clear_screen()
    print("Please select YAML config file")
    config_path = select_config_file()
    return config_path


def print_and_sleep(msg):
    print(msg)
    time.sleep(2)


def main():
    while True:
        choice = welcome_screen()
        if choice == "1":
            while True:
                timestamp = get_current_ts()

                config_path = select_and_validate_config()
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
                    logger.info("Scanning folders to find associated files...")
                    video = Video(pathutils.video_path)
                    abs_start_frame, abs_end_frame = datapool.get_mp4_abs_frame_range(
                        video_to_process, pathutils.cam_serial
                    )
                    selected_video_df = video.get_video_stats_df(
                        abs_start_frame, abs_end_frame
                    )
                    associated_files = datapool.find_associated_files(video_to_process)
                    associated_json_df = pd.DataFrame.from_records(
                        associated_files["JSON"]
                    )
                    associated_nev_df = pd.DataFrame.from_records(
                        associated_files["NEV"]
                    )
                    associated_ns5_df = pd.DataFrame.from_records(
                        associated_files["NS5"]
                    )

                    logger.debug(f"Selected VIDEO:\n{selected_video_df}")
                    logger.debug(f"Associated JSON:\n{associated_json_df}")
                    logger.debug(f"Associated NEV:\n{associated_nev_df}")
                    logger.debug(f"Associated NS5:\n{associated_ns5_df}")

                    logger.info("Loading camera JSON file...")
                    videojson = Videojson(pathutils.json_path)
                    camera_df = videojson.get_camera_df(pathutils.cam_serial)
                    CameraJSONDF(camera_df, logger).log_dataframe_info()

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

                        logger.info("Getting chunk serial data from NEV...")
                        nev = Nev(pathutils.nev_abs_path)
                        nev_chunk_serial_df = nev.get_chunk_serial_df()
                        NevChunkSerialDF(
                            nev_chunk_serial_df, logger
                        ).log_dataframe_info()
                        nev.plot_cam_exposure_all(pathutils.cam_exposure_path, 0, 200)

                        logger.info(f"Getting {pathutils.ns5_channel} in NS5...")
                        ns5 = Nsx(pathutils.ns5_abs_path)
                        ns5_channel_df = ns5.get_channel_df(pathutils.ns5_channel)
                        logger.debug(f"ns5_channel_df:\n{ns5_channel_df}")
                        ns5.plot_channel_array(
                            pathutils.ns5_channel,
                            pathutils.channel_array_path,
                        )

                        logger.info("Merging NEV and Camera JSON...")
                        chunk_serial_joined = nev_chunk_serial_df.merge(
                            camera_df,
                            left_on="chunk_serial",
                            right_on="chunk_serial_data",
                            how="inner",
                        )
                        ChunkSerialJoinedDF(
                            chunk_serial_joined, logger
                        ).log_dataframe_info()

                        logger.info("Merging JSON, NEV with NS5...")
                        ns5_slice = ns5.get_channel_df_between_ts(
                            ns5_channel_df,
                            chunk_serial_joined.iloc[0]["TimeStamps"],
                            chunk_serial_joined.iloc[-1]["TimeStamps"],
                        )
                        all_merged = ns5_slice.merge(
                            chunk_serial_joined,
                            left_on="TimeStamp",
                            right_on="TimeStamps",
                            how="left",
                        )
                        all_merged_dfs.append(all_merged)

                    # concat all_merged_dfs
                    all_merged_concat_df = pd.concat(all_merged_dfs, ignore_index=True)
                    AllMergeConcatDF(all_merged_concat_df, logger).log_dataframe_info()

                    logger.info("Saving frames from video...")
                    frame_list = video.extract_frames(pathutils.frames_output_dir)

                    logger.info("Getting frame durations in fps...")
                    all_merged_concat_dropped = all_merged_concat_df.dropna()
                    timestamps = all_merged_concat_dropped["TimeStamp"].tolist()
                    frame_ids = all_merged_concat_dropped[
                        "frame_ids_reconstructed"
                    ].tolist()
                    # TODO: this approach will discard the last frame
                    # calculate the time in s for each frame
                    # we know 30000 timestamps = 1s
                    # so each timestamp is 1 / 30000s
                    frame_duration = [
                        (timestamps[i] - timestamps[i - 1]) / 30000
                        for i in range(1, len(timestamps))
                    ]

                    logger.info("Creating FFmpeg config file...")
                    with open(pathutils.frame_list_path, "w") as f:
                        # don't need the last frame
                        for i in range(len(frame_ids) - 1):
                            frame_index = int(frame_ids[i] - abs_start_frame)
                            f.write(f"file '{frame_list[frame_index]}'\n")
                            f.write(f"duration {frame_duration[i]}\n")
                        # Write the last frame again to signal the end
                        last_frame_index = int(frame_ids[i] - abs_start_frame)
                        f.write(f"file '{frame_list[last_frame_index]}'\n")

                    logger.info("Creating video with variable fps...")
                    os.system(
                        f"ffmpeg -f concat -safe 0 -i {pathutils.frame_list_path} -vsync vfr -pix_fmt yuv420p {pathutils.video_out_path}"
                    )

                    # Step 5: Combine Audio and Video
                    audio_sample_rate = 30000  # 30kHz
                    audio_data = all_merged_concat_df["Amplitude"].to_numpy()

                    logger.info("Saving audio...")
                    write(pathutils.audio_out_path, audio_sample_rate, audio_data)

                    logger.info("Combining audio and video...")

                    os.system(
                        f"ffmpeg -i {pathutils.video_out_path} -i {pathutils.audio_out_path} -c:v copy -c:a aac -strict experimental {pathutils.final_video_out_path}"
                    )
                    logger.info("Video Sync Complete!!!")
                    time.sleep(30)

        elif choice == "2":
            print("Exiting program. Goodbye!")
            break
        else:
            print("Invalid choice. Please try again.")


if __name__ == "__main__":
    main()

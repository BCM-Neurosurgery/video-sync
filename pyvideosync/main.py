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

# Configure logging
central = pytz.timezone("US/Central")


def get_current_ts() -> str:
    return datetime.now(central).strftime("%Y%m%d_%H%M%S")


def configure_logging(log_dir, current_time):
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    log_file_path = os.path.join(log_dir, f"log_{current_time}.log")

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)

    # Create handlers
    c_handler = logging.StreamHandler()
    f_handler = logging.FileHandler(log_file_path)

    # Set level for handlers
    c_handler.setLevel(logging.INFO)
    f_handler.setLevel(logging.DEBUG)

    # Create formatters and add it to handlers
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    c_handler.setFormatter(formatter)
    f_handler.setFormatter(formatter)

    # Add handlers to the logger
    logger.addHandler(c_handler)
    logger.addHandler(f_handler)

    return logger


def extract_basename(input_path: str) -> str:
    """Extract name from input path

    Args:
        input_path (str): e.g. "/video/video_sync_test_0530_20240530_115639.23512906.mp4"

    Returns:
        str: e.g. video_sync_test_0530_20240530_115639_23512906
    """
    basename = os.path.basename(input_path)
    splitted = os.path.splitext(basename)[0]
    return splitted.replace(".", "_")


def validate_config(config):
    required_fields = [
        "cam_serial",
        "nsp_dir",
        "cam_recording_dir",
        "output_dir",
        "channel_name",
    ]
    missing_fields = [field for field in required_fields if field not in config]
    return missing_fields


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


def align_audio_video(video_path, audio_path, output_path):
    """
    Align the audio with the video and save the result to a new file.

    Args:
        video_path (str): Path to the input video file.
        audio_path (str): Path to the input audio file.
        output_path (str): Path to save the output video file with aligned audio.
    """
    video_clip = VideoFileClip(video_path)
    audio_clip = AudioFileClip(audio_path)
    video_clip = video_clip.set_audio(audio_clip)
    video_clip.write_videofile(
        output_path, codec="libx264", audio_codec="aac", logger="bar"
    )


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


def load_config(config_path):
    """
    Load a YAML configuration file.

    Args:
        config_path (str): Path to the YAML configuration file.

    Returns:
        dict: Loaded configuration as a dictionary.
    """
    if not os.path.exists(config_path):
        print(f"Configuration file '{config_path}' does not exist.")
        sys.exit(1)

    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
        return config
    except yaml.YAMLError as e:
        print(f"Error loading configuration file '{config_path}': {e}")
        sys.exit(1)


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


def main():
    while True:
        clear_screen()
        print("\nWelcome to Video Sync Program v1.0")
        print("Please select an option:")
        print("1. Load a config file")
        print("2. Exit")

        choice = input("Enter your choice: ")

        if choice == "1":
            while True:
                clear_screen()
                print("Please select YAML config file")
                config_path = select_config_file()
                if not config_path:
                    print(
                        "You have not selected a config file, exiting to initial screen..."
                    )
                    time.sleep(2)
                    break

                config = load_config(config_path)

                missing_fields = validate_config(config)
                if missing_fields:
                    print("Config not valid, exiting to inital screen...")
                    time.sleep(2)
                    break

                timestamp = get_current_ts()
                cam_serial = config["cam_serial"]
                nsp_dir = config["nsp_dir"]
                cam_recording_dir = config["cam_recording_dir"]
                output_dir = config["output_dir"]
                ns5_channel = config["channel_name"]

                datapool = DataPool(nsp_dir, cam_recording_dir)

                # initial data integrity check
                init_file_integrity_check = datapool.verify_integrity()
                if not init_file_integrity_check:
                    print(
                        "Initial file integrity check failed, exiting to initial screen."
                    )
                    time.sleep(2)
                    break
                else:
                    print("Initial file integrity check passed!")
                    time.sleep(2)

                while True:
                    clear_screen()
                    cam_mp4_files = datapool.get_mp4_filelist(cam_serial)
                    video_to_process = prompt_user_for_video_file(cam_mp4_files)
                    if not video_to_process:
                        break
                    video_output_dir = os.path.join(
                        output_dir, extract_basename(video_to_process)
                    )
                    os.makedirs(video_output_dir, exist_ok=True)

                    # configure logging
                    logger = configure_logging(video_output_dir, timestamp)
                    logger.debug(f"Configuration:\n{yaml.dump(config)}")

                    # find associated nev, ns5, json file to that video
                    logger.info(f"You selected {video_to_process}")
                    logger.info("Scanning folders to find associated files...")
                    video_path = os.path.join(cam_recording_dir, video_to_process)
                    video = Video(video_path)
                    abs_start_frame, abs_end_frame = datapool.get_mp4_abs_frame_range(
                        video_to_process, cam_serial
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
                    json_path = datapool.get_abs_json_path(video_to_process)
                    videojson = Videojson(json_path)
                    camera_df = videojson.get_camera_df(cam_serial)
                    logger.debug(f"camera json df:\n{camera_df}")
                    logger.info(
                        f"num of discontinuities in frame ids in camera json: {utils.count_discontinuities(camera_df, 'frame_ids_reconstructed')}"
                    )
                    logger.info(
                        f"num of unique frame ids in camera json: {len(camera_df['frame_id'].unique())}"
                    )
                    plot_histogram(
                        camera_df,
                        "frame_id",
                        os.path.join(
                            video_output_dir, "camera_json_frame_id_diff_hist.png"
                        ),
                    )

                    all_merged_dfs = []
                    for i, (nev_dict, ns5_dict) in enumerate(
                        zip(associated_files["NEV"], associated_files["NS5"])
                    ):
                        logger.info(f"Entering {i+1}th iteration...")
                        logger.info(
                            f"Processig {nev_dict['nev_rel_path']} and {ns5_dict['ns5_rel_path']}...",
                        )
                        chunk_output_dir = os.path.join(video_output_dir, str(i))
                        os.makedirs(chunk_output_dir, exist_ok=True)

                        logger.info("Getting chunk serial data from NEV...")
                        nev_path = datapool.get_abs_nev_path(nev_dict["nev_rel_path"])
                        nev = Nev(nev_path)
                        nev_chunk_serial_df = nev.get_chunk_serial_df()
                        logger.debug(f"nev_chunk_serial_df:\n{nev_chunk_serial_df}")
                        nev.plot_cam_exposure_all(
                            os.path.join(chunk_output_dir, "cam_exposure_all.png"),
                            0,
                            200,
                        )

                        logger.info(f"Getting {ns5_channel} in NS5...")
                        ns5_path = datapool.get_abs_ns5_path(ns5_dict["ns5_rel_path"])
                        ns5 = Nsx(ns5_path)
                        ns5_channel_df = ns5.get_channel_df(ns5_channel)
                        logger.debug(f"ns5_channel_df:\n{ns5_channel_df}")
                        ns5.plot_channel_array(
                            config["channel_name"],
                            os.path.join(chunk_output_dir, f"ns5_{ns5_channel}.png"),
                        )

                        logger.info("Merging NEV and Camera JSON...")
                        chunk_serial_joined = nev_chunk_serial_df.merge(
                            camera_df,
                            left_on="chunk_serial",
                            right_on="chunk_serial_data",
                            how="inner",
                        )
                        logger.debug(f"chunk_serial_df_joined:\n{chunk_serial_joined}")

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
                        logger.info(
                            f"There are {utils.count_discontinuities(all_merged, 'frame_ids_reconstructed')} discontinuities in frame ids in all_merged"
                        )
                        logger.info(
                            f"There are {utils.count_unique_values(all_merged, 'frame_ids_reconstructed')} unique frame ids in all_merged"
                        )
                        all_merged_dfs.append(all_merged)

                    # concat all_merged_dfs
                    all_merged_concat_df = pd.concat(all_merged_dfs, ignore_index=True)
                    running_total_frame_id = (
                        all_merged_concat_df["frame_id"].dropna().astype(int).to_numpy()
                    )
                    logger.debug(
                        f"Length of total frame id:{len(running_total_frame_id)}"
                    )
                    logger.debug(
                        f"Length of all unique: {len(np.unique(running_total_frame_id))}"
                    )
                    logger.debug(f"All merged concat df:\n{all_merged_concat_df}")

                    # make save paths
                    output_video_path = os.path.join(
                        video_output_dir,
                        f"video_{cam_serial}_sliced_{timestamp}.mp4",
                    )
                    audio_output_path = os.path.join(
                        video_output_dir,
                        f"audio_{cam_serial}_sliced_{timestamp}.wav",
                    )
                    final_output_path = os.path.join(
                        video_output_dir,
                        f"final_{cam_serial}_aligned_{timestamp}.mp4",
                    )

                    logger.info("Processing valid audio...")
                    valid_audio = utils.keep_valid_audio(all_merged_concat_df)
                    utils.analog2audio(
                        valid_audio, ns5.get_sample_resolution(), audio_output_path
                    )
                    logger.info(f"Saved sliced audio to {audio_output_path}")

                    logger.info("Slicing video...")
                    output_fps = len(running_total_frame_id) / (
                        len(valid_audio) / ns5.get_sample_resolution()
                    )
                    logger.debug(f"Input video frame count: {video.get_frame_count()}")
                    logger.debug(f"Input video fps: {video.get_fps()}")
                    logger.debug(f"Output video fps: {output_fps}")
                    offset_frame_id = running_total_frame_id - (abs_start_frame - 1)
                    video.slice_video(output_video_path, offset_frame_id, output_fps)
                    logger.info(f"Saved sliced video to {output_video_path}")

                    logger.info("Aligning audio and video...")
                    align_audio_video(
                        output_video_path, audio_output_path, final_output_path
                    )
                    logger.info(f"Final video saved to {final_output_path}")

                    remove_file(output_video_path)
                    remove_file(audio_output_path)
                    logger.info(f"Removed intermediate media files")

                    logger.info("Video Sync complete!! Returning to video selection...")
                    time.sleep(3)

        elif choice == "2":
            print("Exiting program. Goodbye!")
            break
        else:
            print("Invalid choice. Please try again.")


if __name__ == "__main__":
    main()

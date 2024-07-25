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
from pyvideosync.dataframelogger import DataFrameLogger
from moviepy.editor import VideoFileClip, AudioFileClip
import yaml
import sys
import pandas as pd
from pathlib import Path
import tkinter as tk
from tkinter import filedialog
import time
from scipy.io.wavfile import write

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
                    frames_output_dir = os.path.join(video_output_dir, "frames")
                    os.makedirs(video_output_dir, exist_ok=True)
                    os.makedirs(frames_output_dir, exist_ok=True)

                    # configure logging
                    logger = configure_logging(video_output_dir, timestamp)
                    logger.debug(f"Configuration:\n{yaml.dump(config)}")

                    # configure dataframe logger
                    df_logger = DataFrameLogger()

                    # find associated nev, ns5, json file to that video
                    logger.info(f"You selected {video_to_process}")
                    logger.info("Scanning folders to find associated files...")
                    video_path = os.path.join(cam_recording_dir, video_to_process)
                    video = Video(video_path)
                    abs_start_frame, abs_end_frame = datapool.get_mp4_abs_frame_range(
                        video_to_process, cam_serial
                    )
                    print(f"abs_start_frame: {abs_start_frame}")
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
                        f"camera json df stats:\n{df_logger.log_dataframe_info('camera_json_df', camera_df)}"
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
                        logger.info(
                            f"nev_chunk_serial_df stats:\n{df_logger.log_dataframe_info('nev_chunk_serial_df', nev_chunk_serial_df)}"
                        )
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
                        logger.info(
                            f"chunk_serial_df_joined stats:\n{df_logger.log_dataframe_info('chunk_serial_df_joined', chunk_serial_joined)}"
                        )

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
                            f"all_merged stats:\n{df_logger.log_dataframe_info('all_merged_df', all_merged)}"
                        )
                        all_merged_dfs.append(all_merged)

                    # concat all_merged_dfs
                    all_merged_concat_df = pd.concat(all_merged_dfs, ignore_index=True)
                    running_total_frame_id = (
                        all_merged_concat_df["frame_id"].dropna().astype(int).to_numpy()
                    )
                    logger.info(
                        f"all_merged_concat_df stats:\n{df_logger.log_dataframe_info('all_merged_concat_df', all_merged_concat_df)}"
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

                    logger.info("Saving frames from video...")
                    frame_list = video.extract_frames(frames_output_dir)

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
                    with open(
                        os.path.join(video_output_dir, "frame_list.txt"), "w"
                    ) as f:
                        # don't need the last frame
                        for i in range(len(frame_ids) - 1):
                            frame_index = int(frame_ids[i] - abs_start_frame)
                            # print(f"frame_index: {frame_index}")
                            f.write(f"file '{frame_list[frame_index]}'\n")
                            f.write(f"duration {frame_duration[i]}\n")
                        # Write the last frame again to signal the end
                        last_frame_index = int(frame_ids[i] - abs_start_frame)
                        f.write(f"file '{frame_list[last_frame_index]}'\n")

                    logger.info("Creating video with variable fps...")
                    os.system(
                        f"ffmpeg -f concat -safe 0 -i {os.path.join(video_output_dir, 'frame_list.txt')} -vsync vfr -pix_fmt yuv420p {output_video_path}"
                    )

                    # Step 5: Combine Audio and Video
                    audio_sample_rate = 30000  # 30kHz
                    audio_data = all_merged_concat_df["Amplitude"].to_numpy()

                    logger.info("Saving audio...")
                    write(audio_output_path, audio_sample_rate, audio_data)

                    logger.info("Combining audio and video...")

                    os.system(
                        f"ffmpeg -i {output_video_path} -i {audio_output_path} -c:v copy -c:a aac -strict experimental {final_output_path}"
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

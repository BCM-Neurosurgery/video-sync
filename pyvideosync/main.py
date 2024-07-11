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
import argparse
import sys
import pandas as pd
from pathlib import Path

# Configure logging
central = pytz.timezone("US/Central")


def get_current_ts() -> str:
    return datetime.now(central).strftime("%Y%m%d_%H%M%S")


def configure_logging(debug_mode, log_dir, current_time):
    log_level = logging.DEBUG if debug_mode else logging.INFO

    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    log_file_path = os.path.join(log_dir, f"log_{current_time}.log")

    logger = logging.getLogger(__name__)
    logger.setLevel(log_level)

    # Create handlers
    c_handler = logging.StreamHandler()
    f_handler = logging.FileHandler(log_file_path)

    # Set level for handlers
    c_handler.setLevel(log_level)
    f_handler.setLevel(log_level)

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


def log_msg(logger, message):
    now = datetime.now(central).strftime("%Y-%m-%d %H:%M:%S %Z%z")
    logger.info(f"{now} - {message}")


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
    if missing_fields:
        raise ValueError(f"Missing required config fields: {', '.join(missing_fields)}")


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
    video_clip.write_videofile(output_path, codec="libx264", audio_codec="aac")


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
            choice = int(input("Enter the number of the file you want to process: "))
            if 1 <= choice <= len(cam_mp4_files):
                return cam_mp4_files[choice - 1]
            else:
                print(f"Please enter a number between 1 and {len(cam_mp4_files)}.")
        except ValueError:
            print("Invalid input. Please enter a number.")


def main():
    parser = argparse.ArgumentParser(
        description="Process and merge NEV, NS5, and camera data, then align audio with video."
    )
    parser.add_argument(
        "--config",
        type=str,
        required=True,
        help="Path to the configuration file",
    )
    args = parser.parse_args()

    with open(args.config, "r") as f:
        config = yaml.safe_load(f)

    validate_config(config)

    debug_mode = config.get("debug_mode", False)
    timestamp = get_current_ts()
    cam_serial = config["cam_serial"]
    nsp_dir = config["nsp_dir"]
    cam_recording_dir = config["cam_recording_dir"]
    output_dir = config["output_dir"]
    ns5_channel = config["channel_name"]

    # initialize DataPool
    datapool = DataPool(nsp_dir, cam_recording_dir)

    # initial data integrity check
    init_file_integrity_check = datapool.verify_integrity()
    if not init_file_integrity_check:
        print("Initial file integrity check failed, exiting...")
        sys.exit()

    # prompt for video file(s) to be processed
    cam_mp4_files = datapool.get_mp4_filelist(cam_serial)
    video_to_process = prompt_user_for_video_file(cam_mp4_files)
    video_output_dir = os.path.join(output_dir, extract_basename(video_to_process))
    os.makedirs(video_output_dir, exist_ok=True)

    # configure logging
    logger = configure_logging(debug_mode, video_output_dir, timestamp)
    log_msg(logger, f"Configuration:\n{yaml.dump(config)}")

    # find associated nev, ns5, json file to that video
    log_msg(logger, f"You selected {video_to_process}")
    video_path = os.path.join(cam_recording_dir, video_to_process)
    video = Video(video_path)
    abs_start_frame, abs_end_frame = datapool.get_mp4_abs_frame_range(
        video_to_process, cam_serial
    )
    selected_video_df = video.get_video_stats_df(abs_start_frame, abs_end_frame)
    associated_files = datapool.find_associated_files(video_to_process)
    associated_json_df = pd.DataFrame.from_records(associated_files["JSON"])
    associated_nev_df = pd.DataFrame.from_records(associated_files["NEV"])
    associated_ns5_df = pd.DataFrame.from_records(associated_files["NS5"])

    log_msg(logger, f"Selected VIDEO:\n{selected_video_df}")
    log_msg(logger, f"Associated JSON:\n{associated_json_df}")
    log_msg(logger, f"Associated NEV:\n{associated_nev_df}")
    log_msg(logger, f"Associated NS5:\n{associated_ns5_df}")

    # iterate through associated files
    # for each associated pair of NEV and NS5
    # process and export one video
    log_msg(logger, "Loading camera JSON file")
    json_path = datapool.get_abs_json_path(video_to_process)
    videojson = Videojson(json_path)
    camera_df = videojson.get_camera_df(cam_serial)
    if debug_mode:
        log_msg(logger, f"camera json df:\n{camera_df}")
        log_msg(
            logger,
            f"num of unique frame ids in camera json: {len(camera_df['frame_id'].unique())}",
        )
        plot_histogram(
            camera_df,
            "frame_id",
            os.path.join(video_output_dir, "camera_json_frame_id_diff_hist.png"),
        )

    all_merged_dfs = []
    for i, (nev_dict, ns5_dict) in enumerate(
        zip(associated_files["NEV"], associated_files["NS5"])
    ):
        log_msg(logger, f"Entering {i+1}th iteration...")
        log_msg(
            logger,
            f"Processig {nev_dict['nev_rel_path']} and {ns5_dict['ns5_rel_path']}",
        )
        chunk_output_dir = os.path.join(video_output_dir, str(i))
        os.makedirs(chunk_output_dir, exist_ok=True)

        log_msg(logger, "Loading NEV file")
        nev_path = datapool.get_abs_nev_path(nev_dict["nev_rel_path"])
        nev = Nev(nev_path)
        nev_chunk_serial_df = nev.get_chunk_serial_df()
        if debug_mode:
            log_msg(logger, f"nev_chunk_serial_df:\n{nev_chunk_serial_df}")
            nev.plot_cam_exposure_all(
                os.path.join(chunk_output_dir, "cam_exposure_all.png"), 0, 200
            )

        log_msg(logger, "Loading NS5 file")
        ns5_path = datapool.get_abs_ns5_path(ns5_dict["ns5_rel_path"])
        ns5 = Nsx(ns5_path)
        ns5_channel_df = ns5.get_channel_df(ns5_channel)
        if debug_mode:
            log_msg(logger, f"ns5_channel_df:\n{ns5_channel_df}")
            ns5.plot_channel_array(
                config["channel_name"],
                os.path.join(chunk_output_dir, f"ns5_{ns5_channel}.png"),
            )

        log_msg(logger, "Merging NEV and Camera JSON")
        chunk_serial_joined = nev_chunk_serial_df.merge(
            camera_df, left_on="chunk_serial", right_on="chunk_serial_data", how="inner"
        )
        if debug_mode:
            log_msg(logger, f"chunk_serial_df_joined:\n{chunk_serial_joined}")

        log_msg(logger, "Merging with NS5")
        ns5_slice = ns5.get_channel_df_between_ts(
            ns5_channel_df,
            chunk_serial_joined.iloc[0]["TimeStamps"],
            chunk_serial_joined.iloc[-1]["TimeStamps"],
        )
        all_merged = ns5_slice.merge(
            chunk_serial_joined, left_on="TimeStamp", right_on="TimeStamps", how="left"
        )
        all_merged_dfs.append(all_merged)

    # concat all_merged_dfs
    all_merged_concat_df = pd.concat(all_merged_dfs, ignore_index=True)
    running_total_frame_id = (
        all_merged_concat_df["frame_id"].dropna().astype(int).to_numpy()
    )
    log_msg(logger, f"Length of total frame id:{len(running_total_frame_id)}")
    log_msg(logger, f"Length of all unique: {len(np.unique(running_total_frame_id))}")
    log_msg(logger, f"All merged concat df:\n{all_merged_concat_df}")

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

    log_msg(logger, "Processing valid audio")
    valid_audio = utils.keep_valid_audio(all_merged_concat_df)
    utils.analog2audio(valid_audio, ns5.get_sample_resolution(), audio_output_path)
    log_msg(logger, f"Saved sliced audio to {audio_output_path}")

    log_msg(logger, "Slicing video")
    output_fps = len(running_total_frame_id) / (
        len(valid_audio) / ns5.get_sample_resolution()
    )
    log_msg(logger, f"Input video frame count: {video.get_frame_count()}")
    log_msg(logger, f"Input video fps: {video.get_fps()}")
    log_msg(logger, f"Output video fps: {output_fps}")
    offset_frame_id = running_total_frame_id - (abs_start_frame - 1)
    video.slice_video(output_video_path, offset_frame_id, output_fps)
    log_msg(logger, f"Saved sliced video to {output_video_path}")

    log_msg(logger, "Aligning audio and video")
    align_audio_video(output_video_path, audio_output_path, final_output_path)
    log_msg(logger, f"Final video saved to {final_output_path}")


if __name__ == "__main__":
    main()

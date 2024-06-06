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
from pyvideosync import utils
from moviepy.editor import VideoFileClip, AudioFileClip
import yaml
import argparse

# Configure logging
central = pytz.timezone("US/Central")


def configure_logging(debug_mode, log_dir):
    log_level = logging.DEBUG if debug_mode else logging.INFO

    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    current_time = datetime.now(central).strftime("%Y%m%d_%H%M%S")
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


def create_directories(directories: list):
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)


def validate_config(config):
    required_fields = [
        "cam_serial",
        "nev_path",
        "ns5_path",
        "json_path",
        "video_path",
        "output_video_path",
        "audio_output_path",
        "final_output_path",
        "plot_save_dir",
        "channel_name",
        "log_file_dir",
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
    plt.show()
    plt.close()


def reconstruct_frame_id(df):
    """
    Reconstruct the frame IDs to continue after 65535 instead of rolling over.

    Args:
        df (pd.DataFrame): DataFrame containing the frame IDs.

    Returns:
        pd.DataFrame: DataFrame with reconstructed frame IDs.
    """
    frame_ids = df["frame_id"].to_numpy()
    counters = np.cumsum(np.diff(frame_ids) < 0)
    df["frame_ids_reconstructed"] = frame_ids + 65535 * counters
    return df


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
    log_file_dir = config["log_file_dir"]

    logger = configure_logging(debug_mode, log_file_dir)

    cam_serial = config["cam_serial"]
    nev_path = config["nev_path"]
    ns5_path = config["ns5_path"]
    json_path = config["json_path"]
    video_path = config["video_path"]
    output_video_path = config["output_video_path"]
    audio_output_path = config["audio_output_path"]
    final_output_path = config["final_output_path"]
    plot_save_dir = config["plot_save_dir"]
    ns5_channel = config["channel_name"]

    create_directories(
        [
            plot_save_dir,
            os.path.dirname(output_video_path),
            os.path.dirname(audio_output_path),
            os.path.dirname(final_output_path),
        ]
    )

    log_msg(logger, "Loading NEV file")
    nev = Nev(nev_path)
    nev_chunk_serial_df = nev.get_chunk_serial_df()
    if debug_mode:
        log_msg(logger, f"nev_chunk_serial_df:\n{nev_chunk_serial_df.head()}")
        nev.plot_cam_exposure_all(os.path.join(plot_save_dir, "cam_exposure_all.png"))

    log_msg(logger, "Loading NS5 file")
    ns5 = Nsx(ns5_path)
    ns5_channel_df = ns5.get_channel_df(ns5_channel)
    if debug_mode:
        log_msg(logger, f"nev_chunk_serial_df:\n{nev_chunk_serial_df.head()}")
        ns5.plot_channel_array(
            config["channel_name"],
            os.path.join(plot_save_dir, f"ns5_{ns5_channel}.png"),
        )

    log_msg(logger, "Loading camera JSON file")
    videojson = Videojson(json_path)
    camera_df = videojson.get_camera_df(cam_serial)
    if debug_mode:
        log_msg(logger, f"camera json df:\n{camera_df.head()}")
        log_msg(logger, "Plotting difference histograms")
        plot_histogram(
            nev_chunk_serial_df,
            "chunk_serial",
            os.path.join(plot_save_dir, "nev_chunk_serial_diff_hist.png"),
        )
        plot_histogram(
            camera_df,
            "frame_id",
            os.path.join(plot_save_dir, "camera_json_frame_id_diff_hist.png"),
        )

    log_msg(logger, "Merging NEV and Camera JSON")
    chunk_serial_joined = nev_chunk_serial_df.merge(
        camera_df, left_on="chunk_serial", right_on="chunk_serial_data", how="inner"
    )
    if debug_mode:
        log_msg(logger, f"chunk_serial_df_joined:\n{chunk_serial_joined.head()}")

    log_msg(logger, "Merging with NS5")
    ns5_slice = ns5.get_channel_df_between_ts(
        ns5_channel_df,
        chunk_serial_joined.iloc[0]["TimeStamps"],
        chunk_serial_joined.iloc[-1]["TimeStamps"],
    )
    all_merged = ns5_slice.merge(
        chunk_serial_joined, left_on="TimeStamp", right_on="TimeStamps", how="left"
    )
    frame_id = all_merged["frame_id"].dropna().astype(int).to_numpy()
    if debug_mode:
        log_msg(logger, f"all_merged_df:\n{all_merged.head()}")

    log_msg(logger, "Processing valid audio")
    valid_audio = utils.keep_valid_audio(all_merged)
    utils.analog2audio(valid_audio, ns5.get_sample_resolution(), audio_output_path)
    log_msg(logger, f"Saved sliced audio to {audio_output_path}")

    log_msg(logger, "Slicing video")
    video = Video(video_path)
    output_fps = len(frame_id) / (len(valid_audio) / ns5.get_sample_resolution())
    log_msg(logger, f"Output video fps: {output_fps}")
    video.slice_video(output_video_path, frame_id, output_fps)
    log_msg(logger, f"Saved sliced video to {output_video_path}")

    log_msg(logger, "Aligning audio and video")
    align_audio_video(output_video_path, audio_output_path, final_output_path)
    log_msg(logger, f"Final video saved to {final_output_path}")


if __name__ == "__main__":
    main()

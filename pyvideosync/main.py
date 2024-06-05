"""
TODO:
1. Add debugging mode for plotting
2. Create directories if they do not exist
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

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
eastern = pytz.timezone("US/Eastern")


def log_with_eastern_time(message):
    now = datetime.now(eastern).strftime("%Y-%m-%d %H:%M:%S %Z%z")
    logger.info(f"{now} - {message}")


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
    plt.show()
    plt.savefig(save_path)


def load_camera_json(json_path, cam_serial):
    """
    Load the camera JSON file and retrieve the camera data for the specified camera serial.

    Args:
        json_path (str): Path to the camera JSON file.
        cam_serial (str): Camera serial number to retrieve data for.

    Returns:
        pd.DataFrame: DataFrame containing the camera data.
    """
    videojson = Videojson(json_path)
    return videojson.get_camera_df(cam_serial)


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


def merge_data(nev_chunk_serial_df, camera_df):
    """
    Merge NEV chunk serial data with camera data on chunk serial.

    Args:
        nev_chunk_serial_df (pd.DataFrame): DataFrame containing NEV chunk serial data.
        camera_df (pd.DataFrame): DataFrame containing camera data.

    Returns:
        pd.DataFrame: Merged DataFrame.
    """
    return nev_chunk_serial_df.merge(
        camera_df, left_on="chunk_serial", right_on="chunk_serial_data", how="inner"
    )


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
    """
    Main function to orchestrate the loading, processing, and merging of NEV, NS5, and camera data,
    and aligning the audio with the video.
    """
    with open("main_configs/config.yaml", "r") as f:
        config = yaml.safe_load(f)

    indir = config["indir"]
    cam_serial = config["cam_serial"]
    nev_path = os.path.join(indir, config["nev_path"])
    ns5_path = os.path.join(indir, config["ns5_path"])
    json_path = os.path.join(indir, config["json_path"])
    video_path = os.path.join(indir, config["video_path"])
    output_video_path = os.path.join(indir, config["output_video_path"])
    audio_output_path = os.path.join(indir, config["audio_output_path"])
    final_output_path = os.path.join(indir, config["final_output_path"])
    plot_save_dir = os.path.join(indir, config["plot_save_dir"])

    log_with_eastern_time("Loading NEV file")
    nev = Nev(nev_path)
    first_n_rows = 200
    nev_chunk_serial_df = nev.get_chunk_serial_df()
    nev.plot_cam_exposure_all(plot_save_dir, first_n_rows)

    log_with_eastern_time("Loading NS5 file")
    ns5 = Nsx(ns5_path)
    ns5_sample_resolution = ns5.get_sample_resolution()
    log_with_eastern_time(f"NS5 sample resolution: {ns5_sample_resolution}")
    ns5_channel_df = ns5.get_channel_df(config["channel_name"])
    ns5_channel_df["Amplitude"].plot()
    plt.title(f"{config['channel_name']} Amplitude")
    plt.xlabel("TimeStamps")
    plt.savefig(os.path.join(plot_save_dir, "ns5_audio.png"))
    os.makedirs(os.path.dirname(audio_output_path), exist_ok=True)
    utils.analog2audio(
        ns5_channel_df["Amplitude"].to_numpy(), ns5_sample_resolution, audio_output_path
    )
    log_with_eastern_time(f"Saved NS5 original audio to {audio_output_path}")

    log_with_eastern_time("Loading camera JSON file")
    camera_df = load_camera_json(json_path, cam_serial)

    log_with_eastern_time("Plotting difference histograms")
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

    log_with_eastern_time("Merging data")
    chunk_serial_joined = merge_data(nev_chunk_serial_df, camera_df)
    frame_id = chunk_serial_joined["frame_id"].dropna().astype(int).to_numpy()

    log_with_eastern_time("Slicing video")
    video = Video(video_path)
    video.slice_video(output_video_path, frame_id)
    log_with_eastern_time(f"Saved sliced video to {output_video_path}")

    log_with_eastern_time("Processing valid audio")
    valid_audio = utils.keep_valid_audio(chunk_serial_joined)
    utils.analog2audio(valid_audio, 29800, audio_output_path)
    log_with_eastern_time(f"Saved sliced audio to {audio_output_path}")

    log_with_eastern_time("Aligning audio and video")
    align_audio_video(output_video_path, audio_output_path, final_output_path)
    log_with_eastern_time(f"Final video saved to {final_output_path}")


if __name__ == "__main__":
    main()

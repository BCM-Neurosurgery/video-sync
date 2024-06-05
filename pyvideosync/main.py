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


def log_msg(message):
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
    plt.close()


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
    ns5_channel = config["channel_name"]

    log_msg("Loading NEV file")
    nev = Nev(nev_path)
    nev_chunk_serial_df = nev.get_chunk_serial_df()
    print(nev_chunk_serial_df.head())
    nev.plot_cam_exposure_all(os.path.join(plot_save_dir, "cam_exposure_all.png"))

    log_msg("Loading NS5 file")
    ns5 = Nsx(ns5_path)
    ns5_channel_df = ns5.get_channel_df(ns5_channel)
    ns5.plot_channel_array(
        config["channel_name"], os.path.join(plot_save_dir, f"ns5_{ns5_channel}.png")
    )

    log_msg("Loading camera JSON file")
    camera_df = load_camera_json(json_path, cam_serial)
    print(camera_df.head())

    log_msg("Plotting difference histograms")
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

    log_msg("Merging NEV and Camera JSON")
    chunk_serial_joined = nev_chunk_serial_df.merge(
        camera_df, left_on="chunk_serial", right_on="chunk_serial_data", how="inner"
    )

    log_msg("Merging with NS5")
    ns5_slice = ns5.get_channel_df_between_ts(
        ns5_channel_df,
        chunk_serial_joined.iloc[0]["TimeStamps"],
        chunk_serial_joined.iloc[-1]["TimeStamps"],
    )
    all_merged = ns5_slice.merge(
        chunk_serial_joined, left_on="TimeStamp", right_on="TimeStamps", how="left"
    )
    frame_id = all_merged["frame_id"].dropna().astype(int).to_numpy()

    # log_msg("Slicing video")
    # video = Video(video_path)
    # video.slice_video(output_video_path, frame_id)
    # log_msg(f"Saved sliced video to {output_video_path}")

    log_msg("Processing valid audio")
    saved_video = Video(output_video_path)
    valid_audio = utils.keep_valid_audio(all_merged)
    saved_sample_rate = utils.get_sample_rate(
        len(valid_audio),
        saved_video.get_length(),
    )
    log_msg(f"Saved sample rate: {saved_sample_rate}")
    utils.analog2audio(valid_audio, saved_sample_rate, audio_output_path)
    log_msg(f"Saved sliced audio to {audio_output_path}")

    log_msg("Aligning audio and video")
    align_audio_video(output_video_path, audio_output_path, final_output_path)
    log_msg(f"Final video saved to {final_output_path}")


if __name__ == "__main__":
    main()

import os
import json
import cv2
import numpy as np
import pandas as pd
from tqdm import tqdm
import matplotlib.pyplot as plt
from datetime import datetime
from collections import Counter
from brpylib import NevFile, NsxFile
from pyvideosync.nev import Nev
from pyvideosync.nsx import Nsx
from pyvideosync.match import Match
from pyvideosync.videojson import Videojson
from pyvideosync import utils
import soundfile as sf
from moviepy.editor import VideoFileClip, AudioFileClip


def load_nev(nev_path: str):
    """
    Load the NEV file and retrieve digital events and chunk serial data.

    Args:
        nev_path (str): Path to the NEV file.

    Returns:
        tuple: DataFrames containing the digital events and chunk serial data.
    """
    nev = Nev(nev_path)
    nev_digital_events_df = nev.get_digital_events_df()
    save_dir = "output/plots_updated"
    first_n_rows = 200
    nev.plot_cam_exposure_all(save_dir, first_n_rows)
    nev_chunk_serial_df = nev.get_chunk_serial_df()
    return nev_digital_events_df, nev_chunk_serial_df


def plot_histogram(
    data: pd.DataFrame, column: str, color: str = "skyblue", alpha: float = 0.7
):
    """
    Plot a histogram of the differences in the specified column of the DataFrame.

    Args:
        data (DataFrame): DataFrame containing the data to plot.
        column (str): Column name to calculate differences and plot histogram.
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


def load_ns5(ns5_path: str, channel_name: str = "RoomMic2"):
    """
    Load the NS5 file and retrieve the audio data for the specified channel.

    Args:
        ns5_path (str): Path to the NS5 file.
        channel_name (str): Name of the audio channel to retrieve data for.

    Returns:
        DataFrame: DataFrame containing the audio data for the specified channel.
    """
    ns5 = Nsx(ns5_path)
    ns5_channel_df = ns5.get_channel_df(channel_name)
    ns5_extended_headers_df = ns5.get_extended_headers_df()
    ns5_channel_df["Amplitude"].plot()
    plt.title(f"{channel_name} Amplitude")
    plt.xlabel("TimeStamps")
    plt.show()
    os.makedirs("./output/audio", exist_ok=True)
    utils.analog2audio(
        ns5_channel_df["Amplitude"].to_numpy(), 30000, "./output/audio/ns5_003.wav"
    )
    return ns5_channel_df


def load_camera_json(json_path: str, cam_serial: str):
    """
    Load the camera JSON file and retrieve the camera data for the specified camera serial.

    Args:
        json_path (str): Path to the camera JSON file.
        cam_serial (str): Camera serial number to retrieve data for.

    Returns:
        DataFrame: DataFrame containing the camera data.
    """
    videojson = Videojson(json_path)
    camera_df = videojson.get_camera_df(cam_serial)
    return camera_df


def reconstruct_frame_id(df):
    """
    Reconstruct the frame IDs to continue after 65535 instead of rolling over.

    Args:
        df (DataFrame): DataFrame containing the frame IDs.

    Returns:
        DataFrame: DataFrame with reconstructed frame IDs.
    """
    frame_ids = df["frame_id"].to_numpy()
    counters = [0]
    counter = 0
    for i in range(1, len(frame_ids)):
        if frame_ids[i - 1] > frame_ids[i]:
            counter += 1
        counters.append(counter)
    frame_ids = frame_ids + 65535 * np.array(counters)
    df["frame_ids_reconstructed"] = frame_ids
    return df


def merge_data(nev_chunk_serial_df, camera_df):
    """
    Merge NEV chunk serial data with camera data on chunk serial.

    Args:
        nev_chunk_serial_df (DataFrame): DataFrame containing NEV chunk serial data.
        camera_df (DataFrame): DataFrame containing camera data.

    Returns:
        DataFrame: Merged DataFrame.
    """
    chunk_serial_joined = nev_chunk_serial_df.merge(
        camera_df, left_on="chunk_serial", right_on="chunk_serial_data", how="inner"
    )
    return chunk_serial_joined


def slice_video(input_file, output_file, frames_to_keep):
    """
    Slice the input video to keep only specified frames.

    Args:
        input_file (str): Path to the input video file.
        output_file (str): Path to save the output video file.
        frames_to_keep (list): List of frame indices to keep in the output video.
    """
    cap = cv2.VideoCapture(input_file)
    if not cap.isOpened():
        print("Error opening video file.")
        return

    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = 29.995
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(output_file, fourcc, fps, (frame_width, frame_height))

    frames_to_keep = set(frames_to_keep)
    pbar = tqdm(total=total_frames, desc="Processing video", unit="frame")
    current_frame_index = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if current_frame_index in frames_to_keep:
            out.write(frame)

        current_frame_index += 1
        pbar.update(1)

    pbar.close()
    cap.release()
    out.release()
    cv2.destroyAllWindows()
    print("Video processing completed.")


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
    indir = "/home/yewen/BCM/videosync/05302024"
    cam_serial = "23512906"
    nev_path = os.path.join(indir, "nsp/20240530-113523/NSP1-20240530-113523-003.nev")
    ns5_path = os.path.join(indir, "nsp/20240530-113523/NSP1-20240530-113523-003.ns5")
    json_path = os.path.join(indir, "video/video_sync_test_0530_20240530_115639.json")
    video_path = os.path.join(
        indir, "video/video_sync_test_0530_20240530_115639.23512906.mp4"
    )
    output_video_path = os.path.join(
        indir, "./output/video/video_23512906_sliced_with_valid_frames.mp4"
    )
    audio_output_path = os.path.join(indir, "./output/audio/valid_audio_29995.wav")
    final_output_path = os.path.join(
        indir, "./output/video/audio_video_aligned_0530_29995.mp4"
    )

    nev_digital_events_df, nev_chunk_serial_df = load_nev(nev_path)
    ns5_channel_df = load_ns5(ns5_path)
    camera_df = load_camera_json(json_path, cam_serial)

    plot_histogram(nev_chunk_serial_df, "chunk_serial")
    plot_histogram(camera_df, "frame_id")

    chunk_serial_joined = merge_data(nev_chunk_serial_df, camera_df)
    frame_id = chunk_serial_joined["frame_id"].dropna().astype(int).to_numpy()
    slice_video(video_path, output_video_path, frame_id)

    valid_audio = utils.keep_valid_audio(chunk_serial_joined)
    utils.analog2audio(valid_audio, 29995, audio_output_path)

    align_audio_video(output_video_path, audio_output_path, final_output_path)


if __name__ == "__main__":
    main()

from pyvideosync.video import Video
from pyvideosync.videojson import Videojson
from pyvideosync.nev import Nev
from pyvideosync.nsx import Nsx
from pyvideosync.dataframes import (
    CameraJSONDF,
    NevChunkSerialDF,
    ChunkSerialJoinedDF,
)
import os
from scipy.io.wavfile import write
from moviepy.editor import VideoFileClip, AudioFileClip


def process_video(abs_start_frame, abs_end_frame, pathutils, logger):
    logger.info("Processing Video...")
    video = Video(pathutils.video_path, abs_start_frame, abs_end_frame)
    selected_video_df = video.get_video_stats_df()
    logger.debug(f"Selected VIDEO:\n{selected_video_df}")
    return video


def process_camera_json(pathutils, logger):
    logger.info("Loading camera JSON file...")
    videojson = Videojson(pathutils.json_path)
    camera_df = videojson.get_camera_df(pathutils.cam_serial)
    CameraJSONDF(camera_df, logger).log_dataframe_info()
    return camera_df


def process_nev_chunk_serial(pathutils, logger):
    logger.info("Getting chunk serial data from NEV...")
    nev = Nev(pathutils.nev_abs_path)
    nev_chunk_serial_df = nev.get_chunk_serial_df()
    NevChunkSerialDF(nev_chunk_serial_df, logger).log_dataframe_info()
    nev.plot_cam_exposure_all(pathutils.cam_exposure_path, 0, 200)
    return nev_chunk_serial_df


def process_ns5_channel_data(pathutils, logger):
    logger.info(f"Getting {pathutils.ns5_channel} in NS5...")
    ns5 = Nsx(pathutils.ns5_abs_path)
    ns5_channel_df = ns5.get_channel_df(pathutils.ns5_channel)
    logger.debug(f"ns5_channel_df:\n{ns5_channel_df}")
    ns5.plot_channel_array(
        pathutils.ns5_channel,
        pathutils.channel_array_path,
    )
    return ns5, ns5_channel_df


def nev_inner_join_camera_json(nev_chunk_serial_df, camera_df, logger):
    logger.info("Merging NEV and Camera JSON...")
    chunk_serial_joined = nev_chunk_serial_df.merge(
        camera_df,
        left_on="chunk_serial",
        right_on="chunk_serial_data",
        how="inner",
    )
    ChunkSerialJoinedDF(chunk_serial_joined, logger).log_dataframe_info()
    return chunk_serial_joined


def ns5_leftjoin_joined(chunk_serial_joined, ns5, ns5_channel_df, logger):
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
    return all_merged


def extract_and_save_frames(video, pathutils, logger):
    logger.info("Saving frames from video...")
    frame_list = video.extract_frames(pathutils.frames_output_dir)
    return frame_list


def save_frame_duration_to_file(
    all_merged_concat_df, frame_list, abs_start_frame, pathutils, logger
):
    logger.info("Getting frame durations in fps...")
    all_merged_concat_dropped = all_merged_concat_df.dropna()
    timestamps = all_merged_concat_dropped["TimeStamp"].tolist()
    frame_ids = all_merged_concat_dropped["frame_ids_reconstructed"].tolist()
    # TODO: this approach will discard the last frame
    # calculate the time in s for each frame
    # we know 30000 timestamps = 1s
    # so each timestamp is 1 / 30000s
    frame_duration = [
        (timestamps[i] - timestamps[i - 1]) / 30000 for i in range(1, len(timestamps))
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


def export_video_variable_fps(pathutils, logger):
    logger.info("Creating video with variable fps...")
    os.system(
        f"ffmpeg -f concat -safe 0 -i {pathutils.frame_list_path} -vsync vfr -pix_fmt yuv420p {pathutils.video_out_path}"
    )


def export_audio(all_merged_concat_df, pathutils, logger):
    audio_sample_rate = 30000  # 30kHz
    audio_data = all_merged_concat_df["Amplitude"].to_numpy()

    logger.info("Saving audio...")
    write(pathutils.audio_out_path, audio_sample_rate, audio_data)


def combine_video_audio(pathutils, logger):
    logger.info("Combining audio and video...")
    os.system(
        f"ffmpeg -i {pathutils.video_out_path} -i {pathutils.audio_out_path} -c:v copy -c:a aac -strict experimental {pathutils.final_video_out_path}"
    )
    logger.info("Video Sync Complete!!!")


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
